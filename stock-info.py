import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import shutil
import requests
import json
import sys

# FMP API Configuration
# Use environment variable for FMP API key
FMP_API_KEY = os.getenv('FMP_API_KEY')
if not FMP_API_KEY:
    print("\nError: FMP_API_KEY environment variable not set!")
    print("Please set your Financial Modeling Prep API key using:")
    print("export FMP_API_KEY='your_api_key_here'")
    print("\nYou can get an API key from: https://financialmodelingprep.com/developer")
    sys.exit(1)

FMP_BASE_URL = "https://financialmodelingprep.com/api/v3"

# Clear yfinance cache
cache_dir = os.path.expanduser('~/.cache/yfinance')
if os.path.exists(cache_dir):
    shutil.rmtree(cache_dir)

# Configure pandas display options
pd.set_option('display.float_format', lambda x: '%.3f' % x)

def calculate_rsi(data, periods=14):
    """
    Calculate RSI (Relative Strength Index)
    """
    # Calculate price changes
    delta = data['Close'].diff()
    
    # Separate gains and losses
    gain = (delta.where(delta > 0, 0)).rolling(window=periods).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=periods).mean()
    
    # Calculate RS (Relative Strength)
    rs = gain / loss
    
    # Calculate RSI
    rsi = 100 - (100 / (1 + rs))
    
    return rsi

def calculate_macd(data):
    """
    Calculate MACD (Moving Average Convergence Divergence)
    """
    # Calculate the short term exponential moving average
    ema12 = data['Close'].ewm(span=12, adjust=False).mean()
    
    # Calculate the long term exponential moving average
    ema26 = data['Close'].ewm(span=26, adjust=False).mean()
    
    # Calculate MACD line
    macd_line = ema12 - ema26
    
    # Calculate signal line (9-day EMA of MACD)
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    
    # Calculate MACD histogram
    macd_histogram = macd_line - signal_line
    
    return macd_line.iloc[-1], signal_line.iloc[-1], macd_histogram.iloc[-1]

def calculate_moving_averages(data):
    """
    Calculate short-term and medium-term moving averages (10-day and 25-day)
    """
    ma10 = data['Close'].rolling(window=10).mean()
    ma25 = data['Close'].rolling(window=25).mean()
    
    return ma10.iloc[-1], ma25.iloc[-1]

def calculate_20_day_ma(data):
    """
    Calculate 20-day moving average
    """
    ma20 = data['Close'].rolling(window=20).mean()
    return ma20.iloc[-1] if len(ma20) >= 20 else None

def should_sell_stock(data, threshold_percent=5.0, consecutive_days=1):
    """
    Determine if stock should be sold based on 20-day moving average strategy.
    
    Parameters:
    - data: Historical price data (pandas DataFrame with 'Close' column)
    - threshold_percent: Percentage below 20-DMA to trigger sell signal (default 5%)
    - consecutive_days: Number of consecutive days below threshold to confirm sell (default 1)
    
    Returns:
    - Dictionary with sell decision, current price, 20-DMA, drop percentage, and recommendation
    """
    if len(data) < 20:
        return {
            'sell_decision': False,
            'reason': 'Insufficient data for 20-day moving average calculation',
            'current_price': None,
            'ma_20': None,
            'drop_percentage': None,
            'recommendation': 'HOLD - Need more historical data'
        }
    
    # Calculate 20-day moving average
    ma20 = data['Close'].rolling(window=20).mean()
    current_price = data['Close'].iloc[-1]
    current_ma20 = ma20.iloc[-1]
    
    # Calculate drop percentage: (20-DMA - Current Price) / 20-DMA * 100
    drop_percentage = ((current_ma20 - current_price) / current_ma20) * 100
    
    # Check if current price is below 20-DMA by threshold percentage
    is_below_threshold = drop_percentage >= threshold_percent
    
    # Check consecutive days if required
    consecutive_count = 0
    if consecutive_days > 1:
        for i in range(1, min(consecutive_days + 1, len(data))):
            past_price = data['Close'].iloc[-i]
            past_ma20 = ma20.iloc[-i]
            past_drop = ((past_ma20 - past_price) / past_ma20) * 100
            
            if past_drop >= threshold_percent:
                consecutive_count += 1
            else:
                break
        
        meets_consecutive_requirement = consecutive_count >= consecutive_days
    else:
        meets_consecutive_requirement = True
    
    # Make sell decision
    sell_decision = is_below_threshold and meets_consecutive_requirement
    
    # Generate recommendation
    if sell_decision:
        if drop_percentage >= threshold_percent * 2:  # Double the threshold
            recommendation = f"STRONG SELL - Price is {drop_percentage:.2f}% below 20-DMA (threshold: {threshold_percent}%)"
        else:
            recommendation = f"SELL - Price is {drop_percentage:.2f}% below 20-DMA (threshold: {threshold_percent}%)"
    elif drop_percentage >= threshold_percent * 0.7:  # Within 70% of threshold
        recommendation = f"CAUTION - Price is {drop_percentage:.2f}% below 20-DMA, approaching sell threshold"
    elif drop_percentage > 0:  # Below MA but not at threshold
        recommendation = f"WATCH - Price is {drop_percentage:.2f}% below 20-DMA but within acceptable range"
    else:  # Above MA
        recommendation = f"HOLD - Price is {abs(drop_percentage):.2f}% above 20-DMA"
    
    return {
        'sell_decision': sell_decision,
        'current_price': current_price,
        'ma_20': current_ma20,
        'drop_percentage': drop_percentage,
        'threshold_percent': threshold_percent,
        'consecutive_days_required': consecutive_days,
        'consecutive_days_met': consecutive_count if consecutive_days > 1 else 1,
        'recommendation': recommendation,
        'reason': f"Price closed {'below' if drop_percentage > 0 else 'above'} 20-DMA by {abs(drop_percentage):.2f}%"
    }

