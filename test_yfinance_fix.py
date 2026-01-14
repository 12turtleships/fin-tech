#!/usr/bin/env python3.7
"""
Test script to diagnose and fix yfinance issues
"""

import sys
import time
import os

def test_basic_connectivity():
    """Test basic network connectivity"""
    print("1. Testing basic network connectivity...")
    try:
        import requests
        response = requests.get("https://finance.yahoo.com", timeout=10)
        print(f"   ✓ Yahoo Finance accessible: HTTP {response.status_code}")
        return True
    except Exception as e:
        print(f"   ✗ Network issue: {e}")
        return False

def test_yfinance_import():
    """Test yfinance import and version"""
    print("2. Testing yfinance import...")
    try:
        import yfinance as yf
        print(f"   ✓ yfinance imported successfully: v{yf.__version__}")
        return yf
    except Exception as e:
        print(f"   ✗ yfinance import failed: {e}")
        return None

def test_different_methods(yf):
    """Test different data fetching methods"""
    print("3. Testing different data fetching methods...")
    
    # Clear cache first
    try:
        import shutil
        cache_dir = os.path.expanduser('~/.cache/yfinance')
        if os.path.exists(cache_dir):
            shutil.rmtree(cache_dir)
            print("   ✓ Cache cleared")
    except:
        pass
    
    test_symbols = ['AAPL', 'MSFT', 'SPY', 'QQQ']
    
    for symbol in test_symbols:
        print(f"\n   Testing {symbol}:")
        
        # Method 1: Basic history
        try:
            ticker = yf.Ticker(symbol)
            time.sleep(1)  # Rate limiting
            hist = ticker.history(period='5d')
            if len(hist) > 0:
                print(f"   ✓ Method 1 (basic): {len(hist)} days, latest: ${hist['Close'].iloc[-1]:.2f}")
                return symbol, hist  # Return first working symbol
            else:
                print(f"   ✗ Method 1: No data")
        except Exception as e:
            print(f"   ✗ Method 1 error: {str(e)[:50]}...")
        
        # Method 2: Download function
        try:
            from datetime import datetime, timedelta
            end_date = datetime.now()
            start_date = end_date - timedelta(days=7)
            time.sleep(1)  # Rate limiting
            hist = yf.download(symbol, start=start_date, end=end_date, progress=False)
            if len(hist) > 0:
                print(f"   ✓ Method 2 (download): {len(hist)} days, latest: ${hist['Close'].iloc[-1]:.2f}")
                return symbol, hist  # Return first working symbol
            else:
                print(f"   ✗ Method 2: No data")
        except Exception as e:
            print(f"   ✗ Method 2 error: {str(e)[:50]}...")
        
        # Method 3: Different period
        try:
            ticker = yf.Ticker(symbol)
            time.sleep(1)  # Rate limiting
            hist = ticker.history(period='1mo', interval='1d')
            if len(hist) > 0:
                print(f"   ✓ Method 3 (1mo): {len(hist)} days, latest: ${hist['Close'].iloc[-1]:.2f}")
                return symbol, hist  # Return first working symbol
            else:
                print(f"   ✗ Method 3: No data")
        except Exception as e:
            print(f"   ✗ Method 3 error: {str(e)[:50]}...")
    
    return None, None

def test_with_user_agent():
    """Test with custom user agent"""
    print("4. Testing with custom user agent...")
    try:
        import yfinance as yf
        import requests
        
        # Set custom headers
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
        
        # Try with custom session
        ticker = yf.Ticker('AAPL', session=session)
        time.sleep(2)  # Extra delay
        hist = ticker.history(period='5d')
        
        if len(hist) > 0:
            print(f"   ✓ Custom user agent worked: {len(hist)} days")
            return 'AAPL', hist
        else:
            print(f"   ✗ Custom user agent: No data")
            
    except Exception as e:
        print(f"   ✗ Custom user agent error: {e}")
    
    return None, None

def main():
    print("="*60)
    print("YFINANCE DIAGNOSTIC AND FIX TOOL")
    print("="*60)
    
    # Test 1: Network connectivity
    if not test_basic_connectivity():
        print("\n❌ Network connectivity failed. Check your internet connection.")
        return
    
    # Test 2: yfinance import
    yf = test_yfinance_import()
    if not yf:
        print("\n❌ yfinance import failed. Try: pip3.7 install yfinance")
        return
    
    # Test 3: Different methods
    symbol, hist = test_different_methods(yf)
    if symbol and hist is not None:
        print(f"\n✅ SUCCESS! {symbol} data fetched successfully.")
        print(f"   You can now use: python3.7 stock-info.py {symbol}")
        return
    
    # Test 4: User agent method
    symbol, hist = test_with_user_agent()
    if symbol and hist is not None:
        print(f"\n✅ SUCCESS! {symbol} data fetched with custom user agent.")
        return
    
    print("\n❌ All methods failed. Possible solutions:")
    print("   1. Wait 10-15 minutes (rate limiting)")
    print("   2. Try different network/VPN")
    print("   3. Use demo version: python3.7 demo_sell_decision.py AAPL")
    print("   4. Check if Yahoo Finance is down: https://downdetector.com/status/yahoo/")

if __name__ == "__main__":
    main()
