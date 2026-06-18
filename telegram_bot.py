from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import requests
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TelegramBot:
    def __init__(self, app, bot_token, webhook_url):
        self.app = app
        self.bot_token = bot_token
        self.webhook_url = webhook_url
        self.application = Application.builder().token(bot_token).build()
        
        # Register handlers
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CallbackQueryHandler(self.button_callback))
        self.application.add_handler(MessageHandler(filters.CONTACT, self.handle_contact))
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        args = context.args
        chat_id = update.effective_chat.id
        
        if args and len(args) > 0:
            # User has an activation token
            token = args[0]
            
            # Verify token with our app
            try:
                response = requests.post(
                    f"{self.webhook_url}/api/verify-token",
                    json={'token': token, 'chat_id': chat_id},
                    timeout=5
                )
                
                if response.status_code == 200:
                    # Token is valid, request phone number
                    keyboard = [[KeyboardButton("مشاركة رقم الهاتف", request_contact=True)]]
                    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
                    
                    await update.message.reply_text(
                        "مرحباً! 👋\n\n"
                        "لتفعيل حسابك، نحتاج تأكيد رقم هاتفك.\n"
                        "اضغط على الزر بالأسفل لمشاركة رقم هاتفك:",
                        reply_markup=reply_markup
                    )
                    
                    # Store token in user data
                    context.user_data['activation_token'] = token
                    return
                else:
                    await update.message.reply_text("❌ رابط التفعيل غير صالح أو منتهي.")
                    return
            except Exception as e:
                logger.error(f"Error verifying token: {e}")
                await update.message.reply_text("❌ حدث خطأ في التحقق من الرابط.")
                return
        else:
            # Regular start without token
            await update.message.reply_text(
                "🤖 مرحباً بك في بوت PriceTracker!\n\n"
                "هذا البوت يستخدم لتفعيل حسابك على موقع PriceTracker.\n"
                "يرجى تسجيل الدخول إلى الموقع واتباع خطوات تفعيل الحساب."
            )
    
    async def handle_contact(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle contact sharing"""
        contact = update.message.contact
        chat_id = update.effective_chat.id
        phone_number = contact.phone_number
        
        # Get activation token from user data
        token = context.user_data.get('activation_token')
        
        if not token:
            await update.message.reply_text("❌ لم يتم العثور على رمز التفعيل.")
            return
        
        # Send data to our app
        try:
            response = requests.post(
                f"{self.webhook_url}/api/activate-account",
                json={
                    'token': token,
                    'chat_id': chat_id,
                    'phone': phone_number
                },
                timeout=5
            )
            
            if response.status_code == 200:
                await update.message.reply_text(
                    "✅ تم تفعيل حسابك بنجاح!\n\n"
                    "يمكنك الآن العودة إلى الموقع والاستمتاع بجميع المميزات."
                )
            else:
                await update.message.reply_text("❌ حدث خطأ في تفعيل الحساب.")
        except Exception as e:
            logger.error(f"Error activating account: {e}")
            await update.message.reply_text("❌ حدث خطأ في الاتصال بالخادم.")
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button callbacks"""
        query = update.callback_query
        await query.answer()
    
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
    
    def set_webhook(self):
        """Set webhook for Telegram bot"""
        try:
            webhook_url = f"{self.webhook_url}/telegram/webhook"
            response = requests.post(
                f"https://api.telegram.org/bot{self.bot_token}/setWebhook",
                json={'url': webhook_url},
                timeout=10
            )
            logger.info(f"Webhook set response: {response.text}")
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Error setting webhook: {e}")
            return False
    
    def start(self):
        """Start the bot (for polling, not used with webhook)"""
        self.application.run_polling()