def get_momentum_signal(rsi, ma10, ma25, macd_line, signal_line):
    """
    Generate trading signal based on momentum indicators
    """
    signals = []
    
    # RSI signals (using 20/80 for stronger signals)
    if rsi >= 80:
        signals.append("Strongly Overbought")
    elif rsi >= 70:
        signals.append("Overbought")
    elif rsi <= 20:
        signals.append("Strongly Oversold")
    elif rsi <= 30:
        signals.append("Oversold")
        
    # Moving Average signals
    if ma10 > ma25:
        signals.append("Bullish MA Crossover")
    elif ma10 < ma25:
        signals.append("Bearish MA Crossover")
        
    # MACD signals
    if macd_line > signal_line:
        signals.append("Bullish MACD")
    else:
        signals.append("Bearish MACD")
        
    return " | ".join(signals)

def calculate_pegy(info, current_price):
    """
    Calculate PEGY ratio
    PEGY = Price / (EPS growth TTM + (Daily Dividend Yield * 100))
    A lower PEGY ratio indicates better value
    """
    try:
        growth_rate = info.get('earningsGrowth', None)
        dividend_yield = info.get('dividendYield', 0)
        
        if growth_rate is None:
            return None
            
        # Convert growth rate to percentage if it's in decimal
        if abs(growth_rate) < 1:
            growth_rate *= 100
            
        # Convert dividend yield to percentage if it's in decimal
        if dividend_yield and dividend_yield < 1:
            dividend_yield *= 100
            
        denominator = growth_rate + (dividend_yield * 100)
        
        # Avoid division by zero or negative denominator
        if denominator <= 0:
            return None
            
        pegy = current_price / denominator
        return pegy
    except:
        return None

def calculate_eps_metrics(ticker):
    """
    Calculate comprehensive EPS metrics including:
    - Basic EPS (using latest quarterly data)
    - Diluted EPS
    - Rolling EPS (using last 4 quarters)
    - EPS Growth
    """
    try:
        # Get financial data
        info = ticker.info
        quarterly_financials = ticker.quarterly_financials
        quarterly_balance_sheet = ticker.quarterly_balance_sheet
        
        if quarterly_financials.empty or quarterly_balance_sheet.empty:
            return {
                'Basic EPS': 'N/A',
                'Rolling EPS': 'N/A',
                'EPS Growth': 'N/A',
                'P/E Ratio': 'N/A'
            }
        
        # Get net income data
        if 'Net Income' in quarterly_financials.index:
            net_income_data = quarterly_financials.loc['Net Income']
        else:
            return {'Error': 'No Net Income data available'}
            
        # Get shares outstanding data
        if 'Common Stock' in quarterly_balance_sheet.index:
            shares_data = quarterly_balance_sheet.loc['Common Stock']
        else:
            return {'Error': 'No Common Stock data available'}
            
        eps_metrics = {}
        
        # Calculate Basic EPS (most recent quarter)
        latest_net_income = net_income_data.iloc[0]  # Most recent quarter
        latest_shares = shares_data.iloc[0]  # Most recent quarter
        if latest_shares != 0:
            basic_eps = latest_net_income / latest_shares
            eps_metrics['Basic EPS'] = f"${basic_eps:.2f}"
        else:
            eps_metrics['Basic EPS'] = 'N/A'
            
        # Calculate Rolling EPS (last 4 quarters)
        if len(net_income_data) >= 4 and len(shares_data) >= 4:
            rolling_net_income = net_income_data.iloc[:4].sum()
            avg_shares = shares_data.iloc[:4].mean()  # Using average shares for the period
            if avg_shares != 0:
                rolling_eps = rolling_net_income / avg_shares
                eps_metrics['Rolling EPS'] = f"${rolling_eps:.2f}"
                
                # Calculate year-over-year EPS growth if we have enough data
                if len(net_income_data) >= 8 and len(shares_data) >= 8:
                    prev_year_net_income = net_income_data.iloc[4:8].sum()
                    prev_year_avg_shares = shares_data.iloc[4:8].mean()
                    if prev_year_avg_shares != 0:
                        prev_year_eps = prev_year_net_income / prev_year_avg_shares
                        if prev_year_eps != 0:
                            eps_growth = ((rolling_eps - prev_year_eps) / abs(prev_year_eps)) * 100
                            eps_metrics['EPS Growth'] = f"{eps_growth:.2f}%"
        else:
            eps_metrics['Rolling EPS'] = 'N/A'
            eps_metrics['EPS Growth'] = 'N/A'
            
        # Calculate P/E Ratio if we have current price and rolling EPS
        current_price = info.get('currentPrice')
        if current_price and 'Rolling EPS' in eps_metrics and eps_metrics['Rolling EPS'] != 'N/A':
            rolling_eps_value = float(eps_metrics['Rolling EPS'].replace('$', ''))
            if rolling_eps_value > 0:  # Only calculate P/E if EPS is positive
                pe_ratio = current_price / rolling_eps_value
                eps_metrics['P/E Ratio'] = f"{pe_ratio:.2f}"
            else:
                eps_metrics['P/E Ratio'] = 'N/A (Negative EPS)'
        else:
            eps_metrics['P/E Ratio'] = 'N/A'
            
        return eps_metrics
        
    except Exception as e:
        return {'Error': str(e)}

