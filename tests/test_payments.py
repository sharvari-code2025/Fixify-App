"""
Fixify — Payment Processing Test Suite
Tests simulated demo payments, transaction auditing, and payment receipt persistence.
"""
import pytest
from database.db import get_db
from services.booking_service import create_booking
from services.repair_service import create_estimate


def test_payment_recording_flow(client, auth, app):
    """Test simulating invoice payment and auditing in SQLite."""
    with app.app_context():
        b_id, ref = create_booking(
            customer_id=5,
            phone_brand='Xiaomi',
            phone_model='Redmi Note 12',
            category_id=2,
            problem_description='Battery replaced',
            device_condition='Normal',
            service_type='walk_in',
            pickup_address=None,
            preferred_date=None,
            additional_notes=None
        )
        create_estimate(b_id, 2, 1200, 300, 0, 'Completed')

    auth.login_customer()
    pay_res = client.post(f'/payments/checkout/{b_id}', data={
        'amount': '1500',
        'payment_method': 'demo_upi',
        'notes': 'Demo UPI transaction'
    }, follow_redirects=True)

    assert b'Simulated payment of' in pay_res.data

    with app.app_context():
        db = get_db()
        payment = db.execute("SELECT * FROM payments WHERE booking_id = ?", (b_id,)).fetchone()
        assert payment is not None
        assert payment['amount'] == 1500.0
        assert payment['payment_method'] == 'demo_upi'
        assert payment['payment_status'] == 'Completed'
        assert payment['reference_id'].startswith('PAY-')
