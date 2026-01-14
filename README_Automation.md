# Automated Portfolio Analyzer

This system automatically analyzes your portfolio every hour during market hours (9am-3:55pm EDT/EST, weekdays only) and sends email notifications when buy/sell recommendations are found using the shoulder strategy.

## 🚀 Quick Setup

### 1. Run the Setup Script
```bash
cd /Users/sungchun/projects/fin-tech
./setup_automation.sh
```

The setup script will:
- Configure email settings
- Set up the cron job for hourly execution
- Test the system

### 2. Manual Setup (Alternative)

#### Email Configuration
1. **Get Gmail App Password:**
   - Go to [Google Account Settings](https://myaccount.google.com/)
   - Enable 2-Factor Authentication
   - Go to Security > App passwords
   - Generate a new app password for "Mail"
   - Copy the 16-character password

2. **Set Environment Variable:**
   ```bash
   export EMAIL_PASSWORD='your_16_character_app_password'
   echo 'export EMAIL_PASSWORD="your_16_character_app_password"' >> ~/.bash_profile
   ```

#### Cron Job Setup
```bash
# Add to crontab (runs every hour 9am-3:55pm, weekdays only)
crontab -e

# Add this line:
0 9-15 * * 1-5 cd /Users/sungchun/projects/fin-tech && python automated_portfolio_analyzer.py >> /Users/sungchun/projects/fin-tech/cron.log 2>&1
```

## 📁 Files Created

- `automated_portfolio_analyzer.py` - Main automation script
- `setup_automation.sh` - Setup script
- `test_email.py` - Email testing script
- `portfolio_analyzer.log` - Analysis logs
- `cron.log` - Cron execution logs

## 🔧 How It Works

### Analysis Schedule
- **Frequency:** Every hour
- **Hours:** 9:00 AM - 3:55 PM EDT/EST
- **Days:** Monday through Friday only
- **Strategy:** 20-day moving average shoulder strategy

### Thresholds
- **Sell Threshold:** 10% below 20-DMA (for bought stocks)
- **Buy Threshold:** 10% below 20-DMA (for interest stocks)

### Email Notifications
- **Trigger:** Only when buy/sell recommendations are found
- **Content:** Detailed analysis with current prices and recommendations
- **Recipient:** sungchun71@gmail.com

## 📊 Monitoring

### View Logs
```bash
# Real-time analysis logs
tail -f portfolio_analyzer.log

# Cron execution logs
tail -f cron.log

# Check crontab
crontab -l
```

### Test Email
```bash
python test_email.py
```

### Manual Run
```bash
python automated_portfolio_analyzer.py
```

## 🛠️ Troubleshooting

### Common Issues

1. **Email not sending:**
   - Check EMAIL_PASSWORD environment variable
   - Verify Gmail App Password is correct
   - Test with: `python test_email.py`

2. **Cron job not running:**
   - Check crontab: `crontab -l`
   - Verify paths in cron job are correct
   - Check cron logs: `tail -f cron.log`

3. **Script errors:**
   - Check analysis logs: `tail -f portfolio_analyzer.log`
   - Verify stock list files exist
   - Test manual run: `python automated_portfolio_analyzer.py`

### Log Locations
- Analysis logs: `/Users/sungchun/projects/fin-tech/portfolio_analyzer.log`
- Cron logs: `/Users/sungchun/projects/fin-tech/cron.log`

## 📈 Email Format

When recommendations are found, you'll receive an email like this:

```
Subject: 🚨 Portfolio Alert - 2 Sell & 1 Buy Recommendations

Portfolio Analysis Alert - 2025-09-20 14:30:00
================================================================================

🔴 SELL RECOMMENDATIONS (2 stocks):
------------------------------------------------------------
FIG    | $   56.81 |   12.57% below MA | SELL - Price is 12.57% below 20-DMA (threshold: 10.0%)
NMAX   | $   12.84 |   11.77% below MA | SELL - Price is 11.77% below 20-DMA (threshold: 10.0%)

🟢 BUY RECOMMENDATIONS (1 stocks):
------------------------------------------------------------
NUE    | $  133.30 |   12.59% below MA | BUY - Price is 12.59% below 20-DMA (buy threshold: 10.0%)

================================================================================
This is an automated alert from your Portfolio Analyzer.
Please review these recommendations and make your own investment decisions.
```

## 🛑 Stopping the Automation

### Remove Cron Job
```bash
crontab -e
# Delete the line with automated_portfolio_analyzer.py
```

### Disable Temporarily
```bash
# Comment out the cron job line
crontab -e
# Add # at the beginning of the line
```

## 🔄 Updating

To update the system:
1. Modify `automated_portfolio_analyzer.py` as needed
2. The cron job will automatically use the updated version
3. No need to restart anything

## 📞 Support

If you encounter issues:
1. Check the logs first
2. Test email functionality
3. Verify cron job is running
4. Test manual execution

---

**Happy Automated Investing! 📈🤖**
