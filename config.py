import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///pricetracker.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Telegram Bot Configuration
    TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
    TELEGRAM_WEBHOOK_URL = os.environ.get('TELEGRAM_WEBHOOK_URL')
    
    # Price Check Interval (in minutes)
    PRICE_CHECK_INTERVAL = int(os.environ.get('PRICE_CHECK_INTERVAL', 5))
    
    # Railway Configuration
    PORT = int(os.environ.get('PORT', 5000))
