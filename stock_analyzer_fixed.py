#!/usr/bin/env python3.7
"""
Fixed Stock Analyzer with 20-Day Moving Average Sell Decision
Handles yfinance rate limiting and provides fallback options
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import sys
import os

def calculate_20_day_ma(data):
    """Calculate 20-day moving average"""
    return data['Close'].rolling(window=20).mean().iloc[-1]

def should_sell_stock(data, threshold_percent=5.0, consecutive_days=1):
    """
    Determine if stock should be sold based on 20-day moving average strategy
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

def try_fetch_with_delays(ticker_symbol, max_retries=3):
    """
    Try to fetch data with increasing delays to handle rate limiting
    """
    import yfinance as yf
    
    # Clear cache
    try:
        import shutil
        cache_dir = os.path.expanduser('~/.cache/yfinance')
        if os.path.exists(cache_dir):
            shutil.rmtree(cache_dir)
    except:
        pass
    
    delays = [2, 5, 10]  # Increasing delays in seconds
    
    for attempt in range(max_retries):
        try:
            print(f"Attempt {attempt + 1}/{max_retries}: Fetching {ticker_symbol} data...")
            
            if attempt > 0:
                delay = delays[min(attempt - 1, len(delays) - 1)]
                print(f"Waiting {delay} seconds to avoid rate limiting...")
                time.sleep(delay)
            
            # Try different approaches
            ticker = yf.Ticker(ticker_symbol)
            
            # Method 1: Try 1 month period
            hist = ticker.history(period='1mo', interval='1d')
            if len(hist) >= 20:
                print(f"✓ Success! Fetched {len(hist)} days of data")
                return hist, True
            
            # Method 2: Try 3 months if 1 month failed
            time.sleep(2)
            hist = ticker.history(period='3mo', interval='1d')
            if len(hist) >= 20:
                print(f"✓ Success! Fetched {len(hist)} days of data")
                return hist, True
                
            # Method 3: Try download function
            time.sleep(2)
            end_date = datetime.now()
            start_date = end_date - timedelta(days=60)
            hist = yf.download(ticker_symbol, start=start_date, end=end_date, progress=False)
            if len(hist) >= 20:
                print(f"✓ Success! Fetched {len(hist)} days of data")
                return hist, True
                
            print(f"✗ Attempt {attempt + 1} failed: Only got {len(hist)} days")
            
        except Exception as e:
            print(f"✗ Attempt {attempt + 1} error: {str(e)[:100]}...")
            if attempt < max_retries - 1:
                time.sleep(delays[min(attempt, len(delays) - 1)])
    
    return None, False

def create_sample_data(ticker_symbol):
    """Create realistic sample data when yfinance fails"""
    print(f"Creating sample data for {ticker_symbol} (yfinance unavailable)")
    
    # Base prices for different stocks
    base_prices = {
        'AAPL': 190.50, 'MSFT': 378.85, 'GOOGL': 138.45, 'TSLA': 248.50,
        'NVDA': 445.30, 'AMZN': 148.75, 'META': 342.20, 'NFLX': 425.60
    }
    
    start_price = base_prices.get(ticker_symbol, 100.0)
    dates = pd.date_range(start=datetime.now() - timedelta(days=30), periods=30, freq='D')
    
    # Create realistic declining pattern (to demonstrate sell signal)
    prices = []
    current_price = start_price
    
    for i in range(30):
        if i < 10:  # First 10 days: slight uptrend
            daily_change = np.random.normal(0.002, 0.012)
        elif i < 20:  # Days 10-20: sideways
            daily_change = np.random.normal(-0.001, 0.015)
        else:  # Last 10 days: decline (triggers sell signal)
            daily_change = np.random.normal(-0.006, 0.018)
        
        current_price *= (1 + daily_change)
        prices.append(current_price)
    
    # Create DataFrame
    data = pd.DataFrame({
        'Open': [p * np.random.uniform(0.99, 1.01) for p in prices],
        'High': [p * np.random.uniform(1.00, 1.02) for p in prices],
        'Low': [p * np.random.uniform(0.98, 1.00) for p in prices],
        'Close': prices,
        'Volume': [np.random.randint(1000000, 10000000) for _ in range(30)]
    }, index=dates)
    
    return data

