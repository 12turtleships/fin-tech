#!/bin/bash

# Setup script for Automated Portfolio Analyzer
# This script helps configure email settings and cron job

echo "🚀 Setting up Automated Portfolio Analyzer"
echo "=========================================="

# Check if we're in the right directory
if [ ! -f "automated_portfolio_analyzer.py" ]; then
    echo "❌ Error: Please run this script from the fin-tech directory"
    exit 1
fi

# Make the Python script executable
chmod +x automated_portfolio_analyzer.py
echo "✅ Made automated_portfolio_analyzer.py executable"

# Set up email password
echo ""
echo "📧 Email Configuration"
echo "======================"
echo "To send email notifications, you need to set up an App Password for Gmail."
echo ""
echo "Steps to get Gmail App Password:"
echo "1. Go to your Google Account settings"
echo "2. Enable 2-Factor Authentication if not already enabled"
echo "3. Go to Security > App passwords"
echo "4. Generate a new app password for 'Mail'"
echo "5. Copy the 16-character password"
echo ""

read -p "Enter your Gmail App Password (16 characters): " -s email_password
echo ""

if [ ${#email_password} -eq 16 ]; then
    # Add to bash profile
    echo "export EMAIL_PASSWORD='$email_password'" >> ~/.bash_profile
    echo "export EMAIL_PASSWORD='$email_password'" >> ~/.bashrc
    
    # Set for current session
    export EMAIL_PASSWORD="$email_password"
    
    echo "✅ Email password configured"
else
    echo "❌ Invalid password length. Please make sure it's 16 characters."
    echo "You can set it manually later with: export EMAIL_PASSWORD='your_password'"
fi

# Set up cron job
echo ""
echo "⏰ Setting up Cron Job"
echo "======================"
echo "This will create a cron job to run the analyzer every hour during market hours (9am-3:55pm EDT/EST, weekdays only)"
echo ""

# Get the full path to the script
SCRIPT_PATH=$(pwd)/automated_portfolio_analyzer.py
PYTHON_PATH=$(which python)

echo "Script path: $SCRIPT_PATH"
echo "Python path: $PYTHON_PATH"
echo ""

# Create cron job entry
CRON_ENTRY="0 9-15 * * 1-5 cd $(pwd) && $PYTHON_PATH $SCRIPT_PATH >> $(pwd)/cron.log 2>&1"

echo "Cron job entry:"
echo "$CRON_ENTRY"
echo ""

read -p "Do you want to add this cron job? (y/n): " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    # Add to crontab
    (crontab -l 2>/dev/null; echo "$CRON_ENTRY") | crontab -
    echo "✅ Cron job added successfully"
    echo ""
    echo "Current crontab:"
    crontab -l
else
    echo "⏭️  Skipping cron job setup"
    echo ""
    echo "To add it manually later, run:"
    echo "crontab -e"
    echo "Then add this line:"
    echo "$CRON_ENTRY"
fi

# Test the script
echo ""
echo "🧪 Testing the Script"
echo "===================="
read -p "Do you want to test the script now? (y/n): " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Running test..."
    python automated_portfolio_analyzer.py
    echo ""
    echo "✅ Test completed. Check the output above for any errors."
fi

echo ""
echo "🎉 Setup Complete!"
echo "=================="
echo ""
echo "Summary:"
echo "• Automated portfolio analyzer is ready"
echo "• Email notifications configured"
echo "• Cron job set up for hourly execution during market hours"
echo ""
echo "Files created:"
echo "• automated_portfolio_analyzer.py - Main script"
echo "• portfolio_analyzer.log - Log file"
echo "• cron.log - Cron execution log"
echo ""
echo "To monitor the system:"
echo "• View logs: tail -f portfolio_analyzer.log"
echo "• View cron logs: tail -f cron.log"
echo "• Check crontab: crontab -l"
echo ""
echo "To stop the automation:"
echo "• Remove cron job: crontab -e (then delete the line)"
echo ""
echo "Happy investing! 📈"
