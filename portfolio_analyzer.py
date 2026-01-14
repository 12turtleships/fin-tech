#!/usr/bin/env python3
"""
Portfolio Analyzer - Shoulder Strategy Analysis
Analyzes bought stocks for sell decisions and interest stocks for buy decisions
using 20-day moving average shoulder strategy.
"""

import yfinance as yf
import pandas as pd
import sys
from datetime import datetime, timedelta
import time

def should_sell_stock(data, threshold_percent=5.0, consecutive_days=1):
    """
    Determine if a stock should be sold based on 20-day moving average shoulder strategy.
    
    Args:
        data: DataFrame with stock price data
        threshold_percent: Percentage below 20-DMA to trigger sell signal
        consecutive_days: Number of consecutive days below threshold to confirm sell
    
    Returns:
        Dictionary with sell decision, current price, 20-DMA, drop percentage, and recommendation
    """
    if len(data) < 20:
        return {
            'sell_decision': False,
            'current_price': None,
            'ma_20': None,
            'drop_percentage': None,
            'recommendation': 'Insufficient data for 20-day moving average',
            'reason': 'Insufficient data'
        }
    
    # Calculate 20-day moving average
    data['MA_20'] = data['Close'].rolling(window=20).mean()
    
    # Get current price and 20-DMA
    current_price = data['Close'].iloc[-1]
    ma_20 = data['MA_20'].iloc[-1]
    
    # Calculate drop percentage
    drop_percentage = ((ma_20 - current_price) / ma_20) * 100
    
    # Check if current price is below 20-DMA by threshold percentage
    is_below_threshold = drop_percentage >= threshold_percent
    
    # Check consecutive days requirement
    meets_consecutive_requirement = True
    if consecutive_days > 1:
        consecutive_count = 0
        for i in range(len(data) - 1, max(0, len(data) - 10), -1):  # Check last 10 days
            if i >= 20:  # Ensure we have enough data for MA calculation
                past_ma = data['MA_20'].iloc[i]
                past_price = data['Close'].iloc[i]
                past_drop = ((past_ma - past_price) / past_ma) * 100
                if past_drop >= threshold_percent:
                    consecutive_count += 1
                else:
                    break
        meets_consecutive_requirement = consecutive_count >= consecutive_days
    
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
        recommendation = f"HOLD - Price is {drop_percentage:.2f}% below 20-DMA (threshold: {threshold_percent}%)"
    else:  # Above MA
        recommendation = f"STRONG HOLD - Price is {abs(drop_percentage):.2f}% above 20-DMA"
    
    return {
        'sell_decision': sell_decision,
        'current_price': current_price,
        'ma_20': ma_20,
        'drop_percentage': drop_percentage,
        'recommendation': recommendation,
        'threshold_percent': threshold_percent,
        'reason': f"Price closed {'below' if drop_percentage > 0 else 'above'} 20-DMA by {abs(drop_percentage):.2f}%"
    }

def should_buy_stock(data, threshold_percent=-10.0, consecutive_days=1):
    """
    Determine if a stock should be bought based on 20-day moving average shoulder strategy.
    For buy decisions, we look for stocks that are significantly below their 20-DMA.
    
    Args:
        data: DataFrame with stock price data
        threshold_percent: Percentage below 20-DMA to trigger buy signal (negative value)
        consecutive_days: Number of consecutive days below threshold to confirm buy
    
    Returns:
        Dictionary with buy decision, current price, 20-DMA, drop percentage, and recommendation
    """
    if len(data) < 20:
        return {
            'buy_decision': False,
            'current_price': None,
            'ma_20': None,
            'drop_percentage': None,
            'recommendation': 'Insufficient data for 20-day moving average',
            'reason': 'Insufficient data'
        }
    
    # Calculate 20-day moving average
    data['MA_20'] = data['Close'].rolling(window=20).mean()
    
    # Get current price and 20-DMA
    current_price = data['Close'].iloc[-1]
    ma_20 = data['MA_20'].iloc[-1]
    
    # Calculate drop percentage (positive when below MA)
    drop_percentage = ((ma_20 - current_price) / ma_20) * 100
    
    # For buy decisions, we want stocks significantly below their 20-DMA
    # threshold_percent is negative (e.g., -10%), so we check if drop_percentage >= abs(threshold_percent)
    is_below_threshold = drop_percentage >= abs(threshold_percent)
    
    # Check consecutive days requirement
    meets_consecutive_requirement = True
    if consecutive_days > 1:
        consecutive_count = 0
        for i in range(len(data) - 1, max(0, len(data) - 10), -1):  # Check last 10 days
            if i >= 20:  # Ensure we have enough data for MA calculation
                past_ma = data['MA_20'].iloc[i]
                past_price = data['Close'].iloc[i]
                past_drop = ((past_ma - past_price) / past_ma) * 100
                if past_drop >= abs(threshold_percent):
                    consecutive_count += 1
                else:
                    break
        meets_consecutive_requirement = consecutive_count >= consecutive_days
    
    # Make buy decision
    buy_decision = is_below_threshold and meets_consecutive_requirement
    
    # Generate recommendation
    if buy_decision:
        if drop_percentage >= abs(threshold_percent) * 2:  # Double the threshold
            recommendation = f"STRONG BUY - Price is {drop_percentage:.2f}% below 20-DMA (buy threshold: {abs(threshold_percent)}%)"
        else:
            recommendation = f"BUY - Price is {drop_percentage:.2f}% below 20-DMA (buy threshold: {abs(threshold_percent)}%)"
    elif drop_percentage >= abs(threshold_percent) * 0.7:  # Within 70% of threshold
        recommendation = f"WATCH - Price is {drop_percentage:.2f}% below 20-DMA, approaching buy threshold"
    elif drop_percentage > 0:  # Below MA but not at threshold
        recommendation = f"WAIT - Price is {drop_percentage:.2f}% below 20-DMA (buy threshold: {abs(threshold_percent)}%)"
    else:  # Above MA
        recommendation = f"AVOID - Price is {abs(drop_percentage):.2f}% above 20-DMA"
    
    return {
        'buy_decision': buy_decision,
        'current_price': current_price,
        'ma_20': ma_20,
        'drop_percentage': drop_percentage,
        'recommendation': recommendation,
        'threshold_percent': abs(threshold_percent),
        'reason': f"Price closed {'below' if drop_percentage > 0 else 'above'} 20-DMA by {abs(drop_percentage):.2f}%"
    }

