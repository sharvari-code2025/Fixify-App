"""
Fixify — Repair Service
Handles diagnosis, estimates, and repair workflow.
"""
from database.db import get_db
from services.notification_service import create_notification


def create_diagnosis(booking_id, technician_id, diagnosis_text, recommended_repair):
    """Create or update a diagnosis for a booking."""
    db = get_db()

    existing = db.execute(
        "SELECT id FROM diagnoses WHERE booking_id = ?", (booking_id,)
    ).fetchone()

    if existing:
        db.execute(
            """UPDATE diagnoses SET diagnosis_text = ?, recommended_repair = ?,
               updated_at = datetime('now') WHERE booking_id = ?""",
            (diagnosis_text, recommended_repair, booking_id)
        )
    else:
        db.execute(
            """INSERT INTO diagnoses (booking_id, technician_id, diagnosis_text, recommended_repair)
               VALUES (?, ?, ?, ?)""",
            (booking_id, technician_id, diagnosis_text, recommended_repair)
        )

    db.commit()

    # Notify customer
    booking = db.execute("SELECT customer_id, reference FROM bookings WHERE id = ?", (booking_id,)).fetchone()
    if booking:
        create_notification(
            booking['customer_id'],
            'Diagnosis Complete',
            f'The technician has completed the diagnosis for booking {booking["reference"]}.',
            f'/customer/bookings/{booking_id}'
        )

    return True


def create_estimate(booking_id, technician_id, parts_cost, labour_cost,
                    additional_charges, estimated_completion):
    """Create or update a repair estimate."""
    db = get_db()

    total_cost = float(parts_cost) + float(labour_cost) + float(additional_charges)

    existing = db.execute(
        "SELECT id FROM estimates WHERE booking_id = ?", (booking_id,)
    ).fetchone()

    if existing:
        db.execute(
            """UPDATE estimates SET parts_cost = ?, labour_cost = ?, additional_charges = ?,
               total_cost = ?, estimated_completion = ?, approval_status = 'Pending',
               approved_by = NULL, approval_date = NULL, approval_notes = NULL,
               updated_at = datetime('now')
               WHERE booking_id = ?""",
            (parts_cost, labour_cost, additional_charges, total_cost,
             estimated_completion, booking_id)
        )
    else:
        db.execute(
            """INSERT INTO estimates (booking_id, technician_id, parts_cost, labour_cost,
               additional_charges, total_cost, estimated_completion)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (booking_id, technician_id, parts_cost, labour_cost,
             additional_charges, total_cost, estimated_completion)
        )

    db.commit()

    # Notify customer
    booking = db.execute("SELECT customer_id, reference FROM bookings WHERE id = ?", (booking_id,)).fetchone()
    if booking:
        create_notification(
            booking['customer_id'],
            'Estimate Ready',
            f'A repair estimate of ₹{total_cost:.2f} is ready for booking {booking["reference"]}. Please review and approve or reject.',
            f'/customer/bookings/{booking_id}'
        )

    return True


def approve_estimate(booking_id, customer_id, approved, notes=None):
    """Customer approves or rejects an estimate."""
    db = get_db()

    estimate = db.execute(
        "SELECT * FROM estimates WHERE booking_id = ?", (booking_id,)
    ).fetchone()

    if not estimate:
        return False, "No estimate found"

    if estimate['approval_status'] != 'Pending':
        return False, "Estimate has already been reviewed"

    status = 'Approved' if approved else 'Rejected'

    db.execute(
        """UPDATE estimates SET approval_status = ?, approved_by = ?,
           approval_date = datetime('now'), approval_notes = ?,
           updated_at = datetime('now')
           WHERE booking_id = ?""",
        (status, customer_id, notes, booking_id)
    )

    db.commit()

    # Notify technician
    booking = db.execute(
        "SELECT technician_id, reference FROM bookings WHERE id = ?", (booking_id,)
    ).fetchone()
    if booking and booking['technician_id']:
        create_notification(
            booking['technician_id'],
            f'Estimate {status}',
            f'The customer has {status.lower()} the estimate for booking {booking["reference"]}.',
            f'/technician/repairs/{booking_id}'
        )

    # Notify admins
    admins = db.execute("SELECT id FROM users WHERE role = 'admin' AND is_active = 1").fetchall()
    for admin in admins:
        create_notification(
            admin['id'],
            f'Estimate {status}',
            f'Customer {status.lower()} estimate for booking {booking["reference"]}.',
            f'/admin/bookings/{booking_id}'
        )

    return True, f"Estimate {status.lower()}"


def get_diagnosis(booking_id):
    """Get diagnosis for a booking."""
    db = get_db()
    return db.execute(
        """SELECT d.*, u.full_name as technician_name
           FROM diagnoses d
           JOIN users u ON d.technician_id = u.id
           WHERE d.booking_id = ?""",
        (booking_id,)
    ).fetchone()


def get_estimate(booking_id):
    """Get estimate for a booking."""
    db = get_db()
    return db.execute(
        """SELECT e.*, u.full_name as technician_name
           FROM estimates e
           JOIN users u ON e.technician_id = u.id
           WHERE e.booking_id = ?""",
        (booking_id,)
    ).fetchone()
