# 🚀 Dogecoin Automated Trading System

A complete system that analyzes Dogecoin market data with AI and automatically executes trades based on recommendations.

## ⚠️ IMPORTANT SAFETY WARNINGS

- **REAL MONEY TRADING**: This system executes real trades with real money
- **START SMALL**: Test with small amounts first
- **MONITOR CLOSELY**: Always supervise automated trading
- **UNDERSTAND RISKS**: Cryptocurrency trading involves significant risk
- **BACKUP YOUR DATA**: Keep records of all trades

## 🎯 Features

### **AI-Powered Analysis**
- Fetches 30-day Dogecoin data from Coinbase
- Uses GPT-4o for professional financial analysis
- Provides BUY/SELL/HOLD recommendations with specific percentages

### **Automated Trade Execution**
- Executes trades directly on Coinbase
- Supports BUY orders (percentage of USD balance)
- Supports SELL orders (percentage of DOGE holdings)
- Safety confirmations before each trade

### **Portfolio Management**
- Real-time balance tracking
- Trade history logging
- Risk assessment and monitoring

## 🔧 Setup

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure API Keys
Copy the environment template and fill in your keys:
```bash
cp env_template.txt .env
```

Edit `.env` with your actual credentials:
```
COINBASE_API_KEY=your_actual_api_key
COINBASE_PRIVATE_KEY=your_actual_private_key
COINBASE_PASSPHRASE=your_actual_passphrase
OPENAI_API_KEY=your_actual_openai_key
```

### 3. Get Coinbase API Credentials
1. Go to [Coinbase Advanced Trade](https://pro.coinbase.com/)
2. Sign in and go to API settings
3. Create a new API key with **trading permissions**
4. Copy the API key, secret, and passphrase

### 4. Test Connection
```bash
python test_trading.py
```

## 🚀 Usage

### **Run Complete Analysis + Trading**
```bash
python mvp.py
```

This will:
1. Fetch Dogecoin market data
2. Get AI analysis and recommendation
3. Ask if you want to execute the trade
4. Execute the trade if confirmed

### **Example Workflow**

```
🐕 Fetching Dogecoin data from Coinbase...
✅ Successfully fetched 30 days of Dogecoin data
📊 Analyzing chart data...
Current DOGE Price: $0.18992
30-day Change: -19.91%
Volatility: 5.9%
🤖 Getting AI analysis from ChatGPT...

============================================================
🎯 DOGECOIN INVESTMENT ANALYSIS
============================================================
📋 QUICK SUMMARY: BUY 25% of portfolio
------------------------------------------------------------
[Detailed AI analysis...]
============================================================

💼 TRADE EXECUTION
------------------------------
Execute the recommended trade? (y/N): y

🤖 AI Recommendation: BUY 25% of portfolio
Execute BUY order for 25% of USD balance? (y/N): y

🚀 EXECUTING TRADE: BUY 25
==================================================
💰 Current Balances:
   USD: $1000.00
   DOGE: 0.00
📈 Current DOGE Price: $0.18992
💵 Buying DOGE worth $250.00 (25% of USD balance)
✅ Buy order placed successfully!
   Order ID: abc123
   Amount: $250.00
   Status: filled
✅ Trade execution completed
```

## 🛡️ Safety Features

### **Confirmation Prompts**
- Double confirmation before each trade
- Clear display of trade amounts
- Option to cancel at any time

### **Balance Validation**
- Checks sufficient funds before trading
- Prevents overdraft situations
- Real-time balance updates

### **Trade Logging**
- All trades logged to `trade_history.json`
- Timestamp and result tracking
- Success/failure monitoring

### **Error Handling**
- Graceful handling of API errors
- Network timeout protection
- Invalid order prevention

## 📊 Trading Logic

### **BUY Orders**
- Spends specified percentage of USD balance
- Uses market orders for immediate execution
- Calculates DOGE amount based on current price

### **SELL Orders**
- Sells specified percentage of DOGE holdings
- Uses market orders for immediate execution
- Converts DOGE to USD

### **HOLD Recommendations**
- No trade execution
- Logs the recommendation
- Continues monitoring

## 📈 Portfolio Tracking

### **Real-time Balances**
- USD balance tracking
- DOGE balance tracking
- Current market prices

### **Trade History**
- JSON format logging
- Timestamp tracking
- Success/failure records

### **Performance Monitoring**
- Trade execution results
- Balance changes over time
- AI recommendation accuracy

## 🔍 Testing

### **Connection Test**
```bash
python test_trading.py
```

### **Small Amount Testing**
- Start with 1% trades
- Monitor results closely
- Verify order execution

### **Paper Trading**
- Disable trading in code
- Review recommendations only
- Practice with virtual money

## ⚠️ Risk Management

### **Position Sizing**
- AI recommends 10-50% for BUY orders
- AI recommends 25-100% for SELL orders
- Never risk more than you can afford to lose

### **Market Volatility**
- Cryptocurrency markets are highly volatile
- Prices can change rapidly
- Past performance doesn't guarantee future results

### **Technical Risks**
- API connection failures
- Network timeouts
- Exchange maintenance

## 🛠️ Troubleshooting

### **Common Issues**

1. **"Missing Coinbase API credentials"**
   - Check your `.env` file
   - Verify all three credentials are set
   - Ensure no extra spaces or quotes

2. **"Unable to get account balances"**
   - Check API key permissions
   - Verify account has funds
   - Check network connection

3. **"Error placing order"**
   - Check minimum order sizes
   - Verify sufficient balance
   - Check market hours

### **Debug Mode**
Add debug prints to see detailed API responses:
```python
print(f"API Response: {response.text}")
```

## 📚 API Documentation

### **Coinbase Advanced Trade API**
- [Official Documentation](https://docs.cloud.coinbase.com/advanced-trade-api/docs)
- [Authentication Guide](https://docs.cloud.coinbase.com/advanced-trade-api/docs/auth)
- [Order Management](https://docs.cloud.coinbase.com/advanced-trade-api/docs/orders)

### **OpenAI API**
- [Chat Completions](https://platform.openai.com/docs/api-reference/chat)
- [Rate Limits](https://platform.openai.com/docs/guides/rate-limits)

## 🚨 Legal Disclaimer

- **Not Financial Advice**: This system is for educational purposes
- **Use at Your Own Risk**: Trading involves significant financial risk
- **No Guarantees**: Past performance doesn't predict future results
- **Regulatory Compliance**: Ensure compliance with local laws
- **Tax Implications**: Trading may have tax consequences

## 📞 Support

If you encounter issues:
1. Check the troubleshooting section
2. Verify your API credentials
3. Test with small amounts first
4. Review the trade logs

Remember: **Start small, test thoroughly, and never risk more than you can afford to lose!**
