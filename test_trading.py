#!/usr/bin/env python3
"""
Test script for trade execution functionality
"""

from trade_executor import CoinbaseTradeExecutor

def test_connection():
    """Test Coinbase API connection."""
    print("🔍 Testing Coinbase API connection...")
    
    try:
        executor = CoinbaseTradeExecutor()
        
        # Test getting balances
        usd_balance = executor.get_usd_balance()
        doge_balance = executor.get_dogecoin_balance()
        current_price = executor.get_current_price()
        
        print("✅ Connection successful!")
        print(f"   USD Balance: ${usd_balance:.2f}")
        print(f"   DOGE Balance: {doge_balance:.2f}")
        print(f"   Current DOGE Price: ${current_price}")
        
        return True
        
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False

def test_trade_simulation():
    """Test trade execution (simulation only)."""
    print("\n🧪 Testing trade simulation...")
    
    try:
        executor = CoinbaseTradeExecutor()
        
        # Simulate a small buy order (1% of USD balance)
        print("Testing BUY 1% simulation...")
        result = executor.execute_trade('BUY', 1)
        
        if result:
            print("✅ Trade simulation successful")
        else:
            print("❌ Trade simulation failed")
            
    except Exception as e:
        print(f"❌ Trade simulation error: {e}")

if __name__ == "__main__":
    print("🚀 Dogecoin Trade Executor Test")
    print("=" * 40)
    
    # Test connection
    if test_connection():
        print("\n" + "=" * 40)
        print("⚠️  WARNING: This will test with REAL MONEY!")
        print("Make sure you have small amounts in your account for testing.")
        print("=" * 40)
        
        proceed = input("Continue with trade test? (y/N): ").lower()
        if proceed == 'y':
            test_trade_simulation()
        else:
            print("⏸️  Trade test skipped")
    else:
        print("❌ Cannot proceed without successful connection")
