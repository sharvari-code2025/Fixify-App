"""
Fixify — Authentication Routes
Handles user registration, dual login (password & OTP), password reset, profile, and logout.
"""
import os
import re
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
import secrets
from urllib.parse import urlencode
import requests
from database.db import get_db, query_db, insert_db, update_db
from services.auth_service import (
    hash_password, verify_password, check_login_rate_limit, record_login_attempt,
    generate_mobile_otp, verify_mobile_otp, create_password_reset_token,
    verify_password_reset_token, consume_password_reset_token, login_required, get_current_user,
    dispatch_real_otp, generate_totp_secret, get_totp_uri, verify_totp_code
)

bp = Blueprint('auth', __name__, url_prefix='/auth')

EMAIL_REGEX = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
PHONE_REGEX = r'^[6-9]\d{9}$'  # Standard 10-digit mobile number


@bp.route('/register', methods=['GET', 'POST'])
def register():
    """Customer registration route. Always assigns 'customer' role."""
    if session.get('user_id'):
        return redirect(url_for('customer.dashboard'))

    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        mobile = request.form.get('mobile', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        # Server-side validation
        errors = []
        if not full_name or len(full_name) < 2:
            errors.append('Full name must be at least 2 characters.')
        if not email or not re.match(EMAIL_REGEX, email):
            errors.append('Please provide a valid email address.')
        if not mobile or not re.match(PHONE_REGEX, mobile):
            errors.append('Mobile number must be a valid 10-digit number starting with 6-9.')
        if len(password) < 8:
            errors.append('Password must be at least 8 characters long.')
        if not any(c.isupper() for c in password) or not any(c.islower() for c in password) or not any(c.isdigit() for c in password):
            errors.append('Password must contain at least one uppercase letter, one lowercase letter, and one number.')
        if password != confirm_password:
            errors.append('Passwords do not match.')

        if errors:
            for err in errors:
                flash(err, 'danger')
            return render_template('register.html', full_name=full_name, email=email, mobile=mobile)

        # Duplicate account checks
        db = get_db()
        existing_email = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if existing_email:
            flash('An account with this email address already exists. Please log in.', 'warning')
            return render_template('register.html', full_name=full_name, email=email, mobile=mobile)

        existing_mobile = db.execute("SELECT id FROM users WHERE mobile = ?", (mobile,)).fetchone()
        if existing_mobile:
            flash('An account with this mobile number already exists. Please log in.', 'warning')
            return render_template('register.html', full_name=full_name, email=email, mobile=mobile)

        # Insert customer
        pwd_hash = hash_password(password)
        user_id = insert_db(
            "INSERT INTO users (full_name, email, mobile, password_hash, role) VALUES (?, ?, ?, ?, 'customer')",
            (full_name, email, mobile, pwd_hash)
        )

        flash('Registration successful! Please log in with your credentials.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('register.html')


@bp.route('/login', methods=['GET', 'POST'])
def login():
    """User login supporting Option A (Email/Password) and Option B (Mobile OTP tab)."""
    if session.get('user_id'):
        role = session.get('user_role')
        if role == 'admin':
            return redirect(url_for('admin.dashboard'))
        elif role == 'technician':
            return redirect(url_for('technician.dashboard'))
        elif role == 'delivery':
            return redirect(url_for('delivery.dashboard'))
        return redirect(url_for('customer.dashboard'))

    tab = request.args.get('tab', 'password')

    if request.method == 'POST':
        login_type = request.form.get('login_type', 'password')

        if login_type == 'password':
            identifier = request.form.get('email', '').strip().lower()
            password = request.form.get('password', '')

            # Check rate limit
            is_locked, rem_sec = check_login_rate_limit(identifier)
            if is_locked:
                flash(f'Account temporarily locked due to excessive failed attempts. Please retry in {rem_sec} seconds.', 'danger')
                return render_template('login.html', active_tab='password', email=identifier)

            db = get_db()
            user = db.execute(
                "SELECT * FROM users WHERE (email = ? OR mobile = ?) AND is_active = 1",
                (identifier, identifier)
            ).fetchone()

            if not user or not verify_password(password, user['password_hash']):
                record_login_attempt(identifier, success=False)
                flash('Invalid credentials. Please verify your email/phone and password.', 'danger')
                return render_template('login.html', active_tab='password', email=identifier)

            # Success
            record_login_attempt(identifier, success=True)
            session.clear()
            session['user_id'] = user['id']
            session['user_name'] = user['full_name']
            session['user_email'] = user['email']
            session['user_role'] = user['role']
            session.permanent = True

            flash(f'Welcome back, {user["full_name"]}!', 'success')
            next_url = request.args.get('next')
            if next_url and next_url.startswith('/'):
                return redirect(next_url)

            if user['role'] == 'admin':
                return redirect(url_for('admin.dashboard'))
            elif user['role'] == 'technician':
                return redirect(url_for('technician.dashboard'))
            elif user['role'] == 'delivery':
                return redirect(url_for('delivery.dashboard'))
            else:
                return redirect(url_for('customer.dashboard'))

    return render_template('login.html', active_tab=tab)


@bp.route('/send-otp', methods=['POST'])
def send_otp():
    """Send real OTP for user authentication across SMS and Email."""
    identifier = request.form.get('mobile', '').strip()

    db = get_db()
    # Check if identifier matches mobile or email
    user = db.execute(
        "SELECT * FROM users WHERE (mobile = ? OR email = ?) AND is_active = 1",
        (identifier, identifier.lower())
    ).fetchone()

    if not user:
        flash('No active account found for that mobile or email. Please register first.', 'warning')
        return render_template('login.html', active_tab='otp', mobile=identifier)

    # Use registered mobile for token generation (or fallback to identifier)
    token_mobile = user['mobile'] or identifier
    otp_code, error = generate_mobile_otp(token_mobile)
    if error:
        flash(error, 'warning')
        return render_template('login.html', active_tab='otp', mobile=identifier)

    # Dispatch via real email and/or real SMS
    delivery = dispatch_real_otp(user['mobile'], user['email'], otp_code, user['full_name'])

    if delivery['real_sent']:
        flash(f"✅ Real OTP code sent via {delivery['summary']}! Please check your device.", "success")
    else:
        # Transparent, helpful notification
        flash(
            f"⚡ Verification code generated: {otp_code}. (To receive live SMS/Email directly to your phone, set your Twilio or Gmail SMTP credentials in .env).",
            "info"
        )

    return render_template(
        'login.html',
        active_tab='otp',
        mobile=identifier,
        otp_sent=True,
        demo_otp=otp_code if not delivery['real_sent'] else None,
        real_sent=delivery['real_sent'],
        delivery_channel=delivery['summary']
    )


@bp.route('/verify-otp', methods=['POST'])
def verify_otp():
    """Verify OTP (SMS/Email or Google Authenticator TOTP) and authenticate user."""
    identifier = request.form.get('mobile', '').strip()
    otp_code = request.form.get('otp_code', '').strip()

    db = get_db()
    user = db.execute(
        "SELECT * FROM users WHERE (mobile = ? OR email = ?) AND is_active = 1",
        (identifier, identifier.lower())
    ).fetchone()

    if not user:
        flash('User account not found.', 'danger')
        return redirect(url_for('auth.login'))

    # Check if user has TOTP enabled and submitted a valid TOTP code
    is_totp_valid = False
    if user['is_totp_enabled'] and user['totp_secret']:
        is_totp_valid = verify_totp_code(user['totp_secret'], otp_code)

    if not is_totp_valid:
        # Verify database token
        token_mobile = user['mobile'] or identifier
        success, msg = verify_mobile_otp(token_mobile, otp_code)
        if not success:
            flash(msg, 'danger')
            return render_template('login.html', active_tab='otp', mobile=identifier, otp_sent=True)

    session.clear()
    session['user_id'] = user['id']
    session['user_name'] = user['full_name']
    session['user_email'] = user['email']
    session['user_role'] = user['role']
    session['avatar_url'] = user['avatar_url']
    session.permanent = True

    flash(f'Logged in successfully! Welcome back, {user["full_name"]}.', 'success')

    if user['role'] == 'admin':
        return redirect(url_for('admin.dashboard'))
    elif user['role'] == 'technician':
        return redirect(url_for('technician.dashboard'))
    elif user['role'] == 'delivery':
        return redirect(url_for('delivery.dashboard'))
    else:
        return redirect(url_for('customer.dashboard'))


# ============================================================
# REAL GOOGLE OAUTH 2.0 AUTHENTICATION
# ============================================================
@bp.route('/google')
def google_login():
    """Initiates real Google OAuth 2.0 flow."""
    client_id = current_app.config.get('GOOGLE_CLIENT_ID')
    client_secret = current_app.config.get('GOOGLE_CLIENT_SECRET')

    if not client_id or not client_secret:
        # Render a quick setup guide or modal so user can configure or test
        return render_template('google_setup.html')

    state = secrets.token_urlsafe(16)
    session['oauth_state'] = state
    redirect_uri = current_app.config.get('GOOGLE_REDIRECT_URI') or url_for('auth.google_callback', _external=True)

    params = {
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'response_type': 'code',
        'scope': 'openid email profile',
        'state': state,
        'access_type': 'offline',
        'prompt': 'select_account'
    }
    google_auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
    return redirect(google_auth_url)


@bp.route('/google/callback')
def google_callback():
    """Handles Google OAuth 2.0 code exchange and user authentication."""
    error = request.args.get('error')
    if error:
        flash(f'Google Sign-In was cancelled ({error}).', 'warning')
        return redirect(url_for('auth.login'))

    code = request.args.get('code')
    state = request.args.get('state')

    if not code or state != session.get('oauth_state'):
        flash('Invalid OAuth state. Please try signing in with Google again.', 'danger')
        return redirect(url_for('auth.login'))

    client_id = current_app.config.get('GOOGLE_CLIENT_ID')
    client_secret = current_app.config.get('GOOGLE_CLIENT_SECRET')
    redirect_uri = current_app.config.get('GOOGLE_REDIRECT_URI') or url_for('auth.google_callback', _external=True)

    try:
        token_res = requests.post(
            'https://oauth2.googleapis.com/token',
            data={
                'code': code,
                'client_id': client_id,
                'client_secret': client_secret,
                'redirect_uri': redirect_uri,
                'grant_type': 'authorization_code'
            },
            timeout=10
        )
        if token_res.status_code != 200:
            flash(f'Failed to exchange authorization token with Google ({token_res.status_code}). Please verify your Client Secret.', 'danger')
            return redirect(url_for('auth.login'))

        token_data = token_res.json()
        access_token = token_data.get('access_token')

        userinfo_res = requests.get(
            'https://www.googleapis.com/oauth2/v2/userinfo',
            headers={'Authorization': f'Bearer {access_token}'},
            timeout=10
        )
        if userinfo_res.status_code != 200:
            flash('Failed to fetch user profile information from Google.', 'danger')
            return redirect(url_for('auth.login'))

        user_info = userinfo_res.json()
        google_id = user_info.get('id')
        email = user_info.get('email', '').lower()
        full_name = user_info.get('name') or email.split('@')[0]
        avatar_url = user_info.get('picture')

        db = get_db()
        user = db.execute("SELECT * FROM users WHERE google_id = ? OR email = ?", (google_id, email)).fetchone()

        if user:
            db.execute(
                "UPDATE users SET google_id = ?, avatar_url = COALESCE(?, avatar_url), updated_at = datetime('now') WHERE id = ?",
                (google_id, avatar_url, user['id'])
            )
            db.commit()
            user_id = user['id']
            role = user['role']
            full_name = user['full_name']
        else:
            cur = db.execute(
                """INSERT INTO users (full_name, email, google_id, avatar_url, role, is_active)
                   VALUES (?, ?, ?, ?, 'customer', 1)""",
                (full_name, email, google_id, avatar_url)
            )
            db.commit()
            user_id = cur.lastrowid
            role = 'customer'

        session.clear()
        session['user_id'] = user_id
        session['user_name'] = full_name
        session['user_email'] = email
        session['user_role'] = role
        session['avatar_url'] = avatar_url
        session.permanent = True

        flash(f'Successfully signed in with Google! Welcome, {full_name}.', 'success')
        if role == 'admin':
            return redirect(url_for('admin.dashboard'))
        elif role == 'technician':
            return redirect(url_for('technician.dashboard'))
        elif role == 'delivery':
            return redirect(url_for('delivery.dashboard'))
        return redirect(url_for('customer.dashboard'))

    except Exception as e:
        flash(f'An error occurred during Google Sign-In: {str(e)}', 'danger')
        return redirect(url_for('auth.login'))


@bp.route('/google/setup', methods=['GET', 'POST'])
def google_setup():
    """Setup and credentials management for Google OAuth."""
    if request.method == 'POST':
        client_id = request.form.get('client_id', '').strip()
        client_secret = request.form.get('client_secret', '').strip()

        if client_id and client_secret:
            env_path = os.path.join(current_app.root_path, '.env')
            existing_lines = []
            if os.path.exists(env_path):
                with open(env_path, 'r', encoding='utf-8') as f:
                    existing_lines = f.readlines()

            new_lines = []
            keys_updated = {'GOOGLE_CLIENT_ID': False, 'GOOGLE_CLIENT_SECRET': False}
            for line in existing_lines:
                if line.startswith('GOOGLE_CLIENT_ID='):
                    new_lines.append(f'GOOGLE_CLIENT_ID={client_id}\n')
                    keys_updated['GOOGLE_CLIENT_ID'] = True
                elif line.startswith('GOOGLE_CLIENT_SECRET='):
                    new_lines.append(f'GOOGLE_CLIENT_SECRET={client_secret}\n')
                    keys_updated['GOOGLE_CLIENT_SECRET'] = True
                else:
                    new_lines.append(line)

            if not keys_updated['GOOGLE_CLIENT_ID']:
                new_lines.append(f'GOOGLE_CLIENT_ID={client_id}\n')
            if not keys_updated['GOOGLE_CLIENT_SECRET']:
                new_lines.append(f'GOOGLE_CLIENT_SECRET={client_secret}\n')

            with open(env_path, 'w', encoding='utf-8') as f:
                f.writelines(new_lines)

            # Update running app config in memory
            current_app.config['GOOGLE_CLIENT_ID'] = client_id
            current_app.config['GOOGLE_CLIENT_SECRET'] = client_secret

            flash('✅ Google OAuth credentials saved successfully! Redirecting to Google...', 'success')
            return redirect(url_for('auth.google_login'))
        else:
            flash('Please provide both Google Client ID and Google Client Secret.', 'danger')

    return render_template('google_setup.html')


@bp.route('/google/simulate-demo')
def google_simulate_demo():
    """Simulate Google Sign-in with a verified demo Google profile for immediate testing."""
    db = get_db()
    demo_email = "alex.rivera.google@gmail.com"
    demo_name = "Alex Rivera (Google User)"
    demo_sub = "google-oauth2-109876543210"
    demo_avatar = "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=150&auto=format&fit=crop&q=80"

    user = db.execute("SELECT * FROM users WHERE email = ?", (demo_email,)).fetchone()
    if not user:
        cur = db.execute(
            """INSERT INTO users (full_name, email, google_id, avatar_url, role, is_active)
               VALUES (?, ?, ?, ?, 'customer', 1)""",
            (demo_name, demo_email, demo_sub, demo_avatar)
        )
        db.commit()
        user_id = cur.lastrowid
        role = 'customer'
    else:
        user_id = user['id']
        role = user['role']

    session.clear()
    session['user_id'] = user_id
    session['user_name'] = demo_name
    session['user_email'] = demo_email
    session['user_role'] = role
    session['avatar_url'] = demo_avatar
    session.permanent = True

    flash('✅ Signed in via Google Profile Simulation (Alex Rivera)! Real Google OAuth is also active when credentials are set.', 'success')
    return redirect(url_for('customer.dashboard'))


# ============================================================
# TOTP (GOOGLE AUTHENTICATOR / AUTHY)
# ============================================================
@bp.route('/totp/setup', methods=['GET', 'POST'])
@login_required()
def totp_setup():
    """Set up Google Authenticator (TOTP) 2-factor authentication."""
    user = get_current_user()
    db = get_db()

    secret = session.get('pending_totp_secret')
    if not secret:
        secret = generate_totp_secret()
        session['pending_totp_secret'] = secret

    uri = get_totp_uri(secret, user['email'])

    if request.method == 'POST':
        code = request.form.get('code', '').strip()
        if verify_totp_code(secret, code):
            db.execute(
                "UPDATE users SET totp_secret = ?, is_totp_enabled = 1, updated_at = datetime('now') WHERE id = ?",
                (secret, user['id'])
            )
            db.commit()
            session.pop('pending_totp_secret', None)
            flash('✅ Google Authenticator enabled successfully! You can now use your app to log in.', 'success')
            return redirect(url_for('auth.profile'))
        else:
            flash('Invalid 6-digit code from your authenticator app. Please verify and try again.', 'danger')

    return render_template('totp_setup.html', secret=secret, uri=uri)


@bp.route('/totp/disable', methods=['POST'])
@login_required()
def totp_disable():
    """Disable Google Authenticator."""
    user = get_current_user()
    db = get_db()
    db.execute("UPDATE users SET is_totp_enabled = 0, totp_secret = NULL WHERE id = ?", (user['id'],))
    db.commit()
    flash('Google Authenticator 2FA disabled.', 'info')
    return redirect(url_for('auth.profile'))


@bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Password reset request flow with demo token delivery."""
    demo_reset_url = None
    if request.method == 'POST':
        identifier = request.form.get('identifier', '').strip().lower()
        db = get_db()
        user = db.execute(
            "SELECT * FROM users WHERE (email = ? OR mobile = ?) AND is_active = 1",
            (identifier, identifier)
        ).fetchone()

        if user:
            token = create_password_reset_token(user['id'])
            demo_reset_url = url_for('auth.reset_password', token=token, _external=True)
            flash(
                f'[DEMO MODE] Password reset token generated. In a production environment, an email would be dispatched. You can reset directly below.',
                'info'
            )
        else:
            # Prevent user enumeration in production; show clean message
            flash('If an account exists with that identifier, a reset link has been prepared.', 'info')

    return render_template('forgot_password.html', demo_reset_url=demo_reset_url)


@bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    """Reset password with validated token."""
    user_id = verify_password_reset_token(token)
    if not user_id:
        flash('Invalid or expired password reset link. Please request a new one.', 'danger')
        return redirect(url_for('auth.forgot_password'))

    if request.method == 'POST':
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')

        if len(new_password) < 8:
            flash('Password must be at least 8 characters long.', 'danger')
            return render_template('reset_password.html', token=token)

        if not any(c.isupper() for c in new_password) or not any(c.islower() for c in new_password) or not any(c.isdigit() for c in new_password):
            flash('Password must contain uppercase, lowercase, and numbers.', 'danger')
            return render_template('reset_password.html', token=token)

        if new_password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('reset_password.html', token=token)

        if consume_password_reset_token(token, new_password):
            flash('Your password has been reset successfully. Please log in with your new password.', 'success')
            return redirect(url_for('auth.login'))
        else:
            flash('Failed to reset password. Please try again.', 'danger')
            return redirect(url_for('auth.forgot_password'))

    return render_template('reset_password.html', token=token)


@bp.route('/profile', methods=['GET', 'POST'])
@login_required()
def profile():
    """User profile management and password change."""
    user = get_current_user()
    if not user:
        session.clear()
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'update_profile':
            full_name = request.form.get('full_name', '').strip()
            mobile = request.form.get('mobile', '').strip()

            if len(full_name) < 2:
                flash('Full name must be at least 2 characters.', 'danger')
            elif mobile and not re.match(PHONE_REGEX, mobile):
                flash('Mobile number must be a valid 10-digit number.', 'danger')
            elif not mobile and user['password_hash']:
                flash('Mobile number is required.', 'danger')
            else:
                db = get_db()
                if mobile:
                    existing = db.execute("SELECT id FROM users WHERE mobile = ? AND id != ?", (mobile, user['id'])).fetchone()
                    if existing:
                        flash('That mobile number is already in use by another account.', 'danger')
                        return render_template('profile.html', user=user)
                db.execute(
                    "UPDATE users SET full_name = ?, mobile = ?, updated_at = datetime('now') WHERE id = ?",
                    (full_name, mobile or None, user['id'])
                )
                db.commit()
                session['user_name'] = full_name
                flash('Profile updated successfully!', 'success')
                return redirect(url_for('auth.profile'))

        elif action == 'change_password':
            current_pwd = request.form.get('current_password', '')
            new_pwd = request.form.get('new_password', '')
            confirm_pwd = request.form.get('confirm_password', '')

            # Google-only accounts may not have a password_hash yet
            has_existing_password = bool(user['password_hash'])

            if has_existing_password and not verify_password(current_pwd, user['password_hash']):
                flash('Current password is incorrect.', 'danger')
            elif len(new_pwd) < 8:
                flash('New password must be at least 8 characters long.', 'danger')
            elif not any(c.isupper() for c in new_pwd) or not any(c.islower() for c in new_pwd) or not any(c.isdigit() for c in new_pwd):
                flash('Password must contain uppercase, lowercase, and a number.', 'danger')
            elif new_pwd != confirm_pwd:
                flash('New passwords do not match.', 'danger')
            else:
                db = get_db()
                new_hash = hash_password(new_pwd)
                db.execute("UPDATE users SET password_hash = ?, updated_at = datetime('now') WHERE id = ?", (new_hash, user['id']))
                db.commit()
                if has_existing_password:
                    flash('Password changed successfully!', 'success')
                else:
                    flash('Password set successfully! You can now log in with email and password.', 'success')
                return redirect(url_for('auth.profile'))

    return render_template('profile.html', user=user)


@bp.route('/logout')
def logout():
    """Clear session and log out user."""
    session.clear()
    flash('You have been logged out safely.', 'info')
    return redirect(url_for('index'))
