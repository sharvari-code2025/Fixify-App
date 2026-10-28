"""
Fixify — Booking Workflow Test Suite
Tests booking creation, reference code uniqueness, initial status, and public tracking.
"""
import pytest
from database.db import get_db


def test_customer_booking_creation(client, auth, app):
    """Test customer creating a new repair booking."""
    auth.login_customer()

    response = client.post('/bookings/new', data={
        'phone_brand': 'Apple',
        'phone_model': 'iPhone 13',
        'category_id': '1',
        'problem_description': 'Screen shattered after drop, touchscreen unresponsive',
        'device_condition': 'Dented upper frame, back glass fine',
        'service_type': 'pickup_delivery',
        'pickup_address': 'Flat 402, Skyline Towers, Sector 62',
        'preferred_date': '2026-10-25',
        'additional_notes': 'Please call before arrival'
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b'Repair Booking Confirmed' in response.data or b'FIX-' in response.data

    with app.app_context():
        db = get_db()
        booking = db.execute("SELECT * FROM bookings WHERE phone_model = 'iPhone 13'").fetchone()
        assert booking is not None
        assert booking['reference'].startswith('FIX-')
        assert booking['status'] == 'Booked'

        # Check status history
        history = db.execute("SELECT * FROM status_history WHERE booking_id = ?", (booking['id'],)).fetchall()
        assert len(history) >= 1
        assert history[0]['new_status'] == 'Booked'


def test_public_tracking_portal(client, auth, app):
    """Test lookup by booking reference code."""
    # Create booking
    auth.login_customer()
    client.post('/bookings/new', data={
        'phone_brand': 'Samsung',
        'phone_model': 'Galaxy S22',
        'category_id': '2',
        'problem_description': 'Battery draining from 100% to 0% in 30 minutes',
        'service_type': 'walk_in'
    }, follow_redirects=True)

    with app.app_context():
        db = get_db()
        booking = db.execute("SELECT reference FROM bookings WHERE phone_model = 'Galaxy S22'").fetchone()
        ref = booking['reference']

    # Public tracking (unauthenticated)
    auth.logout()
    track_res = client.get(f'/bookings/track?ref={ref}')
    assert track_res.status_code == 200
    assert bytes(ref, 'utf-8') in track_res.data
    assert b'Galaxy S22' in track_res.data
