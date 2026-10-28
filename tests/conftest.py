"""
Fixify — Pytest Fixtures & Configuration
Provides isolated temporary database instances and authenticated test clients.
"""
import os
import tempfile
import pytest
from app import create_app
from config import TestConfig
from database.db import init_db, seed_demo_data, get_db


@pytest.fixture
def app():
    """Create and configure a fresh Flask app instance for each test."""
    db_fd, db_path = tempfile.mkstemp()

    class CustomTestConfig(TestConfig):
        DATABASE = db_path
        TESTING = True
        WTF_CSRF_ENABLED = False
        SECRET_KEY = 'test-secret-key-123'

    flask_app = create_app(CustomTestConfig)

    with flask_app.app_context():
        # Read schema and execute directly into the temp db
        schema_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'schema.sql')
        db = get_db()
        with open(schema_path, 'r') as f:
            db.executescript(f.read())
        seed_demo_data()

    yield flask_app

    os.close(db_fd)
    try:
        os.unlink(db_path)
    except Exception:
        pass


@pytest.fixture
def client(app):
    """Test client for performing HTTP requests."""
    return app.test_client()


class AuthActions:
    """Helper for logging in with different roles."""
    def __init__(self, client):
        self._client = client

    def login(self, email='customer@fixify.demo', password='Customer@123'):
        return self._client.post(
            '/auth/login',
            data={'email': email, 'password': password, 'login_type': 'password'},
            follow_redirects=True
        )

    def logout(self):
        return self._client.get('/auth/logout', follow_redirects=True)

    def login_admin(self):
        return self.login('admin@fixify.demo', 'Admin@123')

    def login_technician(self):
        return self.login('tech@fixify.demo', 'Tech@123')

    def login_delivery(self):
        return self.login('delivery@fixify.demo', 'Delivery@123')

    def login_customer(self):
        return self.login('customer@fixify.demo', 'Customer@123')


@pytest.fixture
def auth(client):
    """Fixture providing authentication helpers."""
    return AuthActions(client)