def identify_elliott_waves(data, window=20):
    """
    Identify Elliott Wave patterns in price data
    Returns wave pattern and potential buy signals
    """
    try:
        # Get closing prices
        closes = data['Close']
        
        # Initialize wave tracking
        waves = []
        wave_points = []
        current_trend = None
        last_extreme = closes.iloc[0]
        wave_count = 0
        
        # Find local maxima and minima using rolling window
        for i in range(window, len(closes)-window):
            # Check if current point is a peak or trough
            window_left = closes.iloc[i-window:i]
            window_right = closes.iloc[i:i+window]
            current_price = closes.iloc[i]
            
            is_peak = current_price > max(window_left) and current_price > max(window_right)
            is_trough = current_price < min(window_left) and current_price < min(window_right)
            
            if is_peak or is_trough:
                # Determine trend
                if current_trend is None:
                    current_trend = 'up' if is_trough else 'down'
                    wave_points.append((i, current_price))
                    waves.append(('1' if current_trend == 'up' else 'A', i, current_price))
                    wave_count = 1
                else:
                    # Check if trend has changed
                    if (current_trend == 'up' and is_peak) or (current_trend == 'down' and is_trough):
                        wave_count += 1
                        wave_points.append((i, current_price))
                        
                        # Label waves
                        if current_trend == 'up':
                            if wave_count <= 5:
                                waves.append((str(wave_count), i, current_price))
                            if wave_count == 5:
                                current_trend = 'down'
                                wave_count = 0
                        else:  # downtrend
                            waves.append((chr(ord('A') + wave_count - 1), i, current_price))
                            if wave_count == 3:
                                current_trend = 'up'
                                wave_count = 0
        
        # Analyze wave pattern for buy signals
        buy_signals = []
        if len(waves) >= 3:
            # Look for end of corrective wave (wave C)
            for i in range(len(waves)-1):
                if waves[i][0] == 'C':
                    buy_signals.append(f"Potential buy signal: End of corrective wave C at price ${waves[i][2]:.2f}")
                
            # Look for wave 2 completion (start of wave 3)
            for i in range(len(waves)-1):
                if waves[i][0] == '2' and waves[i+1][0] == '3':
                    buy_signals.append(f"Strong buy signal: Wave 2 completed, Wave 3 starting at ${waves[i][2]:.2f}")
        
        return waves, buy_signals
        
    except Exception as e:
        return [], [f"Error in Elliott Wave analysis: {str(e)}"]

def analyze_combined_signals(rsi, macd_line, signal_line, ma10, ma25, waves, current_price):
    """
    Combine Elliott Wave analysis with other technical indicators
    to generate stronger trading signals
    """
    signals = []
    signal_strength = 0  # Track the overall signal strength
    
    # 1. Check Elliott Wave patterns
    if waves:
        last_wave = waves[-1][0]
        last_wave_price = waves[-1][2]
        
        # Look for Wave 2 completion (potential start of Wave 3)
        if last_wave == '2':
            signals.append("Elliott Wave: Wave 2 completed, potential start of Wave 3 (Strong Buy)")
            signal_strength += 2
        # Look for end of corrective Wave C
        elif last_wave == 'C':
            signals.append("Elliott Wave: Corrective Wave C completed (Potential Buy)")
            signal_strength += 1
    
    # 2. Analyze RSI conditions
    if rsi <= 30:
        signals.append(f"RSI: Oversold at {rsi:.2f} (Buy Signal)")
        signal_strength += 1
    elif rsi <= 40:
        signals.append(f"RSI: Approaching oversold at {rsi:.2f} (Watch)")
    elif rsi >= 70:
        signals.append(f"RSI: Overbought at {rsi:.2f} (Caution)")
        signal_strength -= 1
    
    # 3. Check MACD signals
    if macd_line > signal_line:
        if macd_line < 0 and signal_line < 0:  # Both lines below zero
            signals.append("MACD: Bullish crossover below zero (Strong Buy)")
            signal_strength += 2
        else:
            signals.append("MACD: Bullish crossover (Buy)")
            signal_strength += 1
    
    # 4. Analyze Moving Averages
    if ma10 > ma25:
        signals.append("MA: Golden Cross formation (Bullish)")
        signal_strength += 1
    elif ma10 < ma25:
        signals.append("MA: Death Cross formation (Bearish)")
        signal_strength -= 1
    
    # Generate combined signal recommendation
    if signal_strength >= 3:
        recommendation = "STRONG BUY - Multiple indicators showing positive signals"
    elif signal_strength >= 1:
        recommendation = "BUY - Some positive indicators present"
    elif signal_strength == 0:
        recommendation = "NEUTRAL - Mixed or unclear signals"
    elif signal_strength >= -2:
        recommendation = "HOLD - Some negative indicators present"
    else:
        recommendation = "SELL/AVOID - Multiple negative indicators"
    
    return {
        'signals': signals,
        'recommendation': recommendation,
        'signal_strength': signal_strength
    }

