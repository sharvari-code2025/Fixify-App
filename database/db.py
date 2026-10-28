"""
Fixify — Database Access Layer
Provides connection management, initialization, and helper functions.
"""
import sqlite3
import os
from flask import g, current_app


def get_db():
    """Get a database connection for the current request."""
    if 'db' not in g:
        g.db = sqlite3.connect(
            current_app.config['DATABASE'],
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(e=None):
    """Close the database connection at the end of the request."""
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db(app=None):
    """Initialize the database using schema.sql."""
    if app:
        db_path = app.config['DATABASE']
        if db_path == ':memory:':
            return  # handled per-request in tests
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        schema_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'schema.sql')
        with open(schema_path, 'r') as f:
            conn.executescript(f.read())
        conn.close()
    else:
        db = get_db()
        schema_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'schema.sql')
        with open(schema_path, 'r') as f:
            db.executescript(f.read())


def seed_demo_data():
    """Seed demo accounts and sample data. Clearly marked as test data."""
    from werkzeug.security import generate_password_hash
    import secrets

    db = get_db()

    # Check if admin already exists
    existing = db.execute("SELECT id FROM users WHERE email = ?", ('admin@fixify.demo',)).fetchone()
    if existing:
        return  # Already seeded

    # Demo admin account
    db.execute(
        "INSERT INTO users (full_name, email, mobile, password_hash, role) VALUES (?, ?, ?, ?, ?)",
        ('Demo Admin', 'admin@fixify.demo', '9000000001',
         generate_password_hash('Admin@123'), 'admin')
    )

    # Demo technician accounts
    db.execute(
        "INSERT INTO users (full_name, email, mobile, password_hash, role) VALUES (?, ?, ?, ?, ?)",
        ('Demo Technician', 'tech@fixify.demo', '9000000002',
         generate_password_hash('Tech@123'), 'technician')
    )
    db.execute(
        "INSERT INTO users (full_name, email, mobile, password_hash, role) VALUES (?, ?, ?, ?, ?)",
        ('Demo Technician 2', 'tech2@fixify.demo', '9000000003',
         generate_password_hash('Tech@123'), 'technician')
    )

    # Demo delivery staff
    db.execute(
        "INSERT INTO users (full_name, email, mobile, password_hash, role) VALUES (?, ?, ?, ?, ?)",
        ('Demo Delivery', 'delivery@fixify.demo', '9000000004',
         generate_password_hash('Delivery@123'), 'delivery')
    )

    # Demo customer
    db.execute(
        "INSERT INTO users (full_name, email, mobile, password_hash, role) VALUES (?, ?, ?, ?, ?)",
        ('Demo Customer', 'customer@fixify.demo', '9000000005',
         generate_password_hash('Customer@123'), 'customer')
    )

    db.commit()


