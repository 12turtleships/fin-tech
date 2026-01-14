#!/usr/bin/env python3
"""
Demo 20-Day Moving Average Sell Decision Tool
Works without yfinance - uses realistic sample data or CSV input
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os

def calculate_20_day_ma(data):
    """Calculate 20-day moving average"""
    return data['Close'].rolling(window=20).mean().iloc[-1]

def should_sell_stock_demo(data, threshold_percent=5.0, consecutive_days=1):
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

def create_realistic_stock_data(ticker, scenario='mixed'):
    """
    Create realistic stock data for demonstration
    """
    # Base prices for common stocks
    base_prices = {
        'AAPL': 190.50, 'MSFT': 378.85, 'GOOGL': 138.45, 'TSLA': 248.50,
        'NVDA': 445.30, 'AMZN': 148.75, 'META': 342.20, 'NFLX': 425.60,
        'AMD': 142.35, 'INTC': 23.45, 'CRM': 245.80, 'ORCL': 115.25
    }
    
    start_price = base_prices.get(ticker, 100.0)
    dates = pd.date_range(start=datetime.now() - timedelta(days=35), periods=35, freq='D')
    
    prices = []
    current_price = start_price
    
    # Create different scenarios
    if scenario == 'declining':
        # Stock in decline - should trigger sell
        for i in range(35):
            if i < 10:  # First 10 days: slight uptrend
                daily_change = np.random.normal(0.002, 0.015)
            elif i < 20:  # Days 10-20: sideways with volatility
                daily_change = np.random.normal(-0.001, 0.020)
            else:  # Last 15 days: clear decline
                daily_change = np.random.normal(-0.008, 0.018)
            
            current_price *= (1 + daily_change)
            prices.append(max(current_price, start_price * 0.75))  # Floor at 75% of start
            
    elif scenario == 'rising':
        # Stock in uptrend - should not trigger sell
        for i in range(35):
            daily_change = np.random.normal(0.004, 0.015)
            current_price *= (1 + daily_change)
            prices.append(min(current_price, start_price * 1.4))  # Cap at 140% of start
            
    else:  # mixed scenario
        # Realistic mixed pattern with recent weakness
        for i in range(35):
            if i < 15:  # First 15 days: uptrend
                daily_change = np.random.normal(0.003, 0.012)
            elif i < 25:  # Days 15-25: peak and start declining
                daily_change = np.random.normal(-0.002, 0.018)
            else:  # Last 10 days: accelerated decline
                daily_change = np.random.normal(-0.006, 0.020)
            
            current_price *= (1 + daily_change)
            prices.append(current_price)
    
    # Create realistic OHLC data
    data = []
    for i, close_price in enumerate(prices):
        # Generate realistic open, high, low based on close
        daily_volatility = abs(np.random.normal(0, 0.01))
        
        open_price = close_price * (1 + np.random.normal(0, 0.005))
        high_price = max(open_price, close_price) * (1 + daily_volatility)
        low_price = min(open_price, close_price) * (1 - daily_volatility)
        
        data.append({
            'Date': dates[i],
            'Open': round(open_price, 2),
            'High': round(high_price, 2),
            'Low': round(low_price, 2),
            'Close': round(close_price, 2),
            'Volume': np.random.randint(1000000, 15000000)
        })
    
    df = pd.DataFrame(data)
    df.set_index('Date', inplace=True)
    return df

def analyze_and_display(ticker, threshold=5.0, consecutive_days=1, scenario='mixed'):
    """
    Analyze stock and display results
    """
    print("="*65)
    print(f"20-DAY MOVING AVERAGE SELL DECISION ANALYSIS")
    print(f"Stock: {ticker} | Threshold: {threshold}% | Scenario: {scenario.title()}")
    print("="*65)
    
    # Generate data
    data = create_realistic_stock_data(ticker, scenario)
    
    print(f"Analysis Period: {len(data)} days")
    print(f"Date Range: {data.index[0].strftime('%Y-%m-%d')} to {data.index[-1].strftime('%Y-%m-%d')}")
    print(f"Starting Price: ${data['Close'].iloc[0]:.2f}")
    print(f"Current Price: ${data['Close'].iloc[-1]:.2f}")
    print(f"Total Change: {((data['Close'].iloc[-1] - data['Close'].iloc[0]) / data['Close'].iloc[0] * 100):+.2f}%")
    
    # Perform analysis
    result = should_sell_stock_demo(data, threshold, consecutive_days)
    
    if result['sell_decision'] is False and 'Insufficient data' in result['reason']:
        print(f"\nError: {result['reason']}")
        return
    
    print(f"\n📊 TECHNICAL ANALYSIS:")
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
    print(f"\n📈 RECENT 7-DAY TREND:")
    recent_data = data.tail(7)
    ma_20_series = data['Close'].rolling(window=20).mean()
    
    for i in range(len(recent_data)):
        date = recent_data.index[i].strftime('%m-%d')
        price = recent_data['Close'].iloc[i]
        ma_val = ma_20_series.iloc[-(7-i)]
        drop_pct = ((ma_val - price) / ma_val) * 100 if ma_val > 0 else 0
        status = "📉" if drop_pct > threshold else "📊" if drop_pct > 0 else "📈"
        print(f"  {date}: ${price:6.2f} | 20-DMA: ${ma_val:6.2f} | Drop: {drop_pct:5.2f}% {status}")
    
    print("="*65)

def main():
    """Main function"""
    if len(sys.argv) < 2:
        print("20-Day Moving Average Sell Decision Demo")
        print("="*50)
        print("Usage: python3 demo_sell_decision.py <TICKER> [threshold] [consecutive_days] [scenario]")
        print("\nExamples:")
        print("  python3 demo_sell_decision.py AAPL")
        print("  python3 demo_sell_decision.py AAPL 5.0")
        print("  python3 demo_sell_decision.py TSLA 7.5 2")
        print("  python3 demo_sell_decision.py NVDA 5.0 1 declining")
        print("\nScenarios: mixed (default), declining, rising")
        print("\nThis demo uses realistic sample data to demonstrate the algorithm.")
        sys.exit(1)
    
    ticker = sys.argv[1].upper()
    threshold = float(sys.argv[2]) if len(sys.argv) > 2 else 5.0
    consecutive_days = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    scenario = sys.argv[4].lower() if len(sys.argv) > 4 else 'mixed'
    
    if scenario not in ['mixed', 'declining', 'rising']:
        print("Error: Scenario must be 'mixed', 'declining', or 'rising'")
        sys.exit(1)
    
    # Set seed for consistent results
    np.random.seed(42)
    
    analyze_and_display(ticker, threshold, consecutive_days, scenario)
    
    print(f"\n💡 TIP: Try different scenarios:")
    print(f"  python3 demo_sell_decision.py {ticker} {threshold} {consecutive_days} declining")
    print(f"  python3 demo_sell_decision.py {ticker} {threshold} {consecutive_days} rising")

if __name__ == "__main__":
    main()