def get_fmp_dcf(ticker_symbol, current_market_price):
    """
    Get DCF valuation and intrinsic value from Financial Modeling Prep API.
    Uses actual market price from Yahoo Finance for accuracy.
    """
    try:
        print(f"\nDebug: Fetching valuations for {ticker_symbol}")
        
        # Get intrinsic value first
        intrinsic_url = f"{FMP_BASE_URL}/company-fair-value/{ticker_symbol}?apikey={FMP_API_KEY}"
        intrinsic_response = requests.get(intrinsic_url)
        print(f"Debug: Intrinsic Value API Status Code: {intrinsic_response.status_code}")
        
        intrinsic_value = None
        if intrinsic_response.status_code == 200:
            intrinsic_data = intrinsic_response.json()
            print(f"Debug: Intrinsic Value Data: {json.dumps(intrinsic_data, indent=2)}")
            if intrinsic_data:
                intrinsic_value = intrinsic_data[0].get('intrinsicValue', None)
        
        # Get DCF value
        url = f"{FMP_BASE_URL}/discounted-cash-flow/{ticker_symbol}?apikey={FMP_API_KEY}"
        response = requests.get(url)
        print(f"Debug: DCF API Status Code: {response.status_code}")
        
        if response.status_code != 200:
            print(f"Debug: DCF API Error - {response.text}")
            return None
        
        dcf_data = response.json()
        print(f"Debug: DCF Data: {json.dumps(dcf_data, indent=2)}")
        
        if not dcf_data:
            print("Debug: No DCF data returned")
            return None
            
        current_data = dcf_data[0]
        dcf_value = current_data.get('dcf', 0)
        
        print(f"Debug: DCF Value: ${dcf_value}, Intrinsic Value: ${intrinsic_value if intrinsic_value else 'N/A'}, Current Market Price: ${current_market_price}")
        
        # Check for large discrepancy (more than 50% difference)
        price_discrepancy = abs(dcf_value - current_market_price) / current_market_price if current_market_price > 0 else float('inf')
        print(f"Debug: Price Discrepancy: {price_discrepancy:.2%}")
        
        if price_discrepancy > 0.5:  # If DCF differs by more than 50% from current price
            print("Debug: Large price discrepancy detected, trying enterprise value approach")
            # Try enterprise value approach instead
            ev_url = f"{FMP_BASE_URL}/enterprise-values/{ticker_symbol}?limit=1&apikey={FMP_API_KEY}"
            ev_response = requests.get(ev_url)
            print(f"Debug: EV API Status Code: {ev_response.status_code}")
            
            if ev_response.status_code == 200:
                ev_data = ev_response.json()
                print(f"Debug: EV Data: {json.dumps(ev_data, indent=2)}")
                
                if ev_data:
                    ev = ev_data[0]
                    # Calculate implied share price using EV/EBITDA method
                    enterprise_value = ev.get('enterpriseValue', 0)
                    market_cap = ev.get('marketCapitalization', 0)
                    shares = ev.get('numberOfShares', 0)
                    
                    print(f"Debug: EV: ${enterprise_value/1e9:.2f}B, Market Cap: ${market_cap/1e9:.2f}B, Shares: {shares}")
                    
                    if shares > 0:
                        implied_price = market_cap / shares
                        return {
                            'DCF Value': f"${implied_price:.2f}",
                            'Intrinsic Value': f"${intrinsic_value:.2f}" if intrinsic_value else 'N/A',
                            'Current Price': f"${current_market_price:.2f}",
                            'Valuation Method': 'Enterprise Value',
                            'Enterprise Value': f"${enterprise_value/1e9:.2f}B",
                            'Market Cap': f"${market_cap/1e9:.2f}B"
                        }
        
        # Get historical DCF for trend analysis
        historical_url = f"{FMP_BASE_URL}/historical-discounted-cash-flow/{ticker_symbol}?period=quarter&apikey={FMP_API_KEY}"
        historical_response = requests.get(historical_url)
        print(f"Debug: Historical DCF API Status Code: {historical_response.status_code}")
        historical_dcf = historical_response.json() if historical_response.status_code == 200 else []
        
        return {
            'DCF Value': f"${dcf_value:.2f}",
            'Intrinsic Value': f"${intrinsic_value:.2f}" if intrinsic_value else 'N/A',
            'Current Price': f"${current_market_price:.2f}",
            'Valuation Method': 'DCF',
            'Historical DCF': historical_dcf[:4] if historical_dcf else []  # Last 4 quarters
        }
    except Exception as e:
        print(f"Debug: Error in get_fmp_dcf: {str(e)}")
        return None

def get_tech_metrics(ticker_symbol):
    """
    Get additional metrics relevant for tech companies
    """
    try:
        # Get key metrics
        url = f"{FMP_BASE_URL}/key-metrics/{ticker_symbol}?limit=1&apikey={FMP_API_KEY}"
        response = requests.get(url)
        if response.status_code != 200:
            return None
            
        metrics = response.json()
        if not metrics:
            return None
            
        # Get growth metrics
        growth_url = f"{FMP_BASE_URL}/financial-growth/{ticker_symbol}?apikey={FMP_API_KEY}"
        growth_response = requests.get(growth_url)
        growth_data = growth_response.json() if growth_response.status_code == 200 else []
        
        return {
            'key_metrics': metrics[0],
            'growth_metrics': growth_data[0] if growth_data else None
        }
    except Exception as e:
        print(f"Error fetching tech metrics: {str(e)}")
        return None

def get_peer_comparison(ticker_symbol):
    """
    Get peer comparison data
    """
    try:
        # Get peer companies
        url = f"{FMP_BASE_URL}/stock-peers?symbol={ticker_symbol}&apikey={FMP_API_KEY}"
        response = requests.get(url)
        if response.status_code != 200:
            return None
            
        peers = response.json()
        if not peers:
            return None
            
        peer_metrics = []
        for peer in peers[:5]:  # Limit to 5 peers to avoid rate limits
            metrics = get_tech_metrics(peer)
            if metrics:
                peer_metrics.append({
                    'symbol': peer,
                    'metrics': metrics
                })
                
        return peer_metrics
    except Exception as e:
        print(f"Error fetching peer comparison: {str(e)}")
        return None

