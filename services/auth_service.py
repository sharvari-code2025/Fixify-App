"""
Fixify — Authentication & Security Service
Handles password hashing, rate limiting, OTP generation, password reset tokens, and role authorization.
"""
import secrets
import string
from datetime import datetime, timedelta
from functools import wraps
from flask import session, redirect, url_for, flash, abort, request, current_app
from werkzeug.security import generate_password_hash, check_password_hash
from database.db import get_db, query_db, insert_db, update_db


def hash_password(password: str) -> str:
    """Hash password securely using Werkzeug."""
    return generate_password_hash(password, method='scrypt')


def verify_password(password: str, password_hash: str) -> bool:
    """Verify password against Werkzeug hash."""
    return check_password_hash(password_hash, password)


# ============================================================
# LOGIN RATE LIMITING
# ============================================================
def check_login_rate_limit(identifier: str) -> tuple[bool, int]:
    """
    Check if an identifier (email or mobile) has exceeded failed login attempts.
    Returns (is_locked, remaining_seconds).
    """
    db = get_db()
    lockout_sec = current_app.config.get('LOGIN_LOCKOUT_SECONDS', 300)
    max_attempts = current_app.config.get('MAX_LOGIN_ATTEMPTS', 5)

    cutoff = datetime.now() - timedelta(seconds=lockout_sec)
    cutoff_str = cutoff.strftime('%Y-%m-%d %H:%M:%S')

    row = db.execute(
        """SELECT COUNT(*) as failed_count, MAX(attempt_time) as last_attempt
           FROM login_attempts 
           WHERE identifier = ? AND success = 0 AND attempt_time > ?""",
        (identifier, cutoff_str)
    ).fetchone()

    if row and row['failed_count'] >= max_attempts:
        # Calculate remaining time
        if row['last_attempt']:
            try:
                last_time = datetime.strptime(row['last_attempt'], '%Y-%m-%d %H:%M:%S')
                elapsed = (datetime.now() - last_time).total_seconds()
                rem = max(0, int(lockout_sec - elapsed))
                return True, rem
            except Exception:
                return True, lockout_sec
        return True, lockout_sec

    return False, 0


def record_login_attempt(identifier: str, success: bool):
    """Record an authentication attempt for rate limiting."""
    db = get_db()
    db.execute(
        "INSERT INTO login_attempts (identifier, success) VALUES (?, ?)",
        (identifier, 1 if success else 0)
    )
    db.commit()


# ============================================================
# DEMO OTP SERVICE (Mobile Login)
# ============================================================
def generate_mobile_otp(mobile: str) -> tuple[str, str | None]:
    """
    Generate a 6-digit OTP for mobile verification.
    Enforces cooldown between requests.
    Returns (otp_code, error_message).
    """
    db = get_db()
    cooldown = current_app.config.get('OTP_RESEND_COOLDOWN', 60)
    expiry_sec = current_app.config.get('OTP_EXPIRY_SECONDS', 300)

    # Check cooldown
    cutoff = (datetime.now() - timedelta(seconds=cooldown)).strftime('%Y-%m-%d %H:%M:%S')
    recent = db.execute(
        "SELECT id FROM otp_tokens WHERE mobile = ? AND created_at > ?",
        (mobile, cutoff)
    ).fetchone()

    if recent:
        return "", f"Please wait {cooldown} seconds before requesting a new OTP."

    # Generate cryptographically secure 6-digit code
    digits = string.digits
    otp_code = ''.join(secrets.choice(digits) for _ in range(6))
    expires_at = (datetime.now() + timedelta(seconds=expiry_sec)).strftime('%Y-%m-%d %H:%M:%S')

    db.execute(
        "INSERT INTO otp_tokens (mobile, otp_code, expires_at) VALUES (?, ?, ?)",
        (mobile, otp_code, expires_at)
    )
    db.commit()

    return otp_code, None


