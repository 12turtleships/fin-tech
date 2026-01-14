#!/usr/bin/env python3
"""
Automated Portfolio Analyzer with Email Notifications
Runs hourly during market hours (9am-3:55pm EDT/EST) and sends email alerts
for buy/sell recommendations using shoulder strategy.
"""

import yfinance as yf
import pandas as pd
import sys
import smtplib
import ssl
from datetime import datetime, timedelta
import time
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/Users/sungchun/projects/fin-tech/portfolio_analyzer.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Email configuration
EMAIL_CONFIG = {
    'smtp_server': 'smtp.gmail.com',
    'smtp_port': 587,
    'sender_email': 'sungchun71@gmail.com',
    'sender_password': os.getenv('EMAIL_PASSWORD'),  # Set this as environment variable
    'recipient_email': 'sungchun71@gmail.com'
}

def should_sell_stock(data, threshold_percent=5.0, consecutive_days=1):
    """
    Determine if a stock should be sold based on 20-day moving average shoulder strategy.
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
        for i in range(len(data) - 1, max(0, len(data) - 10), -1):
            if i >= 20:
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
        if drop_percentage >= threshold_percent * 2:
            recommendation = f"STRONG SELL - Price is {drop_percentage:.2f}% below 20-DMA (threshold: {threshold_percent}%)"
        else:
            recommendation = f"SELL - Price is {drop_percentage:.2f}% below 20-DMA (threshold: {threshold_percent}%)"
    elif drop_percentage >= threshold_percent * 0.7:
        recommendation = f"CAUTION - Price is {drop_percentage:.2f}% below 20-DMA, approaching sell threshold"
    elif drop_percentage > 0:
        recommendation = f"HOLD - Price is {drop_percentage:.2f}% below 20-DMA (threshold: {threshold_percent}%)"
    else:
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
    
    # Calculate drop percentage
    drop_percentage = ((ma_20 - current_price) / ma_20) * 100
    
    # For buy decisions, we want stocks significantly below their 20-DMA
    is_below_threshold = drop_percentage >= abs(threshold_percent)
    
    # Check consecutive days requirement
    meets_consecutive_requirement = True
    if consecutive_days > 1:
        consecutive_count = 0
        for i in range(len(data) - 1, max(0, len(data) - 10), -1):
            if i >= 20:
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
        if drop_percentage >= abs(threshold_percent) * 2:
            recommendation = f"STRONG BUY - Price is {drop_percentage:.2f}% below 20-DMA (buy threshold: {abs(threshold_percent)}%)"
        else:
            recommendation = f"BUY - Price is {drop_percentage:.2f}% below 20-DMA (buy threshold: {abs(threshold_percent)}%)"
    elif drop_percentage >= abs(threshold_percent) * 0.7:
        recommendation = f"WATCH - Price is {drop_percentage:.2f}% below 20-DMA, approaching buy threshold"
    elif drop_percentage > 0:
        recommendation = f"WAIT - Price is {drop_percentage:.2f}% below 20-DMA (buy threshold: {abs(threshold_percent)}%)"
    else:
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
                    logger.warning(f"Retrying {ticker_symbol} (attempt {attempt + 2})...")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                else:
                    return None
            
            return hist
            
        except Exception as e:
            if attempt < max_retries - 1:
                logger.warning(f"Error fetching {ticker_symbol}: {str(e)[:100]}... Retrying...")
                time.sleep(retry_delay)
                retry_delay *= 2
            else:
                logger.error(f"Failed to fetch {ticker_symbol} after {max_retries} attempts: {str(e)[:100]}")
                return None
    
    return None

def send_email_notification(sell_recommendations, buy_recommendations):
    """Send email notification with buy/sell recommendations."""
    if not sell_recommendations and not buy_recommendations:
        logger.info("No buy/sell recommendations to send via email")
        return False
    
    try:
        # Create message
        msg = MIMEMultipart()
        msg['From'] = EMAIL_CONFIG['sender_email']
        msg['To'] = EMAIL_CONFIG['recipient_email']
        msg['Subject'] = f"🚨 Portfolio Alert - {len(sell_recommendations)} Sell & {len(buy_recommendations)} Buy Recommendations"
        
        # Create email body
        body = f"""
Portfolio Analysis Alert - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
================================================================================

"""
        
        if sell_recommendations:
            body += f"🔴 SELL RECOMMENDATIONS ({len(sell_recommendations)} stocks):\n"
            body += "-" * 60 + "\n"
            for stock in sell_recommendations:
                body += f"{stock['ticker']:6} | ${stock['current_price']:8.2f} | {stock['drop_percentage']:6.2f}% below MA | {stock['recommendation']}\n"
            body += "\n"
        
        if buy_recommendations:
            body += f"🟢 BUY RECOMMENDATIONS ({len(buy_recommendations)} stocks):\n"
            body += "-" * 60 + "\n"
            for stock in buy_recommendations:
                body += f"{stock['ticker']:6} | ${stock['current_price']:8.2f} | {stock['drop_percentage']:6.2f}% below MA | {stock['recommendation']}\n"
            body += "\n"
        
        body += """
