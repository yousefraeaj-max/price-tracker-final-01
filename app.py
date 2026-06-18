from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from datetime import datetime, timedelta
import os
import threading
import logging

from config import Config
from database import db, User, Link, PriceHistory
from price_scraper import PriceScraper
from telegram_bot import TelegramBot
from apscheduler.schedulers.background import BackgroundScheduler

# Initialize Flask app
app = Flask(__name__)
app.config.from_object(Config)

# Initialize extensions
db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'يرجى تسجيل الدخول للوصول إلى هذه الصفحة'

# Initialize price scraper
scraper = PriceScraper()

# Initialize Telegram bot (if token is provided)
telegram_bot = None
if app.config['TELEGRAM_BOT_TOKEN']:
    telegram_bot = TelegramBot(
        app,
        app.config['TELEGRAM_BOT_TOKEN'],
        app.config.get('TELEGRAM_WEBHOOK_URL', '')
    )

# Initialize scheduler for price checking
scheduler = BackgroundScheduler()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Create database tables
with app.app_context():
    db.create_all()

# Routes
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email_or_phone = request.form.get('email_or_phone')
        password = request.form.get('password')
        
        user = User.query.filter(
            (User.email == email_or_phone) | (User.phone == email_or_phone)
        ).first()
        
        if user and user.check_password(password):
            if not user.is_active:
                flash('⚠️ حسابك معلق. يرجى تفعيله عبر تليجرام أولاً.', 'warning')
                return render_template('pending_activation.html', user=user)
            
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('❌ البريد الإلكتروني أو رقم الهاتف أو كلمة المرور غير صحيحة.', 'error')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        # Validation
        if not email and not phone:
            flash('❌ يجب إدخال البريد الإلكتروني أو رقم الهاتف.', 'error')
            return render_template('register.html')
        
        if password != confirm_password:
            flash('❌ كلمات المرور غير متطابقة.', 'error')
            return render_template('register.html')
        
        # Check if user already exists
        if email and User.query.filter_by(email=email).first():
            flash('❌ هذا البريد الإلكتروني مسجل بالفعل.', 'error')
            return render_template('register.html')
        
        if phone and User.query.filter_by(phone=phone).first():
            flash('❌ رقم الهاتف مسجل بالفعل.', 'error')
            return render_template('register.html')
        
        # Create user
        user = User(
            name=name,
            email=email if email else None,
            phone=phone if phone else None
        )
        user.set_password(password)
        user.generate_activation_token()
        
        db.session.add(user)
        db.session.commit()
        
        flash('✅ تم إنشاء الحساب بنجاح! يرجى تفعيله عبر تليجرام.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('تم تسجيل الخروج بنجاح.', 'success')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    if not current_user.is_active:
        return render_template('pending_activation.html', user=current_user)
    
    my_store_links = Link.query.filter_by(user_id=current_user.id, link_type='my_store').all()
    competitor_links = Link.query.filter_by(user_id=current_user.id, link_type='competitor').all()
    
    # Calculate statistics
    total_links = len(my_store_links) + len(competitor_links)
    active_links = len([l for l in my_store_links + competitor_links if l.is_active])
    recent_changes = PriceHistory.query.join(Link).filter(Link.user_id == current_user.id).order_by(PriceHistory.checked_at.desc()).limit(5).all()
    
    return render_template('dashboard.html', 
                         my_store_links=my_store_links,
                         competitor_links=competitor_links,
                         total_links=total_links,
                         active_links=active_links,
                         recent_changes=recent_changes)

@app.route('/add-link', methods=['POST'])
@login_required
def add_link():
    url = request.form.get('url')
    name = request.form.get('name')
    link_type = request.form.get('link_type')  # 'my_store' or 'competitor'
    
    if not url:
        flash('❌ الرابط مطلوب.', 'error')
        return redirect(url_for('dashboard'))
    
    link = Link(
        user_id=current_user.id,
        url=url,
        name=name if name else url,
        link_type=link_type
    )
    
    db.session.add(link)
    db.session.commit()
    
    flash('✅ تم إضافة الرابط بنجاح!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/delete-link/<int:link_id>')
@login_required
def delete_link(link_id):
    link = Link.query.get_or_404(link_id)
    
    if link.user_id != current_user.id:
        flash('❌ ليس لديك صلاحية حذف هذا الرابط.', 'error')
        return redirect(url_for('dashboard'))
    
    db.session.delete(link)
    db.session.commit()
    
    flash('✅ تم حذف الرابط بنجاح!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/toggle-link/<int:link_id>')
@login_required
def toggle_link(link_id):
    link = Link.query.get_or_404(link_id)
    
    if link.user_id != current_user.id:
        flash('❌ ليس لديك صلاحية تعديل هذا الرابط.', 'error')
        return redirect(url_for('dashboard'))
    
    link.is_active = not link.is_active
    db.session.commit()
    
    status = 'تفعيل' if link.is_active else 'إيقاف'
    flash(f'✅ تم {status} الرابط بنجاح!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/link-history/<int:link_id>')
@login_required
def link_history(link_id):
    link = Link.query.get_or_404(link_id)
    
    if link.user_id != current_user.id:
        flash('❌ ليس لديك صلاحية عرض هذا الرابط.', 'error')
        return redirect(url_for('dashboard'))
    
    history = PriceHistory.query.filter_by(link_id=link_id).order_by(PriceHistory.checked_at.desc()).limit(50).all()
    
    # Calculate statistics
    if history:
        prices = [h.price for h in history]
        min_price = min(prices)
        max_price = max(prices)
        avg_price = sum(prices) / len(prices)
        current_price = history[0].price
    else:
        min_price = max_price = avg_price = current_price = None
    
    return render_template('link_history.html', link=link, history=history,
                         min_price=min_price, max_price=max_price, 
                         avg_price=avg_price, current_price=current_price)

@app.route('/api/verify-token', methods=['POST'])
def verify_token():
    """Verify activation token from Telegram bot"""
    data = request.json
    token = data.get('token')
    
    user = User.query.filter_by(activation_token=token).first()
    
    if user:
        return jsonify({'valid': True})
    else:
        return jsonify({'valid': False}), 400

@app.route('/api/activate-account', methods=['POST'])
def activate_account():
    """Activate account from Telegram bot"""
    data = request.json
    token = data.get('token')
    chat_id = data.get('chat_id')
    phone = data.get('phone')
    
    user = User.query.filter_by(activation_token=token).first()
    
    if not user:
        return jsonify({'success': False}), 400
    
    # Update user
    user.telegram_chat_id = str(chat_id)
    user.telegram_phone = phone
    user.is_active = True
    user.activation_token = None
    
    db.session.commit()
    
    return jsonify({'success': True})

@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    if request.method == 'POST':
        notification_threshold = request.form.get('notification_threshold', type=float)
        
        if notification_threshold is not None and notification_threshold >= 0:
            current_user.notification_threshold = notification_threshold
            db.session.commit()
            flash('✅ تم تحديث الإعدادات بنجاح!', 'success')
        else:
            flash('❌ قيمة غير صحيحة.', 'error')
        
        return redirect(url_for('settings'))
    
    return render_template('settings.html')

@app.route('/compare')
@login_required
def compare():
    """Compare prices of multiple products"""
    links = Link.query.filter_by(user_id=current_user.id, is_active=True).all()
    
    # Get latest price for each link
    comparison_data = []
    for link in links:
        latest = PriceHistory.query.filter_by(link_id=link.id).order_by(PriceHistory.checked_at.desc()).first()
        if latest:
            comparison_data.append({
                'link': link,
                'price': latest.price,
                'checked_at': latest.checked_at
            })
    
    # Sort by price
    comparison_data.sort(key=lambda x: x['price'])
    
    return render_template('compare.html', comparison_data=comparison_data)

@app.route('/statistics')
@login_required
def statistics():
    """Show price statistics and trends"""
    links = Link.query.filter_by(user_id=current_user.id).all()
    
    stats = []
    for link in links:
        history = PriceHistory.query.filter_by(link_id=link.id).order_by(PriceHistory.checked_at.desc()).limit(30).all()
        
        if len(history) >= 2:
            current_price = history[0].price
            previous_price = history[1].price
            change_percent = ((current_price - previous_price) / previous_price) * 100 if previous_price > 0 else 0
            
            prices = [h.price for h in history]
            min_price = min(prices)
            max_price = max(prices)
            avg_price = sum(prices) / len(prices)
            
            stats.append({
                'link': link,
                'current_price': current_price,
                'previous_price': previous_price,
                'change_percent': change_percent,
                'min_price': min_price,
                'max_price': max_price,
                'avg_price': avg_price,
                'history_count': len(history)
            })
    
    return render_template('statistics.html', stats=stats)

@app.route('/check-activation/<token>')
def check_activation(token):
    """Check if account is activated (for polling)"""
    user = User.query.filter_by(activation_token=token).first()
    
    if user and user.is_active:
        return jsonify({'activated': True})
    else:
        return jsonify({'activated': False})

@app.route('/telegram/webhook', methods=['POST'])
def telegram_webhook():
    """Handle Telegram webhook"""
    if telegram_bot:
        # Process the update
        from telegram import Update
        from telegram.ext import Application
        import json
        
        update = Update.de_json(request.get_json(force=True), telegram_bot.application.bot)
        telegram_bot.application.update_queue.put(update)
        
        return jsonify({'status': 'ok'})
    return jsonify({'status': 'error'}), 400

# Price checking function
def check_prices():
    """Check prices for all active links"""
    with app.app_context():
        logger.info("Starting price check...")
        
        active_links = Link.query.filter_by(is_active=True).all()
        
        for link in active_links:
            try:
                price = scraper.extract_price(link.url)
                
                if price:
                    # Record price history
                    history = PriceHistory(
                        link_id=link.id,
                        price=price,
                        currency='EGP'
                    )
                    db.session.add(history)
                    
                    # Check if price changed
                    if link.last_price and price != link.last_price:
                        # Calculate change percentage
                        change_percent = ((price - link.last_price) / link.last_price) * 100 if link.last_price > 0 else 0
                        
                        # Send notification only if change exceeds threshold
                        if abs(change_percent) >= link.user.notification_threshold:
                            if link.user.telegram_chat_id:
                                direction = "📈 ارتفاع" if price > link.last_price else "📉 انخفاض"
                                message = (
                                    f"🔔 <b>تغيير في السعر!</b>\n\n"
                                    f"📦 المنتج: {link.name}\n"
                                    f"{direction} بنسبة {abs(change_percent):.1f}%\n"
                                    f"💰 السعر القديم: {link.last_price} ج.م\n"
                                    f"💰 السعر الجديد: {price} ج.م\n"
                                    f"🔗 الرابط: {link.url}"
                                )
                                telegram_bot.send_notification(link.user.telegram_chat_id, message)
                    
                    link.last_price = price
                    link.last_checked = datetime.utcnow()
                    
            except Exception as e:
                logger.error(f"Error checking price for link {link.id}: {e}")
        
        db.session.commit()
        logger.info("Price check completed.")

# Start scheduler
def start_scheduler():
    scheduler.add_job(
        func=check_prices,
        trigger='interval',
        minutes=app.config['PRICE_CHECK_INTERVAL'],
        id='price_check_job',
        name='Check prices periodically',
        replace_existing=True
    )
    scheduler.start()
    logger.info("Scheduler started.")

# Set webhook on startup
def set_telegram_webhook():
    if telegram_bot and app.config['TELEGRAM_WEBHOOK_URL']:
        telegram_bot.set_webhook()

if __name__ == '__main__':
    # Start scheduler in a separate thread
    scheduler_thread = threading.Thread(target=start_scheduler)
    scheduler_thread.daemon = True
    scheduler_thread.start()
    
    # Set Telegram webhook
    set_telegram_webhook()
    
    # Run Flask app
    app.run(host='0.0.0.0', port=app.config['PORT'], debug=False)