def verify_mobile_otp(mobile: str, otp_code: str) -> tuple[bool, str]:
    """
    Verify mobile OTP with attempt counting, expiration check, and single-use invalidation.
    Returns (success, message).
    """
    db = get_db()
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    max_attempts = current_app.config.get('OTP_MAX_ATTEMPTS', 3)

    record = db.execute(
        """SELECT id, otp_code, attempts, is_used, expires_at
           FROM otp_tokens
           WHERE mobile = ? AND is_used = 0 AND expires_at > ?
           ORDER BY created_at DESC LIMIT 1""",
        (mobile, now_str)
    ).fetchone()

    if not record:
        return False, "OTP has expired or is invalid. Please request a new one."

    if record['attempts'] >= max_attempts:
        return False, "Too many failed attempts. This OTP has been invalidated. Please request a new one."

    if record['otp_code'] != otp_code.strip():
        db.execute(
            "UPDATE otp_tokens SET attempts = attempts + 1 WHERE id = ?",
            (record['id'],)
        )
        db.commit()
        remaining = max_attempts - (record['attempts'] + 1)
        return False, f"Incorrect OTP. {remaining} attempt(s) remaining."

    # Success: mark as used
    db.execute("UPDATE otp_tokens SET is_used = 1 WHERE id = ?", (record['id'],))
    db.commit()
    return True, "OTP verified successfully."


# ============================================================
# PASSWORD RESET TOKENS
# ============================================================
def create_password_reset_token(user_id: int) -> str:
    """Generate a secure password reset token."""
    db = get_db()
    token = secrets.token_urlsafe(32)
    expiry_sec = current_app.config.get('RESET_TOKEN_EXPIRY_SECONDS', 1800)
    expires_at = (datetime.now() + timedelta(seconds=expiry_sec)).strftime('%Y-%m-%d %H:%M:%S')

    # Invalidate previous unused tokens for this user
    db.execute("UPDATE password_reset_tokens SET is_used = 1 WHERE user_id = ? AND is_used = 0", (user_id,))
    db.execute(
        "INSERT INTO password_reset_tokens (user_id, token, expires_at) VALUES (?, ?, ?)",
        (user_id, token, expires_at)
    )
    db.commit()
    return token


def verify_password_reset_token(token: str) -> int | None:
    """Validate reset token and return user_id if valid."""
    db = get_db()
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    record = db.execute(
        """SELECT user_id FROM password_reset_tokens
           WHERE token = ? AND is_used = 0 AND expires_at > ?""",
        (token, now_str)
    ).fetchone()
    return record['user_id'] if record else None


def consume_password_reset_token(token: str, new_password: str) -> bool:
    """Consume the reset token and update user password."""
    user_id = verify_password_reset_token(token)
    if not user_id:
        return False

    db = get_db()
    pwd_hash = hash_password(new_password)
    db.execute("UPDATE users SET password_hash = ?, updated_at = datetime('now') WHERE id = ?", (pwd_hash, user_id))
    db.execute("UPDATE password_reset_tokens SET is_used = 1 WHERE token = ?", (token,))
    db.commit()
    return True


# ============================================================
# ACCESS CONTROL DECORATORS
# ============================================================
def login_required(roles=None):
    """
    Decorator to protect routes.
    If roles is provided (str or list of str), verifies the user has one of those roles.
    """
    if isinstance(roles, str):
        roles = [roles]

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user_id = session.get('user_id')
            if not user_id:
                flash('Please log in to access this page.', 'warning')
                return redirect(url_for('auth.login', next=request.path))

            user_role = session.get('user_role')

            if roles and user_role not in roles:
                flash('You do not have permission to access that resource.', 'danger')
                # Redirect to appropriate home/dashboard based on actual role
                if user_role == 'admin':
                    return redirect(url_for('admin.dashboard'))
                elif user_role == 'technician':
                    return redirect(url_for('technician.dashboard'))
                elif user_role == 'delivery':
                    return redirect(url_for('delivery.dashboard'))
                else:
                    return redirect(url_for('customer.dashboard'))

            return f(*args, **kwargs)
        return decorated_function
    return decorator


