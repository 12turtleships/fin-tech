#!/usr/bin/env python3
"""
Test script for email functionality
"""

import os
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

# Email configuration
EMAIL_CONFIG = {
    'smtp_server': 'smtp.gmail.com',
    'smtp_port': 587,
    'sender_email': 'sungchun71@gmail.com',
    'sender_password': os.getenv('EMAIL_PASSWORD'),
    'recipient_email': 'sungchun71@gmail.com'
}

def test_email():
    """Test email sending functionality."""
    print("🧪 Testing Email Functionality")
    print("=" * 40)
    
    if not EMAIL_CONFIG['sender_password']:
        print("❌ EMAIL_PASSWORD environment variable not set")
        print("Please set it with: export EMAIL_PASSWORD='your_app_password'")
        return False
    
    try:
        # Create test message
        msg = MIMEMultipart()
        msg['From'] = EMAIL_CONFIG['sender_email']
        msg['To'] = EMAIL_CONFIG['recipient_email']
        msg['Subject'] = "🧪 Portfolio Analyzer Test Email"
        
        body = f"""
Portfolio Analyzer Test Email
============================

This is a test email from your automated portfolio analyzer.

Test Details:
• Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
• From: {EMAIL_CONFIG['sender_email']}
• To: {EMAIL_CONFIG['recipient_email']}

If you receive this email, your email configuration is working correctly!

Best regards,
Your Portfolio Analyzer
"""
        
        msg.attach(MIMEText(body, 'plain'))
        
        # Send email
        context = ssl.create_default_context()
        with smtplib.SMTP(EMAIL_CONFIG['smtp_server'], EMAIL_CONFIG['smtp_port']) as server:
            server.starttls(context=context)
            server.login(EMAIL_CONFIG['sender_email'], EMAIL_CONFIG['sender_password'])
            server.send_message(msg)
        
        print("✅ Test email sent successfully!")
        print(f"📧 Check your inbox at {EMAIL_CONFIG['recipient_email']}")
        return True
        
    except Exception as e:
        print(f"❌ Failed to send test email: {str(e)}")
        return False

if __name__ == "__main__":
    test_email()