def analyze_growth_potential(ticker_symbol, tech_metrics):
    """
    Analyze growth potential specifically for tech companies
    """
    if not tech_metrics or 'growth_metrics' not in tech_metrics:
        return None
        
    growth = tech_metrics['growth_metrics']
    
    analysis = {
        'revenue_growth': growth.get('revenueGrowth', 0) * 100,
        'eps_growth': growth.get('epsgrowth', 0) * 100,
        'r_and_d_growth': growth.get('rdexpenseGrowth', 0) * 100 if 'rdexpenseGrowth' in growth else None,
        'fcf_growth': growth.get('freeCashFlowGrowth', 0) * 100
    }
    
    # Calculate growth score (0-100)
    growth_factors = [v for v in analysis.values() if v is not None]
    if growth_factors:
        analysis['growth_score'] = min(100, sum(growth_factors) / len(growth_factors))
    else:
        analysis['growth_score'] = None
        
    return analysis

def calculate_intrinsic_value(ticker_symbol, current_market_price, ticker):
    """
    Calculate intrinsic value using multiple methods:
    1. DCF from FMP
    2. Dividend Discount Model (if applicable)
    3. Asset-based valuation
    4. Comparable company analysis
    """
    try:
        # Get financial data
        info = ticker.info
        balance_sheet = ticker.balance_sheet
        
        valuations = {}
        
        # 1. Get DCF value from FMP
        dcf_url = f"{FMP_BASE_URL}/discounted-cash-flow/{ticker_symbol}?apikey={FMP_API_KEY}"
        dcf_response = requests.get(dcf_url)
        if dcf_response.status_code == 200:
            dcf_data = dcf_response.json()
            if dcf_data:
                valuations['DCF'] = dcf_data[0].get('dcf', 0)
        
        # 2. Dividend Discount Model (if company pays dividends)
        dividend_yield = info.get('dividendYield', 0)
        if dividend_yield > 0:
            try:
                annual_dividend = current_market_price * dividend_yield
                cost_of_equity = info.get('beta', 1) * 0.06 + 0.02  # Simple CAPM
                growth_rate = info.get('earningsGrowth', 0.03)  # Use earnings growth or default to 3%
                
                # Gordon Growth Model
                ddm_value = annual_dividend * (1 + growth_rate) / (cost_of_equity - growth_rate)
                valuations['DDM'] = ddm_value
            except:
                valuations['DDM'] = None
        
        # 3. Asset-based valuation
        if not balance_sheet.empty:
            try:
                total_assets = balance_sheet.loc['Total Assets'].iloc[0]
                total_liabilities = balance_sheet.loc['Total Liabilities'].iloc[0]
                shares_outstanding = info.get('sharesOutstanding', 0)
                
                if shares_outstanding > 0:
                    book_value_per_share = (total_assets - total_liabilities) / shares_outstanding
                    valuations['Asset-Based'] = book_value_per_share
            except:
                valuations['Asset-Based'] = None
        
        # 4. Get comparable company analysis from FMP
        peers_url = f"{FMP_BASE_URL}/stock-peers?symbol={ticker_symbol}&apikey={FMP_API_KEY}"
        peers_response = requests.get(peers_url)
        if peers_response.status_code == 200:
            peers = peers_response.json()
            if peers:
                peer_pes = []
                for peer in peers[:5]:  # Use top 5 peers
                    metrics_url = f"{FMP_BASE_URL}/key-metrics/{peer}?limit=1&apikey={FMP_API_KEY}"
                    metrics_response = requests.get(metrics_url)
                    if metrics_response.status_code == 200:
                        metrics_data = metrics_response.json()
                        if metrics_data:
                            pe = metrics_data[0].get('peRatio', None)
                            if pe and pe > 0:
                                peer_pes.append(pe)
                
                if peer_pes:
                    avg_pe = sum(peer_pes) / len(peer_pes)
                    eps = info.get('trailingEps', 0)
                    if eps:
                        valuations['Comparable'] = avg_pe * eps
        
        # Calculate weighted average intrinsic value
        valid_values = [v for v in valuations.values() if v and v > 0]
        if valid_values:
            avg_intrinsic_value = sum(valid_values) / len(valid_values)
            valuations['Average'] = avg_intrinsic_value
            
            # Calculate margin of safety
            if current_market_price > 0:
                margin_of_safety = ((avg_intrinsic_value - current_market_price) / current_market_price) * 100
                valuations['Margin of Safety'] = f"{margin_of_safety:.1f}%"
        
        return valuations
        
    except Exception as e:
        print(f"Error calculating intrinsic value: {str(e)}")
        return None

