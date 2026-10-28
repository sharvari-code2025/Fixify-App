-- Fixify Database Schema
-- SQLite with foreign key enforcement

PRAGMA foreign_keys = ON;

-- ============================================================
-- USERS
-- ============================================================
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    mobile TEXT,
    password_hash TEXT,
    google_id TEXT UNIQUE,
    avatar_url TEXT,
    totp_secret TEXT,
    is_totp_enabled INTEGER NOT NULL DEFAULT 0,
    role TEXT NOT NULL DEFAULT 'customer' CHECK(role IN ('customer','admin','technician','delivery')),
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ============================================================
-- OTP TOKENS (for mobile OTP login — demo mode)
-- ============================================================
CREATE TABLE IF NOT EXISTS otp_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mobile TEXT NOT NULL,
    otp_code TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    is_used INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at TEXT NOT NULL
);

-- ============================================================
-- PASSWORD RESET TOKENS
-- ============================================================
CREATE TABLE IF NOT EXISTS password_reset_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    token TEXT NOT NULL UNIQUE,
    is_used INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- ============================================================
-- LOGIN ATTEMPTS (rate limiting)
-- ============================================================
CREATE TABLE IF NOT EXISTS login_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    identifier TEXT NOT NULL,  -- email or mobile
    attempt_time TEXT NOT NULL DEFAULT (datetime('now')),
    success INTEGER NOT NULL DEFAULT 0
);

-- ============================================================
-- REPAIR CATEGORIES
-- ============================================================
CREATE TABLE IF NOT EXISTS repair_categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ============================================================
-- BOOKINGS
-- ============================================================
CREATE TABLE IF NOT EXISTS bookings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reference TEXT NOT NULL UNIQUE,
    customer_id INTEGER NOT NULL,
    phone_brand TEXT NOT NULL,
    phone_model TEXT NOT NULL,
    category_id INTEGER,
    problem_description TEXT NOT NULL,
    device_condition TEXT,
    service_type TEXT NOT NULL DEFAULT 'walk_in' CHECK(service_type IN ('walk_in','pickup_delivery')),
    pickup_address TEXT,
    preferred_date TEXT,
    additional_notes TEXT,
    status TEXT NOT NULL DEFAULT 'Booked' CHECK(status IN (
        'Booked','Assigned','Diagnosis','Waiting for Approval',
        'Estimate Rejected','In Progress','Ready for Pickup',
        'Out for Delivery','Delivered','Completed','Cancelled','Unable to Repair'
    )),
    technician_id INTEGER,
    delivery_staff_id INTEGER,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (customer_id) REFERENCES users(id),
    FOREIGN KEY (category_id) REFERENCES repair_categories(id),
    FOREIGN KEY (technician_id) REFERENCES users(id),
    FOREIGN KEY (delivery_staff_id) REFERENCES users(id)
);

-- ============================================================
-- BOOKING IMAGES
-- ============================================================
CREATE TABLE IF NOT EXISTS booking_images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    booking_id INTEGER NOT NULL,
    filename TEXT NOT NULL,
    original_name TEXT NOT NULL,
    uploaded_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (booking_id) REFERENCES bookings(id)
);

-- ============================================================
-- STATUS HISTORY
-- ============================================================
CREATE TABLE IF NOT EXISTS status_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    booking_id INTEGER NOT NULL,
    previous_status TEXT,
    new_status TEXT NOT NULL,
    changed_by INTEGER NOT NULL,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (booking_id) REFERENCES bookings(id),
    FOREIGN KEY (changed_by) REFERENCES users(id)
);

-- ============================================================
-- DIAGNOSES
-- ============================================================
CREATE TABLE IF NOT EXISTS diagnoses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    booking_id INTEGER NOT NULL,
    technician_id INTEGER NOT NULL,
    diagnosis_text TEXT NOT NULL,
    recommended_repair TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (booking_id) REFERENCES bookings(id),
    FOREIGN KEY (technician_id) REFERENCES users(id)
);

-- ============================================================
-- ESTIMATES
-- ============================================================
CREATE TABLE IF NOT EXISTS estimates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    booking_id INTEGER NOT NULL,
    technician_id INTEGER NOT NULL,
    parts_cost REAL NOT NULL DEFAULT 0,
    labour_cost REAL NOT NULL DEFAULT 0,
    additional_charges REAL NOT NULL DEFAULT 0,
    total_cost REAL NOT NULL DEFAULT 0,
    estimated_completion TEXT,
    approval_status TEXT NOT NULL DEFAULT 'Pending' CHECK(approval_status IN ('Pending','Approved','Rejected')),
    approved_by INTEGER,
    approval_date TEXT,
    approval_notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (booking_id) REFERENCES bookings(id),
    FOREIGN KEY (technician_id) REFERENCES users(id),
    FOREIGN KEY (approved_by) REFERENCES users(id)
);

-- ============================================================
-- DELIVERY TASKS
-- ============================================================
CREATE TABLE IF NOT EXISTS delivery_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    booking_id INTEGER NOT NULL,
    delivery_staff_id INTEGER NOT NULL,
    task_type TEXT NOT NULL CHECK(task_type IN ('pickup','delivery')),
    status TEXT NOT NULL DEFAULT 'Assigned' CHECK(status IN ('Assigned','In Transit','Completed','Failed')),
    address TEXT NOT NULL,
    contact_name TEXT,
    contact_phone TEXT,
    scheduled_date TEXT,
    completed_at TEXT,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (booking_id) REFERENCES bookings(id),
    FOREIGN KEY (delivery_staff_id) REFERENCES users(id)
);

