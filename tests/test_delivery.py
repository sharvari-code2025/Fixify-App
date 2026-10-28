"""
Fixify — Delivery Logistics Test Suite
Tests delivery task creation, status updates, and lifecycle synchronization with repair bookings.
"""
import pytest
from database.db import get_db
from services.booking_service import create_booking, update_booking_status


def test_delivery_dispatch_and_completion(client, auth, app):
    """Test dispatching delivery staff, moving to In Transit, and marking Completed."""
    with app.app_context():
        # Setup booking in 'Ready for Pickup' status
        b_id, ref = create_booking(
            customer_id=5,
            phone_brand='Google',
            phone_model='Pixel 7',
            category_id=1,
            problem_description='Cracked screen replaced',
            device_condition='Good',
            service_type='pickup_delivery',
            pickup_address='Plot 12, Indiranagar, Bengaluru',
            preferred_date=None,
            additional_notes=None
        )
        update_booking_status(b_id, 'Assigned', 1)
        update_booking_status(b_id, 'Diagnosis', 2)
        update_booking_status(b_id, 'Waiting for Approval', 2)
        update_booking_status(b_id, 'In Progress', 5)
        update_booking_status(b_id, 'Ready for Pickup', 2)

    # Admin assigns delivery staff (User ID 4)
    auth.login_admin()
    assign_res = client.post(f'/admin/bookings/{b_id}/assign-delivery', data={
        'delivery_staff_id': '4',
        'task_type': 'delivery',
        'notes': 'Deliver before 5 PM'
    }, follow_redirects=True)
    assert b'Assigned delivery task' in assign_res.data
    auth.logout()

    # Get created delivery task ID
    with app.app_context():
        db = get_db()
        task = db.execute("SELECT id FROM delivery_tasks WHERE booking_id = ?", (b_id,)).fetchone()
        assert task is not None
        task_id = task['id']

    # Delivery staff sets status to 'In Transit'
    auth.login_delivery()
    transit_res = client.post(f'/delivery/tasks/{task_id}/update', data={
        'status': 'In Transit',
        'notes': 'Out on delivery bike'
    }, follow_redirects=True)
    assert b'Out for Delivery' in transit_res.data

    with app.app_context():
        db = get_db()
        booking = db.execute("SELECT status FROM bookings WHERE id = ?", (b_id,)).fetchone()
        assert booking['status'] == 'Out for Delivery'

    # Delivery staff completes delivery
    done_res = client.post(f'/delivery/tasks/{task_id}/update', data={
        'status': 'Completed',
        'notes': 'Delivered to customer at door'
    }, follow_redirects=True)
    assert b'Delivery completed' in done_res.data

    with app.app_context():
        db = get_db()
        booking = db.execute("SELECT status FROM bookings WHERE id = ?", (b_id,)).fetchone()
        assert booking['status'] in ('Delivered', 'Completed')