def get_stock_info(ticker_symbol):
    """
    Fetch comprehensive stock information for a given ticker symbol
    """
    try:
        # Create ticker object with no caching
        ticker = yf.Ticker(ticker_symbol)
        
        # Clear any existing cache
        import shutil
        cache_dir = os.path.expanduser('~/.cache/yfinance')
        if os.path.exists(cache_dir):
            try:
                shutil.rmtree(cache_dir)
            except:
                pass
        
        # Try different approaches to get historical data
        hist = None
        
        # Method 1: Try with different periods and intervals
        periods_to_try = ['3mo', '2mo', '1mo', '1y']
        for period in periods_to_try:
            try:
                print(f"Trying to fetch {period} of data for {ticker_symbol}...")
                hist = ticker.history(period=period, interval='1d', auto_adjust=True, prepost=False, repair=True)
                if len(hist) >= 5:
                    print(f"Successfully fetched {len(hist)} days of data")
                    break
                else:
                    print(f"Only got {len(hist)} days, trying next period...")
            except Exception as e:
                print(f"Failed with period {period}: {str(e)}")
                continue
        
        # Method 2: If still no data, try with download function
        if hist is None or len(hist) < 5:
            try:
                print("Trying alternative download method...")
                from datetime import datetime, timedelta
                end_date = datetime.now()
                start_date = end_date - timedelta(days=90)
                hist = yf.download(ticker_symbol, start=start_date, end=end_date, progress=False, auto_adjust=True)
                if len(hist) >= 5:
                    print(f"Alternative method successful: {len(hist)} days of data")
            except Exception as e:
                print(f"Alternative method failed: {str(e)}")
        
        # Method 3: Try with Ticker.history with different parameters
        if hist is None or len(hist) < 5:
            try:
                print("Trying with basic parameters...")
                hist = ticker.history(period='1mo')
                if len(hist) >= 5:
                    print(f"Basic method successful: {len(hist)} days of data")
            except Exception as e:
                print(f"Basic method failed: {str(e)}")
        
        if hist is None or len(hist) < 5:
            return f"Error: Unable to fetch sufficient historical data for {ticker_symbol}. This could be due to:\n" + \
                   "1. Network connectivity issues\n" + \
                   "2. Yahoo Finance API temporary issues\n" + \
                   "3. Invalid ticker symbol\n" + \
                   "4. Market closure (try again during market hours)\n" + \
                   f"Please verify the ticker symbol '{ticker_symbol}' is correct and try again later."
            
        # Get stock info directly
        info = ticker.fast_info
        
        # Get current price from Yahoo Finance
        current_price = hist['Close'].iloc[-1]
        
        # Calculate technical indicators (adjusted for available data)
        if len(hist) >= 14:
            rsi = calculate_rsi(hist)
            current_rsi = rsi.iloc[-1]
        else:
            current_rsi = None
            
        if len(hist) >= 26:
            macd_line, signal_line, macd_hist = calculate_macd(hist)
        else:
            macd_line = signal_line = macd_hist = None
            
        if len(hist) >= 25:
            ma10, ma25 = calculate_moving_averages(hist)
        else:
            ma10 = ma25 = None
            
        # Calculate 20-day moving average and sell decision
        if len(hist) >= 20:
            ma20 = calculate_20_day_ma(hist)
            sell_analysis = should_sell_stock(hist, threshold_percent=5.0, consecutive_days=1)
        else:
            ma20 = None
            sell_analysis = None
        
        # Get Elliott Wave analysis if enough data
        if len(hist) >= 40:
            waves, buy_signals = identify_elliott_waves(hist)
        else:
            waves, buy_signals = [], []
        
        # Get combined technical analysis if we have enough data
        if all([current_rsi, macd_line, signal_line, ma10, ma25]):
            combined_analysis = analyze_combined_signals(
                current_rsi, macd_line, signal_line, ma10, ma25, waves, current_price
            )
        else:
            combined_analysis = {
                'signals': ["Insufficient historical data for complete technical analysis"],
                'recommendation': "NEUTRAL - Limited data available",
                'signal_strength': 0
            }
        
        # Get DCF valuation from FMP using current market price
        dcf_data = get_fmp_dcf(ticker_symbol, current_price)
        
        # Get tech metrics separately
        tech_metrics = get_tech_metrics(ticker_symbol)
        
        # Calculate EPS metrics
        eps_metrics = calculate_eps_metrics(ticker)
        
        # Get previous day's close
        prev_close = hist['Close'].iloc[-2] if len(hist) > 1 else current_price
        daily_change = current_price - prev_close
        daily_change_percent = (daily_change / prev_close) * 100
        
        # Get additional info directly
        try:
            additional_info = ticker.get_info()
        except:
            additional_info = {}
        
        # Compile stock information
        stock_data = {
            "Company Name": additional_info.get('longName', ticker_symbol.upper()),
            "Sector": additional_info.get('sector', 'N/A'),
            "Current Price": f"${current_price:.2f}",
            "Daily Change": f"${daily_change:.2f} ({daily_change_percent:.2f}%)",
            "DCF Analysis": dcf_data,
            "Technical Analysis": combined_analysis['signals'],
            "Overall Signal": combined_analysis['recommendation'],
            **eps_metrics,  # Add all EPS metrics
            "RSI (14-day)": f"{current_rsi:.2f}" if current_rsi is not None else 'N/A',
            "MACD": f"{macd_line:.2f}" if macd_line is not None else 'N/A',
            "MACD Signal": f"{signal_line:.2f}" if signal_line is not None else 'N/A',
            "MACD Hist": f"{macd_hist:.2f}" if macd_hist is not None else 'N/A',
            "MA (10-day)": f"${ma10:.2f}" if ma10 is not None else 'N/A',
            "MA (20-day)": f"${ma20:.2f}" if ma20 is not None else 'N/A',
            "MA (25-day)": f"${ma25:.2f}" if ma25 is not None else 'N/A',
            "Sell Analysis": sell_analysis,
            "Forward P/E": additional_info.get('forwardPE', 'N/A'),
            "52 Week High": additional_info.get('fiftyTwoWeekHigh', max(hist['High']) if len(hist) > 0 else 'N/A'),
            "52 Week Low": additional_info.get('fiftyTwoWeekLow', min(hist['Low']) if len(hist) > 0 else 'N/A'),
            "Target Price": additional_info.get('targetMeanPrice', 'N/A'),
            "Recommendation": additional_info.get('recommendationKey', 'N/A'),
            "Beta": additional_info.get('beta', 'N/A')
        }
        
        # Add tech metrics if available
        if tech_metrics and 'key_metrics' in tech_metrics:
            metrics = tech_metrics['key_metrics']
            stock_data.update({
                "Market Cap": f"${metrics.get('marketCap', 0)/1e9:.2f}B" if metrics.get('marketCap') else 'N/A',
                "R&D to Revenue": f"{metrics.get('researchAndDevelopementToRevenue', 0):.2%}",
                "Operating Cash Flow to Revenue": f"{metrics.get('operatingCashFlowToRevenue', 0):.2%}",
                "ROIC": f"{metrics.get('roic', 0):.2%}"
            })
        
        # Add growth analysis if available
        growth_analysis = analyze_growth_potential(ticker_symbol, tech_metrics)
        if growth_analysis:
            stock_data['Growth Analysis'] = growth_analysis
        
        # Add peer comparison if available
        peer_data = get_peer_comparison(ticker_symbol)
        if peer_data:
            stock_data['Peer Comparison'] = peer_data
        
        # Calculate intrinsic value
        intrinsic_value = calculate_intrinsic_value(ticker_symbol, current_price, ticker)
        if intrinsic_value:
            stock_data['Intrinsic Value'] = intrinsic_value
        
        return stock_data
        
    except Exception as e:
        return f"Error fetching data: {str(e)}"