-- ============================================================
-- PAYMENTS
-- ============================================================
CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    booking_id INTEGER NOT NULL,
    amount REAL NOT NULL,
    payment_method TEXT NOT NULL CHECK(payment_method IN ('demo_upi','demo_card','cash','online')),
    payment_status TEXT NOT NULL DEFAULT 'Pending' CHECK(payment_status IN ('Pending','Completed','Failed','Refunded')),
    reference_id TEXT,
    recorded_by INTEGER NOT NULL,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (booking_id) REFERENCES bookings(id),
    FOREIGN KEY (recorded_by) REFERENCES users(id)
);

-- ============================================================
-- REVIEWS
-- ============================================================
CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    booking_id INTEGER NOT NULL UNIQUE,
    customer_id INTEGER NOT NULL,
    rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
    review_text TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (booking_id) REFERENCES bookings(id),
    FOREIGN KEY (customer_id) REFERENCES users(id)
);

-- ============================================================
-- NOTIFICATIONS
-- ============================================================
CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    link TEXT,
    is_read INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- ============================================================
-- INVENTORY
-- ============================================================
CREATE TABLE IF NOT EXISTS inventory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    part_name TEXT NOT NULL,
    sku TEXT UNIQUE,
    category TEXT,
    stock_quantity INTEGER NOT NULL DEFAULT 0,
    min_stock_threshold INTEGER NOT NULL DEFAULT 5,
    unit_cost REAL NOT NULL DEFAULT 0,
    supplier TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ============================================================
-- INVENTORY MOVEMENTS
-- ============================================================
CREATE TABLE IF NOT EXISTS inventory_movements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    inventory_id INTEGER NOT NULL,
    movement_type TEXT NOT NULL CHECK(movement_type IN ('in','out','adjustment')),
    quantity INTEGER NOT NULL,
    reason TEXT,
    performed_by INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (inventory_id) REFERENCES inventory(id),
    FOREIGN KEY (performed_by) REFERENCES users(id)
);

-- ============================================================
-- AUDIT LOG
-- ============================================================
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    action TEXT NOT NULL,
    entity_type TEXT,
    entity_id INTEGER,
    details TEXT,
    ip_address TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- ============================================================
-- INDEXES
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_mobile ON users(mobile);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
CREATE INDEX IF NOT EXISTS idx_bookings_reference ON bookings(reference);
CREATE INDEX IF NOT EXISTS idx_bookings_customer ON bookings(customer_id);
CREATE INDEX IF NOT EXISTS idx_bookings_status ON bookings(status);
CREATE INDEX IF NOT EXISTS idx_bookings_technician ON bookings(technician_id);
CREATE INDEX IF NOT EXISTS idx_bookings_delivery ON bookings(delivery_staff_id);
CREATE INDEX IF NOT EXISTS idx_status_history_booking ON status_history(booking_id);
CREATE INDEX IF NOT EXISTS idx_diagnoses_booking ON diagnoses(booking_id);
CREATE INDEX IF NOT EXISTS idx_estimates_booking ON estimates(booking_id);
CREATE INDEX IF NOT EXISTS idx_delivery_tasks_booking ON delivery_tasks(booking_id);
CREATE INDEX IF NOT EXISTS idx_delivery_tasks_staff ON delivery_tasks(delivery_staff_id);
CREATE INDEX IF NOT EXISTS idx_payments_booking ON payments(booking_id);
CREATE INDEX IF NOT EXISTS idx_reviews_booking ON reviews(booking_id);
CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_user ON audit_log(user_id);
CREATE INDEX IF NOT EXISTS idx_login_attempts_identifier ON login_attempts(identifier);

-- ============================================================
-- DEFAULT REPAIR CATEGORIES
-- ============================================================
INSERT OR IGNORE INTO repair_categories (name, description) VALUES
    ('Screen Replacement', 'Cracked, shattered, or unresponsive display replacement'),
    ('Battery Replacement', 'Swollen, draining, or non-charging battery replacement'),
    ('Charging Port Repair', 'Loose, broken, or non-functional charging port fix'),
    ('Camera Repair', 'Front or rear camera malfunction repair'),
    ('Speaker/Mic Repair', 'Speaker distortion, low volume, or microphone issues'),
    ('Software Issues', 'OS crashes, boot loops, software corruption'),
    ('Water Damage', 'Liquid ingress diagnosis and component-level repair'),
    ('Button Repair', 'Power, volume, or home button replacement'),
    ('Back Panel Replacement', 'Cracked or damaged back glass/panel replacement'),
    ('Motherboard Repair', 'Component-level motherboard diagnosis and repair'),
    ('Data Recovery', 'Recovery of data from damaged or non-booting devices'),
    ('General Diagnosis', 'Full device health check and diagnostic report');

-- ============================================================
-- DEFAULT ADMIN ACCOUNT (demo only — password: Admin@123)
-- ============================================================
-- Password hash for "Admin@123" will be inserted by the seed script
