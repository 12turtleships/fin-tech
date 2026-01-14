import os
import json
import requests
import pandas as pd
import time
from datetime import datetime, timedelta
from typing import Optional
from dotenv import load_dotenv
import openai
from trade_executor import CoinbaseTradeExecutor
import ta
from ta.trend import *
from ta.momentum import *
from ta.volatility import *
from ta.volume import *
from ta.utils import dropna
from serpapi import GoogleSearch
import base64
from pathlib import Path
import sqlite3

# Import database module
from database import TradingDatabase

# Import screen capture functionality
from screen_capture import (
    create_chrome_driver_for_screen_capture,
    wait_for_page_ready,
    dismiss_cookies_banner,
    click_time_range,
    open_indicators_panel,
    select_indicator_by_search,
    click_indicator_bollinger,
    click_maximize_chart,
)

# Load environment variables
load_dotenv()

class DogecoinAnalyzer:
    def __init__(self):
        """Initialize the Dogecoin analyzer with API credentials."""
        self.coinbase_api_key = os.getenv('COINBASE_API_KEY')
        self.coinbase_private_key = os.getenv('COINBASE_PRIVATE_KEY')
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        self.serpapi_key = os.getenv('SERPAPI_KEY')
        
        if not self.openai_api_key:
            raise ValueError("Missing required OpenAI API key in .env file")
        
        # Initialize OpenAI client
        openai.api_key = self.openai_api_key
        
        # Initialize trade executor
        try:
            self.trade_executor = CoinbaseTradeExecutor()
            self.trading_enabled = True
        except Exception as e:
            print(f"⚠️  Trade execution disabled: {e}")
            self.trade_executor = None
            # Keep trading_enabled as True even if credentials are missing (for simulation/demo)
            # This allows trades to be saved to database even without API credentials
            self.trading_enabled = True
        
        # Initialize latest analysis JSON storage
        self.latest_analysis_json = None
        self.latest_chart_image_path = None
        
        # Initialize database
        try:
            self.db = TradingDatabase()
            self.database_enabled = True
        except Exception as e:
            print(f"⚠️  Database initialization failed: {e}")
            self.db = None
            self.database_enabled = False
    
    def fetch_dogecoin_data(self, days=30, end_date=None):
        """
        Fetch Dogecoin historical data for the specified number of days.
        
        Args:
            days: Number of days of historical data to fetch (default: 30)
            end_date: Optional datetime to use as end date (default: now). 
                     If provided, fetches historical data ending at this date.
        
        Returns:
            DataFrame with OHLCV data
        """
        try:
            # Use provided end_date or default to now
            if end_date is None:
                end_date = datetime.now()
            
            # Calculate start date (N days before end_date)
            start_date = end_date - timedelta(days=days)
            
            # Format dates for Coinbase API
            start_iso = start_date.isoformat()
            end_iso = end_date.isoformat()
            
            # Fetch historical data using Coinbase Advanced API
            # Note: Using the public API endpoint for historical data
            url = "https://api.exchange.coinbase.com/products/DOGE-USD/candles"
            params = {
                'start': start_iso,
                'end': end_iso,
                'granularity': 3600*24  # 1 day intervals
            }
            
            response = requests.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            # Convert to DataFrame
            df = pd.DataFrame(data, columns=['timestamp', 'low', 'high', 'open', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
            df = df.sort_values('timestamp')
            
            # Filter to only include data up to end_date (in case API returns future data)
            if end_date:
                df = df[df['timestamp'] <= end_date]
            
            return df
            
        except Exception as e:
            print(f"Error fetching Dogecoin data: {e}")
            return None
    
    def fetch_24h_ohlcv_data(self, end_date=None):
        """
        Fetch 24-hour OHLCV data for more detailed analysis.
        
        Args:
            end_date: Optional datetime to use as end date (default: now). 
                     If provided, fetches 24 hours of data ending at this date.
        
        Returns:
            DataFrame with hourly OHLCV data
        """
        try:
            # Use provided end_date or default to now
            if end_date is None:
                end_date = datetime.now()
            
            # Calculate dates for 24 hours before end_date to end_date
            start_date = end_date - timedelta(hours=24)
            
            # Format dates for Coinbase API
            start_iso = start_date.isoformat()
            end_iso = end_date.isoformat()
            
            url = "https://api.exchange.coinbase.com/products/DOGE-USD/candles"
            params = {
                'start': start_iso,
                'end': end_iso,
                'granularity': 3600  # 1 hour intervals
            }
            
            response = requests.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            # Convert to DataFrame
            df = pd.DataFrame(data, columns=['timestamp', 'low', 'high', 'open', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
            df = df.sort_values('timestamp')
            
            # Filter to only include data up to end_date
            df = df[df['timestamp'] <= end_date]
            
            return df
            
        except Exception as e:
            print(f"Error fetching 24h data: {e}")
            return None
    
    def fetch_order_book_data(self, target_date=None):
        """
        Fetch order book data.
        
        Args:
            target_date: Optional datetime for historical simulation. For historical dates,
                        we estimate order book from price data since historical order book
                        snapshots are not readily available via API.
        
        Returns:
            Dictionary with order book data and metrics
        """
        try:
            # For historical dates, we need to estimate order book from price data
            # Coinbase API doesn't provide historical order book snapshots easily
            if target_date:
                # Fetch price data for the target date
                price_data = self.fetch_historical_price_at_timestamp(target_date)
                if price_data:
                    price = price_data.get('close', 0)
                    # Estimate order book based on typical spread (0.01-0.05%)
                    spread_percent = 0.03  # Assume 0.03% spread
                    spread = price * (spread_percent / 100)
                    
                    # Create estimated order book
                    best_bid = price * (1 - spread_percent / 200)
                    best_ask = price * (1 + spread_percent / 200)
                    
                    # Estimate volumes (these are approximations)
                    bid_volume = 1000.0  # Estimated
                    ask_volume = 1000.0  # Estimated
                    
                    order_book = {
                        'bids': [[str(best_bid), str(bid_volume)]],
                        'asks': [[str(best_ask), str(ask_volume)]],
                        'sequence': 0,
                        'is_estimated': True,
                        'target_date': target_date.isoformat() if isinstance(target_date, datetime) else str(target_date),
                        'metrics': {
                            'best_bid': best_bid,
                            'best_ask': best_ask,
                            'spread': spread,
                            'spread_percent': spread_percent,
                            'bid_volume_top10': bid_volume,
                            'ask_volume_top10': ask_volume,
                            'volume_imbalance': 0.0  # Estimated as balanced
                        }
                    }
                    return order_book
                else:
                    print(f"⚠️  Could not fetch price data for order book estimation at {target_date}")
                    return None
            
            # Fetch current order book data
            url = "https://api.exchange.coinbase.com/products/DOGE-USD/book"
            params = {'level': 2}  # Level 2 order book
            
            response = requests.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            # Process order book data
            order_book = {
                'bids': data.get('bids', []),  # Buy orders
                'asks': data.get('asks', []),  # Sell orders
                'sequence': data.get('sequence', 0),
                'is_estimated': False
            }
            
            # Calculate order book metrics
            if order_book['bids'] and order_book['asks']:
                best_bid = float(order_book['bids'][0][0])
                best_ask = float(order_book['asks'][0][0])
                spread = best_ask - best_bid
                spread_percent = (spread / best_bid) * 100
                
                # Calculate bid/ask volume
                bid_volume = sum(float(bid[1]) for bid in order_book['bids'][:10])  # Top 10 bids
                ask_volume = sum(float(ask[1]) for ask in order_book['asks'][:10])  # Top 10 asks
                
                order_book['metrics'] = {
                    'best_bid': best_bid,
                    'best_ask': best_ask,
                    'spread': spread,
                    'spread_percent': spread_percent,
                    'bid_volume_top10': bid_volume,
                    'ask_volume_top10': ask_volume,
                    'volume_imbalance': (bid_volume - ask_volume) / (bid_volume + ask_volume) * 100 if (bid_volume + ask_volume) > 0 else 0
                }
            
            return order_book
            
        except Exception as e:
            print(f"Error fetching order book: {e}")
            return None
    
    def get_investment_status(self, target_date=None, current_usd_balance=None, current_doge_balance=None):
        """
        Get investment status and portfolio metrics.
        
        Args:
            target_date: Optional datetime for historical simulation. For historical dates,
                        calculates portfolio based on trades up to that date from database.
            current_usd_balance: Optional current USD balance (for simulation use)
            current_doge_balance: Optional current DOGE balance (for simulation use)
        
        Returns:
            Dictionary with investment status and portfolio metrics
        """
        # For historical simulation, calculate portfolio from database trades
        if target_date and self.database_enabled and self.db:
            try:
                # Get all trades up to target_date
                all_trades = self.db.get_all_trades()
                if all_trades:
                    # Filter trades up to target_date
                    from datetime import datetime as dt
                    if isinstance(target_date, str):
                        target_dt = dt.fromisoformat(target_date.replace('Z', '+00:00'))
                    else:
                        target_dt = target_date
                    
                    # Use provided current balances or calculate from trades
                    if current_usd_balance is not None and current_doge_balance is not None:
                        # Use provided balances (from simulation loop)
                        usd_balance = current_usd_balance
                        doge_balance = current_doge_balance
                    else:
                        # Calculate from initial balances by replaying trades
                        # Start with initial balances: $500 USD + $500 worth of DOGE
                        initial_usd_value = 500.0
                        initial_price_data = self.fetch_historical_price_at_timestamp(
                            datetime.now() - timedelta(days=7)  # Use first simulation time as reference
                        )
                        if initial_price_data:
                            initial_price = initial_price_data['close']
                            usd_balance = initial_usd_value
                            doge_balance = (500.0 / initial_price) if initial_price > 0 else 0.0
                        else:
                            usd_balance = 500.0
                            doge_balance = 0.0
                        
                        # Replay trades up to target_date
                        for trade in all_trades:
                            trade_timestamp = dt.fromisoformat(trade['timestamp'].replace('Z', '+00:00')) if isinstance(trade['timestamp'], str) else trade['timestamp']
                            if trade_timestamp > target_dt:
                                continue  # Skip trades after target_date
                            
                            action = trade['action']
                            percentage = trade['percentage'] or 0.0
                            trade_price = trade['current_price'] or 0.0
                            
                            if action == 'BUY' and trade_price > 0:
                                usd_to_spend = usd_balance * (percentage / 100)
                                doge_to_buy = usd_to_spend / trade_price
                                usd_balance -= usd_to_spend
                                doge_balance += doge_to_buy
                            elif action == 'SELL' and trade_price > 0:
                                doge_to_sell = doge_balance * (percentage / 100)
                                usd_from_sale = doge_to_sell * trade_price
                                doge_balance -= doge_to_sell
                                usd_balance += usd_from_sale
                    
                    # Get price at target_date
                    price_data = self.fetch_historical_price_at_timestamp(target_dt)
                    current_price = price_data['close'] if price_data else 0.0
                    
                    if current_price > 0:
                        # Calculate portfolio metrics
                        doge_value_usd = doge_balance * current_price
                        total_portfolio_value = usd_balance + doge_value_usd
                        
                        usd_percentage = (usd_balance / total_portfolio_value) * 100 if total_portfolio_value > 0 else 0
                        doge_percentage = (doge_value_usd / total_portfolio_value) * 100 if total_portfolio_value > 0 else 0
                        
                        # Calculate performance for different periods
                        performance_metrics = self.calculate_portfolio_performance_periods(
                            target_date=target_dt,
                            current_usd_balance=usd_balance,
                            current_doge_balance=doge_balance
                        )
                        
                        investment_status = {
                            'current_balances': {
                                'usd': usd_balance,
                                'doge': doge_balance,
                                'doge_value_usd': doge_value_usd,
                                'total_portfolio_value': total_portfolio_value
                            },
                            'current_price': current_price,
                            'allocation': {
                                'usd_percentage': usd_percentage,
                                'doge_percentage': doge_percentage
                            },
                            'performance': performance_metrics,
                            'is_historical': True,
                            'target_date': target_dt.isoformat()
                        }
                        return investment_status
            except Exception as e:
                print(f"⚠️  Error calculating historical investment status: {e}")
        
        # Get current investment status (default behavior)
        if not self.trading_enabled:
            return None
        
        try:
            # Get current balances
            usd_balance = self.trade_executor.get_usd_balance()
            doge_balance = self.trade_executor.get_dogecoin_balance()
            current_price = self.trade_executor.get_current_price()
            
            if usd_balance is None or doge_balance is None or current_price is None:
                return None
        except ValueError as e:
            # Authentication error - stop execution
            print(f"\n{'='*70}")
            print("❌ AUTHENTICATION ERROR - STOPPING EXECUTION")
            print(f"{'='*70}")
            print(str(e))
            print(f"{'='*70}\n")
            raise  # Re-raise to stop execution
        
        # Calculate portfolio metrics (only reached if no authentication error)
        doge_value_usd = doge_balance * current_price
        total_portfolio_value = usd_balance + doge_value_usd
        
        # Calculate allocation percentages
        usd_percentage = (usd_balance / total_portfolio_value) * 100 if total_portfolio_value > 0 else 0
        doge_percentage = (doge_value_usd / total_portfolio_value) * 100 if total_portfolio_value > 0 else 0
        
        # Load trade history for performance calculation
        performance_data = self.load_trade_history()
        
        # Calculate performance for different periods
        performance_metrics = self.calculate_portfolio_performance_periods(
            target_date=None,
            current_usd_balance=usd_balance,
            current_doge_balance=doge_balance
        )
        
        # Merge performance data (legacy) with new performance metrics
        if performance_data:
            performance_metrics['trade_history'] = performance_data
        
        investment_status = {
            'current_balances': {
                'usd': usd_balance,
                'doge': doge_balance,
                'doge_value_usd': doge_value_usd,
                'total_portfolio_value': total_portfolio_value
            },
            'allocation': {
                'usd_percentage': usd_percentage,
                'doge_percentage': doge_percentage
            },
            'current_price': current_price,
            'performance': performance_metrics,
            'is_historical': False
        }
        
        return investment_status
    
    def load_trade_history(self):
        """Load and analyze trade history for performance metrics."""
        try:
            with open('trade_history.json', 'r') as f:
                trades = json.load(f)
            
            if not trades:
                return {'total_trades': 0, 'success_rate': 0, 'recent_trades': []}
            
            # Calculate performance metrics
            successful_trades = [t for t in trades if t.get('success', False)]
            total_trades = len(trades)
            success_rate = (len(successful_trades) / total_trades) * 100 if total_trades > 0 else 0
            
            # Get recent trades (last 10)
            recent_trades = trades[-10:] if len(trades) >= 10 else trades
            
            return {
                'total_trades': total_trades,
                'successful_trades': len(successful_trades),
                'success_rate': success_rate,
                'recent_trades': recent_trades
            }
            
        except (FileNotFoundError, json.JSONDecodeError):
            return {'total_trades': 0, 'success_rate': 0, 'recent_trades': []}
    
    def fetch_fear_and_greed_index(self, limit=5, target_date=None):
        """
        Fetch Fear and Greed Index data from Alternative.me API.
        
        Args:
            limit: Number of historical records to fetch (default: 5)
            target_date: Optional datetime to fetch historical data for. If provided, 
                        will find the closest available data point to this date.
        
        Returns:
            Dictionary with current and historical Fear & Greed Index data
        """
        try:
            url = "https://api.alternative.me/fng/"
            
            # Fetch enough data to cover historical requests (up to 365 days)
            # For historical data, we need more records
            fetch_limit = limit if target_date is None else min(365, limit * 30)
            
            # Use Unix timestamp format (not 'world' date format) to avoid parsing issues
            params = {
                'limit': fetch_limit,
                'format': 'json'
                # Removed 'date_format': 'world' to get Unix timestamps instead of date strings
            }
            
            response = requests.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get('metadata', {}).get('error'):
                print(f"Fear and Greed API error: {data['metadata']['error']}")
                return None
            
            # Process the data
            fear_greed_data = {
                'name': data.get('name', 'Fear and Greed Index'),
                'current': None,
                'historical': []
            }
            
            if data.get('data'):
                # If target_date is provided, find the closest historical value
                if target_date:
                    closest_item = None
                    min_time_diff = float('inf')
                    
                    # Convert target_date to timestamp for comparison
                    from datetime import datetime as dt
                    if isinstance(target_date, str):
                        target_dt = dt.fromisoformat(target_date.replace('Z', '+00:00'))
                    elif isinstance(target_date, dt):
                        target_dt = target_date
                    else:
                        target_dt = target_date
                    
                    target_timestamp = int(target_dt.timestamp())
                    
                    # Find the closest data point
                    for item in data['data']:
                        # Handle both Unix timestamp (int) and date string formats
                        timestamp_value = item.get('timestamp', 0)
                        if isinstance(timestamp_value, str):
                            # Try to parse date string format (DD-MM-YYYY or similar)
                            try:
                                # Try parsing as ISO format first
                                if 'T' in timestamp_value or '-' in timestamp_value:
                                    item_timestamp = int(dt.fromisoformat(timestamp_value.replace('Z', '+00:00')).timestamp())
                                else:
                                    # Try parsing as Unix timestamp string
                                    item_timestamp = int(timestamp_value)
                            except (ValueError, TypeError):
                                # If parsing fails, try common date formats
                                try:
                                    # Try DD-MM-YYYY format
                                    item_timestamp = int(dt.strptime(timestamp_value, '%d-%m-%Y').timestamp())
                                except (ValueError, TypeError):
                                    try:
                                        # Try MM-DD-YYYY format
                                        item_timestamp = int(dt.strptime(timestamp_value, '%m-%d-%Y').timestamp())
                                    except (ValueError, TypeError):
                                        # Fallback: skip this item
                                        continue
                        else:
                            # Already a number (Unix timestamp)
                            item_timestamp = int(timestamp_value)
                        
                        time_diff = abs(item_timestamp - target_timestamp)
                        
                        # Prefer data before or at target_date (not future data)
                        if item_timestamp <= target_timestamp and time_diff < min_time_diff:
                            min_time_diff = time_diff
                            closest_item = item
                    
                    if closest_item:
                        fear_greed_data['current'] = {
                            'value': int(closest_item.get('value', 0)),
                            'classification': closest_item.get('value_classification', 'Unknown'),
                            'timestamp': closest_item.get('timestamp', ''),
                            'time_until_update': closest_item.get('time_until_update', ''),
                            'is_historical': True,
                            'target_date': target_dt.isoformat(),
                            'time_difference_days': abs(min_time_diff) / 86400  # Convert to days
                        }
                        return fear_greed_data
                    else:
                        print(f"⚠️  Could not find Fear & Greed Index data for {target_date}")
                        # Fall through to return latest if historical not found
                
                # Current (latest) data
                current = data['data'][0]
                fear_greed_data['current'] = {
                    'value': int(current.get('value', 0)),
                    'classification': current.get('value_classification', 'Unknown'),
                    'timestamp': current.get('timestamp', ''),
                    'time_until_update': current.get('time_until_update', ''),
                    'is_historical': False
                }
                
                # Historical data
                for item in data['data'][1:limit+1] if limit > 0 else []:
                    fear_greed_data['historical'].append({
                        'value': int(item.get('value', 0)),
                        'classification': item.get('value_classification', 'Unknown'),
                        'timestamp': item.get('timestamp', '')
                    })
            
            return fear_greed_data
            
        except Exception as e:
            print(f"Error fetching Fear and Greed Index: {e}")
            return None
    
    def fetch_historical_fear_and_greed_index(self, target_date):
        """
        Fetch Fear and Greed Index data for a specific historical date.
        
        Args:
            target_date: datetime object or ISO string for the target date
        
        Returns:
            Fear & Greed Index value for the target date, or None if not found
        """
        result = self.fetch_fear_and_greed_index(limit=365, target_date=target_date)
        if result and result.get('current'):
            return result['current'].get('value')
            return None
    
    def fetch_crypto_news(self, limit=10):
        """Fetch recent cryptocurrency news using SerpAPI Google News."""
        if not self.serpapi_key:
            print("Warning: SerpAPI key not found. News analysis will be skipped.")
            return None
        
        try:
            # Search for Dogecoin and cryptocurrency news
            search_queries = [
                "Dogecoin DOGE cryptocurrency news",
                "cryptocurrency market news",
            ]
            
            all_news = []
            
            for query in search_queries:
                try:
                    params = {
                        "engine": "google_news",
                        "q": query,
                        "gl": "us",
                        "hl": "en",
                        "num": limit // len(search_queries) + 1,  # Distribute results across queries
                        "api_key": self.serpapi_key
                    }
                    
                    search = GoogleSearch(params)
                    results = search.get_dict()
                    
                    if 'news_results' in results:
                        for news_item in results['news_results']:
                            # Extract relevant information
                            news_data = {
                                'headline': news_item.get('title', ''),
                                'date': news_item.get('date', '')
                            }
                            all_news.append(news_data)
                    
                    # Small delay to avoid rate limiting
                    import time
                    time.sleep(0.5)
                    
                except Exception as e:
                    print(f"Error fetching news for query '{query}': {e}")
                    continue
            
            # Remove duplicates based on headline
            seen_headlines = set()
            unique_news = []
            for news in all_news:
                if news['headline'] not in seen_headlines:
                    seen_headlines.add(news['headline'])
                    unique_news.append(news)
            
            # Sort by date (most recent first) and limit results
            unique_news = sorted(unique_news, key=lambda x: x['date'], reverse=True)[:limit]
            
            return {
                'total_articles': len(unique_news),
                'articles': unique_news,
                'fetched_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"Error fetching crypto news: {e}")
            return None
    
    def analyze_news_sentiment(self, news_data):
        """Analyze news sentiment using OpenAI."""
        if not news_data or not news_data.get('articles'):
            return None
        
        try:
            # Prepare news headlines for sentiment analysis
            headlines = []
            for article in news_data['articles'][:5]:  # Analyze top 5 articles
                headlines.append(f"- {article['headline']}")
            
            headlines_text = "\n".join(headlines)
            
            prompt = f"""
            Analyze the sentiment of these recent cryptocurrency news headlines and provide a market sentiment assessment:
            
            {headlines_text}
            
            Please provide:
            1. Overall sentiment (Very Positive/Positive/Neutral/Negative/Very Negative)
            2. Confidence level (High/Medium/Low)
            3. Key themes identified
            4. Market impact assessment (Bullish/Bearish/Neutral)
            5. Brief reasoning for the sentiment analysis
            
            Focus on how these news items might affect cryptocurrency markets, particularly Dogecoin.
            """
            
            client = openai.OpenAI(api_key=self.openai_api_key)
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are a financial news analyst specializing in cryptocurrency market sentiment analysis."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=10000,
                temperature=0.6
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            print(f"Error analyzing news sentiment: {e}")
            return None
    
    def calculate_technical_indicators(self, df):
        """Calculate comprehensive technical analysis indicators using ta library."""
        if df is None or df.empty:
            return {}
        
        try:
            # Clean the data
            df_clean = dropna(df.copy())
            
            # Ensure we have the required columns
            required_cols = ['open', 'high', 'low', 'close', 'volume']
            if not all(col in df_clean.columns for col in required_cols):
                print("Warning: Missing required OHLCV columns")
                return {}
            
            # Check if we have enough data points for calculations
            # Note: We'll calculate what we can with available data (some indicators need fewer points)
            if len(df_clean) < 7:  # Minimum needed for shortest indicator (7-day SMA)
                print(f"⚠️  Insufficient data points ({len(df_clean)}). Need at least 7 for basic technical analysis.")
                return {}
            
            # Warn if we have less than 30 points (some indicators won't be available)
            if len(df_clean) < 30:
                print(f"ℹ️  Limited data points ({len(df_clean)}). Some indicators requiring 30+ points will be skipped.")
            
            # Rename columns to match ta library expectations
            df_clean = df_clean.rename(columns={
                'open': 'Open',
                'high': 'High', 
                'low': 'Low',
                'close': 'Close',
                'volume': 'Volume'
            })
            
            technical_indicators = {}
            
            # TREND INDICATORS
            print("📊 Calculating trend indicators...")
            
            # Simple Moving Averages (only if we have enough data)
            if len(df_clean) >= 7:
                try:
                    technical_indicators['sma_7'] = SMAIndicator(close=df_clean['Close'], window=7).sma_indicator().iloc[-1]
                except:
                    pass
            
            if len(df_clean) >= 14:
                try:
                    technical_indicators['sma_14'] = SMAIndicator(close=df_clean['Close'], window=14).sma_indicator().iloc[-1]
                except:
                    pass
            
            if len(df_clean) >= 30:
                try:
                    technical_indicators['sma_30'] = SMAIndicator(close=df_clean['Close'], window=30).sma_indicator().iloc[-1]
                except:
                    pass
            
            # Exponential Moving Averages
            if len(df_clean) >= 7:
                try:
                    technical_indicators['ema_7'] = EMAIndicator(close=df_clean['Close'], window=7).ema_indicator().iloc[-1]
                except:
                    pass
            
            if len(df_clean) >= 14:
                try:
                    technical_indicators['ema_14'] = EMAIndicator(close=df_clean['Close'], window=14).ema_indicator().iloc[-1]
                except:
                    pass
            
            # MACD (needs at least 26 periods)
            if len(df_clean) >= 26:
                try:
                    macd = MACD(close=df_clean['Close'])
                    technical_indicators['macd'] = macd.macd().iloc[-1]
                    technical_indicators['macd_signal'] = macd.macd_signal().iloc[-1]
                    technical_indicators['macd_histogram'] = macd.macd_diff().iloc[-1]
                except:
                    pass
            
            # MOMENTUM INDICATORS
            print("📈 Calculating momentum indicators...")
            
            # RSI (needs at least 14 periods)
            if len(df_clean) >= 14:
                try:
                    rsi = RSIIndicator(close=df_clean['Close'])
                    technical_indicators['rsi'] = rsi.rsi().iloc[-1]
                except:
                    pass
            
            # Stochastic Oscillator (needs at least 14 periods)
            if len(df_clean) >= 14:
                try:
                    stoch = StochasticOscillator(high=df_clean['High'], low=df_clean['Low'], close=df_clean['Close'])
                    technical_indicators['stoch_k'] = stoch.stoch().iloc[-1]
                    technical_indicators['stoch_d'] = stoch.stoch_signal().iloc[-1]
                except:
                    pass
            
            # Williams %R (needs at least 14 periods)
            if len(df_clean) >= 14:
                try:
                    williams = WilliamsRIndicator(high=df_clean['High'], low=df_clean['Low'], close=df_clean['Close'])
                    technical_indicators['williams_r'] = williams.williams_r().iloc[-1]
                except:
                    pass
            
            # VOLATILITY INDICATORS
            print("📉 Calculating volatility indicators...")
            
            # Bollinger Bands (needs at least 20 periods)
            if len(df_clean) >= 20:
                try:
                    bb = BollingerBands(close=df_clean['Close'])
                    technical_indicators['bb_upper'] = bb.bollinger_hband().iloc[-1]
                    technical_indicators['bb_middle'] = bb.bollinger_mavg().iloc[-1]
                    technical_indicators['bb_lower'] = bb.bollinger_lband().iloc[-1]
                    technical_indicators['bb_width'] = bb.bollinger_wband().iloc[-1]
                    technical_indicators['bb_percent'] = bb.bollinger_pband().iloc[-1]
                except:
                    pass
            
            # Average True Range (needs at least 14 periods)
            if len(df_clean) >= 14:
                try:
                    atr = AverageTrueRange(high=df_clean['High'], low=df_clean['Low'], close=df_clean['Close'])
                    technical_indicators['atr'] = atr.average_true_range().iloc[-1]
                except:
                    pass
            
            # VOLUME INDICATORS
            print("📊 Calculating volume indicators...")
            
            # On Balance Volume
            try:
                obv = OnBalanceVolumeIndicator(close=df_clean['Close'], volume=df_clean['Volume'])
                technical_indicators['obv'] = obv.on_balance_volume().iloc[-1]
            except:
                pass
            
            # Chaikin Money Flow (needs at least 20 periods)
            if len(df_clean) >= 20:
                try:
                    cmf = ChaikinMoneyFlowIndicator(high=df_clean['High'], low=df_clean['Low'], close=df_clean['Close'], volume=df_clean['Volume'])
                    technical_indicators['cmf'] = cmf.chaikin_money_flow().iloc[-1]
                except:
                    pass
            
            # Clean up NaN values
            technical_indicators = {k: round(v, 6) if pd.notna(v) else None for k, v in technical_indicators.items()}
            
            print(f"✅ Calculated {len(technical_indicators)} technical indicators")
            return technical_indicators
            
        except Exception as e:
            print(f"Error calculating technical indicators: {e}")
            return {}
    
    def prepare_comprehensive_data(self, df_30d, df_24h, order_book, investment_status, fear_greed_data, news_data, news_sentiment):
        """Prepare comprehensive data for analysis including all new data sources."""
        if df_30d is None or df_30d.empty:
            return None
        
        # Calculate 30-day metrics
        current_price = df_30d['close'].iloc[-1]
        price_30_days_ago = df_30d['close'].iloc[0]
        price_change = current_price - price_30_days_ago
        price_change_percent = (price_change / price_30_days_ago) * 100
        
        # Calculate moving averages
        df_30d['ma_7'] = df_30d['close'].rolling(window=7).mean()
        df_30d['ma_14'] = df_30d['close'].rolling(window=14).mean()
        df_30d['ma_30'] = df_30d['close'].rolling(window=30).mean()
        
        # Calculate volatility (standard deviation of returns)
        df_30d['returns'] = df_30d['close'].pct_change()
        volatility_30d = df_30d['returns'].std() * 100
        
        # Get recent trends
        recent_high = df_30d['high'].max()
        recent_low = df_30d['low'].min()
        
        # Calculate 24-hour metrics
        volatility_24h = 0
        volume_24h_avg = 0
        price_range_24h = 0
        
        if df_24h is not None and not df_24h.empty:
            df_24h['returns'] = df_24h['close'].pct_change()
            volatility_24h = df_24h['returns'].std() * 100
            volume_24h_avg = df_24h['volume'].mean()
            price_range_24h = ((df_24h['high'].max() - df_24h['low'].min()) / df_24h['close'].iloc[0]) * 100
        
        # Prepare order book metrics
        order_book_metrics = {}
        if order_book and 'metrics' in order_book:
            order_book_metrics = order_book['metrics']
        
        # Prepare investment status
        investment_metrics = {}
        if investment_status:
            investment_metrics = {
                'current_allocation': investment_status.get('allocation', {}),
                'current_balances': investment_status.get('current_balances', {}),  # Include current_balances for USD/DOGE dollar values
                'portfolio_value': investment_status.get('current_balances', {}).get('total_portfolio_value', 0),
                'performance': investment_status.get('performance', {})  # Optional, may not exist for historical simulations
            }
        
        # Calculate technical indicators for 30-day data
        print("🔬 Calculating technical analysis indicators...")
        technical_indicators_30d = self.calculate_technical_indicators(df_30d)
        
        # Calculate technical indicators for 24-hour data
        technical_indicators_24h = self.calculate_technical_indicators(df_24h) if df_24h is not None else {}
        
        comprehensive_data = {
            # 30-day chart data
            'current_price': round(current_price, 6),
            'price_30_days_ago': round(price_30_days_ago, 6),
            'price_change': round(price_change, 6),
            'price_change_percent': round(price_change_percent, 2),
            'recent_high': round(recent_high, 6),
            'recent_low': round(recent_low, 6),
            'volatility_30d': round(volatility_30d, 2),
            
            # Moving averages
            'moving_averages': {
                'ma_7': round(df_30d['ma_7'].iloc[-1], 6) if not pd.isna(df_30d['ma_7'].iloc[-1]) else None,
                'ma_14': round(df_30d['ma_14'].iloc[-1], 6) if not pd.isna(df_30d['ma_14'].iloc[-1]) else None,
                'ma_30': round(df_30d['ma_30'].iloc[-1], 6) if not pd.isna(df_30d['ma_30'].iloc[-1]) else None
            },
            
            # Volume analysis
            'volume_analysis': {
                'avg_volume_30d': round(df_30d['volume'].mean(), 2),
                'recent_volume_30d': round(df_30d['volume'].iloc[-1], 2),
                'avg_volume_24h': round(volume_24h_avg, 2)
            },
            
            # 24-hour data
            'volatility_24h': round(volatility_24h, 2),
            'price_range_24h': round(price_range_24h, 2),
            
            # Order book data
            'order_book': order_book_metrics,
            
            # Investment status
            'investment_status': investment_metrics,
            
            # Technical indicators (30-day)
            'technical_indicators_30d': technical_indicators_30d,
            
            # Technical indicators (24-hour)
            'technical_indicators_24h': technical_indicators_24h,
            
            # Fear and Greed Index
            'fear_greed_index': fear_greed_data,
            
            # News Analysis
            'news_data': news_data,
            'news_sentiment': news_sentiment
        }
        
        return comprehensive_data
    
    def capture_doge_chart_image(self) -> str:
        """Capture the DOGE chart screenshot and return as base64 encoded string (headless mode)."""
        print("📸 Capturing DOGE chart screenshot (headless mode)...")
        
        driver = None
        try:
            # Create Chrome driver in headless mode (no browser window visible)
            driver = create_chrome_driver_for_screen_capture()
            
            # Increase page load timeout to handle slow loading
            driver.set_page_load_timeout(60)  # 60 seconds timeout
            
            # Navigate to Coinbase DOGE page
            DEFAULT_URL = "https://www.coinbase.com/advanced-trade/spot/DOGE-USD"
            print(f"Opening {DEFAULT_URL}...")
            try:
                driver.get(DEFAULT_URL)
            except Exception as e:
                print(f"⚠️  Page load timeout, continuing anyway: {e}")
            
            # Wait for page to load with longer timeout
            print("Waiting for page to load...")
            try:
                wait_for_page_ready(driver)
            except Exception as e:
                print(f"⚠️  Page ready check failed, continuing: {e}")
                time.sleep(3)  # Give it extra time
            
            # Dismiss cookies banner (non-blocking)
            try:
                dismiss_cookies_banner(driver)
            except Exception as e:
                print(f"⚠️  Could not dismiss cookies: {e}")
            
            # Click the 5D tab (non-blocking)
            try:
                click_time_range(driver, '5D', "/html/body/div[3]/div[3]/div[2]/div/div[2]/div/div/button[4]/div")
            except Exception as e:
                print(f"⚠️  Could not click 5D tab: {e}")
            
            # Try enabling Bollinger Bands indicator (non-blocking)
            try:
                if open_indicators_panel(driver):
                    if not select_indicator_by_search(driver, "Bollinger Bands"):
                        click_indicator_bollinger(driver)
            except Exception as e:
                print(f"⚠️  Could not add Bollinger Bands: {e}")
            
            # Click maximize chart (non-blocking)
            try:
                click_maximize_chart(driver)
            except Exception as e:
                print(f"⚠️  Could not maximize chart: {e}")
            
            # Note: Window size is already set via Chrome options (1600x900)
            # maximize_window() is not needed in headless mode
            
            # Wait for any animations to settle
            time.sleep(2)
            
            # Save screenshot to screenshots directory (same as screen_capture.py)
            screenshots_dir = Path(__file__).resolve().parent / "screenshots"
            screenshots_dir.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            screenshot_path = screenshots_dir / f"doge-chart-{timestamp}.png"
            
            try:
                # Capture screenshot with timeout protection
                try:
                    driver.save_screenshot(str(screenshot_path))
                    print(f"✅ Screenshot captured: {screenshot_path}")
                except Exception as e:
                    print(f"⚠️  Screenshot capture failed: {e}")
                    # Try one more time after a short wait
                    time.sleep(1)
                    try:
                        driver.save_screenshot(str(screenshot_path))
                        print(f"✅ Screenshot captured on retry: {screenshot_path}")
                    except Exception:
                        raise
                
                # Read image and convert to base64
                with open(screenshot_path, 'rb') as img_file:
                    img_bytes = img_file.read()
                    img_base64 = base64.b64encode(img_bytes).decode('utf-8')
                
                # Store chart path for database storage
                self.latest_chart_image_path = str(screenshot_path)
                
                print(f"📸 Screenshot saved at: {screenshot_path}")
                print(f"📊 Image size: {len(img_bytes)} bytes ({len(img_bytes)/1024:.1f} KB)")
                
                return img_base64
            except Exception as e:
                print(f"⚠️  Error processing screenshot: {e}")
                # Clean up if file was created but corrupted
                if screenshot_path and os.path.exists(screenshot_path):
                    try:
                        os.unlink(screenshot_path)
                    except Exception:
                        pass
                return None
            
        except Exception as e:
            print(f"⚠️  Error capturing chart screenshot: {e}")
            return None
        finally:
            if driver:
                try:
                    driver.quit()
                except Exception:
                    pass
    
    def analyze_with_chatgpt(self, chart_data, skip_chart_capture=False):
        """Send chart data to ChatGPT for analysis and get investment recommendation.
        
        Args:
            chart_data: Comprehensive market data dictionary
            skip_chart_capture: If True, skip chart screenshot capture (useful for simulations)
        """
        if not chart_data:
            return "Unable to analyze: No chart data available"
        
        # Capture the DOGE chart screenshot first (unless skipped)
        chart_image_base64 = None
        if not skip_chart_capture:
            try:
                chart_image_base64 = self.capture_doge_chart_image()
                if not chart_image_base64:
                    print("⚠️  Chart capture failed or returned no image, continuing without chart")
            except Exception as e:
                print(f"⚠️  Chart capture error: {e}")
                print("⏭️  Continuing without chart image")
                chart_image_base64 = None
        else:
            print("⏭️  Skipping chart capture for simulation")
        
        # Prepare the prompt for ChatGPT
        chart_image_note = ""
        if chart_image_base64:
            chart_image_note = "\n\n📈 CHART IMAGE:\nA live chart screenshot of the DOGE-USD trading view is provided below. Please analyze the visual chart patterns, candlestick formations, Bollinger Bands overlay, and other technical indicators visible in the image. Consider the chart patterns alongside the numerical data provided.\n"
        
        prompt = f"""
        As a professional financial analyst, please analyze the following comprehensive Dogecoin (DOGE) data and provide a personalized investment recommendation.{chart_image_note}

        📊 MARKET DATA ANALYSIS:
        
        **30-Day Chart Data:**
        - Current Price: ${chart_data['current_price']}
        - Price 30 days ago: ${chart_data['price_30_days_ago']}
        - Price Change: ${chart_data['price_change']} ({chart_data['price_change_percent']}%)
        - Recent High: ${chart_data['recent_high']}
        - Recent Low: ${chart_data['recent_low']}
        - 30-Day Volatility: {chart_data['volatility_30d']}%
        - 7-day Moving Average: ${chart_data['moving_averages']['ma_7']}
        - 14-day Moving Average: ${chart_data['moving_averages']['ma_14']}
        - 30-day Moving Average: ${chart_data['moving_averages']['ma_30']}
        
        **24-Hour Analysis:**
        - 24-Hour Volatility: {chart_data['volatility_24h']}%
        - 24-Hour Price Range: {chart_data['price_range_24h']}%
        - Average Volume (30d): {chart_data['volume_analysis']['avg_volume_30d']}
        - Recent Volume (30d): {chart_data['volume_analysis']['recent_volume_30d']}
        - Average Volume (24h): {chart_data['volume_analysis']['avg_volume_24h']}
        
        **Order Book Analysis:**
        - Best Bid: ${chart_data['order_book'].get('best_bid', 'N/A')}
        - Best Ask: ${chart_data['order_book'].get('best_ask', 'N/A')}
        - Spread: ${chart_data['order_book'].get('spread', 'N/A')} ({chart_data['order_book'].get('spread_percent', 'N/A')}%)
        - Bid Volume (Top 10): {chart_data['order_book'].get('bid_volume_top10', 'N/A')}
        - Ask Volume (Top 10): {chart_data['order_book'].get('ask_volume_top10', 'N/A')}
        - Volume Imbalance: {chart_data['order_book'].get('volume_imbalance', 'N/A')}%
        
        **CURRENT INVESTMENT STATUS:**
        - Portfolio Value: ${chart_data['investment_status'].get('portfolio_value', 'N/A')}
        - Current USD Allocation: {chart_data['investment_status'].get('current_allocation', {}).get('usd_percentage', 'N/A')}%
        - Current DOGE Allocation: {chart_data['investment_status'].get('current_allocation', {}).get('doge_percentage', 'N/A')}%
        - Total Trades Executed: {chart_data['investment_status'].get('performance', {}).get('total_trades', 'N/A')}
        - Success Rate: {chart_data['investment_status'].get('performance', {}).get('success_rate', 'N/A')}%

        **TECHNICAL ANALYSIS INDICATORS (30-Day):**
        
        **Trend Indicators:**
        - SMA 7: ${chart_data['technical_indicators_30d'].get('sma_7', 'N/A')}
        - SMA 14: ${chart_data['technical_indicators_30d'].get('sma_14', 'N/A')}
        - SMA 30: ${chart_data['technical_indicators_30d'].get('sma_30', 'N/A')}
        - EMA 7: ${chart_data['technical_indicators_30d'].get('ema_7', 'N/A')}
        - EMA 14: ${chart_data['technical_indicators_30d'].get('ema_14', 'N/A')}
        - MACD: {chart_data['technical_indicators_30d'].get('macd', 'N/A')}
        - MACD Signal: {chart_data['technical_indicators_30d'].get('macd_signal', 'N/A')}
        - ADX: {chart_data['technical_indicators_30d'].get('adx', 'N/A')}
        
        **Momentum Indicators:**
        - RSI: {chart_data['technical_indicators_30d'].get('rsi', 'N/A')}
        - Stochastic %K: {chart_data['technical_indicators_30d'].get('stoch_k', 'N/A')}
        - Stochastic %D: {chart_data['technical_indicators_30d'].get('stoch_d', 'N/A')}
        - Williams %R: {chart_data['technical_indicators_30d'].get('williams_r', 'N/A')}
        - CCI: {chart_data['technical_indicators_30d'].get('cci', 'N/A')}
        - ROC: {chart_data['technical_indicators_30d'].get('roc', 'N/A')}%
        
        **Volatility Indicators:**
        - Bollinger Upper: ${chart_data['technical_indicators_30d'].get('bb_upper', 'N/A')}
        - Bollinger Middle: ${chart_data['technical_indicators_30d'].get('bb_middle', 'N/A')}
        - Bollinger Lower: ${chart_data['technical_indicators_30d'].get('bb_lower', 'N/A')}
        - Bollinger %B: {chart_data['technical_indicators_30d'].get('bb_percent', 'N/A')}
        - ATR: {chart_data['technical_indicators_30d'].get('atr', 'N/A')}
        
        **Volume Indicators:**
        - OBV: {chart_data['technical_indicators_30d'].get('obv', 'N/A')}
        - CMF: {chart_data['technical_indicators_30d'].get('cmf', 'N/A')}
        - VWAP: ${chart_data['technical_indicators_30d'].get('vwap', 'N/A')}

        **MARKET SENTIMENT (Fear and Greed Index):**
        - Current Value: {chart_data['fear_greed_index'].get('current', {}).get('value', 'N/A') if chart_data.get('fear_greed_index') else 'N/A'}
        - Classification: {chart_data['fear_greed_index'].get('current', {}).get('classification', 'N/A') if chart_data.get('fear_greed_index') else 'N/A'}
        - Time Until Update: {chart_data['fear_greed_index'].get('current', {}).get('time_until_update', 'N/A') if chart_data.get('fear_greed_index') else 'N/A'} seconds
        - Historical Trend: {len(chart_data['fear_greed_index'].get('historical', [])) if chart_data.get('fear_greed_index') else 0} previous readings available

        **RECENT NEWS ANALYSIS:**
        - Total Articles Analyzed: {chart_data['news_data'].get('total_articles', 'N/A') if chart_data.get('news_data') else 'N/A'}
        - News Sentiment Analysis: {chart_data['news_sentiment'] if chart_data.get('news_sentiment') else 'N/A'}
        - Top News Headlines:
        {chr(10).join([f"  • {article['headline']}" for article in chart_data['news_data'].get('articles', [])[:3]]) if chart_data.get('news_data') and chart_data['news_data'].get('articles') else '  • No news data available'}

        Please provide your analysis in the following JSON format:
        {{
            "recommendation": "BUY|SELL|HOLD",
            "percentage": <number between 0-100, null if HOLD>,
            "confidence_level": "High|Medium|Low",
            "reasoning": "<detailed reasoning text>",
            "risk_assessment": "Low|Medium|High",
            "risk_factors": ["<factor1>", "<factor2>", ...],
            "portfolio_rebalancing": "<rebalancing considerations text>",
            "key_market_factors": ["<factor1>", "<factor2>", ...],
            "timing_considerations": "<timing considerations text>"
        }}

        For percentage recommendations (following proven risk management principles):
        - BUY: Suggest 20-30% of available funds when bullish signals are clear (rigorous risk management - never recommend 100% allocation)
        - SELL: Suggest 20-30% of current holdings when bearish signals are clear or taking profits is prudent (never recommend 100% sell unless extreme circumstances)
        - HOLD: Set percentage to null (not 0). Only recommend HOLD when:
          * There are genuinely mixed signals with no clear direction
          * Waiting for confirmation is truly the best strategy
          * NOT just because you're being overly cautious - if there's a clear signal (even if modest), make a recommendation
        - CRITICAL: Balance capital preservation with opportunity. Being too conservative means missing profitable opportunities. 
        - Make DECISIVE recommendations when signals are present - don't default to HOLD just because you're uncertain

        IMPORTANT DECISION GUIDELINES:
        - **AGGRESSIVE BUY SIGNALS**: 
          * Price near historical support level → STRONG BUY signal (buying opportunity at discounted price)
          * Price dropped significantly (10%+ in 30 days) → BUY opportunity (mean reversion potential)
          * Fear and Greed Index shows extreme fear (<30) → BUY opportunity (contrarian strategy)
          * Price below key moving averages BUT near support → BUY (buying at support)
          * Portfolio is heavily weighted to USD (>70%) → Look for BUY opportunities to rebalance
        - If price is near support with bullish patterns forming → BUY (don't just HOLD waiting)
        - If price is near resistance with bearish patterns forming → SELL (don't just HOLD hoping)
        - If price shows clear trend with momentum → Follow the trend with BUY or SELL
        - **CRITICAL**: When portfolio is >70% USD and price is near support or has dropped significantly, BUY is the default action (not HOLD)
        - **CRITICAL**: When Fear and Greed Index shows extreme fear (<30), consider BUY as a contrarian opportunity
        - HOLD should be a conscious strategic choice, not a default due to uncertainty
        - **NEVER** recommend HOLD when price is at support AND portfolio is heavily weighted to USD (>70%) - this is a clear BUY opportunity

        In your reasoning, prioritize in this order (CHART ANALYSIS IS PRIMARY):

        PRIMARY ANALYSIS (Most Important):
        1. **Chart Analysis - Support and Resistance Levels**:
           - Identify key support and resistance levels from the chart (CRITICAL for buy/sell decisions)
           - Use support/resistance as benchmarks to determine entry and exit points
           - These are the most important decision-making tools
        
        2. **Chart Analysis - Candlestick Patterns and Moving Averages**:
           - Focus on candlestick patterns (primary tool for reading market psychology)
           - Analyze moving averages (more important than technical indicators)
           - Decipher the underlying psychology of market participants from chart patterns
           - Predict market trends and reversals through candlestick formations
        
        3. **Chart Analysis - Market Flow and Psychology**:
           - Read market flow from the chart
           - Understand market participant psychology reflected in the chart
           - Identify uptrends and downtrends from chart analysis
           - Observe how market is reacting to key levels

        SECONDARY ANALYSIS (Supporting Factors):
        4. **Market Sentiment Analysis**:
           - Use Fear and Greed Index to understand market sentiment
           - Remember: if market sentiment is positive, even negative news likely has little effect
           - If sentiment is negative, even positive news likely has little impact
           - Chart-based sentiment (from visual chart) takes priority over numerical sentiment
        
        5. **Trend Analysis** (from chart):
           - Moving averages visible in the chart
           - Short-term vs long-term trends visible in the chart
           - Chart formations and patterns

        TERTIARY ANALYSIS (Reference Only):
        6. Technical indicators (RSI, MACD, Bollinger Bands, etc.) - use as reference, not primary decision makers
        7. Volume analysis (OBV, CMF, VWAP, volume bars) - supporting information
        8. News sentiment - consider but prioritize chart signals over news
        9. Order book depth - reference information only
        10. Current portfolio allocation - factor into risk management
        11. Recent trading performance - context only

        REMEMBER: Chart-based trading is the foundation. Technical indicators are secondary. News is tertiary.

        **PORTFOLIO REBALANCING LOGIC** (CRITICAL - CHECK THIS FIRST):
        - Current portfolio allocation is shown in "Current Investment Status"
        - **IF USD allocation >70% AND (price near support OR price dropped 10%+ OR Fear Index <30)**:
          → **BUY 20-30% to rebalance** (portfolio is too USD-heavy, this is a buying opportunity)
          → Do NOT recommend HOLD when portfolio is >70% USD - this means money is sitting idle
        - **IF DOGE allocation >70% AND (price near resistance OR price rose 10%+ OR Greed Index >70)**:
          → **SELL 20-30% to rebalance** (take profits, reduce exposure)
        - Balance is key - don't let portfolio become too heavily weighted in one direction

        **FEAR = BUY OPPORTUNITY** (Contrarian Strategy):
        - When Fear and Greed Index is <30 (extreme fear) → **BUY opportunity** (buy when others are fearful)
        - Fear often indicates oversold conditions and potential bounce
        - "Buy the dip" - significant price drops (10%+) are buying opportunities, not reasons to HOLD

        **REBALANCING EXAMPLES**:
        - Portfolio: 99% USD, 1% DOGE, Price near support, Fear Index: 29
          → **BUY 25-30%** (rebalance from USD to DOGE at support level)
        - Portfolio: 50% USD, 50% DOGE, Price near resistance, Greed Index: 75
          → **SELL 20-25%** (take profits, reduce DOGE exposure)
        - Portfolio: 80% USD, 20% DOGE, Price dropped 15%, Fear Index: 30
          → **BUY 25%** (buying opportunity: price dropped, fear present, USD-heavy)

        Consider the investor's current position and provide personalized advice based on their specific portfolio allocation and trading history.
        Return ONLY valid JSON, no additional text before or after.
        """
        
        try:
            client = openai.OpenAI(api_key=self.openai_api_key)
            
            # Prepare messages with image if available
            messages = [
                {
                    "role": "system",
                    "content": """
                        You are a chart-based Bitcoin trading system that strictly follows the principles and trading philosophy of a professional Bitcoin investor.
                        Your mission is to execute trades with high win rates, strict risk control, and consistent compounding returns.
                        Follow these rules precisely:

                        1. Core Philosophy
                        - Trade only based on charts — never on news, rumors, or speculative information.
                        - Ignore metrics like long/short ratios, liquidation data, or funding rates unless they clearly influence overall market sentiment.
                        - Your edge is chart mastery — read price action and market psychology through candlestick patterns, support/resistance, and trend structure.

                        2. Market Sentiment & Flexibility
                        - Continuously evaluate market sentiment.
                        - If sentiment is positive, negative news has limited effect — the market tends to rise.
                        - If sentiment is negative, positive news has limited effect — the market tends to fall.
                        - Adapt your trading plan flexibly based on the current sentiment and market behavior.
                        - Use macro indicators and major economic events only to understand the bigger market context, not for direct trade triggers.

                        3. Chart-Based Strategy
                        - Identify major support and resistance levels to determine precise buy/sell zones.
                        - Analyze overall market structure to detect uptrends, downtrends, and reversals.
                        - Use candlestick formations and moving averages (not complex indicators) to confirm entry or exit signals.
                        - Focus primarily on Bitcoin and large-cap coins.
                        - When trading altcoins, always reference Bitcoin’s chart trend first.

                        4. Risk Management & Stop-Loss
                        - Apply mechanical stop-losses when:
                        - The market deviates from your planned scenario, or
                        - Your mental or emotional state becomes unstable.
                        - Predefine stop-loss levels before each trade and execute them without hesitation or emotion.
                        - Never average down losing positions.
                        - Split positions into smaller trades to reduce risk exposure.
                        - Preserve capital above all else.

                        5. Leverage & Capital Management
                        - Use only 20–30% of total available capital per active trade.
                        - When total capital is small, up to 10x leverage may be used cautiously.
                        - As total assets grow, gradually reduce leverage to maintain safety and stability.
                        - Always practice split buying and stop-loss selling.
                        - Avoid impulsive trades or emotional reactions to price swings.

                        6. Compounding & Performance Goal
                        - Prioritize high win rate and small, consistent gains.
                        - Target 1–2% daily profit, focusing on steady compounding, not large one-time wins.
                        - Maintain discipline — no revenge trading, no emotional decisions.
                        - Over time, consistent compounding creates exponential returns.

                        7. Continuous Improvement
                        - Treat charts as a reflection of collective market psychology.
                        - Constantly study and practice chart reading to enhance accuracy.
                        - Each trading day, review performance, note psychological mistakes, and refine entry/exit logic.

                        Execution Mode
                        - Analyze Bitcoin chart and sentiment first.
                        - Identify key levels and trend direction.
                        - Wait for high-probability setup before entering.
                        - Manage trades automatically according to this system — never deviate.
                        - Always prioritize risk management and preservation of trading capital.
                    """,
                },
                {
                    "role": "user",
                    "content": []
                }
            ]
            
            # Add text prompt
            messages[1]["content"].append({
                "type": "text",
                "text": prompt
            })
            
            # Add chart image if captured successfully
            if chart_image_base64:
                messages[1]["content"].append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{chart_image_base64}"
                    }
                })
                print("✅ Chart image included in analysis")
            
            # Define strict JSON schema for validation
            json_schema = {
                "type": "object",
                "properties": {
                    "recommendation": {
                        "type": "string",
                        "enum": ["BUY", "SELL", "HOLD"]
                    },
                    "percentage": {
                        "type": ["number", "null"],
                        "minimum": 0,
                        "maximum": 100
                    },
                    "confidence_level": {
                        "type": "string",
                        "enum": ["High", "Medium", "Low"]
                    },
                    "reasoning": {
                        "type": "string"
                    },
                    "risk_assessment": {
                        "type": "string",
                        "enum": ["High", "Medium", "Low"]
                    },
                    "risk_factors": {
                        "type": "array",
                        "items": {
                            "type": "string"
                        }
                    },
                    "portfolio_rebalancing": {
                        "type": "string"
                    },
                    "key_market_factors": {
                        "type": "array",
                        "items": {
                            "type": "string"
                        }
                    },
                    "timing_considerations": {
                        "type": "string"
                    }
                },
                "required": ["recommendation", "confidence_level", "reasoning", "risk_assessment"],
                "strict": True,
                "additionalProperties": False  # Strict: no extra fields allowed
            }
            
            # Note: OpenAI's response_format currently only supports {"type": "json_object"}
            # JSON Schema validation is done manually after parsing
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                max_tokens=10000,  # Increased for structured JSON output
                temperature=0.3,  # Lower temperature for more consistent results
                response_format={"type": "json_object"}  # Force JSON output, schema validated manually
            )
            
            # Parse JSON response
            response_content = response.choices[0].message.content
            try:
                analysis_json = json.loads(response_content)
                
                # Validate against JSON schema
                validation_error = self.validate_json_schema(analysis_json, json_schema)
                if validation_error:
                    raise ValueError(f"JSON Schema validation failed: {validation_error}")
                
                # Format the JSON response as a readable text analysis
                formatted_analysis = self.format_json_analysis(analysis_json)
                
                # Store the JSON for later use
                self.latest_analysis_json = analysis_json
                
                print("✅ JSON response successfully parsed and validated against schema")
                
                return formatted_analysis
            except json.JSONDecodeError as e:
                print(f"⚠️  Warning: Failed to parse JSON response: {e}")
                print(f"Raw response: {response_content[:200]}...")
                return response_content  # Fallback to raw response
            except ValueError as e:
                print(f"⚠️  Warning: {e}")
                print(f"Raw response: {response_content[:200]}...")
                return response_content  # Fallback to raw response
            
        except Exception as e:
            return f"Error getting ChatGPT analysis: {e}"
    
    def validate_json_schema(self, data, schema):
        """Validate JSON data against a JSON schema definition."""
        errors = []
        
        # Check if data is an object
        if not isinstance(data, dict):
            return f"Expected object, got {type(data).__name__}"
        
        # Check required fields
        if "required" in schema:
            for field in schema["required"]:
                if field not in data:
                    errors.append(f"Missing required field: {field}")
        
        # Check additional properties
        if schema.get("additionalProperties") is False:
            allowed_fields = set(schema.get("properties", {}).keys())
            actual_fields = set(data.keys())
            extra_fields = actual_fields - allowed_fields
            if extra_fields:
                errors.append(f"Extra fields not allowed: {', '.join(extra_fields)}")
        
        # Validate each property
        if "properties" in schema:
            for field_name, field_schema in schema["properties"].items():
                if field_name not in data:
                    continue  # Optional fields are handled by required check
                
                value = data[field_name]
                field_type = field_schema.get("type")
                
                # Handle union types (e.g., ["number", "null"])
                if isinstance(field_type, list):
                    if not any(self._validate_type(value, t) for t in field_type):
                        errors.append(f"Field '{field_name}': expected one of {field_type}, got {type(value).__name__}")
                    continue
                
                # Check type
                if not self._validate_type(value, field_type):
                    errors.append(f"Field '{field_name}': expected {field_type}, got {type(value).__name__}")
                    continue
                
                # Check enum
                if "enum" in field_schema:
                    if value not in field_schema["enum"]:
                        errors.append(f"Field '{field_name}': expected one of {field_schema['enum']}, got '{value}'")
                
                # Check number constraints
                if field_type == "number" and isinstance(value, (int, float)):
                    if "minimum" in field_schema and value < field_schema["minimum"]:
                        errors.append(f"Field '{field_name}': value {value} is below minimum {field_schema['minimum']}")
                    if "maximum" in field_schema and value > field_schema["maximum"]:
                        errors.append(f"Field '{field_name}': value {value} is above maximum {field_schema['maximum']}")
                
                # Check array items
                if field_type == "array" and "items" in field_schema:
                    items_schema = field_schema["items"]
                    for i, item in enumerate(value):
                        if not self._validate_type(item, items_schema.get("type")):
                            errors.append(f"Field '{field_name}[{i}]': expected {items_schema.get('type')}, got {type(item).__name__}")
        
        if errors:
            return "; ".join(errors)
        return None
    
    def _validate_type(self, value, expected_type):
        """Check if value matches expected type."""
        if expected_type == "string":
            return isinstance(value, str)
        elif expected_type == "number":
            return isinstance(value, (int, float))
        elif expected_type == "integer":
            return isinstance(value, int)
        elif expected_type == "boolean":
            return isinstance(value, bool)
        elif expected_type == "array":
            return isinstance(value, list)
        elif expected_type == "object":
            return isinstance(value, dict)
        elif expected_type == "null":
            return value is None
        return False
    
    def format_json_analysis(self, analysis_json):
        """Format JSON analysis response into readable text format."""
        try:
            recommendation = analysis_json.get('recommendation', 'HOLD').upper()
            percentage = analysis_json.get('percentage')
            confidence = analysis_json.get('confidence_level', 'Medium')
            reasoning = analysis_json.get('reasoning', 'No reasoning provided')
            risk_assessment = analysis_json.get('risk_assessment', 'Medium')
            risk_factors = analysis_json.get('risk_factors', [])
            portfolio_rebalancing = analysis_json.get('portfolio_rebalancing', 'No specific rebalancing recommendations')
            key_market_factors = analysis_json.get('key_market_factors', [])
            timing_considerations = analysis_json.get('timing_considerations', 'No specific timing considerations')
            
            # Build formatted text output
            formatted = f"""### Recommendation: {recommendation}

#### 1. Recommendation Details:
- **Action**: {recommendation}"""
            
            if percentage is not None:
                formatted += f"\n- **Percentage**: {percentage}%"
            else:
                formatted += "\n- **Percentage**: N/A (HOLD recommendation)"
            
            formatted += f"""
- **Confidence Level**: {confidence}

#### 2. Brief Reasoning:

{reasoning}

#### 3. Risk Assessment: {risk_assessment}"""
            
            if risk_factors:
                formatted += "\n- **Risk Factors**:"
                for factor in risk_factors:
                    formatted += f"\n  - {factor}"
            
            formatted += f"""

#### 4. Portfolio Rebalancing Considerations:
{portfolio_rebalancing}"""
            
            if key_market_factors:
                formatted += "\n#### 5. Key Market Factors:"
                for factor in key_market_factors:
                    formatted += f"\n- {factor}"
            
            formatted += f"""

#### 6. Timing Considerations:
{timing_considerations}
"""
            
            return formatted
            
        except Exception as e:
            return f"Error formatting JSON analysis: {e}\n\nRaw JSON: {json.dumps(analysis_json, indent=2)}"
    
    def highlight_percentage_recommendations(self, analysis):
        """Highlight percentage recommendations in the analysis text."""
        import re
        
        # Look for percentage patterns in the text
        percentage_patterns = [
            r'(BUY|SELL)\s+(\d+%)\s+(?:of\s+)?(?:portfolio|holdings|funds)',
            r'(BUY|SELL)\s+(\d+%)\s+(?:of\s+)?(?:your\s+)?(?:current\s+)?(?:position|holdings)',
            r'(\d+%)\s+(?:of\s+)?(?:portfolio|holdings|funds|position)',
            r'(?:allocate|invest|sell)\s+(\d+%)',
        ]
        
        highlighted_text = analysis
        
        for pattern in percentage_patterns:
            matches = re.finditer(pattern, analysis, re.IGNORECASE)
            for match in matches:
                original = match.group(0)
                # Add emoji and formatting for percentage recommendations
                if 'BUY' in original.upper():
                    highlighted = f"🟢 {original}"
                elif 'SELL' in original.upper():
                    highlighted = f"🔴 {original}"
                else:
                    highlighted = f"📊 {original}"
                
                highlighted_text = highlighted_text.replace(original, highlighted)
        
        return highlighted_text
    
    def display_comprehensive_summary(self, comprehensive_data):
        """Display a comprehensive summary of all data sources."""
        if not comprehensive_data:
            return
        
        print("\n" + "="*80)
        print("📊 COMPREHENSIVE MARKET ANALYSIS SUMMARY")
        print("="*80)
        
        # Price and Performance
        print(f"💰 Current Price: ${comprehensive_data['current_price']}")
        print(f"📈 30-Day Change: {comprehensive_data['price_change_percent']}%")
        print(f"📊 Price Range: ${comprehensive_data['recent_low']} - ${comprehensive_data['recent_high']}")
        
        # Volatility Analysis
        print(f"\n📉 Volatility Analysis:")
        print(f"   30-Day: {comprehensive_data['volatility_30d']}%")
        print(f"   24-Hour: {comprehensive_data['volatility_24h']}%")
        print(f"   24-Hour Range: {comprehensive_data['price_range_24h']}%")
        
        # Moving Averages
        print(f"\n📊 Moving Averages:")
        ma_data = comprehensive_data['moving_averages']
        print(f"   7-Day: ${ma_data['ma_7']}")
        print(f"   14-Day: ${ma_data['ma_14']}")
        print(f"   30-Day: ${ma_data['ma_30']}")
        
        # Volume Analysis
        print(f"\n📊 Volume Analysis:")
        vol_data = comprehensive_data['volume_analysis']
        print(f"   Average (30d): {vol_data['avg_volume_30d']}")
        print(f"   Recent (30d): {vol_data['recent_volume_30d']}")
        print(f"   Average (24h): {vol_data['avg_volume_24h']}")
        
        # Order Book Analysis
        if comprehensive_data['order_book']:
            print(f"\n📚 Order Book Analysis:")
            ob_data = comprehensive_data['order_book']
            print(f"   Best Bid: ${ob_data.get('best_bid', 'N/A')}")
            print(f"   Best Ask: ${ob_data.get('best_ask', 'N/A')}")
            print(f"   Spread: ${ob_data.get('spread', 'N/A')} ({ob_data.get('spread_percent', 'N/A')}%)")
            print(f"   Volume Imbalance: {ob_data.get('volume_imbalance', 'N/A')}%")
        
        # Investment Status
        if comprehensive_data['investment_status']:
            print(f"\n💼 Current Investment Status:")
            inv_data = comprehensive_data['investment_status']
            print(f"   Portfolio Value: ${inv_data.get('portfolio_value', 'N/A')}")
            
            # Show actual dollar values instead of percentages
            balances = inv_data.get('current_balances', {})
            usd_value = balances.get('usd', 0)
            doge_value_usd = balances.get('doge_value_usd', 0)
            
            print(f"   USD: ${usd_value:.2f}")
            print(f"   DOGE: ${doge_value_usd:.2f}")
            
            # Show performance metrics for different periods
            perf_data = inv_data.get('performance', {})
            # Debug: Check if performance data exists
            if not perf_data:
                print(f"⚠️  No performance data in investment_status. Keys: {list(inv_data.keys())}")
            elif not isinstance(perf_data, dict):
                print(f"⚠️  Performance data is not a dict: {type(perf_data)}")
            elif len(perf_data) == 0:
                print(f"⚠️  Performance data dict is empty")
            
            if perf_data and isinstance(perf_data, dict) and len(perf_data) > 0:
                # Check if it's the new performance metrics format (period-based)
                has_period_metrics = any(key in perf_data for key in ['1d', '5d', '1m', '3m', '6m', 'ytd', '1y', 'entire'])
                
                if has_period_metrics:
                    print(f"\n📊 Portfolio Performance (vs Buy-and-Hold):")
                    periods = {
                        '1d': '1 Day',
                        '5d': '5 Days',
                        '1m': '1 Month',
                        '3m': '3 Months',
                        '6m': '6 Months',
                        'ytd': 'YTD',
                        '1y': '1 Year',
                        'entire': 'Entire'
                    }
                    for period_key, period_label in periods.items():
                        if period_key in perf_data:
                            period_info = perf_data[period_key]
                            value = period_info.get('value', 0)
                            symbol = "📈" if value > 0 else "📉" if value < 0 else "➡️"
                            print(f"   {symbol} {period_label}: {value:+.2f}%")
                else:
                    # Show trade history performance if available (legacy format)
                    if 'total_trades' in perf_data:
                        print(f"\n📊 Trading Statistics:")
            print(f"   Total Trades: {perf_data.get('total_trades', 'N/A')}")
            print(f"   Success Rate: {perf_data.get('success_rate', 'N/A')}%")
        
        # Technical Indicators Summary
        if comprehensive_data.get('technical_indicators_30d'):
            print(f"\n🔬 Key Technical Indicators:")
            ti_data = comprehensive_data['technical_indicators_30d']
            
            # Key momentum indicators
            rsi = ti_data.get('rsi')
            if rsi:
                rsi_status = "Overbought" if rsi > 70 else "Oversold" if rsi < 30 else "Neutral"
                print(f"   RSI: {rsi:.1f} ({rsi_status})")
            
            # MACD
            macd = ti_data.get('macd')
            macd_signal = ti_data.get('macd_signal')
            if macd and macd_signal:
                macd_status = "Bullish" if macd > macd_signal else "Bearish"
                print(f"   MACD: {macd:.4f} vs Signal: {macd_signal:.4f} ({macd_status})")
            
            # Bollinger Bands
            bb_upper = ti_data.get('bb_upper')
            bb_lower = ti_data.get('bb_lower')
            bb_percent = ti_data.get('bb_percent')
            if bb_percent is not None:
                bb_status = "Above Upper" if bb_percent > 1 else "Below Lower" if bb_percent < 0 else "Within Bands"
                print(f"   Bollinger %B: {bb_percent:.2f} ({bb_status})")
            
            # Stochastic
            stoch_k = ti_data.get('stoch_k')
            if stoch_k:
                stoch_status = "Overbought" if stoch_k > 80 else "Oversold" if stoch_k < 20 else "Neutral"
                print(f"   Stochastic %K: {stoch_k:.1f} ({stoch_status})")
        
        # Fear and Greed Index Summary
        if comprehensive_data.get('fear_greed_index'):
            print(f"\n😨😈 Market Sentiment (Fear and Greed Index):")
            fg_data = comprehensive_data['fear_greed_index']
            current = fg_data.get('current', {})
            
            if current:
                value = current.get('value', 0)
                classification = current.get('classification', 'Unknown')
                
                # Determine sentiment emoji and interpretation
                if value <= 25:
                    sentiment_emoji = "😨"
                    sentiment_desc = "Extreme Fear - Potential buying opportunity"
                elif value <= 45:
                    sentiment_emoji = "😟"
                    sentiment_desc = "Fear - Cautious sentiment"
                elif value <= 55:
                    sentiment_emoji = "😐"
                    sentiment_desc = "Neutral - Balanced sentiment"
                elif value <= 75:
                    sentiment_emoji = "😊"
                    sentiment_desc = "Greed - Optimistic sentiment"
                else:
                    sentiment_emoji = "😈"
                    sentiment_desc = "Extreme Greed - Potential selling opportunity"
                
                print(f"   {sentiment_emoji} Current Value: {value} ({classification})")
                print(f"   📊 Interpretation: {sentiment_desc}")
                
                # Show historical trend if available
                historical = fg_data.get('historical', [])
                if historical:
                    prev_value = historical[0].get('value', 0) if historical else 0
                    trend = "↗️ Rising" if value > prev_value else "↘️ Falling" if value < prev_value else "➡️ Stable"
                    print(f"   📈 Trend: {trend} (Previous: {prev_value})")
        
        # News Analysis Summary
        if comprehensive_data.get('news_data'):
            print(f"\n📰 Recent News Analysis:")
            news_data = comprehensive_data['news_data']
            print(f"   📊 Total Articles: {news_data.get('total_articles', 'N/A')}")
            
            # Show top headlines
            articles = news_data.get('articles', [])
            if articles:
                print(f"   📋 Top Headlines:")
                for i, article in enumerate(articles[:3], 1):
                    headline = article.get('headline', 'No headline')[:60] + "..." if len(article.get('headline', '')) > 60 else article.get('headline', 'No headline')
                    date = article.get('date', 'Unknown date')
                    print(f"      {i}. {headline} - {date}")
            
            # Show news sentiment if available
            if comprehensive_data.get('news_sentiment'):
                print(f"\n🔍 News Sentiment Analysis:")
                sentiment = comprehensive_data['news_sentiment']
                # Extract first line as summary
                first_line = sentiment.split('\n')[0] if sentiment else 'No sentiment analysis available'
                print(f"   📊 {first_line}")
        
        print("="*80)
    
    def extract_recommendation_summary(self, analysis):
        """Extract the key recommendation and percentage from the analysis."""
        # First try to get from JSON if available
        if self.latest_analysis_json:
            try:
                recommendation = self.latest_analysis_json.get('recommendation', '').upper()
                percentage = self.latest_analysis_json.get('percentage')
                
                if recommendation in ['BUY', 'SELL', 'HOLD']:
                    if recommendation in ['BUY', 'SELL'] and percentage is not None:
                        return f"{recommendation} {percentage}% of portfolio"
                    elif recommendation in ['BUY', 'SELL']:
                        return f"{recommendation} (percentage not specified)"
                    else:
                        return f"{recommendation} (no percentage needed)"
            except Exception:
                pass  # Fall back to text parsing
        
        # Fall back to text parsing (for backward compatibility)
        import re
        
        # Look for recommendation patterns
        patterns = [
            r'(BUY|SELL|HOLD)(?:\s+(\d+%))?(?:\s+(?:of\s+)?(?:portfolio|holdings|funds))?',
            r'(?:recommendation|recommend):\s*(BUY|SELL|HOLD)(?:\s+(\d+%))?',
            r'(?:action|decision):\s*(BUY|SELL|HOLD)(?:\s+(\d+%))?',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, analysis, re.IGNORECASE)
            if match:
                action = match.group(1).upper()
                percentage = match.group(2) if len(match.groups()) > 1 and match.group(2) else None
                
                if action in ['BUY', 'SELL'] and percentage:
                    return f"{action} {percentage} of portfolio"
                elif action in ['BUY', 'SELL']:
                    return f"{action} (percentage not specified)"
                else:
                    return f"{action} (no percentage needed)"
        
        return None
    
    def prompt_trade_reflection(self, trade_id: int, action: str, percentage: float, current_price: float):
        """
        Automatically generate reflection on a completed trade using ground truth data.
        
        Args:
            trade_id: ID of the trade execution record
            action: Trade action (BUY/SELL)
            percentage: Percentage used
            current_price: Price at time of trade
        """
        if not self.database_enabled or not self.db:
            return
        
        print("\n" + "="*60)
        print("📝 AUTO-GENERATING TRADE REFLECTION")
        print("="*60)
        print(f"Trade ID: {trade_id}")
        print(f"Action: {action} {percentage}% @ ${current_price:.6f}")
        print("-"*60)
        
        # Get trade from database
        trade = self.db.get_trade_by_id(trade_id)
        if not trade:
            print("⚠️  Trade not found in database")
            return
        
        # Check if ground truth already exists
        # sqlite3.Row doesn't support .get(), use dictionary-style access
        decision_correct = trade['decision_correct'] if 'decision_correct' in trade else None
        quality_label = trade['decision_quality_label'] if 'decision_quality_label' in trade else None
        quality_score = trade['decision_quality_score'] if 'decision_quality_score' in trade else None
        price_change_percent = None
        
        # If ground truth doesn't exist yet, calculate it
        if decision_correct is None or quality_label is None:
            from datetime import datetime as dt_class
            trade_timestamp_str = trade['timestamp'] if 'timestamp' in trade else None
            if trade_timestamp_str:
                try:
                    if isinstance(trade_timestamp_str, str):
                        trade_timestamp = dt_class.fromisoformat(trade_timestamp_str.replace('Z', '+00:00'))
                    else:
                        trade_timestamp = trade_timestamp_str
                    
                    print("📊 Calculating ground truth...")
                    ground_truth = self.calculate_trade_ground_truth(
                        trade_timestamp=trade_timestamp,
                        action=action,
                        trade_price=current_price,
                        evaluation_window_hours=6
                    )
                    
                    if ground_truth:
                        decision_correct = ground_truth.get('decision_correct')
                        quality_label = ground_truth.get('decision_quality_label', 'unknown')
                        quality_score = ground_truth.get('decision_quality_score', 0)
                        price_change_percent = ground_truth.get('price_change_percent', None)
                        price_at_trade = ground_truth.get('price_at_trade', current_price)
                        price_after_window = ground_truth.get('price_after_window', None)
                    else:
                        print("⚠️  Could not calculate ground truth")
                        return
                except Exception as e:
                    print(f"⚠️  Error calculating ground truth: {e}")
                    return
            else:
                print("⚠️  Trade timestamp not found")
                return
        else:
            # Ground truth exists, try to extract price change from existing reflection
            import re
            reflection_text = trade['reflection'] if 'reflection' in trade else ''
            if reflection_text:
                price_match = re.search(r'Price change:\s*([+-]?\d+\.?\d*)%', reflection_text)
                if price_match:
                    price_change_percent = float(price_match.group(1))
        
        # Generate automatic reflection based on granular quality labels (multi-class)
        # Use quality_label to determine the assessment, not binary decision_correct
        
        # Map quality labels to emoji and descriptive text
        quality_emoji_map = {
            'extremely_good': '🌟',
            'very_good': '✅',
            'moderately_good': '👍',
            'slightly_good': '👍',
            'slightly_bad': '⚠️',
            'moderately_bad': '⚠️',
            'very_bad': '❌',
            'extremely_bad': '❌'
        }
        
        # Determine overall sentiment from quality label
        if quality_label and 'good' in quality_label:
            decision_result_emoji = quality_emoji_map.get(quality_label, '✅')
            decision_sentiment = "successful"
        elif quality_label and 'bad' in quality_label:
            decision_result_emoji = quality_emoji_map.get(quality_label, '❌')
            decision_sentiment = "unsuccessful"
        else:
            decision_result_emoji = '⚠️'
            decision_sentiment = "neutral"
        
        # Generate action-specific context
        if action == 'HOLD':
            if quality_label and 'good' in quality_label:
                result_note = "good call (price dropped)"
            else:
                result_note = "missed opportunity or price increased"
        elif action == 'BUY':
            if quality_label and 'good' in quality_label:
                result_note = "profitable (price increased)"
            else:
                result_note = "unprofitable (price decreased)"
        elif action == 'SELL':
            if quality_label and 'good' in quality_label:
                result_note = "profitable (price decreased)"
            else:
                result_note = "unprofitable (price increased)"
        else:
            result_note = "unknown"
        
        # Get price change information (use from ground truth calculation or existing trade data)
        price_change_info = ""
        if price_change_percent is not None:
            price_change_info = f"Price change: {price_change_percent:.2f}%. "
        
        # Generate reflection text using granular quality label
        reflection = f"System-generated reflection: {decision_result_emoji} Quality: {quality_label} (score: {quality_score}). {price_change_info}Decision analysis: {action} {percentage}% at ${current_price:.6f} was {result_note}. Overall: {decision_sentiment}."
        
        # Update trade with automatic reflection
        try:
            self.db.update_trade_reflection(
                trade_id=trade_id,
                reflection=reflection,
                decision_correct=decision_correct,
                decision_quality_label=quality_label,
                decision_quality_score=quality_score
            )
            print(f"✅ Auto-generated reflection saved")
            print(f"   Quality: {quality_label} (score: {quality_score})")
            if price_change_percent is not None:
                print(f"   Price change: {price_change_percent:.2f}%")
        except Exception as e:
            print(f"⚠️  Failed to save reflection: {e}")
    
    def _execute_simulated_trade_no_api(self, action: str, percentage: float, analysis_id: Optional[int] = None) -> bool:
        """
        Execute a simulated trade when API credentials are not available.
        
        Args:
            action: Trade action ('BUY' or 'SELL')
            percentage: Percentage of portfolio/balance to use
            analysis_id: ID of the related analysis_results record
        
        Returns:
            True if trade was successfully saved, False otherwise
        """
        print("⚠️  No API credentials - simulating trade execution")
        
        # Try to get current price from market data
        current_price = 0.15  # Default fallback
        try:
            price_data = self.fetch_historical_price_at_timestamp(datetime.now())
            if price_data:
                current_price = price_data['close']
        except Exception as e:
            print(f"⚠️  Could not fetch current price: {e}")
            current_price = 0.15  # Fallback
        
        # Get current balances from database or use defaults
        try:
            if self.database_enabled and self.db:
                all_trades = self.db.get_all_trades()
                if all_trades and len(all_trades) > 0:
                    # Get the most recent trade (trades are ordered oldest first, so get last)
                    last_trade = all_trades[-1]
                    balance_usd_before = last_trade.get('balance_usd_after', 1000.0 if action == 'BUY' else 0.0)
                    balance_doge_before = last_trade.get('balance_doge_after', 
                                                         0.0 if action == 'BUY' else (1000.0 / current_price if current_price > 0 else 0.0))
                else:
                    # Default starting balances
                    balance_usd_before = 1000.0 if action == 'BUY' else 0.0
                    balance_doge_before = 0.0 if action == 'BUY' else (1000.0 / current_price if current_price > 0 else 0.0)
            else:
                # Default starting balances
                balance_usd_before = 1000.0 if action == 'BUY' else 0.0
                balance_doge_before = 0.0 if action == 'BUY' else (1000.0 / current_price if current_price > 0 else 0.0)
        except Exception as e:
            print(f"⚠️  Could not get balances from database: {e}")
            balance_usd_before = 1000.0 if action == 'BUY' else 0.0
            balance_doge_before = 0.0 if action == 'BUY' else (1000.0 / current_price if current_price > 0 else 0.0)
        
        # Simulate trade execution
        trade_result = self.simulate_trade_execution(
            action=action,
            percentage=percentage,
            current_price=current_price,
            analysis_id=analysis_id,
            balance_usd_before=balance_usd_before,
            balance_doge_before=balance_doge_before
        )
        
        if trade_result and trade_result[0]:
            trade_id = trade_result[0]
            print(f"✅ Simulated {action} trade saved to database (Trade ID: {trade_id})")
            
            # Prompt for reflection if trade was saved to database
            if trade_id:
                self.prompt_trade_reflection(trade_id, action, percentage, current_price)
            
            return True
        else:
            print("❌ Failed to save simulated trade")
            return False
    
    def execute_recommended_trade(self, analysis, analysis_id=None):
        """Execute trade based on AI recommendation and save to database."""
        if not self.trading_enabled:
            print("⚠️  Trading is disabled - cannot execute trades")
            return False
        
        # First try to get from JSON if available
        if self.latest_analysis_json:
            try:
                recommendation = self.latest_analysis_json.get('recommendation', '').upper()
                percentage = self.latest_analysis_json.get('percentage')
                
                if recommendation == 'BUY' and percentage is not None:
                    print(f"\n🤖 AI Recommendation: BUY {percentage}% of portfolio")
                    # Check if we have API credentials (trade_executor available)
                    if self.trade_executor is None:
                        # No API credentials - simulate the trade and save to database
                        return self._execute_simulated_trade_no_api('BUY', percentage, analysis_id)
                    
                    # Get balances before trade (real execution with API)
                    balance_usd_before = self.trade_executor.get_usd_balance()
                    balance_doge_before = self.trade_executor.get_dogecoin_balance()
                    current_price = self.trade_executor.get_current_price()
                    
                    # Execute trade
                    order_result = self.trade_executor.execute_trade('BUY', percentage)
                    
                    # Get balances after trade
                    balance_usd_after = self.trade_executor.get_usd_balance()
                    balance_doge_after = self.trade_executor.get_dogecoin_balance()
                    
                    # Save trade execution to database
                    trade_id = None
                    if self.database_enabled:
                        try:
                            trade_id = self.db.save_trade_execution(
                                action='BUY',
                                percentage=percentage,
                                order_result=order_result,
                                analysis_id=analysis_id,
                                current_price=current_price,
                                balance_usd_before=balance_usd_before,
                                balance_doge_before=balance_doge_before,
                                balance_usd_after=balance_usd_after,
                                balance_doge_after=balance_doge_after,
                                error_message=None if order_result else "Trade execution failed"
                            )
                        except Exception as e:
                            print(f"⚠️  Failed to save trade execution to database: {e}")
                    
                    # Prompt for reflection if trade was saved to database (even if execution failed)
                    if trade_id:
                        self.prompt_trade_reflection(trade_id, 'BUY', percentage, current_price)
                    
                    return order_result is not None
                elif recommendation == 'SELL' and percentage is not None:
                    print(f"\n🤖 AI Recommendation: SELL {percentage}% of holdings")
                    # Check if we have API credentials (trade_executor available)
                    if self.trade_executor is None:
                        # No API credentials - simulate the trade and save to database
                        return self._execute_simulated_trade_no_api('SELL', percentage, analysis_id)
                    
                    # Get balances before trade (real execution with API)
                    balance_usd_before = self.trade_executor.get_usd_balance()
                    balance_doge_before = self.trade_executor.get_dogecoin_balance()
                    current_price = self.trade_executor.get_current_price()
                    
                    # Execute trade
                    order_result = self.trade_executor.execute_trade('SELL', percentage)
                    
                    # Get balances after trade
                    balance_usd_after = self.trade_executor.get_usd_balance()
                    balance_doge_after = self.trade_executor.get_dogecoin_balance()
                    
                    # Save trade execution to database
                    trade_id = None
                    if self.database_enabled:
                        try:
                            trade_id = self.db.save_trade_execution(
                                action='SELL',
                                percentage=percentage,
                                order_result=order_result,
                                analysis_id=analysis_id,
                                current_price=current_price,
                                balance_usd_before=balance_usd_before,
                                balance_doge_before=balance_doge_before,
                                balance_usd_after=balance_usd_after,
                                balance_doge_after=balance_doge_after,
                                error_message=None if order_result else "Trade execution failed"
                            )
                        except Exception as e:
                            print(f"⚠️  Failed to save trade execution to database: {e}")
                    
                    # Prompt for reflection if trade was saved to database (even if execution failed)
                    if trade_id:
                        self.prompt_trade_reflection(trade_id, 'SELL', percentage, current_price)
                    
                    return order_result is not None
                else:
                    # Only print HOLD if recommendation is explicitly HOLD, not if it's missing/None
                    if recommendation == 'HOLD':
                        print("🤖 AI Recommendation: HOLD - No trade needed")
                    return True
            except Exception:
                return False
    
    def execute_manual_trade(self, action, percentage):
        """Manually execute a trade regardless of AI recommendation.
        
        Args:
            action: 'BUY' or 'SELL'
            percentage: Percentage of balance to trade (0-100)
        
        Returns:
            bool: True if trade was executed successfully, False otherwise
        """
        if not self.trading_enabled:
            print("⚠️  Trading is disabled - cannot execute trades")
            return False
        
        if self.trade_executor is None:
            print("⚠️  No API credentials available - cannot execute real trades")
            return False
        
        if action.upper() not in ['BUY', 'SELL']:
            print(f"❌ Invalid action: {action}. Must be 'BUY' or 'SELL'")
            return False
        
        if not (0 < percentage <= 100):
            print(f"❌ Invalid percentage: {percentage}. Must be between 0 and 100")
            return False
        
        print(f"\n🔧 MANUAL TRADE EXECUTION")
        print("=" * 50)
        print(f"Action: {action.upper()}")
        print(f"Percentage: {percentage}%")
        
        # Get balances
        balance_usd_before = self.trade_executor.get_usd_balance()
        balance_doge_before = self.trade_executor.get_dogecoin_balance()
        current_price = self.trade_executor.get_current_price()
        
        if balance_usd_before is None or balance_doge_before is None:
            print("❌ Unable to get account balances")
            return False
        
        if current_price is None:
            print("❌ Unable to get current DOGE price")
            return False
        
        # Execute trade
        order_result = self.trade_executor.execute_trade(action.upper(), percentage)
        
        # Get balances after trade
        balance_usd_after = self.trade_executor.get_usd_balance()
        balance_doge_after = self.trade_executor.get_dogecoin_balance()
        
        # Save trade execution to database
        trade_id = None
        if self.database_enabled:
            try:
                trade_id = self.db.save_trade_execution(
                    action=action.upper(),
                    percentage=percentage,
                    order_result=order_result,
                    analysis_id=None,  # Manual trade, no analysis ID
                    current_price=current_price,
                    balance_usd_before=balance_usd_before,
                    balance_doge_before=balance_doge_before,
                    balance_usd_after=balance_usd_after,
                    balance_doge_after=balance_doge_after,
                    error_message=None if order_result else "Trade execution failed"
                )
                print(f"✅ Trade execution saved to database (ID: {trade_id})")
            except Exception as e:
                print(f"⚠️  Failed to save trade execution to database: {e}")
        
        if order_result:
            print("✅ Manual trade executed successfully!")
            return True
        else:
            print("❌ Manual trade execution failed")
            return False
        
    
    def run_analysis(self, skip_chart_capture=False, skip_news_data=False, simulation_date=None,
                     current_usd_balance=None, current_doge_balance=None):
        """Run the complete Dogecoin analysis with comprehensive data.
        
        Args:
            skip_chart_capture: If True, skip chart screenshot capture (useful for simulations)
            skip_news_data: If True, skip news data fetching and sentiment analysis (useful for simulations)
            simulation_date: Optional datetime for historical simulation
            current_usd_balance: Optional current USD balance (for simulation use)
            current_doge_balance: Optional current DOGE balance (for simulation use)
        """
        print("🐕 Fetching comprehensive Dogecoin data from Coinbase...")
        
        # Use simulation_date as the reference point for all data fetching
        if simulation_date:
            print(f"📅 Using simulation date: {simulation_date.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Fetch all data sources with simulation_date
        print("📈 Fetching 30-day historical data...")
        df_30d = self.fetch_dogecoin_data(30, end_date=simulation_date)
        
        print("⏰ Fetching 24-hour detailed data...")
        df_24h = self.fetch_24h_ohlcv_data(end_date=simulation_date)
        
        print("📚 Fetching order book data...")
        order_book = self.fetch_order_book_data(target_date=simulation_date)
        
        print("💼 Getting investment status...")
        try:
            investment_status = self.get_investment_status(target_date=simulation_date,
                                                            current_usd_balance=current_usd_balance,
                                                            current_doge_balance=current_doge_balance)
        except ValueError as e:
            # Authentication error - stop execution
            print(f"\n{'='*70}")
            print("❌ AUTHENTICATION ERROR - STOPPING EXECUTION")
            print(f"{'='*70}")
            print(str(e))
            print(f"{'='*70}\n")
            raise  # Re-raise to stop execution
        
        print("📊 Getting Fear and Greed Index...")
        if simulation_date:
            # Fetch historical Fear & Greed Index for simulation
            print(f"   Fetching historical data for {simulation_date.strftime('%Y-%m-%d %H:%M')}...")
            fear_greed_data = self.fetch_fear_and_greed_index(limit=365, target_date=simulation_date)
        else:
            # Fetch current Fear & Greed Index
            fear_greed_data = self.fetch_fear_and_greed_index(5)
        
        # Skip news data if requested (useful for simulations)
        news_data = None
        news_sentiment = None
        if not skip_news_data:
            print("📰 Fetching cryptocurrency news...")
            news_data = self.fetch_crypto_news(10)
        if news_data:
            print("🔍 Analyzing news sentiment...")
            news_sentiment = self.analyze_news_sentiment(news_data)
        else:
            print("⏭️  Skipping news data for simulation")
        
        if df_30d is None:
            print("❌ Failed to fetch Dogecoin data")
            return
        
        print(f"✅ Successfully fetched {len(df_30d)} days of Dogecoin data")
        if df_24h is not None:
            print(f"✅ Successfully fetched {len(df_24h)} hours of 24h data")
        if order_book:
            print("✅ Successfully fetched order book data")
        if investment_status:
            print("✅ Successfully retrieved investment status")
        if fear_greed_data:
            print("✅ Successfully retrieved Fear and Greed Index")
        if news_data:
            print("✅ Successfully retrieved cryptocurrency news")
        if news_sentiment:
            print("✅ Successfully analyzed news sentiment")
        
        # Prepare comprehensive data
        print("📊 Preparing comprehensive data...")
        comprehensive_data = self.prepare_comprehensive_data(df_30d, df_24h, order_book, investment_status, fear_greed_data, news_data, news_sentiment)
        
        # Save market data to database
        market_data_id = None
        if comprehensive_data and self.database_enabled:
            try:
                market_data_id = self.db.save_market_data(comprehensive_data)
            except Exception as e:
                print(f"⚠️  Failed to save market data to database: {e}")
        
        if comprehensive_data:
            print(f"Current DOGE Price: ${comprehensive_data['current_price']}")
            print(f"30-day Change: {comprehensive_data['price_change_percent']}%")
            print(f"30-day Volatility: {comprehensive_data['volatility_30d']}%")
            print(f"24-hour Volatility: {comprehensive_data['volatility_24h']}%")
            
            # Show investment status if available
            if comprehensive_data['investment_status']:
                portfolio_value = comprehensive_data['investment_status'].get('portfolio_value', 0)
                usd_pct = comprehensive_data['investment_status'].get('current_allocation', {}).get('usd_percentage', 0)
                doge_pct = comprehensive_data['investment_status'].get('current_allocation', {}).get('doge_percentage', 0)
                print(f"Portfolio Value: ${portfolio_value:.2f}")
                print(f"Current Allocation: {usd_pct:.1f}% USD, {doge_pct:.1f}% DOGE")
        
        # Display comprehensive summary
        self.display_comprehensive_summary(comprehensive_data)
        
        # Get ChatGPT analysis
        print("🤖 Getting comprehensive AI analysis from ChatGPT...")
        analysis = self.analyze_with_chatgpt(comprehensive_data, skip_chart_capture=skip_chart_capture)
        
        # Save analysis result to database
        analysis_id = None
        if self.latest_analysis_json and self.database_enabled:
            try:
                analysis_id = self.db.save_analysis_result(
                    self.latest_analysis_json,
                    market_data_id=market_data_id,
                    chart_image_path=self.latest_chart_image_path
                )
            except Exception as e:
                print(f"⚠️  Failed to save analysis result to database: {e}")
        
        # Parse and highlight percentage recommendations
        highlighted_analysis = self.highlight_percentage_recommendations(analysis)
        
        # Extract key recommendation for summary
        recommendation_summary = self.extract_recommendation_summary(analysis)
        
        print("\n" + "="*60)
        print("🎯 DOGECOIN INVESTMENT ANALYSIS")
        print("="*60)
        if recommendation_summary:
            print(f"📋 QUICK SUMMARY: {recommendation_summary}")
            print("-" * 60)
        print(highlighted_analysis)
        print("="*60)
        
        # Auto-execute trade without confirmation
        if self.trading_enabled:
            print("\n💼 TRADE EXECUTION")
            print("-" * 30)
            trade_result = self.execute_recommended_trade(analysis, analysis_id=analysis_id)
            if trade_result:
                print("✅ Trade execution completed")
            else:
                print("❌ Trade execution failed")
        
        return analysis
    
    def review_trade_reflections(self):
        """
        Review past trades and add reflections to trades that don't have them yet.
        Useful for self-improvement and self-supervised learning.
        """
        if not self.database_enabled or not self.db:
            print("⚠️  Database not enabled - cannot review trade reflections")
            return
        
        print("\n" + "="*60)
        print("📝 TRADE REFLECTION REVIEW")
        print("="*60)
        
        # Get trades needing reflection
        trades_needing_reflection = self.db.get_trades_needing_reflection(limit=10)
        
        if not trades_needing_reflection:
            print("✅ All recent trades have reflections!")
            return
        
        print(f"\nFound {len(trades_needing_reflection)} trade(s) without reflections:")
        print("-"*60)
        
        for trade in trades_needing_reflection:
            trade_id = trade['id']
            timestamp = trade['timestamp']
            action = trade['action']
            percentage = trade['percentage']
            current_price = trade['current_price']
            success = "✅" if trade['success'] else "❌"
            
            print(f"{success} Trade ID: {trade_id}")
            print(f"   Date: {timestamp}")
            print(f"   Action: {action} {percentage}% @ ${current_price:.6f if current_price else 'N/A'}")
            print("-"*60)
        
        print("\nWould you like to add reflections to any of these trades?")
        review = 'q'  # Auto-skip reflection review for non-interactive mode
        
        if review == 'q':
            return
        
        if review == 'all':
            trades_to_review = trades_needing_reflection
        else:
            try:
                trade_id = int(review)
                trade = self.db.get_trade_by_id(trade_id)
                if trade and (not trade['reflection'] or trade['reflection'] == ''):
                    trades_to_review = [trade]
                else:
                    print(f"⚠️  Trade ID {trade_id} not found or already has a reflection")
                    return
            except ValueError:
                print("⚠️  Invalid Trade ID")
                return
        
        for trade in trades_to_review:
            trade_id = trade['id']
            action = trade['action']
            percentage = trade['percentage']
            current_price = trade['current_price']
            
            print(f"\n{'='*60}")
            print(f"Reviewing Trade ID: {trade_id}")
            print(f"Action: {action} {percentage}% @ ${current_price:.6f if current_price else 'N/A'}")
            print(f"{'='*60}")
            
            # Auto-skip decision input for non-interactive mode
            decision_input = 'skip'  # Skip decision input
            decision_correct = None
            if decision_input == 'y':
                decision_correct = True
            elif decision_input == 'n':
                decision_correct = False
            
            # Auto-skip reflection text input for non-interactive mode
            reflection_lines = []  # Skip input(), just use empty reflection
            
            reflection = '\n'.join(reflection_lines) if reflection_lines else None
            
            if reflection or decision_correct is not None:
                try:
                    self.db.update_trade_reflection(
                        trade_id=trade_id,
                        reflection=reflection,
                        decision_correct=decision_correct
                    )
                    print(f"✅ Reflection saved for Trade ID {trade_id}")
                except Exception as e:
                    print(f"⚠️  Failed to save reflection for Trade ID {trade_id}: {e}")
            else:
                print("⏭️  Reflection skipped")
        
        print("\n✅ Trade reflection review completed")
    
    def get_portfolio_value_at_date(self, target_date, all_trades=None):
        """
        Calculate portfolio value at a specific date by replaying trades up to that date.
        
        Args:
            target_date: Date to calculate portfolio value for
            all_trades: Optional list of all trades (if None, will fetch from database)
        
        Returns:
            Tuple of (usd_balance, doge_balance, portfolio_value, price) or None if error
        """
        if not self.database_enabled or not self.db:
            return None
        
        from datetime import datetime as dt_class
        if isinstance(target_date, str):
            target_dt = dt_class.fromisoformat(target_date.replace('Z', '+00:00'))
        else:
            target_dt = target_date
        
        # Start with initial balances: $500 USD + $500 worth of DOGE
        initial_usd_value = 500.0
        
        # Get price at the start (first simulation date or reference date)
        # For simplicity, use a reference point - if we have trades, use first trade date
        if all_trades and len(all_trades) > 0:
            first_trade = all_trades[0]
            first_trade_timestamp = dt_class.fromisoformat(first_trade['timestamp'].replace('Z', '+00:00')) if isinstance(first_trade['timestamp'], str) else first_trade['timestamp']
            initial_price_data = self.fetch_historical_price_at_timestamp(first_trade_timestamp)
        else:
            initial_price_data = self.fetch_historical_price_at_timestamp(target_dt - timedelta(days=365))
        
        if initial_price_data:
            initial_price = initial_price_data['close']
            initial_doge_balance = (500.0 / initial_price) if initial_price > 0 else 0.0
        else:
            initial_price = 0.0
            initial_doge_balance = 0.0
        
        usd_balance = initial_usd_value
        doge_balance = initial_doge_balance
        
        # Replay trades up to target_date
        if all_trades is None:
            all_trades = self.db.get_all_trades()
        
        for trade in all_trades:
            trade_timestamp = dt_class.fromisoformat(trade['timestamp'].replace('Z', '+00:00')) if isinstance(trade['timestamp'], str) else trade['timestamp']
            if trade_timestamp > target_dt:
                continue  # Skip trades after target_date
            
            action = trade['action']
            percentage = trade['percentage'] or 0.0
            trade_price = trade['current_price'] or 0.0
            
            if action == 'BUY' and trade_price > 0:
                usd_to_spend = usd_balance * (percentage / 100)
                doge_to_buy = usd_to_spend / trade_price
                usd_balance -= usd_to_spend
                doge_balance += doge_to_buy
            elif action == 'SELL' and trade_price > 0:
                doge_to_sell = doge_balance * (percentage / 100)
                usd_from_sale = doge_to_sell * trade_price
                doge_balance -= doge_to_sell
                usd_balance += usd_from_sale
        
        # Get price at target_date
        price_data = self.fetch_historical_price_at_timestamp(target_dt)
        price = price_data['close'] if price_data else 0.0
        
        if price > 0:
            portfolio_value = usd_balance + (doge_balance * price)
        else:
            portfolio_value = usd_balance
        
        return (usd_balance, doge_balance, portfolio_value, price)
    
    def calculate_portfolio_performance_periods(self, target_date=None, current_usd_balance=None, current_doge_balance=None):
        """
        Calculate portfolio performance for multiple time periods.
        
        Args:
            target_date: Optional datetime for historical simulation
            current_usd_balance: Current USD balance
            current_doge_balance: Current DOGE balance
        
        Returns:
            Dictionary with performance metrics for different periods
        """
        performance = {}
        
        if not self.database_enabled or not self.db:
            return performance
        
        # Use current date or target_date as reference
        from datetime import datetime, timedelta
        reference_date = target_date if target_date else datetime.now()
        
        # Get current portfolio value
        if current_usd_balance is not None and current_doge_balance is not None:
            current_price_data = self.fetch_historical_price_at_timestamp(reference_date)
            current_price = current_price_data['close'] if current_price_data else 0.0
            if current_price > 0:
                current_portfolio_value = current_usd_balance + (current_doge_balance * current_price)
            else:
                current_portfolio_value = current_usd_balance
        else:
            # Try to get from database
            result = self.get_portfolio_value_at_date(reference_date)
            if result:
                _, _, current_portfolio_value, _ = result
            else:
                return performance
        
        # Get all trades once for efficiency
        all_trades = self.db.get_all_trades()
        
        # Calculate initial portfolio value (starting balance)
        # Initial: $500 USD + $500 worth of DOGE
        initial_usd_value = 500.0
        # Get first trade date - this is when simulation actually started
        from datetime import datetime as dt_class
        first_trade_timestamp = None
        if all_trades and len(all_trades) > 0:
            first_trade = all_trades[0]
            first_trade_timestamp = dt_class.fromisoformat(first_trade['timestamp'].replace('Z', '+00:00')) if isinstance(first_trade['timestamp'], str) else first_trade['timestamp']
            initial_price_data = self.fetch_historical_price_at_timestamp(first_trade_timestamp)
        else:
            # No trades yet, use reference date
            initial_price_data = self.fetch_historical_price_at_timestamp(reference_date)
            first_trade_timestamp = reference_date
        
        if initial_price_data:
            initial_price = initial_price_data['close']
            initial_doge_balance = (500.0 / initial_price) if initial_price > 0 else 0.0
            initial_portfolio_value = initial_usd_value + (initial_doge_balance * initial_price)
        else:
            initial_portfolio_value = 1000.0  # Default: $500 USD + $500 DOGE value
        
        # Calculate days since first trade (simulation duration)
        if first_trade_timestamp:
            days_since_first_trade = (reference_date - first_trade_timestamp).total_seconds() / 86400
        else:
            days_since_first_trade = 0
        
        # Calculate performance for each period
        periods = {
            '1d': 1,
            '5d': 5,
            '1m': 30,
            '3m': 90,
            '6m': 180,
            'ytd': None,  # Year to date - calculate separately
            '1y': 365,
            'entire': None  # Entire history - use initial value
        }
        
        for period_name, days_back in periods.items():
            try:
                # Initialize ytd_equals_entire flag
                ytd_equals_entire = False
                
                if period_name == 'ytd':
                    # Year to date: from Jan 1st of current year
                    year_start = datetime(reference_date.year, 1, 1)
                    # Use first trade date if it's after year start (simulation started after Jan 1)
                    if first_trade_timestamp and first_trade_timestamp > year_start:
                        # Simulation started after Jan 1, so YTD = entire simulation
                        # Mark it to use same calculation as 'entire'
                        period_start_date = first_trade_timestamp
                        # Set a flag to treat YTD as entire when they're the same
                        ytd_equals_entire = True
                    else:
                        # Simulation started before or on Jan 1, use year start
                        period_start_date = year_start
                        ytd_equals_entire = False
                        # But if we don't have data before first trade, use first trade date
                        if first_trade_timestamp and period_start_date < first_trade_timestamp:
                            # Skip YTD if simulation started after Jan 1 and we don't have earlier data
                            continue
                elif period_name == 'entire':
                    # Entire history - use initial portfolio value at first trade date
                    # This is always valid since it's from the simulation start
                    # Set period_start_date to first_trade_timestamp for consistency
                    if first_trade_timestamp:
                        period_start_date = first_trade_timestamp
                    else:
                        period_start_date = reference_date
                else:
                    # Calculate start date for the period (days_back from reference_date)
                    period_start_date = reference_date - timedelta(days=days_back)
                    
                    # If period start is before first trade, skip this period
                    # We don't have portfolio data before the simulation started
                    # But allow periods that are within the simulation duration
                    if first_trade_timestamp and period_start_date < first_trade_timestamp:
                        # Period start is before simulation started
                        # Check if we have enough time elapsed to calculate this period
                        # Use total seconds to avoid truncation issues with .days
                        time_elapsed = (reference_date - first_trade_timestamp).total_seconds()
                        period_duration_seconds = days_back * 86400  # Convert days to seconds
                        
                        if period_duration_seconds > time_elapsed:
                            # Period is longer than available data - skip it
                            continue
                        # For periods shorter than available data but start date is before first trade,
                        # we can still calculate by using first_trade_timestamp as the start
                        # This allows 1d, 5d periods to show even if calculated start is before first trade
                        period_start_date = first_trade_timestamp
                
                # Calculate trading performance (comparing actual portfolio vs buy-and-hold)
                # This measures the value added/lost by trading decisions, not just price movements
                
                # Get portfolio value at start of period (actual portfolio from trading)
                if period_name == 'entire' or (period_name == 'ytd' and ytd_equals_entire):
                    # Entire history - use initial portfolio value at first trade date
                    # YTD = Entire when simulation started after Jan 1
                    period_start_portfolio_value = initial_portfolio_value
                else:
                    # Get portfolio value at start of period (actual portfolio)
                    result = self.get_portfolio_value_at_date(period_start_date, all_trades)
                    if result:
                        _, _, period_start_portfolio_value, _ = result
                    else:
                        # Fallback: approximate using current balances and start price
                        start_price_data = self.fetch_historical_price_at_timestamp(period_start_date)
                        if start_price_data:
                            start_price = start_price_data['close']
                            period_start_portfolio_value = current_usd_balance + (current_doge_balance * start_price)
                        else:
                            continue
                
                # Calculate buy-and-hold portfolio value at current date
                # Buy-and-hold: initial USD + initial DOGE * current price
                buy_hold_current_value = initial_usd_value + (initial_doge_balance * current_price)
                
                # Calculate trading performance
                # Trading performance = (actual portfolio - buy-and-hold portfolio) / buy-and-hold portfolio * 100
                # This measures the value added/lost by trading decisions vs just holding
                if period_name == 'entire' or (period_name == 'ytd' and ytd_equals_entire):
                    # For entire period, compare current actual portfolio vs buy-and-hold
                    # YTD = Entire when simulation started after Jan 1, so use EXACT same calculation
                    # Both use initial portfolio value and compare against buy-and-hold at current price
                    trading_value_added = current_portfolio_value - buy_hold_current_value
                    if buy_hold_current_value > 0:
                        period_performance = (trading_value_added / buy_hold_current_value) * 100
                    else:
                        period_performance = 0.0
                else:
                    # For specific periods, we need buy-and-hold at start of period
                    # Calculate buy-and-hold portfolio value at start of period
                    # Buy-and-hold: initial USD + initial DOGE * price at period start
                    start_price_data = self.fetch_historical_price_at_timestamp(period_start_date)
                    if not start_price_data:
                        start_price_data = self.fetch_historical_price_at_timestamp(first_trade_timestamp) if first_trade_timestamp else None
                    
                    if start_price_data:
                        start_price = start_price_data['close']
                        # Buy-and-hold portfolio: initial $500 USD + initial $500 worth of DOGE
                        buy_hold_start_value = initial_usd_value + (initial_doge_balance * start_price)
                    else:
                        buy_hold_start_value = initial_portfolio_value
                    
                    # For specific periods, compare portfolio value changes
                    # Actual portfolio change
                    actual_change = current_portfolio_value - period_start_portfolio_value
                    # Buy-and-hold change
                    buy_hold_change = buy_hold_current_value - buy_hold_start_value
                    # Trading performance = difference between actual and buy-and-hold
                    trading_value_added = actual_change - buy_hold_change
                    # Performance as percentage of buy-and-hold start value
                    if buy_hold_start_value > 0:
                        period_performance = (trading_value_added / buy_hold_start_value) * 100
                    else:
                        period_performance = 0.0
                
                performance[period_name] = {
                    'value': round(period_performance, 2),
                    'start_value': round(period_start_portfolio_value, 2),
                    'current_value': round(current_portfolio_value, 2),
                    'buy_hold_value': round(buy_hold_current_value, 2)  # Add buy-and-hold value for reference
                }
            except Exception as e:
                print(f"⚠️  Error calculating {period_name} performance: {e}")
                import traceback
                traceback.print_exc()
                continue
        
        # Debug: Print performance dict if it's not empty
        if not performance:
            print(f"⚠️  No performance metrics calculated. Reference date: {reference_date}, First trade: {first_trade_timestamp}")
        
        return performance
    
    def calculate_trading_performance(self, days: int = 7) -> float:
        """
        Calculate trading performance percentage based on trades in the database.
        Similar to the reference code, calculates return based on initial vs final portfolio value.
        
        Args:
            days: Number of days to look back (default: 7 days)
        
        Returns:
            Performance percentage (positive = profit, negative = loss)
        """
        if not self.database_enabled or not self.db:
            print("⚠️  Database not enabled - cannot calculate performance")
            return 0.0
        
        # Get all trades from the last N days
        trades = self.db.get_all_trades(days=days)
        
        if not trades or len(trades) == 0:
            print(f"⚠️  No trades found in the last {days} days")
            return 0.0
        
        # Sort by timestamp (oldest first)
        trades_sorted = sorted(trades, key=lambda x: x['timestamp'])
        
        if len(trades_sorted) < 2:
            print(f"⚠️  Not enough trades to calculate performance (need at least 2 trades)")
            return 0.0
        
        # Get initial balance (from first trade)
        first_trade = trades_sorted[0]
        initial_usd = first_trade['balance_usd_before'] or 0.0
        initial_doge = first_trade['balance_doge_before'] or 0.0
        initial_price = first_trade['current_price'] or 0.0
        
        # Calculate initial portfolio value
        if initial_price > 0:
            initial_portfolio_value = initial_usd + (initial_doge * initial_price)
        else:
            initial_portfolio_value = initial_usd + initial_doge
        
        # Get final balance (from last trade)
        last_trade = trades_sorted[-1]
        final_usd = last_trade['balance_usd_after'] or last_trade['balance_usd_before'] or 0.0
        final_doge = last_trade['balance_doge_after'] or last_trade['balance_doge_before'] or 0.0
        final_price = last_trade['current_price'] or initial_price
        
        # If we don't have final price, use current market price
        if final_price == 0 and self.trade_executor:
            try:
                final_price = self.trade_executor.get_current_price()
            except:
                final_price = initial_price
        
        # Calculate final portfolio value
        if final_price > 0:
            final_portfolio_value = final_usd + (final_doge * final_price)
        else:
            final_portfolio_value = final_usd + final_doge
        
        # Calculate performance percentage
        if initial_portfolio_value > 0:
            performance = ((final_portfolio_value - initial_portfolio_value) / initial_portfolio_value) * 100
        else:
            performance = 0.0
        
        return performance
    
    def generate_ai_reflection(self, days: int = 7) -> str:
        """
        Generate AI-powered reflection on trading performance using OpenAI.
        Based on the reference code pattern.
        
        Args:
            days: Number of days to analyze (default: 7 days)
        
        Returns:
            AI-generated reflection text
        """
        if not self.database_enabled or not self.db:
            return "⚠️  Database not enabled - cannot generate reflection"
        
        if not self.openai_api_key:
            return "⚠️  OpenAI API key not available - cannot generate reflection"
        
        # Get all trades from the last N days
        trades = self.db.get_all_trades(days=days)
        
        if not trades or len(trades) == 0:
            return f"⚠️  No trades found in the last {days} days to analyze"
        
        # Convert trades to DataFrame-like JSON for analysis
        trades_data = []
        for trade in trades:
            trades_data.append({
                'id': trade['id'],
                'timestamp': trade['timestamp'],
                'action': trade['action'],
                'percentage': trade['percentage'],
                'current_price': trade['current_price'],
                'balance_usd_before': trade['balance_usd_before'],
                'balance_doge_before': trade['balance_doge_before'],
                'balance_usd_after': trade['balance_usd_after'],
                'balance_doge_after': trade['balance_doge_after'],
                'success': bool(trade['success']),
                'decision_correct': bool(trade['decision_correct']) if trade['decision_correct'] is not None else None,
                'decision_quality_label': trade.get('decision_quality_label') or 'unknown',
                'decision_quality_score': trade.get('decision_quality_score') or 0,
                'reflection': trade['reflection']
            })
        
        # Calculate performance
        performance = self.calculate_trading_performance(days=days)
        
        # Prepare statistics with granular quality analysis
        quality_counts = {}
        quality_scores = []
        for trade in trades_data:
            quality_label = trade.get('decision_quality_label') or 'unknown'
            quality_score = trade.get('decision_quality_score') or 0
            
            if quality_label not in quality_counts:
                quality_counts[quality_label] = 0
            quality_counts[quality_label] += 1
            
            if quality_score is not None and isinstance(quality_score, (int, float)):
                quality_scores.append(quality_score)
        
        # Calculate average quality score
        avg_quality_score = sum(quality_scores) / len(quality_scores) if quality_scores else 0
        
        # Group by quality categories
        extremely_good_count = quality_counts.get('extremely_good', 0)
        very_good_count = quality_counts.get('very_good', 0)
        moderately_good_count = quality_counts.get('moderately_good', 0)
        slightly_good_count = quality_counts.get('slightly_good', 0)
        slightly_bad_count = quality_counts.get('slightly_bad', 0)
        moderately_bad_count = quality_counts.get('moderately_bad', 0)
        very_bad_count = quality_counts.get('very_bad', 0)
        extremely_bad_count = quality_counts.get('extremely_bad', 0)
        
        stats = {
            'total_trades': len(trades_data),
            'correct_decisions': len([t for t in trades_data if t['decision_correct'] is True]),
            'incorrect_decisions': len([t for t in trades_data if t['decision_correct'] is False]),
            'average_quality_score': round(avg_quality_score, 2),
            'quality_distribution': {
                'extremely_good': extremely_good_count,
                'very_good': very_good_count,
                'moderately_good': moderately_good_count,
                'slightly_good': slightly_good_count,
                'slightly_bad': slightly_bad_count,
                'moderately_bad': moderately_bad_count,
                'very_bad': very_bad_count,
                'extremely_bad': extremely_bad_count
            },
            'excellent_performance': extremely_good_count + very_good_count,
            'good_performance': moderately_good_count + slightly_good_count,
            'poor_performance': slightly_bad_count + moderately_bad_count,
            'terrible_performance': very_bad_count + extremely_bad_count
        }
        
        # Get current market data summary
        current_market_data = {
            'current_price': self.trade_executor.get_current_price() if self.trade_executor else None,
            'total_trades': len(trades_data),
            'buy_trades': len([t for t in trades_data if t['action'] == 'BUY']),
            'sell_trades': len([t for t in trades_data if t['action'] == 'SELL']),
            'hold_trades': len([t for t in trades_data if t['action'] == 'HOLD']),
            'correct_decisions': len([t for t in trades_data if t['decision_correct'] is True]),
            'incorrect_decisions': len([t for t in trades_data if t['decision_correct'] is False])
        }
        
        # Generate reflection using OpenAI
        try:
            response = openai.ChatCompletion.create(
                model="gpt-4o-2024-08-06",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an AI trading assistant tasked with analyzing recent trading performance and current market conditions to generate insights and improvements for future trading decisions."
                    },
                    {
                        "role": "user",
                        "content": f"""
Recent trading data:
{json.dumps(trades_data, indent=2, default=str)}

Current market data:
{json.dumps(current_market_data, indent=2, default=str)}

Overall performance in the last {days} days: {performance:.2f}%

Trading Statistics:
- Total trades: {stats['total_trades']}
- Correct decisions: {stats['correct_decisions']}
- Incorrect decisions: {stats['incorrect_decisions']}
- Average quality score: {stats['average_quality_score']} (scale: -4 to 4)

Quality Distribution:
- Extremely good: {stats['quality_distribution']['extremely_good']} trades
- Very good: {stats['quality_distribution']['very_good']} trades
- Moderately good: {stats['quality_distribution']['moderately_good']} trades
- Slightly good: {stats['quality_distribution']['slightly_good']} trades
- Slightly bad: {stats['quality_distribution']['slightly_bad']} trades
- Moderately bad: {stats['quality_distribution']['moderately_bad']} trades
- Very bad: {stats['quality_distribution']['very_bad']} trades
- Extremely bad: {stats['quality_distribution']['extremely_bad']} trades

Performance Summary:
- Excellent (extremely/very good): {stats['excellent_performance']} trades
- Good (moderately/slightly good): {stats['good_performance']} trades
- Poor (slightly/moderately bad): {stats['poor_performance']} trades
- Terrible (very/extremely bad): {stats['terrible_performance']} trades

Please analyze this data and provide:
1. A detailed reflection on the recent trading decisions using the granular quality scores
2. Insights on what worked extremely well (extremely_good/very_good) and what went extremely wrong (extremely_bad/very_bad)
3. Suggestions for improvement, especially focusing on reducing extremely_bad and very_bad decisions
4. Any patterns or trends you notice in the quality distribution
5. Analysis of decision quality: Are we making excellent decisions (score 3-4) or settling for mediocre ones (score 1-2)?
6. Recommendations for improving average quality score from {stats['average_quality_score']} to higher values

Note: Quality scores range from -4 (extremely bad) to +4 (extremely good). Analyze the distribution carefully.

Limit your response to 300 words or less.
"""
                    }
                ]
            )
            
            if hasattr(response, 'choices') and len(response.choices) > 0:
                return response.choices[0].message.content
            else:
                return "⚠️  Unexpected response format from OpenAI"
        
        except Exception as e:
            return f"⚠️  Error generating AI reflection: {e}"
    
    def analyze_trading_performance(self, days: int = 7):
        """
        Analyze trading performance and generate comprehensive reflection.
        Combines performance calculation and AI reflection.
        
        Args:
            days: Number of days to analyze (default: 7 days)
        """
        if not self.database_enabled or not self.db:
            print("⚠️  Database not enabled - cannot analyze performance")
            return
        
        print("\n" + "="*70)
        print("📊 TRADING PERFORMANCE ANALYSIS")
        print("="*70)
        print(f"Analyzing trades from the last {days} days...")
        print("-"*70)
        
        # Get all trades
        trades = self.db.get_all_trades(days=days)
        
        if not trades or len(trades) == 0:
            print(f"⚠️  No trades found in the last {days} days")
            return
        
        print(f"\n📈 Found {len(trades)} trades:")
        buy_count = len([t for t in trades if t['action'] == 'BUY'])
        sell_count = len([t for t in trades if t['action'] == 'SELL'])
        hold_count = len([t for t in trades if t['action'] == 'HOLD'])
        
        print(f"   BUY: {buy_count}")
        print(f"   SELL: {sell_count}")
        print(f"   HOLD: {hold_count}")
        
        # Calculate performance
        print(f"\n💰 Calculating performance...")
        performance = self.calculate_trading_performance(days=days)
        
        performance_symbol = "📈" if performance > 0 else "📉" if performance < 0 else "➡️"
        print(f"{performance_symbol} Performance: {performance:.2f}%")
        
        if performance > 0:
            print(f"   ✅ Profitable! Portfolio increased by {performance:.2f}%")
        elif performance < 0:
            print(f"   ❌ Loss of {abs(performance):.2f}%")
        else:
            print(f"   ➡️  Break-even (0% change)")
        
        # Generate AI reflection
        print(f"\n🤖 Generating AI reflection...")
        reflection = self.generate_ai_reflection(days=days)
        
        print("\n" + "="*70)
        print("💭 AI-GENERATED REFLECTION")
        print("="*70)
        print(reflection)
        print("="*70)
        
        print(f"\n✅ Performance analysis completed")
    
    def generate_training_dataset(self, days: int = 7, output_format: str = 'sqlite') -> str:
        """
        Generate a training dataset for self-supervised learning from simulation results.
        Saves to SQLite database format.
        
        Args:
            days: Number of days to include in the dataset (default: 7 days)
            output_format: Output format ('sqlite', 'csv', or 'json', default: 'sqlite')
        
        Returns:
            Path to the generated dataset file
        """
        if not self.database_enabled or not self.db:
            print("⚠️  Database not enabled - cannot generate training dataset")
            return None
        
        print("\n" + "="*70)
        print("📊 GENERATING TRAINING DATASET FOR SELF-SUPERVISED LEARNING")
        print("="*70)
        print(f"Extracting data from the last {days} days...")
        print("-"*70)
        
        # Get all trades with their related data
        trades = self.db.get_all_trades(days=days)
        
        if not trades or len(trades) == 0:
            print(f"⚠️  No trades found in the last {days} days")
            return None
        
        print(f"📈 Found {len(trades)} trades to process...")
        
        # Prepare dataset records
        dataset_records = []
        
        for trade in trades:
            try:
                # Get related market data and analysis
                market_data = None
                analysis_result = None
                
                if trade['analysis_id']:
                    analysis_result = self.db.get_analysis_by_id(trade['analysis_id'])
                    if analysis_result and analysis_result['market_data_id']:
                        market_data = self.db.get_market_data_by_id(analysis_result['market_data_id'])
                
                # Extract features from market data
                features = {}
                
                # Basic trade features
                features['timestamp'] = trade['timestamp']
                features['trade_id'] = trade['id']
                features['action'] = trade['action']  # BUY/SELL/HOLD
                features['percentage'] = trade['percentage'] or 0.0
                features['current_price'] = trade['current_price'] or 0.0
                
                # Balance features
                features['balance_usd_before'] = trade['balance_usd_before'] or 0.0
                features['balance_doge_before'] = trade['balance_doge_before'] or 0.0
                features['balance_usd_after'] = trade['balance_usd_after'] or 0.0
                features['balance_doge_after'] = trade['balance_doge_after'] or 0.0
                
                # Market data features
                if market_data:
                    features['price_30_days_ago'] = market_data['price_30_days_ago'] or 0.0
                    features['price_change'] = market_data['price_change'] or 0.0
                    features['price_change_percent'] = market_data['price_change_percent'] or 0.0
                    features['recent_high'] = market_data['recent_high'] or 0.0
                    features['recent_low'] = market_data['recent_low'] or 0.0
                    features['volatility_30d'] = market_data['volatility_30d'] or 0.0
                    features['volatility_24h'] = market_data['volatility_24h'] or 0.0
                    features['price_range_24h'] = market_data['price_range_24h'] or 0.0
                    
                    # Moving averages
                    features['ma_7'] = market_data['ma_7'] or 0.0
                    features['ma_14'] = market_data['ma_14'] or 0.0
                    features['ma_30'] = market_data['ma_30'] or 0.0
                    
                    # Volume features
                    features['avg_volume_30d'] = market_data['avg_volume_30d'] or 0.0
                    features['recent_volume_30d'] = market_data['recent_volume_30d'] or 0.0
                    features['avg_volume_24h'] = market_data['avg_volume_24h'] or 0.0
                    
                    # Order book features
                    features['best_bid'] = market_data['best_bid'] or 0.0
                    features['best_ask'] = market_data['best_ask'] or 0.0
                    features['spread'] = market_data['spread'] or 0.0
                    features['spread_percent'] = market_data['spread_percent'] or 0.0
                    features['volume_imbalance'] = market_data['volume_imbalance'] or 0.0
                    
                    # Technical indicators
                    features['rsi'] = market_data['rsi'] or 0.0
                    features['macd'] = market_data['macd'] or 0.0
                    features['macd_signal'] = market_data['macd_signal'] or 0.0
                    features['bb_upper'] = market_data['bb_upper'] or 0.0
                    features['bb_middle'] = market_data['bb_middle'] or 0.0
                    features['bb_lower'] = market_data['bb_lower'] or 0.0
                    
                    # Fear & Greed Index
                    features['fear_greed_index'] = market_data['fear_greed_index'] or 0
                    
                    # Portfolio features
                    features['portfolio_value'] = market_data['portfolio_value'] or 0.0
                    features['usd_percentage'] = market_data['usd_percentage'] or 0.0
                    features['doge_percentage'] = market_data['doge_percentage'] or 0.0
                    
                    # Extract technical indicators from JSON if available
                    if market_data['technical_indicators_json']:
                        try:
                            tech_indicators = json.loads(market_data['technical_indicators_json'])
                            # Add any additional technical indicators
                            for key, value in tech_indicators.items():
                                if isinstance(value, (int, float)):
                                    features[f'tech_{key}'] = value
                        except:
                            pass
                else:
                    # Fill with zeros if market data not available
                    market_features = [
                        'price_30_days_ago', 'price_change', 'price_change_percent',
                        'recent_high', 'recent_low', 'volatility_30d', 'volatility_24h',
                        'price_range_24h', 'ma_7', 'ma_14', 'ma_30',
                        'avg_volume_30d', 'recent_volume_30d', 'avg_volume_24h',
                        'best_bid', 'best_ask', 'spread', 'spread_percent', 'volume_imbalance',
                        'rsi', 'macd', 'macd_signal', 'bb_upper', 'bb_middle', 'bb_lower',
                        'fear_greed_index', 'portfolio_value', 'usd_percentage', 'doge_percentage'
                    ]
                    for feature in market_features:
                        features[feature] = 0.0
                
                # Analysis features
                if analysis_result:
                    features['recommendation'] = analysis_result['recommendation'] or 'HOLD'
                    features['confidence_level'] = analysis_result['confidence_level'] or 'Medium'
                    features['risk_assessment'] = analysis_result['risk_assessment'] or 'Medium'
                    
                    # Parse risk factors and key market factors from JSON
                    if analysis_result['risk_factors_json']:
                        try:
                            risk_factors = json.loads(analysis_result['risk_factors_json'])
                            features['num_risk_factors'] = len(risk_factors) if isinstance(risk_factors, list) else 0
                        except:
                            features['num_risk_factors'] = 0
                    else:
                        features['num_risk_factors'] = 0
                    
                    if analysis_result['key_market_factors_json']:
                        try:
                            key_factors = json.loads(analysis_result['key_market_factors_json'])
                            features['num_key_factors'] = len(key_factors) if isinstance(key_factors, list) else 0
                        except:
                            features['num_key_factors'] = 0
                    else:
                        features['num_key_factors'] = 0
                else:
                    features['recommendation'] = 'HOLD'
                    features['confidence_level'] = 'Medium'
                    features['risk_assessment'] = 'Medium'
                    features['num_risk_factors'] = 0
                    features['num_key_factors'] = 0
                
                # Ground truth labels
                features['decision_correct'] = 1 if trade['decision_correct'] == 1 else (0 if trade['decision_correct'] == 0 else None)
                features['success'] = 1 if trade['success'] else 0
                
                # Calculate portfolio value change
                initial_value = features['balance_usd_before'] + (features['balance_doge_before'] * features['current_price'])
                final_value = features['balance_usd_after'] + (features['balance_doge_after'] * features['current_price'])
                if initial_value > 0:
                    features['portfolio_change_percent'] = ((final_value - initial_value) / initial_value) * 100
                else:
                    features['portfolio_change_percent'] = 0.0
                
                # Action encoding (for ML models)
                action_encoding = {'BUY': 1, 'SELL': -1, 'HOLD': 0}
                features['action_encoded'] = action_encoding.get(features['action'], 0)
                
                # Add reflection if available
                features['has_reflection'] = 1 if trade['reflection'] else 0
                
                dataset_records.append(features)
            
            except Exception as e:
                print(f"⚠️  Error processing trade {trade['id']}: {e}")
                continue
        
        if len(dataset_records) == 0:
            print("⚠️  No valid records extracted")
            return None
        
        print(f"✅ Extracted {len(dataset_records)} records with features")
        
        # Generate output file
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        
        if output_format.lower() == 'sqlite' or output_format.lower() == 'db':
            output_path = f"training_dataset_{days}d_{timestamp}.db"
            
            # Create SQLite database
            import sqlite3
            conn = sqlite3.connect(output_path)
            cursor = conn.cursor()
            
            if dataset_records:
                # Get all field names from first record
                fieldnames = list(dataset_records[0].keys())
                
                # Create table with appropriate column types
                column_definitions = []
                for field in fieldnames:
                    # Determine SQLite type based on Python type
                    sample_value = dataset_records[0][field]
                    if sample_value is None:
                        column_type = 'TEXT'
                    elif isinstance(sample_value, (int, bool)):
                        column_type = 'INTEGER'
                    elif isinstance(sample_value, float):
                        column_type = 'REAL'
                    else:
                        column_type = 'TEXT'
                    
                    column_definitions.append(f"`{field}` {column_type}")
                
                create_table_sql = f"""
                    CREATE TABLE IF NOT EXISTS training_data (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        {', '.join(column_definitions)}
                    )
                """
                
                cursor.execute(create_table_sql)
                
                # Insert records
                placeholders = ', '.join(['?' for _ in fieldnames])
                insert_sql = f"INSERT INTO training_data ({', '.join([f'`{f}`' for f in fieldnames])}) VALUES ({placeholders})"
                
                for record in dataset_records:
                    values = [record.get(field) for field in fieldnames]
                    # Convert None to NULL for SQLite
                    values = [None if v is None else v for v in values]
                    cursor.execute(insert_sql, values)
                
                conn.commit()
                
                # Create indexes for common queries
                try:
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_action ON training_data(action)")
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_decision_correct ON training_data(decision_correct)")
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON training_data(timestamp)")
                    conn.commit()
                except Exception as e:
                    print(f"⚠️  Warning: Could not create indexes: {e}")
                
                # Get statistics
                cursor.execute("SELECT COUNT(*) FROM training_data")
                record_count = cursor.fetchone()[0]
                
                cursor.execute("PRAGMA table_info(training_data)")
                columns = cursor.fetchall()
                
                conn.close()
                
                print(f"\n✅ Training dataset saved to: {output_path}")
                print(f"   Format: SQLite Database")
                print(f"   Records: {record_count}")
                print(f"   Features: {len(columns) - 1}")  # -1 for id column
                print(f"   Table: training_data")
                print(f"   Columns: {len(columns)} total")
                print(f"\n   Sample columns: {', '.join([c[1] for c in columns[:10]])}..." if len(columns) > 10 else f"   Columns: {', '.join([c[1] for c in columns])}")
                
                return output_path
        
        elif output_format.lower() == 'csv':
            output_path = f"training_dataset_{days}d_{timestamp}.csv"
            
            # Create CSV file
            import csv
            if dataset_records:
                fieldnames = list(dataset_records[0].keys())
                with open(output_path, 'w', newline='') as csvfile:
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(dataset_records)
                
                print(f"\n✅ Training dataset saved to: {output_path}")
                print(f"   Format: CSV")
                print(f"   Records: {len(dataset_records)}")
                print(f"   Features: {len(fieldnames)}")
                print(f"   Columns: {', '.join(fieldnames[:10])}..." if len(fieldnames) > 10 else f"   Columns: {', '.join(fieldnames)}")
                
                return output_path
        
        elif output_format.lower() == 'json':
            output_path = f"training_dataset_{days}d_{timestamp}.json"
            
            # Create JSON file
            with open(output_path, 'w') as jsonfile:
                json.dump(dataset_records, jsonfile, indent=2, default=str)
            
            print(f"\n✅ Training dataset saved to: {output_path}")
            print(f"   Format: JSON")
            print(f"   Records: {len(dataset_records)}")
            print(f"   Features: {len(dataset_records[0].keys()) if dataset_records else 0}")
            
            return output_path
        
        else:
            print(f"⚠️  Unknown output format: {output_format}. Use 'sqlite', 'csv', or 'json'")
            return None
    
    def fetch_historical_price_at_timestamp(self, timestamp: datetime, granularity: int = 3600):
        """
        Fetch historical price data at a specific timestamp from Coinbase API.
        
        Args:
            timestamp: The timestamp to fetch price for
            granularity: Granularity in seconds (3600 = 1 hour, 900 = 15 min, etc.)
        
        Returns:
            Dictionary with price data or None if not found
        """
        try:
            # Convert timestamp to Unix timestamp
            start_time = timestamp - timedelta(hours=1)  # Get 1 hour window around the timestamp
            end_time = timestamp + timedelta(hours=1)
            
            start_unix = int(start_time.timestamp())
            end_unix = int(end_time.timestamp())
            
            url = "https://api.exchange.coinbase.com/products/DOGE-USD/candles"
            params = {
                'start': start_unix,
                'end': end_unix,
                'granularity': granularity
            }
            
            response = requests.get(url, params=params)
            if response.status_code == 200:
                data = response.json()
                if data and len(data) > 0:
                    # Find the closest candle to our timestamp
                    closest_candle = None
                    min_diff = float('inf')
                    
                    for candle in data:
                        candle_time = datetime.fromtimestamp(candle[0])
                        time_diff = abs((timestamp - candle_time).total_seconds())
                        if time_diff < min_diff:
                            min_diff = time_diff
                            closest_candle = candle
                    
                    if closest_candle:
                        # Coinbase returns: [timestamp, low, high, open, close, volume]
                        return {
                            'timestamp': datetime.fromtimestamp(closest_candle[0]),
                            'open': closest_candle[3],
                            'high': closest_candle[2],
                            'low': closest_candle[1],
                            'close': closest_candle[4],
                            'volume': closest_candle[5]
                        }
            
            return None
        except Exception as e:
            print(f"⚠️  Error fetching historical price at {timestamp}: {e}")
            return None
    
    def calculate_trade_ground_truth(self, trade_timestamp: datetime, action: str, 
                                     trade_price: float, evaluation_window_hours: int = 6):
        """
        Calculate ground truth for a trade by comparing price at trade time vs price after evaluation window.
        
        Args:
            trade_timestamp: When the trade was made
            action: BUY, SELL, or HOLD
            trade_price: Price at time of trade
            evaluation_window_hours: Hours after trade to evaluate (default: 6 hours, matches simulation interval)
        
        Returns:
            Dictionary with ground truth info: {'decision_correct': bool, 'price_change_percent': float, 
            'price_at_trade': float, 'price_after_window': float}
        """
        try:
            # Fetch price at trade time (actual historical price)
            trade_price_data = self.fetch_historical_price_at_timestamp(trade_timestamp)
            if not trade_price_data:
                print(f"⚠️  Could not fetch historical price at {trade_timestamp}, using provided price")
                actual_trade_price = trade_price
            else:
                actual_trade_price = trade_price_data['close']
            
            # Fetch price after evaluation window
            evaluation_timestamp = trade_timestamp + timedelta(hours=evaluation_window_hours)
            
            # If evaluation timestamp is in the future, we can't get ground truth yet
            if evaluation_timestamp > datetime.now():
                return {
                    'decision_correct': None,
                    'price_change_percent': None,
                    'price_at_trade': actual_trade_price,
                    'price_after_window': None,
                    'evaluation_timestamp': evaluation_timestamp,
                    'note': f'Evaluation timestamp is in the future. Need to wait {evaluation_window_hours} hours after trade.'
                }
            
            price_after_data = self.fetch_historical_price_at_timestamp(evaluation_timestamp)
            if not price_after_data:
                print(f"⚠️  Could not fetch price after {evaluation_window_hours} hours")
                return None
            
            price_after_window = price_after_data['close']
            price_change_percent = ((price_after_window - actual_trade_price) / actual_trade_price) * 100
            
            # Calculate granular decision quality rating
            def categorize_performance(price_change_pct, action_type):
                """
                Categorize decision quality based on price change and action type.
                
                Returns:
                    Tuple of (quality_label, quality_score, decision_correct)
                    - quality_label: 'extremely_bad', 'very_bad', 'moderately_bad', 'slightly_bad',
                                    'slightly_good', 'moderately_good', 'very_good', 'extremely_good'
                    - quality_score: -4 to 4 (negative = bad, positive = good)
                    - decision_correct: Boolean for backward compatibility
                """
                abs_change = abs(price_change_pct)
                
                if action_type == 'BUY':
                    # BUY performance based on price increase
                    if price_change_pct > 10:
                        return ('extremely_good', 4, True)
                    elif price_change_pct > 5:
                        return ('very_good', 3, True)
                    elif price_change_pct > 2:
                        return ('moderately_good', 2, True)
                    elif price_change_pct > 0:
                        return ('slightly_good', 1, True)
                    elif price_change_pct > -2:
                        return ('slightly_bad', -1, False)
                    elif price_change_pct > -5:
                        return ('moderately_bad', -2, False)
                    elif price_change_pct > -10:
                        return ('very_bad', -3, False)
                    else:
                        return ('extremely_bad', -4, False)
                
                elif action_type == 'SELL':
                    # SELL performance based on price decrease
                    if price_change_pct < -10:
                        return ('extremely_good', 4, True)
                    elif price_change_pct < -5:
                        return ('very_good', 3, True)
                    elif price_change_pct < -2:
                        return ('moderately_good', 2, True)
                    elif price_change_pct < 0:
                        return ('slightly_good', 1, True)
                    elif price_change_pct < 2:
                        return ('slightly_bad', -1, False)
                    elif price_change_pct < 5:
                        return ('moderately_bad', -2, False)
                    elif price_change_pct < 10:
                        return ('very_bad', -3, False)
                    else:
                        return ('extremely_bad', -4, False)
                
                elif action_type == 'HOLD':
                    # HOLD: rewarded if price dropped (avoided buying), penalized if price increased (missed opportunity)
                    if price_change_pct < -10:
                        return ('extremely_good', 4, True)
                    elif price_change_pct < -5:
                        return ('very_good', 3, True)
                    elif price_change_pct < -2:
                        return ('moderately_good', 2, True)
                    elif price_change_pct < 0:
                        return ('slightly_good', 1, True)
                    elif price_change_pct < 2:
                        return ('slightly_bad', -1, False)
                    elif price_change_pct < 5:
                        return ('moderately_bad', -2, False)
                    elif price_change_pct < 10:
                        return ('very_bad', -3, False)
                    else:
                        return ('extremely_bad', -4, False)
                
                else:
                    return ('unknown', 0, None)
            
            quality_label, quality_score, decision_correct = categorize_performance(price_change_percent, action)
            
            return {
                'decision_correct': decision_correct,  # Boolean for backward compatibility
                'decision_quality_label': quality_label,  # Granular label
                'decision_quality_score': quality_score,  # Numeric score (-4 to 4)
                'price_change_percent': price_change_percent,
                'price_at_trade': actual_trade_price,
                'price_after_window': price_after_window,
                'evaluation_timestamp': evaluation_timestamp,
                'evaluation_window_hours': evaluation_window_hours
            }
        except Exception as e:
            print(f"⚠️  Error calculating ground truth: {e}")
            return None
    
    def simulate_trade_execution(self, action: str, percentage: float, current_price: float, 
                                analysis_id: Optional[int] = None, simulated_timestamp: Optional[str] = None,
                                balance_usd_before: Optional[float] = None, 
                                balance_doge_before: Optional[float] = None) -> tuple:
        """
        Simulate a trade execution (save to DB without actually executing the trade).
        Useful for backtesting and simulation.
        
        Args:
            action: Trade action (BUY, SELL, HOLD)
            percentage: Percentage of portfolio/balance used
            current_price: Price at time of simulation
            analysis_id: ID of the related analysis_results record
            simulated_timestamp: Simulated timestamp for historical simulation
            balance_usd_before: USD balance before trade (optional, for simulation)
            balance_doge_before: DOGE balance before trade (optional, for simulation)
        
        Returns:
            Tuple of (trade_id, balance_usd_after, balance_doge_after)
            - trade_id: ID of the inserted trade execution record
            - balance_usd_after: USD balance after trade
            - balance_doge_after: DOGE balance after trade
        """
        if not self.database_enabled or not self.db:
            print("⚠️  Database not enabled - cannot simulate trade execution")
            return None, None, None
        
        # Create simulated order result
        simulated_order_result = {
            'id': f"SIM-{int(time.time())}",
            'status': 'filled',
            'filled_size': f"{percentage}",
            'executed_value': current_price * percentage if action == 'BUY' else None,
        }
        
        # Use provided balances or fall back to current balances/defaults
        if balance_usd_before is None:
            balance_usd_before = self.trade_executor.get_usd_balance() if self.trade_executor else 1000.0
        if balance_doge_before is None:
            balance_doge_before = self.trade_executor.get_dogecoin_balance() if self.trade_executor else 0.0
        
        # Calculate simulated after balances
        if action == 'BUY':
            balance_usd_after = balance_usd_before * (1 - percentage / 100)
            balance_doge_after = balance_doge_before + (balance_usd_before * percentage / 100 / current_price)
        elif action == 'SELL':
            balance_doge_after = balance_doge_before * (1 - percentage / 100)
            balance_usd_after = balance_usd_before + (balance_doge_before * percentage / 100 * current_price)
        else:
            balance_usd_after = balance_usd_before
            balance_doge_after = balance_doge_before
        
        # Save simulated trade execution to database
        trade_id = self.db.save_trade_execution(
            action=action,
            percentage=percentage,
            order_result=simulated_order_result,
            analysis_id=analysis_id,
            current_price=current_price,
            balance_usd_before=balance_usd_before,
            balance_doge_before=balance_doge_before,
            balance_usd_after=balance_usd_after,
            balance_doge_after=balance_doge_after,
            error_message=None
        )
        
        # Return trade_id and the calculated after balances
        return trade_id, balance_usd_after, balance_doge_after
    
    def simulate_trading_past_7days(self, skip_confirmation=False):
        """
        Simulate trading for the past 365 days (1 year), running analysis every 6 hours.
        Saves all simulated trades to database with reflections.
        Skips chart capture for faster execution.
        
        Args:
            skip_confirmation: If True, skip user confirmation prompt (useful for automated runs)
        """
        if not self.database_enabled or not self.db:
            print("⚠️  Database not enabled - cannot run simulation")
            return
        
        print("\n" + "="*70)
        print("🎮 TRADING SIMULATION - Past 365 Days (1 Year) (Every 6 Hours)")
        print("="*70)
        print("This will simulate trading decisions for the past 365 days (1 year)")
        print("Analysis will run approximately 1460 times (every 6 hours)")
        print("Chart capture and news data will be skipped for faster execution")
        print("="*70)
        print("⚠️  WARNING: This will take a significant amount of time (many hours)")
        print("="*70)
        print("\n▶️  Starting simulation...")
        
        # Calculate timestamps for past 365 days (every 6 hours)
        # 365 days * 24 hours / 6 hours = 1460 simulations
        # Start from 365 days ago and go forward to now
        now = datetime.now()
        simulation_times = []
        for days_ago in range(365, -1, -1):  # From 365 days ago to 0 days ago (now)
            for hours_offset in range(0, 24, 6):  # Every 6 hours: 0, 6, 12, 18
                if days_ago == 0 and hours_offset == 0:
                    # Skip current time, start from 6 hours ago if today
                    continue
                sim_time = now - timedelta(days=days_ago, hours=hours_offset)
                # Only add if it's in the past (not future)
                if sim_time <= now:
                    simulation_times.append(sim_time)
        
        # Sort to go from oldest to newest
        simulation_times.sort()
        
        print(f"\n📊 Running {len(simulation_times)} simulations...")
        print(f"First simulation: {simulation_times[0]}")
        print(f"Last simulation: {simulation_times[-1]}")
        print("-"*70)
        
        # Initialize running balances for simulation (starting portfolio state)
        # Start with $500 USD and $500 worth of DOGE (50/50 split)
        initial_usd_value = 500.0
        target_doge_value = 500.0
        
        # Get the price at the first simulation time to calculate initial DOGE balance
        first_sim_time = simulation_times[0]
        initial_price_data = self.fetch_historical_price_at_timestamp(first_sim_time)
        if initial_price_data:
            initial_price = initial_price_data['close']
            running_balance_usd = initial_usd_value
            running_balance_doge = target_doge_value / initial_price if initial_price > 0 else 0.0
            print(f"\n💰 Starting simulation with initial balances (at {first_sim_time.strftime('%Y-%m-%d %H:%M')}):")
            print(f"   USD Balance: ${running_balance_usd:.2f}")
            print(f"   DOGE Balance: {running_balance_doge:.6f} DOGE")
            print(f"   DOGE Value: ${target_doge_value:.2f} (at ${initial_price:.6f}/DOGE)")
            print(f"   Total Portfolio Value: ${running_balance_usd + target_doge_value:.2f}")
        else:
            # Fallback if we can't get historical price
            running_balance_usd = initial_usd_value
            running_balance_doge = 0.0
            print(f"\n💰 Starting simulation with:")
            print(f"   USD Balance: ${running_balance_usd:.2f}")
            print(f"   DOGE Balance: {running_balance_doge:.6f} (could not fetch historical price)")
        print("-"*70)
        
        total_simulations = len(simulation_times)
        for idx, sim_time in enumerate(simulation_times, 1):
            print(f"\n{'='*70}")
            print(f"🔄 Simulation {idx}/{total_simulations} - {sim_time.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"{'='*70}")
            
            try:
                # Run analysis with chart capture and news data skipped (faster for simulation)
                # Pass simulation date to fetch historical Fear & Greed Index
                # Also pass running balances so investment status reflects current portfolio state
                print(f"📈 Running analysis for {sim_time.strftime('%Y-%m-%d %H:%M')}...")
                analysis = self.run_analysis(skip_chart_capture=True, skip_news_data=True, simulation_date=sim_time,
                                             current_usd_balance=running_balance_usd, current_doge_balance=running_balance_doge)
                
                if not analysis:
                    print(f"⚠️  Analysis failed for {sim_time.strftime('%Y-%m-%d %H:%M')}, skipping...")
                    continue
                
                # Get the latest analysis JSON and ID
                analysis_id = None
                if self.latest_analysis_json and self.database_enabled:
                    # The analysis was already saved in run_analysis, get the latest ID
                    recent_analyses = self.db.get_recent_analyses(limit=1)
                    if recent_analyses:
                        analysis_id = recent_analyses[0]['id']
                
                # Extract recommendation
                recommendation = None
                percentage = None
                if self.latest_analysis_json:
                    recommendation = self.latest_analysis_json.get('recommendation', '').upper()
                    percentage = self.latest_analysis_json.get('percentage')
                
                # Get current price for simulation (fallback)
                current_price = self.trade_executor.get_current_price() if self.trade_executor else 0.08
                
                # Fetch actual historical price at simulation timestamp (needed for all actions)
                historical_price_data = self.fetch_historical_price_at_timestamp(sim_time)
                if historical_price_data:
                    actual_price = historical_price_data['close']
                    print(f"📊 Historical price at {sim_time.strftime('%Y-%m-%d %H:%M')}: ${actual_price:.6f}")
                else:
                    actual_price = current_price
                    print(f"⚠️  Using current price: ${actual_price:.6f}")
                
                # Use current running balances for this simulation
                balance_usd_before = running_balance_usd
                balance_doge_before = running_balance_doge
                
                # Simulate trade if recommendation is BUY or SELL
                trade_id = None
                if recommendation in ['BUY', 'SELL'] and percentage is not None:
                    print(f"\n💼 Simulating {recommendation} order for {percentage}%")
                    print(f"   Balance before: ${balance_usd_before:.2f} USD, {balance_doge_before:.6f} DOGE")
                    
                    result = self.simulate_trade_execution(
                        action=recommendation,
                        percentage=percentage,
                        current_price=actual_price,
                        analysis_id=analysis_id,
                        simulated_timestamp=sim_time.isoformat(),
                        balance_usd_before=balance_usd_before,
                        balance_doge_before=balance_doge_before
                    )
                    
                    if result and result[0]:  # result is (trade_id, balance_usd_after, balance_doge_after)
                        trade_id, balance_usd_after, balance_doge_after = result
                        print(f"✅ Simulated trade saved (Trade ID: {trade_id})")
                        
                        # Update running balances immediately after trade execution
                        running_balance_usd = balance_usd_after
                        running_balance_doge = balance_doge_after
                        print(f"   Balance after: ${running_balance_usd:.2f} USD, {running_balance_doge:.6f} DOGE")
                        
                        # Calculate ground truth (if evaluation window has passed)
                        # Since we run simulation every 6 hours, evaluate 6 hours after trade
                        print(f"📊 Calculating ground truth...")
                        ground_truth = self.calculate_trade_ground_truth(
                            trade_timestamp=sim_time,
                            action=recommendation,
                            trade_price=actual_price,
                            evaluation_window_hours=6  # Evaluate 6 hours after trade (next simulation interval)
                        )
                        
                        if ground_truth:
                            if ground_truth.get('decision_correct') is not None:
                                quality_label = ground_truth.get('decision_quality_label', 'unknown')
                                quality_score = ground_truth.get('decision_quality_score', 0)
                                decision_result = "✅ CORRECT" if ground_truth['decision_correct'] else "❌ INCORRECT"
                                print(f"{decision_result} - Quality: {quality_label} (score: {quality_score})")
                                print(f"   Price changed {ground_truth['price_change_percent']:.2f}%")
                                print(f"   Price at trade: ${ground_truth['price_at_trade']:.6f}")
                                print(f"   Price after {ground_truth['evaluation_window_hours']}h: ${ground_truth['price_after_window']:.6f}")
                                
                                # Automatically update trade with ground truth
                                try:
                                    self.db.update_trade_reflection(
                                        trade_id=trade_id,
                                        reflection=f"Ground truth: {decision_result}. Quality: {quality_label} (score: {quality_score}). Price change: {ground_truth['price_change_percent']:.2f}%. Evaluation: {ground_truth['evaluation_timestamp'].strftime('%Y-%m-%d %H:%M')}",
                                        decision_correct=ground_truth['decision_correct'],
                                        decision_quality_label=quality_label,
                                        decision_quality_score=quality_score
                                    )
                                    print(f"✅ Ground truth saved to database")
                                except Exception as e:
                                    print(f"⚠️  Failed to save ground truth: {e}")
                            else:
                                print(f"⏳ Ground truth not available yet: {ground_truth.get('note', 'Evaluation window not reached')}")
                        else:
                            print(f"⚠️  Could not calculate ground truth")
                        
                        # Skip manual reflection during simulation for automated dataset generation
                        # Manual reflection can be added later using review_trade_reflections()
                        print(f"💭 Note: You can add reflections later using --review-reflections")
                elif recommendation == 'HOLD':
                    print(f"🤖 Recommendation: HOLD - Simulating HOLD decision for training dataset")
                    print(f"   Balance: ${balance_usd_before:.2f} USD, {balance_doge_before:.6f} DOGE")
                    # Save HOLD as a trade execution for training dataset
                    result = self.simulate_trade_execution(
                        action='HOLD',
                        percentage=0.0,
                        current_price=actual_price,
                        analysis_id=analysis_id,
                        simulated_timestamp=sim_time.isoformat(),
                        balance_usd_before=balance_usd_before,
                        balance_doge_before=balance_doge_before
                    )
                    
                    if result and result[0]:  # result is (trade_id, balance_usd_after, balance_doge_after)
                        trade_id, balance_usd_after, balance_doge_after = result
                        print(f"✅ Simulated HOLD saved (Trade ID: {trade_id})")
                        
                        # Update running balances (HOLD doesn't change balances, but we update for consistency)
                        running_balance_usd = balance_usd_after
                        running_balance_doge = balance_doge_after
                        
                        # Calculate ground truth for HOLD (if price stayed relatively stable)
                        print(f"📊 Calculating ground truth for HOLD...")
                        ground_truth = self.calculate_trade_ground_truth(
                            trade_timestamp=sim_time,
                            action='HOLD',
                            trade_price=actual_price,
                            evaluation_window_hours=6
                        )
                        
                        if ground_truth and ground_truth.get('decision_correct') is not None:
                            # For HOLD, decision is correct if price dropped (rewarded for not buying)
                            # Decision is incorrect if price increased (penalized for missing opportunity)
                            hold_decision_correct = ground_truth['decision_correct']
                            if hold_decision_correct:
                                decision_result = "✅ CORRECT"
                                result_note = "good call (price dropped)"
                            else:
                                decision_result = "❌ INCORRECT"
                                result_note = "missed opportunity (price increased)"
                            quality_label = ground_truth.get('decision_quality_label', 'unknown')
                            quality_score = ground_truth.get('decision_quality_score', 0)
                            print(f"{decision_result} - Quality: {quality_label} (score: {quality_score})")
                            print(f"   Price changed {ground_truth['price_change_percent']:.2f}% (HOLD was {result_note})")
                            print(f"   Price at trade: ${ground_truth['price_at_trade']:.6f}")
                            print(f"   Price after {ground_truth['evaluation_window_hours']}h: ${ground_truth['price_after_window']:.6f}")
                            
                            try:
                                self.db.update_trade_reflection(
                                    trade_id=trade_id,
                                    reflection=f"Ground truth: {decision_result}. Quality: {quality_label} (score: {quality_score}). Price change: {ground_truth['price_change_percent']:.2f}%. HOLD decision analysis.",
                                    decision_correct=hold_decision_correct,
                                    decision_quality_label=quality_label,
                                    decision_quality_score=quality_score
                                )
                                print(f"✅ Ground truth saved to database")
                            except Exception as e:
                                print(f"⚠️  Failed to save ground truth: {e}")
                        else:
                            print(f"⏳ Ground truth not available yet for HOLD")
                else:
                    print(f"⚠️  No valid recommendation found (recommendation={recommendation}, percentage={percentage})")
                
            except Exception as e:
                print(f"❌ Error in simulation {idx}: {e}")
                import traceback
                traceback.print_exc()
                continue
            
            # Small delay between simulations to avoid rate limiting
            if idx < total_simulations:
                print(f"\n⏳ Waiting 2 seconds before next simulation...")
                time.sleep(2)
        
        print("\n" + "="*70)
        print("✅ SIMULATION COMPLETED")
        print("="*70)
        print(f"Total simulations: {total_simulations}")
        print("All simulated trades have been saved to the database")
        
        # Display final portfolio status and performance
        if self.database_enabled and self.db:
            print("\n" + "="*70)
            print("📊 FINAL PORTFOLIO STATUS")
            print("="*70)
            
            # Get final balances from last trade or current state
            from datetime import datetime as dt_class
            final_price_data = self.fetch_historical_price_at_timestamp(dt_class.now())
            if final_price_data:
                final_price = final_price_data['close']
                
                # Calculate final portfolio value using current running balances
                final_usd_value = running_balance_usd
                final_doge_value_usd = running_balance_doge * final_price
                final_portfolio_value = final_usd_value + final_doge_value_usd
                
                print(f"💰 Portfolio Value: ${final_portfolio_value:.2f}")
                print(f"   USD: ${final_usd_value:.2f}")
                print(f"   DOGE: ${final_doge_value_usd:.2f} ({running_balance_doge:.6f} DOGE @ ${final_price:.6f})")
                
                # Calculate and display performance metrics
                print(f"\n📊 Trading Performance (vs Buy-and-Hold):")
                
                # Get initial portfolio value
                first_sim_time = simulation_times[0] if simulation_times else dt_class.now() - timedelta(days=7)
                initial_price_data = self.fetch_historical_price_at_timestamp(first_sim_time)
                if initial_price_data:
                    initial_price = initial_price_data['close']
                    initial_usd_value = 500.0
                    initial_doge_value = 500.0
                    initial_portfolio_value = initial_usd_value + initial_doge_value
                    
                    # Calculate buy-and-hold value (initial DOGE at current price)
                    buy_hold_doge_value = initial_doge_value * (final_price / initial_price)
                    buy_hold_portfolio_value = initial_usd_value + buy_hold_doge_value
                    
                    # Calculate trading performance
                    trading_value_added = final_portfolio_value - buy_hold_portfolio_value
                    if buy_hold_portfolio_value > 0:
                        trading_performance_pct = (trading_value_added / buy_hold_portfolio_value) * 100
                        symbol = "📈" if trading_performance_pct > 0 else "📉" if trading_performance_pct < 0 else "➡️"
                        print(f"   {symbol} Trading vs Buy-and-Hold: {trading_performance_pct:+.2f}%")
                        print(f"   Trading Portfolio: ${final_portfolio_value:.2f}")
                        print(f"   Buy-and-Hold Portfolio: ${buy_hold_portfolio_value:.2f}")
                        print(f"   Value Added: ${trading_value_added:+.2f}")
                
                # Get performance metrics for different periods
                perf_metrics = self.calculate_portfolio_performance_periods(
                    target_date=dt_class.now(),
                    current_usd_balance=running_balance_usd,
                    current_doge_balance=running_balance_doge
                )
                
                if perf_metrics:
                    print(f"\n📊 Period Performance (vs Buy-and-Hold):")
                    periods = {
                        '1d': '1 Day',
                        '5d': '5 Days',
                        '1m': '1 Month',
                        '3m': '3 Months',
                        '6m': '6 Months',
                        'ytd': 'YTD',
                        '1y': '1 Year',
                        'entire': 'Entire'
                    }
                    
                    for period_key, period_label in periods.items():
                        if period_key in perf_metrics:
                            period_info = perf_metrics[period_key]
                            value = period_info.get('value', 0)
                            symbol = "📈" if value > 0 else "📉" if value < 0 else "➡️"
                            print(f"   {symbol} {period_label}: {value:+.2f}%")
        
        print("="*70)

def main():
    """Main function to run the Dogecoin analysis."""
    import sys
    
    try:
        analyzer = DogecoinAnalyzer()
        
        # Check for command line arguments
        if len(sys.argv) > 1:
            if sys.argv[1] == '--simulate':
                analyzer.simulate_trading_past_7days()
            elif sys.argv[1] == '--analyze-performance':
                days = int(sys.argv[2]) if len(sys.argv) > 2 else 7
                analyzer.analyze_trading_performance(days=days)
            elif sys.argv[1] == '--review-reflections':
                analyzer.review_trade_reflections()
            elif sys.argv[1] == '--generate-dataset':
                days = int(sys.argv[2]) if len(sys.argv) > 2 else 7
                output_format = sys.argv[3] if len(sys.argv) > 3 else 'sqlite'
                analyzer.generate_training_dataset(days=days, output_format=output_format)
            elif sys.argv[1] == '--simulate-and-dataset':
                # Run simulation first, then generate dataset
                days = int(sys.argv[2]) if len(sys.argv) > 2 else 7
                output_format = sys.argv[3] if len(sys.argv) > 3 else 'sqlite'
                print("🔄 Running simulation first...")
                analyzer.simulate_trading_past_7days(skip_confirmation=True)
                print("\n🔄 Generating training dataset...")
                analyzer.generate_training_dataset(days=days, output_format=output_format)
            elif sys.argv[1] == '--manual-trade':
                # Manual trade execution: --manual-trade SELL 20
                if len(sys.argv) < 4:
                    print("❌ Usage: --manual-trade <BUY|SELL> <percentage>")
                    print("   Example: --manual-trade SELL 20")
                    return
                action = sys.argv[2].upper()
                try:
                    percentage = float(sys.argv[3])
                    analyzer.execute_manual_trade(action, percentage)
                except ValueError:
                    print(f"❌ Invalid percentage: {sys.argv[3]}. Must be a number.")
            else:
                print(f"Unknown argument: {sys.argv[1]}")
                print("Available options:")
                print("  --simulate [--auto]               : Run trading simulation (add --auto to skip confirmation)")
                print("  --simulate-and-dataset [days] [fmt]: Run simulation then generate dataset (default: 7 days, sqlite)")
                print("  --analyze-performance [days]      : Analyze trading performance (default: 7 days)")
                print("  --review-reflections               : Review and add reflections to past trades")
                print("  --generate-dataset [days] [format]: Generate training dataset (default: 7 days, sqlite)")
                print("  --manual-trade <BUY|SELL> <pct>  : Manually execute a trade (e.g., --manual-trade SELL 20)")
        else:
            analysis = analyzer.run_analysis()
        
    except ValueError as e:
        print(f"❌ Configuration Error: {e}")
        print("Please check your .env file and ensure all API keys are set correctly.")
        print("Use env_template.txt as a reference for the required environment variables.")
    except Exception as e:
        print(f"❌ Unexpected Error: {e}")

if __name__ == "__main__":
    main()