================================================================================
This is an automated alert from your Portfolio Analyzer.
Please review these recommendations and make your own investment decisions.

Best regards,
Your Automated Portfolio Analyzer
"""
        
        msg.attach(MIMEText(body, 'plain'))
        
        # Send email
        if not EMAIL_CONFIG['sender_password']:
            logger.error("Email password not set. Please set EMAIL_PASSWORD environment variable.")
            return False
        
        context = ssl.create_default_context()
        with smtplib.SMTP(EMAIL_CONFIG['smtp_server'], EMAIL_CONFIG['smtp_port']) as server:
            server.starttls(context=context)
            server.login(EMAIL_CONFIG['sender_email'], EMAIL_CONFIG['sender_password'])
            server.send_message(msg)
        
        logger.info(f"Email sent successfully with {len(sell_recommendations)} sell and {len(buy_recommendations)} buy recommendations")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send email: {str(e)}")
        return False

def analyze_portfolio():
    """Main portfolio analysis function."""
    logger.info("Starting automated portfolio analysis...")
    
    try:
        # Read stock lists
        with open('/Users/sungchun/projects/fin-tech/bought-list.txt', 'r') as f:
            bought_list = [line.strip().upper() for line in f.readlines() if line.strip()]
        
        with open('/Users/sungchun/projects/fin-tech/interest-list.txt', 'r') as f:
            interest_list = [line.strip().upper() for line in f.readlines() if line.strip()]
        
        logger.info(f"Loaded {len(bought_list)} bought stocks and {len(interest_list)} interest stocks")
        
    except FileNotFoundError as e:
        logger.error(f"Could not find required files: {e}")
        return
    
    # Analyze bought stocks for sell decisions (10% threshold)
    sell_recommendations = []
    for ticker in bought_list:
        if not ticker.strip():
            continue
        
        data = get_stock_data(ticker)
        if data is None:
            logger.warning(f"Could not fetch data for {ticker}")
            continue
        
        result = should_sell_stock(data, 10.0, 1)
        
        if result['sell_decision']:
            sell_recommendations.append({
                'ticker': ticker,
                'current_price': result['current_price'],
                'ma_20': result['ma_20'],
                'drop_percentage': result['drop_percentage'],
                'recommendation': result['recommendation']
            })
        
        time.sleep(0.5)  # Be nice to the API
    
    # Analyze interest stocks for buy decisions (-10% threshold)
    buy_recommendations = []
    for ticker in interest_list:
        if not ticker.strip():
            continue
        
        data = get_stock_data(ticker)
        if data is None:
            logger.warning(f"Could not fetch data for {ticker}")
            continue
        
        result = should_buy_stock(data, -10.0, 1)
        
        if result['buy_decision']:
            buy_recommendations.append({
                'ticker': ticker,
                'current_price': result['current_price'],
                'ma_20': result['ma_20'],
                'drop_percentage': result['drop_percentage'],
                'recommendation': result['recommendation']
            })
        
        time.sleep(0.5)  # Be nice to the API
    
    # Log results
    logger.info(f"Analysis complete: {len(sell_recommendations)} sell recommendations, {len(buy_recommendations)} buy recommendations")
    
    # Send email if there are recommendations
    if sell_recommendations or buy_recommendations:
        send_email_notification(sell_recommendations, buy_recommendations)
    else:
        logger.info("No buy/sell recommendations found - no email sent")
    
    return sell_recommendations, buy_recommendations

def is_market_hours():
    """Check if current time is within market hours (9am-3:55pm EDT/EST, weekdays only)."""
    now = datetime.now()
    
    # Check if it's a weekday (Monday=0, Sunday=6)
    if now.weekday() >= 5:  # Saturday or Sunday
        return False
    
    # Check if it's within market hours (9:00 AM to 3:55 PM)
    market_start = now.replace(hour=9, minute=0, second=0, microsecond=0)
    market_end = now.replace(hour=15, minute=55, second=0, microsecond=0)
    
    return market_start <= now <= market_end

def main():
    """Main function for automated execution."""
    logger.info("Automated Portfolio Analyzer started")
    
    # Check if we're in market hours
    if not is_market_hours():
        logger.info("Outside market hours - skipping analysis")
        return
    
    logger.info("Within market hours - proceeding with analysis")
    
    try:
        analyze_portfolio()
        logger.info("Automated analysis completed successfully")
    except Exception as e:
        logger.error(f"Error during automated analysis: {str(e)}")

if __name__ == "__main__":
    main()
