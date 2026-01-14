# 20-Day Moving Average Sell Decision Strategy

## Overview
This implementation provides a systematic approach to making sell decisions based on the 20-day moving average (20-DMA), inspired by head and shoulders pattern analysis. When a stock price drops below its 20-day moving average by a specified threshold, it may indicate the breakdown of a head and shoulders pattern or other bearish technical formations.

## Algorithm Details

### Core Formula
```
Drop Percentage = (20-DMA - Current Price) / 20-DMA × 100
```

### Decision Logic
- **SELL**: When drop percentage ≥ threshold
- **STRONG SELL**: When drop percentage ≥ 2× threshold  
- **CAUTION**: When drop percentage ≥ 70% of threshold
- **WATCH**: When price is below 20-DMA but within acceptable range
- **HOLD**: When price is above 20-DMA

## Files and Usage

### 1. Main Implementation: `stock-info.py`
Comprehensive stock analysis tool with integrated 20-DMA sell decision.

**Usage:**
```bash
# Full stock analysis (includes sell decision)
python3 stock-info.py AAPL

# Sell decision only
python3 stock-info.py --sell AAPL 5.0 1

# Test yfinance connection
python3 stock-info.py --test

# Custom threshold and consecutive days
python3 stock-info.py --sell TSLA 7.5 2
```

### 2. Simple Version: `simple_sell_check.py`
Standalone sell decision checker that works even when yfinance has issues.

**Usage:**
```bash
# Basic sell check
python3 simple_sell_check.py AAPL

# Custom threshold
python3 simple_sell_check.py AAPL 7.5
```

## Key Features

### 1. Configurable Parameters
- **Threshold Percentage**: Default 5%, customizable (e.g., 3%, 7.5%, 10%)
- **Consecutive Days**: Require multiple days below threshold for confirmation
- **Multiple Timeframes**: Supports different analysis periods

### 2. Robust Data Handling
- **Multiple Data Sources**: Primary yfinance, fallback to sample data
- **Error Recovery**: Handles network issues, rate limiting, API failures
- **Cache Management**: Automatic cache clearing to avoid stale data

### 3. Comprehensive Analysis
- **Technical Indicators**: RSI, MACD, multiple moving averages
- **Fundamental Analysis**: DCF, P/E ratios, EPS metrics
- **Risk Assessment**: Margin of safety calculations

## Example Output

```
==================================================
SELL DECISION ANALYSIS FOR AAPL
==================================================

Stock: AAPL
Current Price: $164.48
20-Day Moving Average: $183.42
Drop from 20-DMA: 10.32%
Sell Threshold: 5.0%

SELL DECISION:       YES
RECOMMENDATION:      STRONG SELL - 10.32% below 20-DMA

Recent 5-day price trend:
  2025-09-15: $172.20 (20-DMA: $191.65, Drop: 10.15%)
  2025-09-16: $167.72 (20-DMA: $189.76, Drop: 11.61%)
  2025-09-17: $168.48 (20-DMA: $187.73, Drop: 10.26%)
  2025-09-18: $165.95 (20-DMA: $185.67, Drop: 10.62%)
  2025-09-19: $164.48 (20-DMA: $183.42, Drop: 10.32%)
```

## Troubleshooting

### yfinance Issues
If you encounter "possibly delisted" or "unsupported pickle protocol" errors:

1. **Update yfinance**: `pip3 install --upgrade yfinance`
2. **Test connection**: `python3 stock-info.py --test`
3. **Use simple version**: `python3 simple_sell_check.py TICKER`
4. **Check network**: Ensure Yahoo Finance is accessible

### Common Solutions
- Clear yfinance cache (done automatically)
- Wait for rate limiting to reset (1-2 minutes)
- Try different ticker symbols
- Use sample data mode for algorithm testing

## Investment Strategy Context

### Head and Shoulders Pattern
This algorithm is particularly effective for detecting:
- **Breakdown below neckline**: 20-DMA often acts as support/resistance
- **Volume confirmation**: Combined with volume analysis
- **Trend reversal signals**: Early warning of bearish momentum

### Risk Management
- **Position sizing**: Use with proper position management
- **Stop losses**: 20-DMA breakdown as systematic stop loss
- **Diversification**: Don't rely solely on technical indicators

### Customization for Risk Tolerance
- **Conservative (3-5%)**: Earlier exits, more false signals
- **Moderate (5-7%)**: Balanced approach, good for most investors  
- **Aggressive (7-10%)**: Later exits, fewer false signals, higher risk

## Dependencies
```bash
pip3 install yfinance pandas numpy requests beautifulsoup4
```

## Notes
- Algorithm works with any timeframe (daily, weekly, etc.)
- Suitable for both individual stocks and ETFs
- Can be integrated into automated trading systems
- Backtesting recommended before live trading

---
*This implementation provides a systematic, emotion-free approach to sell decisions based on proven technical analysis principles.*
