"""
Fixify — Repair Lifecycle & Estimation Test Suite
Tests technician assignment, diagnosis recording, estimate calculation, and customer approval workflow.
"""
import pytest
from database.db import get_db
from services.booking_service import create_booking, update_booking_status, validate_status_transition


def test_status_transition_validator():
    """Verify backend status transition matrix."""
    assert validate_status_transition('Booked', 'Assigned') is True
    assert validate_status_transition('Booked', 'Cancelled') is True
    assert validate_status_transition('Booked', 'Completed') is False  # Cannot skip straight to completed
    assert validate_status_transition('Diagnosis', 'Waiting for Approval') is True
    assert validate_status_transition('Waiting for Approval', 'In Progress') is True
    assert validate_status_transition('In Progress', 'Ready for Pickup') is True
    assert validate_status_transition('Completed', 'Booked') is False  # Completed is terminal


def test_complete_repair_and_estimate_lifecycle(client, auth, app):
    """Test full cycle: Booking -> Assign Tech -> Diagnosis -> Estimate -> Customer Approval -> Ready for Pickup."""
    with app.app_context():
        # 1. Customer creates booking
        b_id, ref = create_booking(
            customer_id=5, # Demo Customer ID
            phone_brand='OnePlus',
            phone_model='11R',
            category_id=1,
            problem_description='Cracked AMOLED display with green lines',
            device_condition='Good except screen',
            service_type='walk_in',
            pickup_address=None,
            preferred_date=None,
            additional_notes=None
        )

    # 2. Admin assigns technician
    auth.login_admin()
    assign_res = client.post(f'/admin/bookings/{b_id}/assign-technician', data={
        'technician_id': '2' # Demo Tech ID
    }, follow_redirects=True)
    assert b'Successfully assigned' in assign_res.data
    auth.logout()

    # Verify status changed to Assigned
    with app.app_context():
        db = get_db()
        booking = db.execute("SELECT status, technician_id FROM bookings WHERE id = ?", (b_id,)).fetchone()
        assert booking['status'] == 'Assigned'
        assert booking['technician_id'] == 2

    # 3. Technician files diagnosis
    auth.login_technician()
    diag_res = client.post(f'/technician/repairs/{b_id}/diagnose', data={
        'diagnosis_text': 'AMOLED display damaged. Frame intact. Touch digitizer unresponsive.',
        'recommended_repair': 'Replace with OEM OnePlus AMOLED display'
    }, follow_redirects=True)
    assert b'Diagnosis recorded' in diag_res.data

    # 4. Technician submits estimate
    est_res = client.post(f'/technician/repairs/{b_id}/estimate', data={
        'parts_cost': '4500',
        'labour_cost': '600',
        'additional_charges': '0',
        'estimated_completion': 'Today by 6 PM'
    }, follow_redirects=True)
    assert b'estimate submitted' in est_res.data.lower()
    auth.logout()

    # Verify status changed to 'Waiting for Approval' and estimate total is 5100
    with app.app_context():
        db = get_db()
        booking = db.execute("SELECT status FROM bookings WHERE id = ?", (b_id,)).fetchone()
        assert booking['status'] == 'Waiting for Approval'
        est = db.execute("SELECT total_cost, approval_status FROM estimates WHERE booking_id = ?", (b_id,)).fetchone()
        assert est['total_cost'] == 5100.0
        assert est['approval_status'] == 'Pending'

    # 5. Customer reviews and approves estimate
    auth.login_customer()
    approve_res = client.post(f'/customer/bookings/{b_id}/estimate', data={
        'action': 'approve',
        'notes': 'Estimate accepted. Please proceed with genuine parts.'
    }, follow_redirects=True)
    assert b'Repair estimate approved' in approve_res.data
    auth.logout()

    # Verify status transitioned to 'In Progress'
    with app.app_context():
        db = get_db()
        booking = db.execute("SELECT status FROM bookings WHERE id = ?", (b_id,)).fetchone()
        assert booking['status'] == 'In Progress'

    # 6. Technician finishes repair and marks 'Ready for Pickup'
    auth.login_technician()
    ready_res = client.post(f'/technician/repairs/{b_id}/status', data={
        'status': 'Ready for Pickup',
        'notes': 'Screen replacement verified and quality tests passed.'
    }, follow_redirects=True)
    assert b'Ready for Pickup' in ready_res.data
    auth.logout()

    with app.app_context():
        db = get_db()
        booking = db.execute("SELECT status FROM bookings WHERE id = ?", (b_id,)).fetchone()
        assert booking['status'] == 'Ready for Pickup'
