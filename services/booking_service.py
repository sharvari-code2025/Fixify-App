"""
Fixify — Booking Service
Handles booking creation, reference generation, and status management.
"""
import secrets
import string
from datetime import datetime
from database.db import get_db
from services.notification_service import create_notification


def generate_booking_reference():
    """Generate a unique booking reference like FIX-XXXXXXXX."""
    chars = string.ascii_uppercase + string.digits
    while True:
        ref = 'FIX-' + ''.join(secrets.choice(chars) for _ in range(8))
        db = get_db()
        existing = db.execute("SELECT id FROM bookings WHERE reference = ?", (ref,)).fetchone()
        if not existing:
            return ref


def create_booking(customer_id, phone_brand, phone_model, category_id,
                   problem_description, device_condition, service_type,
                   pickup_address, preferred_date, additional_notes):
    """Create a new repair booking."""
    db = get_db()
    reference = generate_booking_reference()

    booking_id = db.execute(
        """INSERT INTO bookings 
           (reference, customer_id, phone_brand, phone_model, category_id,
            problem_description, device_condition, service_type, pickup_address,
            preferred_date, additional_notes, status)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Booked')""",
        (reference, customer_id, phone_brand, phone_model, category_id,
         problem_description, device_condition, service_type, pickup_address,
         preferred_date, additional_notes)
    ).lastrowid

    # Create initial status history
    db.execute(
        "INSERT INTO status_history (booking_id, previous_status, new_status, changed_by, notes) VALUES (?, ?, ?, ?, ?)",
        (booking_id, None, 'Booked', customer_id, 'Booking created')
    )

    db.commit()

    # Notify admins
    admins = db.execute("SELECT id FROM users WHERE role = 'admin' AND is_active = 1").fetchall()
    for admin in admins:
        create_notification(
            admin['id'],
            'New Booking',
            f'New repair booking {reference} has been created.',
            f'/admin/bookings/{booking_id}'
        )

    # Notify customer
    create_notification(
        customer_id,
        'Booking Confirmed',
        f'Your repair booking {reference} has been confirmed. We will assign a technician shortly.',
        f'/customer/bookings/{booking_id}'
    )

    return booking_id, reference


def update_booking_status(booking_id, new_status, changed_by, notes=None):
    """Update booking status with history tracking."""
    db = get_db()

    booking = db.execute("SELECT * FROM bookings WHERE id = ?", (booking_id,)).fetchone()
    if not booking:
        return False, "Booking not found"

    old_status = booking['status']

    # Validate transition
    valid = validate_status_transition(old_status, new_status)
    if not valid:
        return False, f"Invalid status transition from '{old_status}' to '{new_status}'"

    db.execute(
        "UPDATE bookings SET status = ?, updated_at = datetime('now') WHERE id = ?",
        (new_status, booking_id)
    )

    db.execute(
        "INSERT INTO status_history (booking_id, previous_status, new_status, changed_by, notes) VALUES (?, ?, ?, ?, ?)",
        (booking_id, old_status, new_status, changed_by, notes)
    )

    db.commit()

    # Notify customer
    create_notification(
        booking['customer_id'],
        'Repair Status Updated',
        f'Your booking {booking["reference"]} status changed to: {new_status}',
        f'/customer/bookings/{booking_id}'
    )

    return True, "Status updated"


def validate_status_transition(current, new):
    """Validate that a status transition is allowed."""
    allowed_transitions = {
        'Booked': ['Assigned', 'Cancelled'],
        'Assigned': ['Diagnosis', 'Cancelled'],
        'Diagnosis': ['Waiting for Approval', 'Unable to Repair', 'Cancelled'],
        'Waiting for Approval': ['In Progress', 'Estimate Rejected', 'Cancelled'],
        'Estimate Rejected': ['Diagnosis', 'Cancelled'],
        'In Progress': ['Ready for Pickup', 'Unable to Repair', 'Cancelled'],
        'Ready for Pickup': ['Out for Delivery', 'Delivered', 'Completed'],
        'Out for Delivery': ['Delivered', 'Ready for Pickup'],  # can fail and come back
        'Delivered': ['Completed'],
        'Completed': [],
        'Cancelled': [],
        'Unable to Repair': ['Cancelled', 'Ready for Pickup'],
    }
    return new in allowed_transitions.get(current, [])


def get_booking_with_details(booking_id):
    """Get a booking with all related details."""
    db = get_db()
    booking = db.execute(
        """SELECT b.*, u.full_name as customer_name, u.mobile as customer_mobile,
                  u.email as customer_email,
                  rc.name as category_name,
                  t.full_name as technician_name,
                  d.full_name as delivery_staff_name
           FROM bookings b
           JOIN users u ON b.customer_id = u.id
           LEFT JOIN repair_categories rc ON b.category_id = rc.id
           LEFT JOIN users t ON b.technician_id = t.id
           LEFT JOIN users d ON b.delivery_staff_id = d.id
           WHERE b.id = ?""",
        (booking_id,)
    ).fetchone()
    return booking


def get_status_history(booking_id):
    """Get status history for a booking."""
    db = get_db()
    return db.execute(
        """SELECT sh.*, u.full_name as changed_by_name
           FROM status_history sh
           JOIN users u ON sh.changed_by = u.id
           WHERE sh.booking_id = ?
           ORDER BY sh.created_at ASC""",
        (booking_id,)
    ).fetchall()