def seed_sample_records():
    """Seed sample bookings, inventory, diagnoses, estimates, and reviews for live demonstration."""
    db = get_db()
    existing_bookings = db.execute("SELECT COUNT(*) as c FROM bookings").fetchone()['c']
    if existing_bookings > 0:
        return

    # Seed Inventory
    existing_inv = db.execute("SELECT COUNT(*) as c FROM inventory").fetchone()['c']
    if existing_inv == 0:
        db.execute(
            """INSERT INTO inventory (part_name, sku, category, stock_quantity, min_stock_threshold, unit_cost, supplier)
               VALUES 
               ('iPhone 14 OLED Screen Assembly', 'SCR-IP14-OLED', 'Screens', 15, 5, 4500.00, 'Apex Tech Components'),
               ('Samsung Galaxy S23 Battery (3900mAh)', 'BAT-SGS23-39', 'Batteries', 12, 4, 1850.00, 'PowerCell India'),
               ('Google Pixel 7 USB-C Port Board', 'PRT-PX7-USBC', 'Charging Ports', 20, 5, 950.00, 'FlexParts Direct'),
               ('iPhone 13 Rear Camera Module', 'CAM-IP13-MOD', 'Cameras', 6, 2, 3200.00, 'SensorOptics Ltd'),
               ('OnePlus 11 Vibration Taptic Motor', 'MTR-OP11-VIB', 'Accessories', 2, 3, 650.00, 'OmniSpares')"""
        )

    # 1. Booking 1: Completed repair with review and payment
    cur = db.execute(
        """INSERT INTO bookings (reference, customer_id, phone_brand, phone_model, category_id,
                                 problem_description, device_condition, service_type, pickup_address,
                                 status, technician_id, delivery_staff_id, created_at, updated_at)
           VALUES ('FIX-DEMO-001', 5, 'Apple', 'iPhone 14 Pro', 9,
                   'Front glass shattered after accidental drop, upper half touch screen unresponsive.',
                   'Minor scuffs on stainless frame, rear ceramic glass undamaged.',
                   'pickup_delivery', 'Flat 402, Green Glen Layout, Bellandur, Bengaluru',
                   'Completed', 2, 4, datetime('now', '-3 days'), datetime('now', '-1 hours'))"""
    )
    b1_id = cur.lastrowid

    # Diagnosis & Estimate for B1
    db.execute(
        """INSERT INTO diagnoses (booking_id, technician_id, diagnosis_text, recommended_repair, created_at)
           VALUES (?, 2, 'OLED display glass fractured, digitizer dead zone detected. Motherboard, TrueDepth Face ID, and chassis undamaged.',
                   'Full front OLED panel replacement and water-resistant adhesive reseal.', datetime('now', '-2 days'))""",
        (b1_id,)
    )
    db.execute(
        """INSERT INTO estimates (booking_id, technician_id, parts_cost, labour_cost, additional_charges,
                                 total_cost, estimated_completion, approval_status, approved_by, approval_date, created_at)
           VALUES (?, 2, 4500.00, 1200.00, 0.00, 5700.00, 'Same Day (4 Hours)', 'Approved', 5, datetime('now', '-2 days'), datetime('now', '-2 days'))""",
        (b1_id,)
    )

    # Status history for B1
    statuses = [
        ('Booked', None, 'Booking submitted by customer.', '-72 hours'),
        ('Assigned', 'Booked', 'Assigned to Demo Technician.', '-68 hours'),
        ('Diagnosis', 'Assigned', 'Diagnosis completed with cost estimate.', '-66 hours'),
        ('Waiting for Approval', 'Diagnosis', 'Estimate submitted to customer for approval.', '-65 hours'),
        ('In Progress', 'Waiting for Approval', 'Customer approved estimate of ₹5,700.00. Repair commenced.', '-64 hours'),
        ('Ready for Pickup', 'In Progress', 'OLED display replacement and 24-point QC testing successful.', '-34 hours'),
        ('Out for Delivery', 'Ready for Pickup', 'Dispatched with Demo Delivery.', '-28 hours'),
        ('Delivered', 'Out for Delivery', 'Device handed over to customer.', '-25 hours'),
        ('Completed', 'Delivered', 'Customer payment and handover verified. Repair closed.', '-1 hours')
    ]
    for new_s, prev_s, note, time_offset in statuses:
        db.execute(
            """INSERT INTO status_history (booking_id, previous_status, new_status, changed_by, notes, created_at)
               VALUES (?, ?, ?, 1, ?, datetime('now', ?))""",
            (b1_id, prev_s, new_s, note, time_offset)
        )

    # Delivery tasks for B1
    db.execute(
        """INSERT INTO delivery_tasks (booking_id, delivery_staff_id, task_type, status, address, contact_name, contact_phone, completed_at, notes, created_at)
           VALUES (?, 4, 'pickup', 'Completed', 'Flat 402, Green Glen Layout, Bellandur, Bengaluru', 'Demo Customer', '9000000005', datetime('now', '-70 hours'), 'Device securely bagged.', datetime('now', '-72 hours'))""",
        (b1_id,)
    )
    db.execute(
        """INSERT INTO delivery_tasks (booking_id, delivery_staff_id, task_type, status, address, contact_name, contact_phone, completed_at, notes, created_at)
           VALUES (?, 4, 'delivery', 'Completed', 'Flat 402, Green Glen Layout, Bellandur, Bengaluru', 'Demo Customer', '9000000005', datetime('now', '-1 hours'), 'Delivered safely with warranty card.', datetime('now', '-28 hours'))""",
        (b1_id,)
    )

    # Payment for B1
    db.execute(
        """INSERT INTO payments (booking_id, amount, payment_method, payment_status, reference_id, recorded_by, notes, created_at)
           VALUES (?, 5700.00, 'demo_upi', 'Completed', 'PAY-DEMO01', 5, 'Full payment cleared via demo UPI simulation.', datetime('now', '-1 hours'))""",
        (b1_id,)
    )

    # Review for B1
    db.execute(
        """INSERT INTO reviews (booking_id, customer_id, rating, review_text, created_at)
           VALUES (?, 5, 5, 'Remarkable service! The pickup and delivery were on time, screen replacement is flawless, and the real-time status tracker kept me completely informed.', datetime('now', '-30 minutes'))""",
        (b1_id,)
    )

    # 2. Booking 2: In Progress
    cur = db.execute(
        """INSERT INTO bookings (reference, customer_id, phone_brand, phone_model, category_id,
                                 problem_description, device_condition, service_type,
                                 status, technician_id, created_at, updated_at)
           VALUES ('FIX-DEMO-002', 5, 'Samsung', 'Galaxy S23', 2,
                   'Battery drains completely in under 3 hours, device runs warm during regular phone calls.',
                   'Clean front glass, slight swelling at rear adhesive seam.',
                   'walk_in', 'In Progress', 2, datetime('now', '-1 days'), datetime('now', '-4 hours'))"""
    )
    b2_id = cur.lastrowid
    db.execute(
        """INSERT INTO diagnoses (booking_id, technician_id, diagnosis_text, recommended_repair, created_at)
           VALUES (?, 2, 'Internal Li-ion battery health degraded to 64% with thermal expansion. Requires fresh 3900mAh battery cell replacement and adhesive recalibration.',
                   'Genuine battery replacement and thermal pad refreshment.', datetime('now', '-20 hours'))""",
        (b2_id,)
    )
    db.execute(
        """INSERT INTO estimates (booking_id, technician_id, parts_cost, labour_cost, additional_charges,
                                 total_cost, estimated_completion, approval_status, approved_by, approval_date, created_at)
           VALUES (?, 2, 1850.00, 650.00, 0.00, 2500.00, 'Tomorrow 2:00 PM', 'Approved', 5, datetime('now', '-16 hours'), datetime('now', '-18 hours'))""",
        (b2_id,)
    )
    for new_s, prev_s, note, time_offset in [
        ('Booked', None, 'Walk-in booking created.', '-1 days'),
        ('Assigned', 'Booked', 'Assigned to Demo Technician.', '-22 hours'),
        ('Diagnosis', 'Assigned', 'Battery degradation confirmed.', '-20 hours'),
        ('Waiting for Approval', 'Diagnosis', 'Estimate submitted.', '-18 hours'),
        ('In Progress', 'Waiting for Approval', 'Customer approved estimate of ₹2,500.00.', '-16 hours')
    ]:
        db.execute(
            """INSERT INTO status_history (booking_id, previous_status, new_status, changed_by, notes, created_at)
               VALUES (?, ?, ?, 1, ?, datetime('now', ?))""",
            (b2_id, prev_s, new_s, note, time_offset)
        )

    # 3. Booking 3: Waiting for Approval
    cur = db.execute(
        """INSERT INTO bookings (reference, customer_id, phone_brand, phone_model, category_id,
                                 problem_description, device_condition, service_type,
                                 status, technician_id, created_at, updated_at)
           VALUES ('FIX-DEMO-003', 5, 'Google', 'Pixel 7', 5,
                   'Loose USB-C connector. Cable disconnects unless held at an awkward angle.',
                   'Pristine screen, minor pocket lint around port.',
                   'walk_in', 'Waiting for Approval', 3, datetime('now', '-8 hours'), datetime('now', '-2 hours'))"""
    )
    b3_id = cur.lastrowid
    db.execute(
        """INSERT INTO diagnoses (booking_id, technician_id, diagnosis_text, recommended_repair, created_at)
           VALUES (?, 3, 'Heavy oxidation and fractured solder pin on sub-board USB-C receptacle. Sub-board replacement required.',
                   'Replace USB-C charging daughterboard and clean microphone acoustic mesh.', datetime('now', '-4 hours'))""",
        (b3_id,)
    )
    db.execute(
        """INSERT INTO estimates (booking_id, technician_id, parts_cost, labour_cost, additional_charges,
                                 total_cost, estimated_completion, approval_status, created_at)
           VALUES (?, 3, 950.00, 550.00, 0.00, 1500.00, 'Tomorrow 5:00 PM', 'Pending', datetime('now', '-2 hours'))""",
        (b3_id,)
    )
    for new_s, prev_s, note, time_offset in [
        ('Booked', None, 'Walk-in booking created.', '-8 hours'),
        ('Assigned', 'Booked', 'Assigned to Demo Technician 2.', '-6 hours'),
        ('Diagnosis', 'Assigned', 'Charging daughterboard failure diagnosed.', '-4 hours'),
        ('Waiting for Approval', 'Diagnosis', 'Estimate of ₹1,500.00 submitted to customer.', '-2 hours')
    ]:
        db.execute(
            """INSERT INTO status_history (booking_id, previous_status, new_status, changed_by, notes, created_at)
               VALUES (?, ?, ?, 1, ?, datetime('now', ?))""",
            (b3_id, prev_s, new_s, note, time_offset)
        )

    # 4. Booking 4: Booked (Awaiting assignment)
    cur = db.execute(
        """INSERT INTO bookings (reference, customer_id, phone_brand, phone_model, category_id,
                                 problem_description, device_condition, service_type,
                                 status, created_at, updated_at)
           VALUES ('FIX-DEMO-004', 5, 'OnePlus', 'OnePlus 11', 12,
                   'Accidental splash of tap water. Phone was switched off immediately and will not turn back on.',
                   'No external cracks.', 'walk_in', 'Booked', datetime('now', '-1 hours'), datetime('now', '-1 hours'))"""
    )
    b4_id = cur.lastrowid
    db.execute(
        """INSERT INTO status_history (booking_id, previous_status, new_status, changed_by, notes, created_at)
           VALUES (?, NULL, 'Booked', 5, 'Initial booking created by customer.', datetime('now', '-1 hours'))""",
        (b4_id,)
    )

    # Sample notifications
    db.execute(
        """INSERT INTO notifications (user_id, title, message, link, is_read, created_at)
           VALUES 
           (5, 'Repair Estimate Ready', 'Estimate for your Pixel 7 (FIX-DEMO-003) is ready for review.', '/customer/bookings/' || ?, 0, datetime('now', '-2 hours')),
           (5, 'Repair In Progress', 'Demo Technician has begun repairs on your Galaxy S23 (FIX-DEMO-002).', '/customer/bookings/' || ?, 1, datetime('now', '-16 hours')),
           (1, 'New Booking Received', 'New booking FIX-DEMO-004 (OnePlus 11) submitted and requires staff assignment.', '/admin/bookings', 0, datetime('now', '-1 hours')),
           (2, 'Repair Assigned', 'You have been assigned to repair Galaxy S23 (FIX-DEMO-002).', '/technician/repairs/' || ?, 1, datetime('now', '-22 hours'))""",
        (b3_id, b2_id, b2_id)
    )

    db.commit()



def query_db(query, args=(), one=False):
    """Execute a query and return results."""
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv


def insert_db(query, args=()):
    """Execute an insert and return the last row id."""
    db = get_db()
    cur = db.execute(query, args)
    db.commit()
    return cur.lastrowid


def update_db(query, args=()):
    """Execute an update/delete and return rows affected."""
    db = get_db()
    cur = db.execute(query, args)
    db.commit()
    return cur.rowcount