def analyze_stock(ticker_symbol, threshold_percent=5.0, consecutive_days=1, use_sample=False):
    """
    Main analysis function
    """
    print("="*70)
    print(f"20-DAY MOVING AVERAGE SELL DECISION ANALYSIS")
    print(f"Stock: {ticker_symbol} | Threshold: {threshold_percent}%")
    print("="*70)
    
    if use_sample:
        print("Using sample data (demo mode)")
        data = create_sample_data(ticker_symbol)
        is_real_data = False
    else:
        # Try to fetch real data
        data, is_real_data = try_fetch_with_delays(ticker_symbol)
        
        if not is_real_data:
            print("\n⚠️  Real data fetch failed. Using sample data for demonstration.")
            data = create_sample_data(ticker_symbol)
    
    # Perform analysis
    result = should_sell_stock(data, threshold_percent, consecutive_days)
    
    # Display results
    print(f"\nData Source: {'Real Market Data' if is_real_data else 'Sample Data (Demo)'}")
    print(f"Analysis Period: {len(data)} days")
    print(f"Date Range: {data.index[0].strftime('%Y-%m-%d')} to {data.index[-1].strftime('%Y-%m-%d')}")
    
    if 'Insufficient data' in result['reason']:
        print(f"\n❌ Error: {result['reason']}")
        return
    
    print(f"\n📊 ANALYSIS RESULTS:")
    print(f"Current Price: ${result['current_price']:.2f}")
    print(f"20-Day Moving Average: ${result['ma_20']:.2f}")
    print(f"Drop from 20-DMA: {result['drop_percentage']:.2f}%")
    print(f"Sell Threshold: {result['threshold_percent']:.1f}%")
    
    if result['consecutive_days_required'] > 1:
        print(f"Consecutive Days Required: {result['consecutive_days_required']}")
        print(f"Consecutive Days Met: {result['consecutive_days_met']}")
    
    print(f"\n🎯 DECISION:")
    print(f"SELL SIGNAL: {'🔴 YES' if result['sell_decision'] else '🟢 NO'}")
    print(f"RECOMMENDATION: {result['recommendation']}")
    print(f"REASON: {result['reason']}")
    
    # Show recent trend
    print(f"\n📈 RECENT TREND (Last 5 days):")
    recent_data = data.tail(5)
    ma_20_series = data['Close'].rolling(window=20).mean()
    
    for i in range(len(recent_data)):
        date = recent_data.index[i].strftime('%Y-%m-%d')
        price = recent_data['Close'].iloc[i]
        ma_val = ma_20_series.iloc[-(5-i)]
        drop_pct = ((ma_val - price) / ma_val) * 100 if ma_val > 0 else 0
        status = "📉" if drop_pct >= threshold_percent else "📊" if drop_pct > 0 else "📈"
        print(f"  {date}: ${price:6.2f} | 20-DMA: ${ma_val:6.2f} | Drop: {drop_pct:5.2f}% {status}")
    
    print("="*70)
    
    if not is_real_data:
        print("\n💡 NOTE: This used sample data due to yfinance rate limiting.")
        print("   Try again in 10-15 minutes for real data, or use --sample for demo mode.")

def main():
    if len(sys.argv) < 2:
        print("Fixed Stock Analyzer with 20-Day MA Sell Decision")
        print("="*55)
        print("Usage: python3.7 stock_analyzer_fixed.py <TICKER> [threshold] [consecutive_days] [--sample]")
        print("\nExamples:")
        print("  python3.7 stock_analyzer_fixed.py AAPL")
        print("  python3.7 stock_analyzer_fixed.py AAPL 5.0")
        print("  python3.7 stock_analyzer_fixed.py TSLA 7.5 2")
        print("  python3.7 stock_analyzer_fixed.py NVDA 5.0 1 --sample")
        print("\nFlags:")
        print("  --sample    Use sample data (demo mode)")
        sys.exit(1)
    
    ticker = sys.argv[1].upper()
    threshold = float(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2] != '--sample' else 5.0
    consecutive_days = int(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3] != '--sample' else 1
    use_sample = '--sample' in sys.argv
    
    # Set seed for consistent sample data
    np.random.seed(42)
    
    analyze_stock(ticker, threshold, consecutive_days, use_sample)

if __name__ == "__main__":
    main()



