"""
Fixify — Authentication Test Suite
Tests registration, password hashing, dual login, rate limiting, OTP, and password reset.
"""
import pytest
from database.db import get_db
from services.auth_service import hash_password, verify_password, check_login_rate_limit, record_login_attempt


def test_password_hashing():
    """Verify Werkzeug password hashing and verification."""
    pwd = "SecurePassword@123"
    hashed = hash_password(pwd)
    assert hashed != pwd
    assert verify_password(pwd, hashed) is True
    assert verify_password("WrongPassword", hashed) is False


def test_customer_registration(client, app):
    """Test successful customer registration."""
    response = client.post('/auth/register', data={
        'full_name': 'New Customer',
        'email': 'newcustomer@test.com',
        'mobile': '9876543299',
        'password': 'Password@123',
        'confirm_password': 'Password@123'
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b'Registration successful' in response.data

    with app.app_context():
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE email = 'newcustomer@test.com'").fetchone()
        assert user is not None
        assert user['role'] == 'customer'  # Public registration strictly creates customer role


def test_duplicate_registration_rejected(client):
    """Test rejection of duplicate email and mobile during registration."""
    # Try registering with existing demo email
    response = client.post('/auth/register', data={
        'full_name': 'Clone User',
        'email': 'customer@fixify.demo',
        'mobile': '9999999999',
        'password': 'Password@123',
        'confirm_password': 'Password@123'
    }, follow_redirects=True)

    assert b'already exists' in response.data


def test_login_success_and_logout(client, auth):
    """Test login with email & password followed by logout."""
    res = auth.login_customer()
    assert res.status_code == 200
    assert b'Welcome back' in res.data

    # Check session
    with client.session_transaction() as sess:
        assert sess['user_role'] == 'customer'
        assert sess['user_email'] == 'customer@fixify.demo'

    # Logout
    logout_res = auth.logout()
    assert b'logged out' in logout_res.data
    with client.session_transaction() as sess:
        assert 'user_id' not in sess


def test_login_invalid_credentials(client, auth):
    """Test login failure with incorrect password."""
    res = auth.login('customer@fixify.demo', 'WrongPassword@123')
    assert b'Invalid credentials' in res.data


def test_mobile_otp_flow(client, app):
    """Test mobile OTP request and verification."""
    # Request OTP for registered mobile
    res = client.post('/auth/send-otp', data={'mobile': '9000000005'}, follow_redirects=True)
    assert res.status_code == 200
    assert (b'Verification code generated' in res.data) or (b'OTP code sent' in res.data)

    # Retrieve generated OTP from DB
    with app.app_context():
        db = get_db()
        token = db.execute(
            "SELECT otp_code FROM otp_tokens WHERE mobile = '9000000005' ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        assert token is not None
        otp = token['otp_code']

    # Verify with correct OTP
    verify_res = client.post('/auth/verify-otp', data={
        'mobile': '9000000005',
        'otp_code': otp
    }, follow_redirects=True)

    assert b'Logged in successfully' in verify_res.data
    with client.session_transaction() as sess:
        assert sess['user_role'] == 'customer'


def test_password_reset_flow(client, app):
    """Test password reset request and token consumption."""
    res = client.post('/auth/forgot-password', data={'identifier': 'customer@fixify.demo'}, follow_redirects=True)
    assert res.status_code == 200

    # Retrieve token
    with app.app_context():
        db = get_db()
        user = db.execute("SELECT id FROM users WHERE email = 'customer@fixify.demo'").fetchone()
        token_row = db.execute(
            "SELECT token FROM password_reset_tokens WHERE user_id = ? AND is_used = 0",
            (user['id'],)
        ).fetchone()
        assert token_row is not None
        token = token_row['token']

    # Complete reset
    reset_res = client.post(f'/auth/reset-password/{token}', data={
        'new_password': 'NewPassword@123',
        'confirm_password': 'NewPassword@123'
    }, follow_redirects=True)

    assert b'password has been reset successfully' in reset_res.data


def test_totp_flow(client, auth, app):
    """Test setting up Google Authenticator TOTP and using it to log in."""
    import pyotp
    # Login as customer
    auth.login_customer()

    # Access TOTP setup page
    res = client.get('/auth/totp/setup')
    assert res.status_code == 200
    assert b'Set Up Two-Factor Authentication' in res.data

    with client.session_transaction() as sess:
        secret = sess.get('pending_totp_secret')
        assert secret is not None

    # Generate valid TOTP code
    totp = pyotp.TOTP(secret)
    code = totp.now()

    # Submit verification
    verify_res = client.post('/auth/totp/setup', data={'code': code}, follow_redirects=True)
    assert verify_res.status_code == 200
    assert b'Google Authenticator enabled successfully' in verify_res.data

    with app.app_context():
        db = get_db()
        user = db.execute("SELECT is_totp_enabled, totp_secret FROM users WHERE email = 'customer@fixify.demo'").fetchone()
        assert user['is_totp_enabled'] == 1
        assert user['totp_secret'] == secret

    # Logout
    auth.logout()

    # Login via OTP tab using TOTP code
    totp_now = pyotp.TOTP(secret).now()
    otp_login = client.post('/auth/verify-otp', data={
        'mobile': 'customer@fixify.demo',
        'otp_code': totp_now
    }, follow_redirects=True)
    assert otp_login.status_code == 200
    assert b'Logged in successfully' in otp_login.data
    with client.session_transaction() as sess:
        assert sess.get('user_role') == 'customer'

    # Disable TOTP
    disable_res = client.post('/auth/totp/disable', follow_redirects=True)
    assert b'Google Authenticator 2FA disabled' in disable_res.data
    with app.app_context():
        db = get_db()
        user = db.execute("SELECT is_totp_enabled, totp_secret FROM users WHERE email = 'customer@fixify.demo'").fetchone()
        assert user['is_totp_enabled'] == 0
        assert user['totp_secret'] is None


def test_google_auth_flows(client, app):
    """Test Google setup view and demo simulation flow."""
    # Test GET /auth/google/setup shows setup page
    res = client.get('/auth/google/setup')
    assert res.status_code == 200
    assert b'Real Google OAuth 2.0 Integration' in res.data

    # Test GET /auth/google initiates OAuth flow when credentials set
    res_login = client.get('/auth/google')
    if app.config.get('GOOGLE_CLIENT_ID'):
        assert res_login.status_code == 302
        assert 'accounts.google.com' in res_login.headers['Location']
    else:
        assert res_login.status_code == 200

    # Test demo profile simulation
    sim_res = client.get('/auth/google/simulate-demo', follow_redirects=True)
    assert sim_res.status_code == 200
    assert b'Signed in via Google Profile Simulation' in sim_res.data
    with client.session_transaction() as sess:
        assert sess['user_email'] == 'alex.rivera.google@gmail.com'
        assert sess['user_role'] == 'customer'