def get_stock_data(ticker_symbol, period="3mo"):
    """Get stock data with error handling and retry logic."""
    max_retries = 3
    retry_delay = 1
    
    for attempt in range(max_retries):
        try:
            ticker = yf.Ticker(ticker_symbol)
            hist = ticker.history(period=period, interval='1d', auto_adjust=True, prepost=False, repair=True)
            
            if hist.empty:
                if attempt < max_retries - 1:
                    print(f"  Retrying {ticker_symbol} (attempt {attempt + 2})...")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                else:
                    return None
            
            return hist
            
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"  Error fetching {ticker_symbol}: {str(e)[:100]}... Retrying...")
                time.sleep(retry_delay)
                retry_delay *= 2
            else:
                print(f"  Failed to fetch {ticker_symbol} after {max_retries} attempts: {str(e)[:100]}")
                return None
    
    return None

def analyze_bought_stocks(bought_list, sell_threshold=10.0):
    """Analyze bought stocks for sell decisions."""
    print("=" * 80)
    print("🔴 BOUGHT STOCKS - SELL ANALYSIS")
    print("=" * 80)
    print(f"Using {sell_threshold}% threshold below 20-DMA for sell decisions")
    print()
    
    sell_recommendations = []
    hold_recommendations = []
    error_stocks = []
    
    for i, ticker in enumerate(bought_list, 1):
        if not ticker.strip():
            continue
            
        print(f"[{i:2d}/{len(bought_list)}] Analyzing {ticker}...", end=" ")
        
        data = get_stock_data(ticker)
        if data is None:
            print("❌ ERROR - Could not fetch data")
            error_stocks.append(ticker)
            continue
        
        result = should_sell_stock(data, sell_threshold, 1)
        
        if result['sell_decision']:
            print("🔴 SELL")
            sell_recommendations.append({
                'ticker': ticker,
                'current_price': result['current_price'],
                'ma_20': result['ma_20'],
                'drop_percentage': result['drop_percentage'],
                'recommendation': result['recommendation']
            })
        else:
            print("🟢 HOLD")
            hold_recommendations.append({
                'ticker': ticker,
                'current_price': result['current_price'],
                'ma_20': result['ma_20'],
                'drop_percentage': result['drop_percentage'],
                'recommendation': result['recommendation']
            })
        
        time.sleep(0.5)  # Be nice to the API
    
    # Print summary
    print("\n" + "=" * 80)
    print("📊 SELL ANALYSIS SUMMARY")
    print("=" * 80)
    
    if sell_recommendations:
        print(f"\n🔴 SELL RECOMMENDATIONS ({len(sell_recommendations)} stocks):")
        print("-" * 60)
        for stock in sell_recommendations:
            print(f"{stock['ticker']:6} | ${stock['current_price']:8.2f} | {stock['drop_percentage']:6.2f}% below MA | {stock['recommendation']}")
    
    if hold_recommendations:
        print(f"\n🟢 HOLD RECOMMENDATIONS ({len(hold_recommendations)} stocks):")
        print("-" * 60)
        for stock in hold_recommendations:
            print(f"{stock['ticker']:6} | ${stock['current_price']:8.2f} | {stock['drop_percentage']:6.2f}% below MA | {stock['recommendation']}")
    
    if error_stocks:
        print(f"\n❌ ERROR STOCKS ({len(error_stocks)} stocks):")
        print("-" * 60)
        for stock in error_stocks:
            print(f"{stock} - Could not fetch data")
    
    return sell_recommendations, hold_recommendations, error_stocks

