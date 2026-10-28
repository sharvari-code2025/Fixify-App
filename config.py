"""
Fixify — Application Configuration
Loads settings from environment variables with sensible defaults for development.
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Base configuration."""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'fixify-dev-secret-change-in-production')
    DATABASE = os.environ.get('DATABASE', os.path.join(os.path.dirname(__file__), 'fixify.db'))
    DEBUG = os.environ.get('FLASK_DEBUG', '0') == '1'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB upload limit
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'static', 'uploads')
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

    # Session settings
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = 3600  # 1 hour

    # Rate limiting
    MAX_LOGIN_ATTEMPTS = 5
    LOGIN_LOCKOUT_SECONDS = 300  # 5 minutes

    # OTP settings (demo mode)
    OTP_EXPIRY_SECONDS = 300  # 5 minutes
    OTP_MAX_ATTEMPTS = 3
    OTP_RESEND_COOLDOWN = 60  # 1 minute

    # Password reset
    RESET_TOKEN_EXPIRY_SECONDS = 1800  # 30 minutes

    # Google OAuth 2.0
    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', '')
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', '')
    GOOGLE_REDIRECT_URI = os.environ.get('GOOGLE_REDIRECT_URI', '')

    # Real Email OTP (SMTP, Gmail, SendGrid, etc.)
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', '1') == '1'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', '')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', '')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'Fixify Support <no-reply@fixify.com>')

    # Real SMS OTP (Twilio or Fast2SMS)
    SMS_PROVIDER = os.environ.get('SMS_PROVIDER', 'twilio')
    TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID', '')
    TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN', '')
    TWILIO_PHONE_NUMBER = os.environ.get('TWILIO_PHONE_NUMBER', '')
    FAST2SMS_API_KEY = os.environ.get('FAST2SMS_API_KEY', '')


class TestConfig(Config):
    """Testing configuration."""
    TESTING = True
    DATABASE = ':memory:'
    SECRET_KEY = 'test-secret-key'
    WTF_CSRF_ENABLED = False
