# 🐕 Dogecoin Analyzer

A Python script that fetches Dogecoin (DOGE) data from Coinbase API and uses ChatGPT to provide investment recommendations.

## Features

- 📊 Fetches 30-day historical Dogecoin data from Coinbase
- 🤖 Analyzes data using OpenAI's ChatGPT
- 💡 Provides BUY/HOLD/SELL recommendations
- 📈 Calculates technical indicators (moving averages, volatility)
- 📋 Comprehensive market analysis

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

Or run the setup script:
```bash
python setup_dogecoin_analyzer.py
```

### 2. Configure API Keys

1. Copy the environment template:
   ```bash
   cp env_template.txt .env
   ```

2. Edit `.env` file with your actual API keys:
   ```
   COINBASE_API_KEY=your_actual_coinbase_api_key
   COINBASE_PRIVATE_KEY=your_actual_coinbase_private_key
   OPENAI_API_KEY=your_actual_openai_api_key
   ```

### 3. Get API Keys

#### Coinbase API Keys
1. Go to [Coinbase Advanced Trade](https://pro.coinbase.com/)
2. Sign in to your account
3. Go to API settings
4. Create a new API key with appropriate permissions
5. Copy the API key and secret

#### OpenAI API Key
1. Go to [OpenAI Platform](https://platform.openai.com/)
2. Sign in to your account
3. Go to API Keys section
4. Create a new API key
5. Copy the key

## Usage

Run the analyzer:
```bash
python mvp.py
```

## What the Script Does

1. **Fetches Data**: Gets 30 days of Dogecoin price data from Coinbase
2. **Calculates Metrics**: 
   - Current price vs 30 days ago
   - Moving averages (7, 14, 30 days)
   - Volatility analysis
   - Volume analysis
3. **AI Analysis**: Sends data to ChatGPT for professional analysis
4. **Recommendation**: Returns BUY/HOLD/SELL recommendation with reasoning

## Sample Output

```
🐕 Fetching Dogecoin data from Coinbase...
✅ Successfully fetched 30 days of Dogecoin data
📊 Analyzing chart data...
Current DOGE Price: $0.082345
30-day Change: 12.5%
Volatility: 8.2%
🤖 Getting AI analysis from ChatGPT...

============================================================
🎯 DOGECOIN INVESTMENT ANALYSIS
============================================================
RECOMMENDATION: HOLD

Based on the technical analysis:
- Current price is above 7-day and 14-day moving averages
- Moderate volatility suggests stable price action
- Volume is within normal ranges
- Risk Level: Medium

Key factors to consider:
- Overall crypto market sentiment
- Dogecoin community activity
- Bitcoin correlation
============================================================
```

## Technical Details

### Data Sources
- **Coinbase Exchange API**: Historical price data
- **OpenAI GPT-3.5-turbo**: AI analysis and recommendations

### Technical Indicators Calculated
- Moving Averages (7, 14, 30 days)
- Price volatility (standard deviation)
- Volume analysis
- Price momentum

### Error Handling
- API key validation
- Network error handling
- Data validation
- Graceful error messages

## Troubleshooting

### Common Issues

1. **"Missing required API keys"**
   - Check your `.env` file exists
   - Verify all API keys are filled in correctly

2. **"Error fetching Dogecoin data"**
   - Check your internet connection
   - Verify Coinbase API keys are correct
   - Check if Coinbase API is accessible

3. **"Error getting ChatGPT analysis"**
   - Verify OpenAI API key is correct
   - Check if you have sufficient OpenAI credits
   - Ensure API key has proper permissions

### Getting Help

If you encounter issues:
1. Check the error messages carefully
2. Verify your API keys are correct
3. Ensure all dependencies are installed
4. Check your internet connection

## Security Notes

- Never commit your `.env` file to version control
- Keep your API keys secure
- Use environment variables in production
- Regularly rotate your API keys

## License

This project is for educational purposes. Use at your own risk for investment decisions.
