#!/usr/bin/env python3
"""
Trade Executor for Dogecoin Analyzer
Automatically executes trades based on AI recommendations
"""

import os
import json
import math
import time
import uuid
from datetime import datetime
from dotenv import load_dotenv
import requests
from coinbase import jwt_generator

# Load environment variables
load_dotenv()

class CoinbaseTradeExecutor:
    def __init__(self):
        """Initialize the trade executor with Coinbase Advanced API credentials.
        
        Uses JWT authentication (no passphrase required).
        API key format: "organizations/{org_id}/apiKeys/{key_id}"
        API secret: EC private key in PEM format
        """
        # Coinbase Advanced API uses the full path format for API key
        self.api_key = os.getenv('COINBASE_API_KEY', '')
        
        # Try both variable names for compatibility
        api_secret_raw = os.getenv('COINBASE_PRIVATE_KEY') or os.getenv('COINBASE_API_SECRET')
        # Handle newline characters in the secret (replace literal \n with actual newlines)
        if api_secret_raw:
            self.api_secret = api_secret_raw.replace('\\n', '\n')
            # Ensure the secret has proper PEM format headers if missing
            if not self.api_secret.strip().startswith('-----BEGIN'):
                # If it's base64 encoded, we need to handle it differently
                # For now, assume it's already in PEM format or will be handled by JWT
                pass
        else:
            self.api_secret = None
        
        # Coinbase Advanced API base URL
        # Documentation: https://docs.cdp.coinbase.com/advanced-trade/docs/welcome
        self.base_url = "https://api.coinbase.com/api/v3/brokerage"
        
        if not all([self.api_key, self.api_secret]):
            raise ValueError("Missing Coinbase API credentials in .env file. Need COINBASE_API_KEY and either COINBASE_PRIVATE_KEY or COINBASE_API_SECRET")
        
        # Validate API secret format
        if not self.api_secret.strip().startswith('-----BEGIN'):
            raise ValueError("API secret must be in PEM format with -----BEGIN EC PRIVATE KEY----- header")
        
        print(f"✅ Coinbase Advanced API credentials loaded")
    
    def _generate_jwt_token(self, method, uri):
        """Generate JWT token for Coinbase Advanced API authentication using official SDK.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            uri: Request URI path (e.g., '/api/v3/brokerage/accounts')
        
        Returns:
            JWT token string
        """
        # Use official SDK's JWT generator
        # Format the JWT URI according to Coinbase Advanced API spec
        jwt_uri = jwt_generator.format_jwt_uri(method, uri)
        
        # Generate JWT using official SDK
        token = jwt_generator.build_rest_jwt(jwt_uri, self.api_key, self.api_secret)
        
        return token
    
    def _make_authenticated_request(self, method, endpoint, data=None):
        """Make authenticated request to Coinbase Advanced API using JWT."""
        # Ensure endpoint starts with /
        if not endpoint.startswith('/'):
            endpoint = '/' + endpoint
        
        # Full URI for JWT generation
        uri = f"/api/v3/brokerage{endpoint}"
        
        # Generate JWT token
        jwt_token = self._generate_jwt_token(method, uri)
        
        headers = {
            'Authorization': f'Bearer {jwt_token}',
            'Content-Type': 'application/json'
        }
        
        url = f"{self.base_url}{endpoint}"
        
        if method == 'GET':
            response = requests.get(url, headers=headers, params=data if data else None)
        elif method == 'POST':
            response = requests.post(url, headers=headers, json=data)
        elif method == 'DELETE':
            response = requests.delete(url, headers=headers)
        
        return response
    
    def get_accounts(self):
        """Get all trading accounts."""
        try:
            response = self._make_authenticated_request('GET', '/accounts')
            if response.status_code == 200:
                data = response.json()
                # Coinbase Advanced API returns accounts in a 'accounts' key
                if isinstance(data, dict) and 'accounts' in data:
                    return data['accounts']
                # Fallback: if it's already a list, return it
                elif isinstance(data, list):
                    return data
                else:
                    print(f"⚠️  Unexpected response structure: {type(data)}")
                    return []
            elif response.status_code == 401:
                # Authentication failed - raise exception to stop execution
                error_msg = f"Authentication failed (401): {response.text}"
                print(f"❌ {error_msg}")
                raise ValueError(f"Invalid Coinbase Advanced API credentials. Please check your .env file:\n"
                               f"  - COINBASE_API_KEY (full path: organizations/.../apiKeys/...)\n"
                               f"  - COINBASE_API_SECRET (or COINBASE_PRIVATE_KEY) - EC private key in PEM format\n"
                               f"Note: Coinbase Advanced API does NOT require a passphrase.\n"
                               f"Error: {response.text}")
            else:
                print(f"Error getting accounts: {response.status_code} - {response.text}")
                return None
        except ValueError:
            # Re-raise authentication errors
            raise
        except Exception as e:
            print(f"Error getting accounts: {e}")
            return None
    
    def get_dogecoin_balance(self):
        """Get current DOGE balance."""
        accounts = self.get_accounts()
        if not accounts:
            return None
        
        for account in accounts:
            # Coinbase Advanced API uses 'available_balance' or 'balance' field
            currency = account.get('available_balance', {}).get('currency') or account.get('currency')
            if currency == 'DOGE':
                balance = account.get('available_balance', {}).get('value') or account.get('balance', {}).get('value') or account.get('balance', 0)
                return float(balance)
        return 0.0
    
    def get_usd_balance(self):
        """Get current USD balance."""
        accounts = self.get_accounts()
        if not accounts:
            return None
        
        for account in accounts:
            # Coinbase Advanced API uses 'available_balance' or 'balance' field
            currency = account.get('available_balance', {}).get('currency') or account.get('currency')
            if currency == 'USD':
                balance = account.get('available_balance', {}).get('value') or account.get('balance', {}).get('value') or account.get('balance', 0)
                return float(balance)
        return 0.0
    
    def get_product_info(self, symbol='DOGE-USD'):
        """Get product information including precision requirements."""
        try:
            response = self._make_authenticated_request('GET', f'/products/{symbol}')
            if response.status_code == 200:
                return response.json()
            else:
                print(f"⚠️  Could not fetch product info: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            print(f"⚠️  Error fetching product info: {e}")
            return None
    
    def get_current_price(self, symbol='DOGE-USD', target_date=None):
        """
        Get price for DOGE-USD. Can fetch historical price if target_date is provided.
        
        Args:
            symbol: Trading pair symbol (default: 'DOGE-USD')
            target_date: Optional datetime object. If provided, fetches historical price
                        for that date/time. Default is None (returns current price).
        
        Returns:
            Float price value, or None if error
        """
        try:
            # If target_date is provided, fetch historical price using candles API
            if target_date:
                from datetime import timedelta
                
                # Convert target_date to datetime if it's a string
                if isinstance(target_date, str):
                    target_dt = datetime.fromisoformat(target_date.replace('Z', '+00:00'))
                else:
                    target_dt = target_date
                
                # Get 1-hour window around the target timestamp
                start_time = target_dt - timedelta(hours=1)
                end_time = target_dt + timedelta(hours=1)
                
                # Convert to Unix timestamps
                start_unix = int(start_time.timestamp())
                end_unix = int(end_time.timestamp())
                
                # Fetch candles data from public Exchange API
                # Note: Historical price data is public and doesn't require authentication
                exchange_api_url = "https://api.exchange.coinbase.com"
                url = f"{exchange_api_url}/products/{symbol}/candles"
                params = {
                    'start': start_unix,
                    'end': end_unix,
                    'granularity': 3600  # 1 hour granularity
                }
                
                response = requests.get(url, params=params)
                if response.status_code == 200:
                    data = response.json()
                    if data and len(data) > 0:
                        # Find the closest candle to target_date
                        # Data format: [timestamp, low, high, open, close, volume]
                        closest_candle = None
                        min_time_diff = float('inf')
                        
                        for candle in data:
                            candle_timestamp = candle[0]
                            time_diff = abs(candle_timestamp - int(target_dt.timestamp()))
                            
                            # Prefer candles at or before target_date (not future)
                            if candle_timestamp <= int(target_dt.timestamp()) and time_diff < min_time_diff:
                                min_time_diff = time_diff
                                closest_candle = candle
                        
                        # If no candle before target, use the closest one
                        if closest_candle is None and len(data) > 0:
                            for candle in data:
                                candle_timestamp = candle[0]
                                time_diff = abs(candle_timestamp - int(target_dt.timestamp()))
                                if time_diff < min_time_diff:
                                    min_time_diff = time_diff
                                    closest_candle = candle
                        
                        if closest_candle:
                            # Return close price (index 4 in candles format)
                            return float(closest_candle[4])
                        else:
                            print(f"⚠️  No candle data found for {target_dt}")
                            return None
                    else:
                        print(f"⚠️  Empty candle data for {target_dt}")
                        return None
                else:
                    print(f"Error fetching historical price: {response.status_code}")
                    return None
            
            # Default: Fetch current price using public Exchange API ticker endpoint
            # Note: Price data is public and doesn't require authentication
            exchange_api_url = "https://api.exchange.coinbase.com"
            response = requests.get(f"{exchange_api_url}/products/{symbol}/ticker")
            if response.status_code == 200:
                data = response.json()
                return float(data['price'])
            else:
                print(f"Error getting price: {response.status_code}")
                return None
        except Exception as e:
            print(f"Error getting price: {e}")
            return None
    
    def place_buy_order(self, amount_usd, symbol='DOGE-USD'):
        """Place a buy order for DOGE using Coinbase Advanced API format."""
        try:
            # Get balance before order to verify execution
            balance_usd_before = self.get_usd_balance()
            balance_doge_before = self.get_dogecoin_balance()
            
            # Generate a unique client order ID
            client_order_id = str(uuid.uuid4())
            
            # Coinbase Advanced API requires quote_size to have proper precision (2 decimal places for USD)
            # Round to 2 decimal places to avoid precision errors
            quote_size = f"{amount_usd:.2f}"
            
            # Coinbase Advanced API order format
            order_data = {
                'client_order_id': client_order_id,
                'product_id': symbol,
                'side': 'BUY',
                'order_configuration': {
                    'market_market_ioc': {
                        'quote_size': quote_size  # Amount in USD (quote currency) to spend, rounded to 2 decimals
                    }
                }
            }
            
            response = self._make_authenticated_request('POST', '/orders', order_data)
            
            if response.status_code == 200:
                order_info = response.json()
                # Check if order was successful
                if order_info.get('success') == False:
                    error_response = order_info.get('error_response', {})
                    error_message = error_response.get('message', 'Unknown error')
                    error_details = error_response.get('error_details', '')
                    preview_failure = error_response.get('preview_failure_reason', '')
                    
                    print(f"❌ Order failed: {error_message}")
                    if preview_failure:
                        print(f"   Preview failure reason: {preview_failure}")
                    if error_details:
                        print(f"   Error details: {error_details}")
                    print(f"   Full error: {json.dumps(error_response, indent=2)}")
                    return None
                
                # Coinbase Advanced API response structure might be different
                # Try to extract order ID from various possible locations
                success_response = order_info.get('success_response', {})
                order_id = (success_response.get('order_id') or 
                           order_info.get('order_id') or 
                           order_info.get('id') or
                           (order_info.get('order') and order_info['order'].get('order_id')))
                
                order_status = (success_response.get('status') or
                               order_info.get('status') or
                               (order_info.get('order') and order_info['order'].get('status')))
                
                # Check if order was actually placed successfully
                if order_id:
                    print(f"✅ Buy order placed successfully!")
                    print(f"   Order ID: {order_id}")
                    print(f"   Amount: ${amount_usd}")
                    if order_status:
                        print(f"   Status: {order_status}")
                    
                    # For market orders, verify execution by checking balances
                    print(f"   Verifying order execution...")
                    time.sleep(2)  # Wait a moment for order to fill
                    new_usd_balance = self.get_usd_balance()
                    new_doge_balance = self.get_dogecoin_balance()
                    
                    if balance_usd_before is not None and new_usd_balance is not None:
                        usd_change = new_usd_balance - balance_usd_before
                        print(f"   USD balance before: ${balance_usd_before:.2f}")
                        print(f"   USD balance after: ${new_usd_balance:.2f}")
                        print(f"   USD balance change: ${usd_change:.2f}")
                        if usd_change < -amount_usd * 0.9:  # Allow for small rounding differences
                            print(f"   ✅ Order appears to have executed (USD balance decreased)")
                        else:
                            print(f"   ⚠️  Order may not have executed yet (USD balance unchanged)")
                    
                    return order_info
                else:
                    print(f"⚠️  Order response received but no Order ID found")
                    print(f"   Response structure may be unexpected")
                    print(f"   Full response: {json.dumps(order_info, indent=2)}")
                    # Still return the order_info in case it contains useful information
                    return order_info
            else:
                print(f"❌ Error placing buy order: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ Error placing buy order: {e}")
            return None
    
    def place_sell_order(self, amount_doge, symbol='DOGE-USD'):
        """Place a sell order for DOGE using Coinbase Advanced API format."""
        try:
            # Generate a unique client order ID
            client_order_id = str(uuid.uuid4())
            
            # Coinbase Advanced API requires base_size to have proper precision
            # Try to get product info to determine exact precision requirements
            product_info = self.get_product_info(symbol)
            base_increment = None
            decimal_places = 0  # Default to whole numbers
            
            if product_info:
                # Try different possible field names for base increment
                base_increment = (product_info.get('base_increment') or 
                                product_info.get('base_min_size') or
                                product_info.get('size_increment'))
                
                if base_increment:
                    # Calculate decimal places from increment (e.g., "1" = 0 decimals, "0.01" = 2 decimals)
                    if '.' in str(base_increment):
                        decimal_places = len(str(base_increment).split('.')[1].rstrip('0'))
                    else:
                        decimal_places = 0
                    print(f"📊 Product info: base_increment={base_increment}, using {decimal_places} decimal places")
                else:
                    print(f"⚠️  Product info retrieved but no base_increment found. Using whole numbers (0 decimals).")
            else:
                # Fallback: For DOGE-USD, use whole numbers (0 decimal places)
                # Coinbase Advanced API appears to require whole DOGE units
                print(f"⚠️  Could not fetch product info. Using whole numbers (0 decimals) as fallback.")
            
            # Round to the required precision
            # For DOGE-USD, Coinbase requires whole numbers (0 decimal places)
            # Always use whole numbers regardless of product info to ensure compatibility
            if decimal_places == 0:
                # Round down to whole DOGE to ensure we don't exceed balance
                whole_doge = int(math.floor(amount_doge))
                # Ensure it's a string without any decimal point
                base_size = str(whole_doge)
                print(f"🔢 Rounded {amount_doge:.8f} DOGE to {base_size} DOGE (whole number)")
            else:
                # Round to specified decimal places (shouldn't happen for DOGE, but just in case)
                base_size = f"{amount_doge:.{decimal_places}f}"
                # Remove trailing zeros and decimal point if not needed
                base_size = base_size.rstrip('0').rstrip('.')
                print(f"🔢 Rounded {amount_doge:.8f} DOGE to {base_size} DOGE ({decimal_places} decimals)")
            
            # Final safety check: ensure base_size is a whole number for DOGE-USD
            if symbol == 'DOGE-USD':
                try:
                    # Try to parse as float and convert to int to ensure it's whole
                    base_size_float = float(base_size)
                    base_size = str(int(base_size_float))
                    print(f"✅ Final base_size for DOGE-USD: {base_size} (ensured whole number)")
                except (ValueError, TypeError):
                    print(f"⚠️  Warning: Could not validate base_size format: {base_size}")
            
            # Coinbase Advanced API order format
            order_data = {
                'client_order_id': client_order_id,
                'product_id': symbol,
                'side': 'SELL',
                'order_configuration': {
                    'market_market_ioc': {
                        'base_size': base_size  # Amount in DOGE (base currency) to sell
                    }
                }
            }
            
            # Debug: Print the exact order data being sent
            print(f"📤 Sending order: base_size='{base_size}' (type: {type(base_size).__name__})")
            print(f"📤 Full order data: {json.dumps(order_data, indent=2)}")
            
            response = self._make_authenticated_request('POST', '/orders', order_data)
            
            if response.status_code == 200:
                order_info = response.json()
                # Debug: print full response to understand structure
                print(f"📋 Order response: {json.dumps(order_info, indent=2)}")
                
                # Check if order was successful
                if order_info.get('success') == False:
                    error_response = order_info.get('error_response', {})
                    error_message = error_response.get('message', 'Unknown error')
                    error_details = error_response.get('error_details', '')
                    preview_failure = error_response.get('preview_failure_reason', '')
                    
                    print(f"❌ Order failed: {error_message}")
                    if preview_failure:
                        print(f"   Preview failure reason: {preview_failure}")
                    if error_details:
                        print(f"   Error details: {error_details}")
                    print(f"   Full error: {json.dumps(error_response, indent=2)}")
                    return None
                
                # Coinbase Advanced API response structure might be different
                # Try to extract order ID from various possible locations
                success_response = order_info.get('success_response', {})
                order_id = (success_response.get('order_id') or 
                           order_info.get('order_id') or 
                           order_info.get('id') or
                           (order_info.get('order') and order_info['order'].get('order_id')))
                
                order_status = (success_response.get('status') or
                               order_info.get('status') or
                               (order_info.get('order') and order_info['order'].get('status')))
                
                # Check if order was actually placed successfully
                if order_id:
                    print(f"✅ Sell order placed successfully!")
                    print(f"   Order ID: {order_id}")
                else:
                    print(f"   Order ID: {order_id} (check response structure)")
                print(f"   Amount: {amount_doge} DOGE")
                if order_status:
                    print(f"   Status: {order_status}")
                return order_info
            else:
                print(f"❌ Error placing sell order: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ Error placing sell order: {e}")
            return None
    
    def execute_trade(self, action, percentage, current_balance_usd=None, current_balance_doge=None):
        """Execute trade based on AI recommendation."""
        print(f"\n🚀 EXECUTING TRADE: {action} {percentage}")
        print("=" * 50)
        
        # Get current balances if not provided
        if current_balance_usd is None:
            current_balance_usd = self.get_usd_balance()
        if current_balance_doge is None:
            current_balance_doge = self.get_dogecoin_balance()
        
        if current_balance_usd is None or current_balance_doge is None:
            print("❌ Unable to get account balances")
            return False
        
        print(f"💰 Current Balances:")
        print(f"   USD: ${current_balance_usd:.2f}")
        print(f"   DOGE: {current_balance_doge:.2f}")
        
        # Get current price
        current_price = self.get_current_price()
        if not current_price:
            print("❌ Unable to get current DOGE price")
            return False
        
        print(f"📈 Current DOGE Price: ${current_price}")
        
        if action.upper() == 'BUY':
            # Calculate amount to buy
            amount_to_spend = current_balance_usd * (percentage / 100)
            if amount_to_spend > current_balance_usd:
                print(f"❌ Insufficient USD balance. Need ${amount_to_spend:.2f}, have ${current_balance_usd:.2f}")
                return False
            
            print(f"💵 Buying DOGE worth ${amount_to_spend:.2f} ({percentage}% of USD balance)")
            return self.place_buy_order(amount_to_spend)
            
        elif action.upper() == 'SELL':
            # Calculate amount to sell
            amount_to_sell = current_balance_doge * (percentage / 100)
            if amount_to_sell > current_balance_doge:
                print(f"❌ Insufficient DOGE balance. Need {amount_to_sell:.2f}, have {current_balance_doge:.2f}")
                return False
            
            print(f"💸 Selling {amount_to_sell:.2f} DOGE ({percentage}% of DOGE balance)")
            return self.place_sell_order(amount_to_sell)
            
        elif action.upper() == 'HOLD':
            print("⏸️  HOLD recommendation - No trade executed")
            return True
            
        else:
            print(f"❌ Unknown action: {action}")
            return False
    
    def log_trade(self, action, percentage, result, timestamp=None):
        """Log trade execution to file."""
        if timestamp is None:
            timestamp = datetime.now().isoformat()
        
        log_entry = {
            'timestamp': timestamp,
            'action': action,
            'percentage': percentage,
            'result': result,
            'success': result is not None
        }
        
        log_file = 'trade_history.json'
        
        # Load existing logs
        try:
            with open(log_file, 'r') as f:
                logs = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            logs = []
        
        # Add new log entry
        logs.append(log_entry)
        
        # Save updated logs
        try:
            with open(log_file, 'w') as f:
                json.dump(logs, f, indent=2)
            print(f"📝 Trade logged to {log_file}")
        except Exception as e:
            print(f"⚠️  Warning: Could not log trade: {e}")

def main():
    """Test the trade executor."""
    try:
        executor = CoinbaseTradeExecutor()
        
        # Test getting balances
        print("🔍 Testing Coinbase connection...")
        usd_balance = executor.get_usd_balance()
        doge_balance = executor.get_dogecoin_balance()
        
        if usd_balance is not None and doge_balance is not None:
            print(f"✅ Connection successful!")
            print(f"   USD Balance: ${usd_balance:.2f}")
            print(f"   DOGE Balance: {doge_balance:.2f}")
        else:
            print("❌ Connection failed")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