def analyze_interest_stocks(interest_list, buy_threshold=-10.0):
    """Analyze interest stocks for buy decisions."""
    print("\n" + "=" * 80)
    print("🟢 INTEREST STOCKS - BUY ANALYSIS")
    print("=" * 80)
    print(f"Using {abs(buy_threshold)}% threshold below 20-DMA for buy decisions")
    print()
    
    buy_recommendations = []
    wait_recommendations = []
    error_stocks = []
    
    for i, ticker in enumerate(interest_list, 1):
        if not ticker.strip():
            continue
            
        print(f"[{i:2d}/{len(interest_list)}] Analyzing {ticker}...", end=" ")
        
        data = get_stock_data(ticker)
        if data is None:
            print("❌ ERROR - Could not fetch data")
            error_stocks.append(ticker)
            continue
        
        result = should_buy_stock(data, buy_threshold, 1)
        
        if result['buy_decision']:
            print("🟢 BUY")
            buy_recommendations.append({
                'ticker': ticker,
                'current_price': result['current_price'],
                'ma_20': result['ma_20'],
                'drop_percentage': result['drop_percentage'],
                'recommendation': result['recommendation']
            })
        else:
            print("⏳ WAIT")
            wait_recommendations.append({
                'ticker': ticker,
                'current_price': result['current_price'],
                'ma_20': result['ma_20'],
                'drop_percentage': result['drop_percentage'],
                'recommendation': result['recommendation']
            })
        
        time.sleep(0.5)  # Be nice to the API
    
    # Print summary
    print("\n" + "=" * 80)
    print("📊 BUY ANALYSIS SUMMARY")
    print("=" * 80)
    
    if buy_recommendations:
        print(f"\n🟢 BUY RECOMMENDATIONS ({len(buy_recommendations)} stocks):")
        print("-" * 60)
        for stock in buy_recommendations:
            print(f"{stock['ticker']:6} | ${stock['current_price']:8.2f} | {stock['drop_percentage']:6.2f}% below MA | {stock['recommendation']}")
    
    if wait_recommendations:
        print(f"\n⏳ WAIT RECOMMENDATIONS ({len(wait_recommendations)} stocks):")
        print("-" * 60)
        for stock in wait_recommendations:
            print(f"{stock['ticker']:6} | ${stock['current_price']:8.2f} | {stock['drop_percentage']:6.2f}% below MA | {stock['recommendation']}")
    
    if error_stocks:
        print(f"\n❌ ERROR STOCKS ({len(error_stocks)} stocks):")
        print("-" * 60)
        for stock in error_stocks:
            print(f"{stock} - Could not fetch data")
    
    return buy_recommendations, wait_recommendations, error_stocks

def main():
    """Main function to analyze portfolio."""
    print("Portfolio Analyzer - Shoulder Strategy Analysis")
    print("=" * 80)
    print(f"Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Read stock lists
    try:
        with open('bought-list.txt', 'r') as f:
            bought_list = [line.strip().upper() for line in f.readlines() if line.strip()]
        
        with open('interest-list.txt', 'r') as f:
            interest_list = [line.strip().upper() for line in f.readlines() if line.strip()]
        
        print(f"Loaded {len(bought_list)} bought stocks and {len(interest_list)} interest stocks")
        print()
        
    except FileNotFoundError as e:
        print(f"Error: Could not find required files: {e}")
        return
    
    # Analyze bought stocks for sell decisions (10% threshold)
    sell_recs, hold_recs, sell_errors = analyze_bought_stocks(bought_list, sell_threshold=10.0)
    
    # Analyze interest stocks for buy decisions (-10% threshold)
    buy_recs, wait_recs, buy_errors = analyze_interest_stocks(interest_list, buy_threshold=-10.0)
    
    # Final summary
    print("\n" + "=" * 80)
    print("🎯 FINAL RECOMMENDATIONS")
    print("=" * 80)
    
    print(f"\n🔴 IMMEDIATE SELL ACTIONS: {len(sell_recs)} stocks")
    if sell_recs:
        for stock in sell_recs:
            print(f"  • {stock['ticker']} - {stock['recommendation']}")
    
    print(f"\n🟢 IMMEDIATE BUY OPPORTUNITIES: {len(buy_recs)} stocks")
    if buy_recs:
        for stock in buy_recs:
            print(f"  • {stock['ticker']} - {stock['recommendation']}")
    
    print(f"\n📊 PORTFOLIO STATUS:")
    print(f"  • Bought stocks to sell: {len(sell_recs)}")
    print(f"  • Bought stocks to hold: {len(hold_recs)}")
    print(f"  • Interest stocks to buy: {len(buy_recs)}")
    print(f"  • Interest stocks to wait: {len(wait_recs)}")
    print(f"  • Stocks with errors: {len(sell_errors) + len(buy_errors)}")

if __name__ == "__main__":
    main()
