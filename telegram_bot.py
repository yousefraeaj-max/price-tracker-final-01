import requests
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TelegramBot:
    def __init__(self, app, bot_token, webhook_url):
        self.app = app
        self.bot_token = bot_token
        self.webhook_url = webhook_url
    
    def send_notification(self, chat_id, message):
        """Send notification to user"""
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            response = requests.post(url, json={
                'chat_id': chat_id,
                'text': message,
                'parse_mode': 'HTML'
            }, timeout=5)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Error sending notification: {e}")
            return False
    
    def send_message(self, chat_id, text):
        """Send simple message to user"""
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            response = requests.post(url, json={
                'chat_id': chat_id,
                'text': text
            }, timeout=5)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return False