def get_current_user():
    """Retrieve currently logged in user record from DB or None."""
    user_id = session.get('user_id')
    if not user_id:
        return None
    db = get_db()
    return db.execute("SELECT * FROM users WHERE id = ? AND is_active = 1", (user_id,)).fetchone()


# ============================================================
# REAL EMAIL & SMS OTP DISPATCH
# ============================================================
def send_email_otp(to_email: str, otp_code: str, user_name: str = "Customer") -> tuple[bool, str]:
    """
    Send real OTP code via SMTP (Gmail, Outlook, SendGrid, Amazon SES, or custom SMTP server).
    """
    mail_username = current_app.config.get('MAIL_USERNAME')
    mail_password = current_app.config.get('MAIL_PASSWORD')
    mail_server = current_app.config.get('MAIL_SERVER', 'smtp.gmail.com')
    mail_port = current_app.config.get('MAIL_PORT', 587)
    sender = current_app.config.get('MAIL_DEFAULT_SENDER') or mail_username or 'no-reply@fixify.com'

    if not mail_username or not mail_password:
        return False, "SMTP credentials (MAIL_USERNAME / MAIL_PASSWORD) not configured in .env."

    try:
        import smtplib
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText

        msg = MIMEMultipart('alternative')
        msg['Subject'] = f"Fixify Verification Code: {otp_code}"
        msg['From'] = sender
        msg['To'] = to_email

        html_body = f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 500px; margin: 0 auto; background: #0f172a; color: #f8fafc; padding: 28px; border-radius: 12px; border: 1px solid #1e293b;">
            <div style="text-align: center; margin-bottom: 24px;">
                <div style="font-size: 32px; margin-bottom: 6px;">⚡</div>
                <h1 style="color: #38bdf8; margin: 0; font-size: 22px; font-weight: 700;">Fixify</h1>
                <p style="color: #94a3b8; font-size: 13px; margin: 4px 0 0;">Smart Mobile Repair Management System</p>
            </div>
            <div style="background: #1e293b; padding: 24px; border-radius: 8px; text-align: center; border: 1px solid #334155;">
                <p style="margin: 0 0 10px; color: #cbd5e1; font-size: 15px;">Hello <strong>{user_name}</strong>,</p>
                <p style="margin: 0 0 20px; color: #94a3b8; font-size: 13px;">Use the following one-time password (OTP) to authenticate your session:</p>
                <div style="font-size: 34px; font-weight: 800; letter-spacing: 8px; color: #38bdf8; background: #0b1120; padding: 14px 28px; display: inline-block; border-radius: 8px; border: 1px solid #0284c7; user-select: all;">
                    {otp_code}
                </div>
                <p style="margin: 20px 0 0; color: #64748b; font-size: 12px;">This code expires in 5 minutes. If you did not request this, please ignore this email.</p>
            </div>
            <div style="text-align: center; margin-top: 20px; color: #475569; font-size: 11px;">
                Fixify Platform &bull; Automated Security Service &bull; Do not reply to this email
            </div>
        </div>
        """
        plain_body = f"Hello {user_name},\n\nYour Fixify one-time verification code is: {otp_code}\n\nThis code expires in 5 minutes.\nDo not share this code with anyone."

        msg.attach(MIMEText(plain_body, 'plain'))
        msg.attach(MIMEText(html_body, 'html'))

        with smtplib.SMTP(mail_server, mail_port, timeout=10) as server:
            if current_app.config.get('MAIL_USE_TLS', True):
                server.starttls()
            server.login(mail_username, mail_password)
            server.sendmail(sender, [to_email], msg.as_string())

        return True, f"Real verification email dispatched to {to_email}."
    except Exception as e:
        return False, f"Email delivery failed: {str(e)}"


def send_sms_otp(mobile: str, otp_code: str) -> tuple[bool, str]:
    """
    Send real SMS OTP using configured SMS Gateway (Twilio or Fast2SMS).
    """
    sid = current_app.config.get('TWILIO_ACCOUNT_SID')
    token = current_app.config.get('TWILIO_AUTH_TOKEN')
    sender = current_app.config.get('TWILIO_PHONE_NUMBER')
    fast2sms_key = current_app.config.get('FAST2SMS_API_KEY')

    # Try Fast2SMS (popular in India, supports instant DLT/OTP route)
    if fast2sms_key:
        try:
            import requests
            res = requests.post(
                "https://www.fast2sms.com/dev/bulkV2",
                headers={"authorization": fast2sms_key},
                data={"variables_values": otp_code, "route": "otp", "numbers": mobile},
                timeout=8
            )
            data = res.json()
            if data.get('return'):
                return True, f"Real SMS dispatched to +91 {mobile} via Fast2SMS."
            return False, f"Fast2SMS rejected: {data.get('message', res.text)}"
        except Exception as e:
            return False, f"Fast2SMS dispatch error: {str(e)}"

    # Try Twilio
    if sid and token and sender:
        try:
            import requests
            to_num = mobile if mobile.startswith('+') else f"+91{mobile}"
            res = requests.post(
                f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
                auth=(sid, token),
                data={
                    'From': sender,
                    'To': to_num,
                    'Body': f'Your Fixify verification code is: {otp_code}. Valid for 5 minutes. Do not share.'
                },
                timeout=8
            )
            if res.status_code in (200, 201):
                return True, f"Real SMS dispatched to {to_num} via Twilio."
            return False, f"Twilio rejected dispatch: {res.text}"
        except Exception as e:
            return False, f"Twilio dispatch error: {str(e)}"

    return False, "SMS gateway credentials (Twilio or Fast2SMS) not configured in .env."


def dispatch_real_otp(mobile: str, email: str, otp_code: str, user_name: str = "Customer") -> dict:
    """
    Unified OTP dispatcher. Tries real SMS and real Email based on available credentials.
    Returns status dict with delivery details.
    """
    delivered_channels = []
    error_reasons = []

    # 1. Try real SMS if mobile provided
    if mobile:
        sms_ok, sms_msg = send_sms_otp(mobile, otp_code)
        if sms_ok:
            delivered_channels.append(f"SMS (+91 {mobile[-4:]})")
        else:
            error_reasons.append(f"SMS: {sms_msg}")

    # 2. Try real Email if email provided
    if email:
        email_ok, email_msg = send_email_otp(email, otp_code, user_name)
        if email_ok:
            delivered_channels.append(f"Email ({email})")
        else:
            error_reasons.append(f"Email: {email_msg}")

    has_real_send = len(delivered_channels) > 0

    return {
        'real_sent': has_real_send,
        'channels': delivered_channels,
        'summary': f"Sent via {', '.join(delivered_channels)}" if has_real_send else "No live gateways connected in .env yet",
        'reasons': error_reasons,
        'live_code': otp_code
    }


# ============================================================
# TOTP (Google Authenticator / Authy)
# ============================================================
def generate_totp_secret() -> str:
    """Generate a base32 TOTP secret for Google Authenticator."""
    import pyotp
    return pyotp.random_base32()


def get_totp_uri(secret: str, email: str) -> str:
    """Get the standard otpauth:// URI for QR code generation."""
    import pyotp
    return pyotp.totp.TOTP(secret).provisioning_uri(name=email, issuer_name='Fixify')


def verify_totp_code(secret: str, code: str) -> bool:
    """Verify 6-digit TOTP code against secret with a 1-step window tolerance."""
    if not secret or not code:
        return False
    import pyotp
    totp = pyotp.TOTP(secret)
    return totp.verify(code.strip(), valid_window=1)