def display_stock_info(ticker_symbol):
    """
    Display formatted stock information
    """
    stock_data = get_stock_info(ticker_symbol)
    
    if isinstance(stock_data, str):
        print(stock_data)
        return
        
    print("\n" + "="*50)
    print(f"Stock Information for {stock_data['Company Name']} ({ticker_symbol.upper()})")
    print("="*50)
    
    # Display Intrinsic Value Analysis first
    print("\nIntrinsic Value Analysis:")
    print("-" * 30)
    if isinstance(stock_data.get("Intrinsic Value"), dict):
        intrinsic = stock_data["Intrinsic Value"]
        print("Valuation Methods:")
        for method, value in intrinsic.items():
            if method != 'Margin of Safety':
                print(f"{method:15}: ${value:.2f}" if isinstance(value, (int, float)) else f"{method:15}: {value}")
        
        if 'Margin of Safety' in intrinsic:
            print(f"\nMargin of Safety: {intrinsic['Margin of Safety']}")
            
        print(f"Current Price: ${stock_data['Current Price']}")
    
    # Display DCF Analysis first
    print("\nValuation Analysis:")
    print("-" * 30)
    if isinstance(stock_data["DCF Analysis"], dict):
        dcf = stock_data["DCF Analysis"]
        print(f"Valuation Method: {dcf.get('Valuation Method', 'DCF')}")
        print(f"DCF Value: {dcf['DCF Value']}")
        print(f"Intrinsic Value: {dcf['Intrinsic Value']}")
        print(f"Current Price: {dcf['Current Price']}")
        
        if dcf.get('Enterprise Value'):
            print(f"Enterprise Value: {dcf['Enterprise Value']}")
            print(f"Market Cap: {dcf['Market Cap']}")
        
        if dcf.get('Historical DCF') and dcf['Valuation Method'] == 'DCF':
            print("\nHistorical DCF (Last 4 quarters):")
            for hist in dcf['Historical DCF']:
                print(f"Date: {hist['date']}, DCF: ${hist['dcf']:.2f}")
    
    # Display Technical Analysis
    print("\nTechnical Analysis:")
    print("-" * 30)
    for signal in stock_data["Technical Analysis"]:
        print(f"• {signal}")
    print(f"\nOVERALL SIGNAL: {stock_data['Overall Signal']}")
    
    # Display EPS metrics
    eps_keys = ["Basic EPS", "Rolling EPS", "EPS Growth", "P/E Ratio"]
    print("\nEPS Metrics:")
    print("-" * 30)
    for key in eps_keys:
        if key in stock_data:
            print(f"{key:15}: {stock_data[key]}")
    
    # Display 20-Day MA Sell Analysis prominently
    if "Sell Analysis" in stock_data and stock_data["Sell Analysis"]:
        sell_data = stock_data["Sell Analysis"]
        print("\n20-Day Moving Average Sell Analysis:")
        print("-" * 40)
        print(f"Current Price: ${sell_data['current_price']:.2f}")
        print(f"20-Day MA: ${sell_data['ma_20']:.2f}")
        print(f"Drop from MA: {sell_data['drop_percentage']:.2f}%")
        print(f"Threshold: {sell_data['threshold_percent']:.1f}%")
        print(f"SELL DECISION: {'YES' if sell_data['sell_decision'] else 'NO'}")
        print(f"RECOMMENDATION: {sell_data['recommendation']}")
        print(f"Reason: {sell_data['reason']}")

    # Display technical indicators
    tech_keys = ["RSI (14-day)", "MACD", "MACD Signal", "MACD Hist", "MA (10-day)", "MA (20-day)", "MA (25-day)"]
    print("\nTechnical Indicators:")
    print("-" * 30)
    for key in tech_keys:
        if key in stock_data:
            print(f"{key:15}: {stock_data[key]}")
    
    print("\nFundamental Data:")
    print("-" * 30)
    for key, value in stock_data.items():
        if (key != "Company Name" and key not in tech_keys and 
            key not in eps_keys and key not in ["Technical Analysis", "Overall Signal", "DCF Analysis"]):
            print(f"{key:15}: {value}")
    print("="*50 + "\n")

