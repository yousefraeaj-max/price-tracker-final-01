from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
import secrets

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    phone = db.Column(db.String(20), unique=True, nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    telegram_chat_id = db.Column(db.String(100), nullable=True)
    telegram_phone = db.Column(db.String(20), nullable=True)
    activation_token = db.Column(db.String(100), unique=True, nullable=True)
    is_active = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Additional settings
    notification_threshold = db.Column(db.Float, default=5.0)  # Minimum price change percentage to notify
    
    # Relationships
    links = db.relationship('Link', backref='user', lazy=True, cascade='all, delete-orphan')
    
    def set_password(self, password):
        from werkzeug.security import generate_password_hash
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        from werkzeug.security import check_password_hash
        return check_password_hash(self.password_hash, password)
    
    def generate_activation_token(self):
        self.activation_token = secrets.token_urlsafe(32)
        return self.activation_token

class Link(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    url = db.Column(db.String(500), nullable=False)
    name = db.Column(db.String(200), nullable=True)
    link_type = db.Column(db.String(20), nullable=False)  # 'my_store' or 'competitor'
    is_active = db.Column(db.Boolean, default=True)
    last_price = db.Column(db.Float, nullable=True)
    last_checked = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    price_history = db.relationship('PriceHistory', backref='link', lazy=True, cascade='all, delete-orphan')

class PriceHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    link_id = db.Column(db.Integer, db.ForeignKey('link.id'), nullable=False)
    price = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(10), nullable=True)
    checked_at = db.Column(db.DateTime, default=datetime.utcnow)
