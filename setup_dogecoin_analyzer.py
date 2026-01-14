#!/usr/bin/env python3
"""
Setup script for Dogecoin Analyzer
This script helps you set up the environment and test the configuration.
"""

import os
import subprocess
import sys

def install_requirements():
    """Install required packages."""
    print("📦 Installing required packages...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✅ Requirements installed successfully!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error installing requirements: {e}")
        return False

def check_env_file():
    """Check if .env file exists and has required keys."""
    if not os.path.exists('.env'):
        print("❌ .env file not found!")
        print("📝 Please create a .env file using env_template.txt as a reference")
        print("   Copy env_template.txt to .env and fill in your API keys")
        return False
    
    # Check if required keys are in .env
    required_keys = ['COINBASE_API_KEY', 'COINBASE_PRIVATE_KEY', 'OPENAI_API_KEY']
    missing_keys = []
    
    with open('.env', 'r') as f:
        content = f.read()
        for key in required_keys:
            if f"{key}=" not in content or f"{key}=your_" in content:
                missing_keys.append(key)
    
    if missing_keys:
        print(f"❌ Missing or incomplete API keys in .env: {', '.join(missing_keys)}")
        print("📝 Please update your .env file with actual API keys")
        return False
    
    print("✅ .env file looks good!")
    return True

def test_imports():
    """Test if all required modules can be imported."""
    print("🔍 Testing imports...")
    try:
        import pandas
        import requests
        import openai
        from coinbase_advanced_trader import CoinbaseAdvancedTrader
        from dotenv import load_dotenv
        print("✅ All imports successful!")
        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False

def main():
    """Main setup function."""
    print("🚀 Setting up Dogecoin Analyzer...")
    print("=" * 50)
    
    # Install requirements
    if not install_requirements():
        return False
    
    print()
    
    # Test imports
    if not test_imports():
        return False
    
    print()
    
    # Check .env file
    if not check_env_file():
        return False
    
    print()
    print("🎉 Setup complete! You can now run:")
    print("   python mvp.py")
    print()
    print("📋 To get started:")
    print("1. Copy env_template.txt to .env")
    print("2. Fill in your API keys in the .env file")
    print("3. Run: python mvp.py")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