def check_sell_decision(ticker_symbol, threshold_percent=5.0, consecutive_days=1):
    """
    Quick function to check if a stock should be sold based on 20-day MA strategy
    
    Parameters:
    - ticker_symbol: Stock ticker symbol (e.g., 'AAPL', 'TSLA')
    - threshold_percent: Percentage below 20-DMA to trigger sell signal (default 5%)
    - consecutive_days: Number of consecutive days below threshold (default 1)
    
    Returns:
    - Dictionary with sell decision and analysis
    """
    try:
        # Create ticker object
        ticker = yf.Ticker(ticker_symbol)
        
        # Get historical data (need at least 20 days for 20-day MA)
        hist = ticker.history(period='2mo', auto_adjust=False)
        
        if len(hist) < 20:
            return {
                'error': f'Insufficient data for {ticker_symbol}. Need at least 20 days of historical data.',
                'sell_decision': False
            }
        
        # Get sell analysis
        sell_analysis = should_sell_stock(hist, threshold_percent, consecutive_days)
        
        # Add ticker symbol to result
        sell_analysis['ticker'] = ticker_symbol.upper()
        
        return sell_analysis
        
    except Exception as e:
        return {
            'error': f'Error analyzing {ticker_symbol}: {str(e)}',
            'sell_decision': False
        }

def test_yfinance_connection():
    """
    Test yfinance connection and diagnose issues
    """
    print("Testing yfinance connection and functionality...")
    print("-" * 50)
    
    # Test 1: Check yfinance version
    try:
        import yfinance as yf
        print(f"✓ yfinance version: {yf.__version__}")
    except Exception as e:
        print(f"✗ yfinance import failed: {e}")
        return
    
    # Test 2: Test network connectivity
    try:
        import requests
        response = requests.get("https://finance.yahoo.com", timeout=10)
        print(f"✓ Yahoo Finance connectivity: {response.status_code}")
    except Exception as e:
        print(f"✗ Network connectivity issue: {e}")
    
    # Test 3: Try simple ticker
    test_tickers = ['MSFT', 'GOOGL', 'TSLA', 'AAPL']
    for ticker_symbol in test_tickers:
        try:
            ticker = yf.Ticker(ticker_symbol)
            hist = ticker.history(period='5d')
            if len(hist) > 0:
                print(f"✓ {ticker_symbol}: {len(hist)} days, latest: ${hist['Close'].iloc[-1]:.2f}")
                return ticker_symbol  # Return first working ticker
            else:
                print(f"✗ {ticker_symbol}: No data returned")
        except Exception as e:
            print(f"✗ {ticker_symbol}: {str(e)[:50]}...")
    
    print("\n⚠️  All test tickers failed. Possible issues:")
    print("   1. Network/firewall blocking Yahoo Finance")
    print("   2. Yahoo Finance API temporarily down")
    print("   3. yfinance library compatibility issue")
    print("   4. System clock/timezone issues")
    
    return None

def print_sell_analysis(ticker_symbol, threshold_percent=5.0, consecutive_days=1):
    """
    Print formatted sell analysis for a stock
    """
    print(f"\n{'='*50}")
    print(f"SELL DECISION ANALYSIS FOR {ticker_symbol.upper()}")
    print(f"{'='*50}")
    
    result = check_sell_decision(ticker_symbol, threshold_percent, consecutive_days)
    
    if 'error' in result:
        print(f"Error: {result['error']}")
        return
    
    print(f"\nStock: {result['ticker']}")
    print(f"Current Price: ${result['current_price']:.2f}")
    print(f"20-Day Moving Average: ${result['ma_20']:.2f}")
    print(f"Drop from 20-DMA: {result['drop_percentage']:.2f}%")
    print(f"Sell Threshold: {result['threshold_percent']:.1f}%")
    
    if result['consecutive_days_required'] > 1:
        print(f"Consecutive Days Required: {result['consecutive_days_required']}")
        print(f"Consecutive Days Met: {result['consecutive_days_met']}")
    
    print(f"\n{'SELL DECISION:':<20} {'YES' if result['sell_decision'] else 'NO'}")
    print(f"{'RECOMMENDATION:':<20} {result['recommendation']}")
    print(f"{'REASON:':<20} {result['reason']}")
    
    print(f"\n{'='*50}")

if __name__ == "__main__":
    import sys
    
    # Check if user wants to test yfinance connection
    if len(sys.argv) >= 2 and sys.argv[1].lower() == '--test':
        working_ticker = test_yfinance_connection()
        if working_ticker:
            print(f"\n✓ yfinance is working! Try: python3 stock-info.py {working_ticker}")
        else:
            print("\n✗ yfinance connection issues detected.")
        sys.exit(0)
    
    # Check if user wants sell analysis only
    elif len(sys.argv) >= 2 and sys.argv[1].lower() == '--sell':
        if len(sys.argv) < 3:
            print("Usage for sell analysis: python stock_info.py --sell <ticker_symbol> [threshold_percent] [consecutive_days]")
            print("Example: python stock_info.py --sell AAPL 5.0 1")
            sys.exit(1)
        
        ticker_symbol = sys.argv[2].upper()
        threshold_percent = float(sys.argv[3]) if len(sys.argv) > 3 else 5.0
        consecutive_days = int(sys.argv[4]) if len(sys.argv) > 4 else 1
        
        print_sell_analysis(ticker_symbol, threshold_percent, consecutive_days)
        
    elif len(sys.argv) == 2:
        # Original full analysis
        ticker_symbol = sys.argv[1].upper()
        display_stock_info(ticker_symbol)
    else:
        print("Usage:")
        print("  Test connection: python3 stock-info.py --test")
        print("  Full analysis: python3 stock-info.py <ticker_symbol>")
        print("  Sell analysis: python3 stock-info.py --sell <ticker_symbol> [threshold_percent] [consecutive_days]")
        print("\nExamples:")
        print("  python3 stock-info.py --test")
        print("  python3 stock-info.py AAPL")
        print("  python3 stock-info.py --sell AAPL 5.0 1")
        print("  python3 stock-info.py --sell TSLA 7.5 2")
        sys.exit(1)
