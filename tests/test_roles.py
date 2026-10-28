"""
Fixify — Role-Based Access Control Test Suite
Tests strict server-side authorization across customer, admin, technician, and delivery staff roles.
"""
import pytest


def test_unauthenticated_redirect(client):
    """Verify protected routes redirect anonymous guests to login."""
    routes = [
        '/customer/dashboard',
        '/admin/dashboard',
        '/technician/dashboard',
        '/delivery/dashboard',
        '/bookings/new',
        '/auth/profile'
    ]
    for r in routes:
        res = client.get(r, follow_redirects=False)
        assert res.status_code in (302, 401)
        assert '/auth/login' in res.headers.get('Location', '')


def test_customer_role_restrictions(client, auth):
    """Verify customer cannot access admin, technician, or delivery panels."""
    auth.login_customer()

    # Attempt admin dashboard
    res = client.get('/admin/dashboard', follow_redirects=True)
    assert b'permission' in res.data or b'Customer Portal' in res.data

    # Attempt technician dashboard
    res = client.get('/technician/dashboard', follow_redirects=True)
    assert b'permission' in res.data or b'Customer Portal' in res.data

    # Attempt delivery dashboard
    res = client.get('/delivery/dashboard', follow_redirects=True)
    assert b'permission' in res.data or b'Customer Portal' in res.data


def test_technician_role_restrictions(client, auth):
    """Verify technician cannot access admin console."""
    auth.login_technician()

    res = client.get('/admin/dashboard', follow_redirects=True)
    assert b'permission' in res.data or b'Technician Workbench' in res.data


def test_delivery_role_restrictions(client, auth):
    """Verify delivery staff cannot access admin console."""
    auth.login_delivery()

    res = client.get('/admin/dashboard', follow_redirects=True)
    assert b'permission' in res.data or b'Delivery Console' in res.data


def test_admin_access_granted(client, auth):
    """Verify administrator has full access to the admin console."""
    auth.login_admin()

    res = client.get('/admin/dashboard', follow_redirects=True)
    assert res.status_code == 200
    assert b'Operations & Analytics Console' in res.data
