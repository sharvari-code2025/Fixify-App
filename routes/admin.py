"""
Fixify — Administrator Routes
Full administrative portal for bookings, staff, assignments, categories, payments, feedback, inventory, and CSV exports.
"""
import io
import csv
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, Response, jsonify
from database.db import get_db, insert_db, update_db
from services.auth_service import login_required, hash_password
from services.booking_service import get_booking_with_details, get_status_history, update_booking_status
from services.notification_service import create_notification

bp = Blueprint('admin', __name__, url_prefix='/admin')


def sanitize_csv_field(val):
    """Sanitize CSV cell against formula injection (leading =, +, -, @)."""
    if val is None:
        return ""
    s = str(val).strip()
    if s and s[0] in ('=', '+', '-', '@', '\t', '\r'):
        return "'" + s
    return s


@bp.route('/dashboard')
@login_required(roles=['admin'])
def dashboard():
    """Admin dashboard aggregating real database statistics."""
    db = get_db()

    # User counts
    total_customers = db.execute("SELECT COUNT(*) as c FROM users WHERE role = 'customer'").fetchone()['c']
    total_technicians = db.execute("SELECT COUNT(*) as c FROM users WHERE role = 'technician' AND is_active = 1").fetchone()['c']
    total_delivery = db.execute("SELECT COUNT(*) as c FROM users WHERE role = 'delivery' AND is_active = 1").fetchone()['c']

    # Booking metrics
    total_bookings = db.execute("SELECT COUNT(*) as c FROM bookings").fetchone()['c']
    pending_repairs = db.execute("SELECT COUNT(*) as c FROM bookings WHERE status IN ('Booked', 'Assigned', 'Diagnosis', 'Waiting for Approval')").fetchone()['c']
    in_progress = db.execute("SELECT COUNT(*) as c FROM bookings WHERE status = 'In Progress'").fetchone()['c']
    ready_for_pickup = db.execute("SELECT COUNT(*) as c FROM bookings WHERE status = 'Ready for Pickup'").fetchone()['c']
    out_for_delivery = db.execute("SELECT COUNT(*) as c FROM bookings WHERE status = 'Out for Delivery'").fetchone()['c']
    completed_repairs = db.execute("SELECT COUNT(*) as c FROM bookings WHERE status = 'Completed'").fetchone()['c']
    cancelled_repairs = db.execute("SELECT COUNT(*) as c FROM bookings WHERE status IN ('Cancelled', 'Unable to Repair')").fetchone()['c']

    # Financials
    payment_row = db.execute("SELECT COALESCE(SUM(amount), 0) as total FROM payments WHERE payment_status = 'Completed'").fetchone()
    total_revenue = payment_row['total'] if payment_row else 0.0

    # Rating
    rating_row = db.execute("SELECT COALESCE(AVG(rating), 0) as avg_rating, COUNT(*) as count FROM reviews").fetchone()
    avg_rating = round(rating_row['avg_rating'], 1)
    review_count = rating_row['count']

    # Status distribution for Chart.js
    status_counts = db.execute(
        "SELECT status, COUNT(*) as count FROM bookings GROUP BY status"
    ).fetchall()
    status_data = {row['status']: row['count'] for row in status_counts}

    # Technician workload
    tech_workload = db.execute(
        """SELECT u.id, u.full_name, COUNT(b.id) as active_count
           FROM users u
           LEFT JOIN bookings b ON u.id = b.technician_id AND b.status IN ('Assigned', 'Diagnosis', 'Waiting for Approval', 'In Progress')
           WHERE u.role = 'technician' AND u.is_active = 1
           GROUP BY u.id, u.full_name
           ORDER BY active_count DESC"""
    ).fetchall()

    # Delivery staff workload
    delivery_workload = db.execute(
        """SELECT u.id, u.full_name, COUNT(dt.id) as active_tasks
           FROM users u
           LEFT JOIN delivery_tasks dt ON u.id = dt.delivery_staff_id AND dt.status IN ('Assigned', 'In Transit')
           WHERE u.role = 'delivery' AND u.is_active = 1
           GROUP BY u.id, u.full_name
           ORDER BY active_tasks DESC"""
    ).fetchall()

    # Recent bookings
    recent_bookings = db.execute(
        """SELECT b.*, u.full_name as customer_name, rc.name as category_name,
                  t.full_name as technician_name
           FROM bookings b
           JOIN users u ON b.customer_id = u.id
           LEFT JOIN repair_categories rc ON b.category_id = rc.id
           LEFT JOIN users t ON b.technician_id = t.id
           ORDER BY b.created_at DESC LIMIT 8"""
    ).fetchall()

    return render_template(
        'admin/dashboard.html',
        total_customers=total_customers,
        total_technicians=total_technicians,
        total_delivery=total_delivery,
        total_bookings=total_bookings,
        pending_repairs=pending_repairs,
        in_progress=in_progress,
        ready_for_pickup=ready_for_pickup,
        out_for_delivery=out_for_delivery,
        completed_repairs=completed_repairs,
        cancelled_repairs=cancelled_repairs,
        total_revenue=total_revenue,
        avg_rating=avg_rating,
        review_count=review_count,
        status_data=status_data,
        tech_workload=tech_workload,
        delivery_workload=delivery_workload,
        recent_bookings=recent_bookings
    )


@bp.route('/bookings')
@login_required(roles=['admin'])
def bookings():
    """All bookings management with status, tech, and search filters."""
    status_filter = request.args.get('status', '').strip()
    tech_filter = request.args.get('tech', '').strip()
    search = request.args.get('q', '').strip()

    db = get_db()
    query = """
        SELECT b.*, u.full_name as customer_name, u.mobile as customer_mobile,
               rc.name as category_name, t.full_name as technician_name,
               d.full_name as delivery_staff_name
        FROM bookings b
        JOIN users u ON b.customer_id = u.id
        LEFT JOIN repair_categories rc ON b.category_id = rc.id
        LEFT JOIN users t ON b.technician_id = t.id
        LEFT JOIN users d ON b.delivery_staff_id = d.id
        WHERE 1=1
    """
    params = []

    if status_filter:
        query += " AND b.status = ?"
        params.append(status_filter)

    if tech_filter:
        query += " AND b.technician_id = ?"
        params.append(tech_filter)

    if search:
        query += " AND (b.reference LIKE ? OR u.full_name LIKE ? OR b.phone_brand LIKE ? OR b.phone_model LIKE ?)"
        wildcard = f"%{search}%"
        params.extend([wildcard, wildcard, wildcard, wildcard])

    query += " ORDER BY b.created_at DESC"
    all_bookings = db.execute(query, params).fetchall()

    technicians = db.execute("SELECT id, full_name FROM users WHERE role = 'technician' AND is_active = 1").fetchall()

    return render_template(
        'admin/bookings.html',
        bookings=all_bookings,
        technicians=technicians,
        current_status=status_filter,
        current_tech=tech_filter,
        search=search
    )


@bp.route('/bookings/<int:booking_id>')
@login_required(roles=['admin'])
def booking_detail(booking_id):
    """Admin view of single booking with assignment controls and full history."""
    booking = get_booking_with_details(booking_id)
    if not booking:
        flash('Booking not found.', 'danger')
        return redirect(url_for('admin.bookings'))

    history = get_status_history(booking_id)
    db = get_db()

    technicians = db.execute("SELECT id, full_name FROM users WHERE role = 'technician' AND is_active = 1").fetchall()
    delivery_staff = db.execute("SELECT id, full_name FROM users WHERE role = 'delivery' AND is_active = 1").fetchall()

    diagnosis = db.execute("SELECT * FROM diagnoses WHERE booking_id = ?", (booking_id,)).fetchone()
    estimate = db.execute("SELECT * FROM estimates WHERE booking_id = ?", (booking_id,)).fetchone()
    payments = db.execute("SELECT * FROM payments WHERE booking_id = ?", (booking_id,)).fetchall()
    review = db.execute("SELECT * FROM reviews WHERE booking_id = ?", (booking_id,)).fetchone()
    images = db.execute("SELECT * FROM booking_images WHERE booking_id = ?", (booking_id,)).fetchall()
    delivery_task = db.execute("SELECT * FROM delivery_tasks WHERE booking_id = ?", (booking_id,)).fetchone()

    return render_template(
        'admin/booking_detail.html',
        booking=booking,
        history=history,
        technicians=technicians,
        delivery_staff=delivery_staff,
        diagnosis=diagnosis,
        estimate=estimate,
        payments=payments,
        review=review,
        images=images,
        delivery_task=delivery_task
    )


@bp.route('/bookings/<int:booking_id>/assign-technician', methods=['POST'])
@login_required(roles=['admin'])
def assign_technician(booking_id):
    """Assign or reassign technician to a repair booking."""
    technician_id = request.form.get('technician_id')
    db = get_db()

    tech = db.execute("SELECT id, full_name FROM users WHERE id = ? AND role = 'technician'", (technician_id,)).fetchone()
    if not tech:
        flash('Selected technician not found.', 'danger')
        return redirect(url_for('admin.booking_detail', booking_id=booking_id))

    booking = db.execute("SELECT * FROM bookings WHERE id = ?", (booking_id,)).fetchone()
    db.execute(
        "UPDATE bookings SET technician_id = ?, updated_at = datetime('now') WHERE id = ?",
        (technician_id, booking_id)
    )

    # If status is still 'Booked', advance to 'Assigned'
    if booking['status'] == 'Booked':
        update_booking_status(booking_id, 'Assigned', session['user_id'], f'Assigned to technician {tech["full_name"]}')

    # Notify technician
    create_notification(
        technician_id,
        'New Repair Assignment',
        f'You have been assigned to repair {booking["reference"]} ({booking["phone_brand"]} {booking["phone_model"]}).',
        f'/technician/repairs/{booking_id}'
    )

    flash(f'Successfully assigned {tech["full_name"]} to repair {booking["reference"]}.', 'success')
    return redirect(url_for('admin.booking_detail', booking_id=booking_id))


@bp.route('/bookings/<int:booking_id>/assign-delivery', methods=['POST'])
@login_required(roles=['admin'])
def assign_delivery(booking_id):
    """Assign delivery staff for pickup or delivery task."""
    delivery_staff_id = request.form.get('delivery_staff_id')
    task_type = request.form.get('task_type', 'pickup')  # 'pickup' or 'delivery'
    notes = request.form.get('notes', '').strip()

    db = get_db()
    staff = db.execute("SELECT id, full_name FROM users WHERE id = ? AND role = 'delivery'", (delivery_staff_id,)).fetchone()
    if not staff:
        flash('Selected delivery personnel not found.', 'danger')
        return redirect(url_for('admin.booking_detail', booking_id=booking_id))

    booking = get_booking_with_details(booking_id)

    # Address determination
    address = booking['pickup_address'] if booking['pickup_address'] else 'Customer registered address'

    # Create delivery task
    db.execute(
        """INSERT INTO delivery_tasks (booking_id, delivery_staff_id, task_type, address, contact_name, contact_phone, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (booking_id, delivery_staff_id, task_type, address, booking['customer_name'], booking['customer_mobile'], notes)
    )

    db.execute(
        "UPDATE bookings SET delivery_staff_id = ?, updated_at = datetime('now') WHERE id = ?",
        (delivery_staff_id, booking_id)
    )
    db.commit()

    # Notify delivery staff
    create_notification(
        delivery_staff_id,
        f'New {task_type.capitalize()} Task',
        f'You have been assigned a {task_type} task for booking {booking["reference"]}.',
        f'/delivery/tasks'
    )

    flash(f'Assigned {task_type} task to {staff["full_name"]}.', 'success')
    return redirect(url_for('admin.booking_detail', booking_id=booking_id))


@bp.route('/users')
@login_required(roles=['admin'])
def users():
    """Staff and customer management directory."""
    role_filter = request.args.get('role', '').strip()
    search = request.args.get('q', '').strip()

    db = get_db()
    query = "SELECT * FROM users WHERE 1=1"
    params = []

    if role_filter:
        query += " AND role = ?"
        params.append(role_filter)

    if search:
        query += " AND (full_name LIKE ? OR email LIKE ? OR mobile LIKE ?)"
        wildcard = f"%{search}%"
        params.extend([wildcard, wildcard, wildcard])

    query += " ORDER BY role, full_name ASC"
    user_list = db.execute(query, params).fetchall()

    return render_template('admin/users.html', users=user_list, current_role=role_filter, search=search)


@bp.route('/users/create', methods=['GET', 'POST'])
@login_required(roles=['admin'])
def create_staff():
    """Create a new staff member (Technician or Delivery staff)."""
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        mobile = request.form.get('mobile', '').strip()
        role = request.form.get('role')
        password = request.form.get('password', '')

        if role not in ('technician', 'delivery', 'admin'):
            flash('Invalid role selected.', 'danger')
            return render_template('admin/create_staff.html')

        if len(password) < 8:
            flash('Password must be at least 8 characters.', 'danger')
            return render_template('admin/create_staff.html')

        db = get_db()
        existing = db.execute("SELECT id FROM users WHERE email = ? OR mobile = ?", (email, mobile)).fetchone()
        if existing:
            flash('A user with that email or mobile number already exists.', 'danger')
            return render_template('admin/create_staff.html')

        pwd_hash = hash_password(password)
        db.execute(
            "INSERT INTO users (full_name, email, mobile, password_hash, role) VALUES (?, ?, ?, ?, ?)",
            (full_name, email, mobile, pwd_hash, role)
        )
        db.commit()

        flash(f'New {role.capitalize()} account for {full_name} created successfully.', 'success')
        return redirect(url_for('admin.users', role=role))

    return render_template('admin/create_staff.html')


@bp.route('/users/<int:user_id>/toggle-status', methods=['POST'])
@login_required(roles=['admin'])
def toggle_user_status(user_id):
    """Activate or deactivate a staff or customer account."""
    if user_id == session['user_id']:
        flash('You cannot deactivate your own account.', 'danger')
        return redirect(url_for('admin.users'))

    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user:
        flash('User not found.', 'danger')
        return redirect(url_for('admin.users'))

    new_status = 0 if user['is_active'] == 1 else 1
    db.execute("UPDATE users SET is_active = ?, updated_at = datetime('now') WHERE id = ?", (new_status, user_id))
    db.commit()

    status_str = "activated" if new_status == 1 else "deactivated"
    flash(f'User {user["full_name"]} has been {status_str}.', 'info')
    return redirect(url_for('admin.users'))


@bp.route('/categories', methods=['GET', 'POST'])
@login_required(roles=['admin'])
def categories():
    """Repair categories management."""
    db = get_db()
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            name = request.form.get('name', '').strip()
            description = request.form.get('description', '').strip()
            if name:
                try:
                    db.execute("INSERT INTO repair_categories (name, description) VALUES (?, ?)", (name, description))
                    db.commit()
                    flash(f'Category "{name}" added.', 'success')
                except Exception:
                    flash('A category with that name already exists.', 'danger')
        elif action == 'toggle':
            cat_id = request.form.get('category_id')
            cat = db.execute("SELECT is_active FROM repair_categories WHERE id = ?", (cat_id,)).fetchone()
            if cat:
                new_state = 0 if cat['is_active'] == 1 else 1
                db.execute("UPDATE repair_categories SET is_active = ? WHERE id = ?", (new_state, cat_id))
                db.commit()
                flash('Category status updated.', 'info')
        return redirect(url_for('admin.categories'))

    category_list = db.execute("SELECT * FROM repair_categories ORDER BY name ASC").fetchall()
    return render_template('admin/categories.html', categories=category_list)


@bp.route('/inventory', methods=['GET', 'POST'])
@login_required(roles=['admin'])
def inventory():
    """Inventory & spare-parts management with transactional updates."""
    db = get_db()

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'add_item':
            part_name = request.form.get('part_name', '').strip()
            sku = request.form.get('sku', '').strip().upper()
            category = request.form.get('category', '').strip()
            stock_qty = int(request.form.get('stock_quantity', 0))
            min_thresh = int(request.form.get('min_stock_threshold', 5))
            unit_cost = float(request.form.get('unit_cost', 0.0))
            supplier = request.form.get('supplier', '').strip()

            try:
                item_id = db.execute(
                    """INSERT INTO inventory (part_name, sku, category, stock_quantity, min_stock_threshold, unit_cost, supplier)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (part_name, sku, category, stock_qty, min_thresh, unit_cost, supplier)
                ).lastrowid

                if stock_qty > 0:
                    db.execute(
                        """INSERT INTO inventory_movements (inventory_id, movement_type, quantity, reason, performed_by)
                           VALUES (?, 'in', ?, 'Initial stock setup', ?)""",
                        (item_id, stock_qty, session['user_id'])
                    )
                db.commit()
                flash(f'Inventory part "{part_name}" added successfully.', 'success')
            except Exception as e:
                flash(f'Failed to add inventory item: {str(e)}', 'danger')

        elif action == 'adjust_stock':
            item_id = request.form.get('item_id')
            movement_type = request.form.get('movement_type')  # 'in' or 'out'
            qty = int(request.form.get('quantity', 0))
            reason = request.form.get('reason', '').strip()

            item = db.execute("SELECT * FROM inventory WHERE id = ?", (item_id,)).fetchone()
            if item and qty > 0:
                current_stock = item['stock_quantity']
                if movement_type == 'out' and current_stock - qty < 0:
                    flash('Cannot reduce below zero stock. Transaction cancelled.', 'danger')
                else:
                    new_stock = current_stock + qty if movement_type == 'in' else current_stock - qty
                    db.execute(
                        "UPDATE inventory SET stock_quantity = ?, updated_at = datetime('now') WHERE id = ?",
                        (new_stock, item_id)
                    )
                    db.execute(
                        """INSERT INTO inventory_movements (inventory_id, movement_type, quantity, reason, performed_by)
                           VALUES (?, ?, ?, ?, ?)""",
                        (item_id, movement_type, qty, reason, session['user_id'])
                    )
                    db.commit()
                    flash(f'Stock updated for "{item["part_name"]}". Current stock: {new_stock}', 'success')

        return redirect(url_for('admin.inventory'))

    items = db.execute("SELECT * FROM inventory ORDER BY stock_quantity ASC, part_name ASC").fetchall()
    movements = db.execute(
        """SELECT im.*, i.part_name, i.sku, u.full_name as staff_name
           FROM inventory_movements im
           JOIN inventory i ON im.inventory_id = i.id
           JOIN users u ON im.performed_by = u.id
           ORDER BY im.created_at DESC LIMIT 20"""
    ).fetchall()

    return render_template('admin/inventory.html', items=items, movements=movements)


@bp.route('/reviews')
@login_required(roles=['admin'])
def reviews():
    """Customer reviews and ratings moderation."""
    db = get_db()
    review_list = db.execute(
        """SELECT r.*, b.reference, b.phone_brand, b.phone_model, u.full_name as customer_name
           FROM reviews r
           JOIN bookings b ON r.booking_id = b.id
           JOIN users u ON r.customer_id = u.id
           ORDER BY r.created_at DESC"""
    ).fetchall()

    stats = db.execute(
        "SELECT COUNT(*) as total_reviews, COALESCE(AVG(rating), 0) as avg_rating FROM reviews"
    ).fetchone()

    return render_template('admin/reviews.html', reviews=review_list, stats=stats)


@bp.route('/payments')
@login_required(roles=['admin'])
def payments():
    """All payments record log."""
    db = get_db()
    payments_list = db.execute(
        """SELECT p.*, b.reference, b.phone_brand, b.phone_model,
                  u.full_name as customer_name, rec.full_name as recorded_by_name
           FROM payments p
           JOIN bookings b ON p.booking_id = b.id
           JOIN users u ON b.customer_id = u.id
           JOIN users rec ON p.recorded_by = rec.id
           ORDER BY p.created_at DESC"""
    ).fetchall()

    totals = db.execute(
        """SELECT COALESCE(SUM(amount), 0) as total_collected,
                  COUNT(*) as total_transactions
           FROM payments WHERE payment_status = 'Completed'"""
    ).fetchone()

    return render_template('admin/payments.html', payments=payments_list, totals=totals)


@bp.route('/export/bookings.csv')
@login_required(roles=['admin'])
def export_bookings_csv():
    """Export bookings to CSV with formula injection defense."""
    db = get_db()
    records = db.execute(
        """SELECT b.reference, u.full_name as customer, u.mobile, b.phone_brand, b.phone_model,
                  rc.name as category, b.service_type, b.status, t.full_name as technician,
                  b.created_at, b.updated_at
           FROM bookings b
           JOIN users u ON b.customer_id = u.id
           LEFT JOIN repair_categories rc ON b.category_id = rc.id
           LEFT JOIN users t ON b.technician_id = t.id
           ORDER BY b.created_at DESC"""
    ).fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Reference', 'Customer', 'Mobile', 'Brand', 'Model', 'Category', 'Service Type', 'Status', 'Technician', 'Created At', 'Updated At'])

    for row in records:
        writer.writerow([
            sanitize_csv_field(row['reference']),
            sanitize_csv_field(row['customer']),
            sanitize_csv_field(row['mobile']),
            sanitize_csv_field(row['phone_brand']),
            sanitize_csv_field(row['phone_model']),
            sanitize_csv_field(row['category'] or 'General'),
            sanitize_csv_field(row['service_type']),
            sanitize_csv_field(row['status']),
            sanitize_csv_field(row['technician'] or 'Unassigned'),
            sanitize_csv_field(row['created_at']),
            sanitize_csv_field(row['updated_at'])
        ])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=fixify_bookings_export.csv"}
    )


@bp.route('/export/payments.csv')
@login_required(roles=['admin'])
def export_payments_csv():
    """Export payments records to CSV with formula sanitization."""
    db = get_db()
    records = db.execute(
        """SELECT p.id, b.reference, p.amount, p.payment_method, p.payment_status,
                  p.reference_id, rec.full_name as recorded_by, p.created_at
           FROM payments p
           JOIN bookings b ON p.booking_id = b.id
           JOIN users rec ON p.recorded_by = rec.id
           ORDER BY p.created_at DESC"""
    ).fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Payment ID', 'Booking Reference', 'Amount (INR)', 'Method', 'Status', 'Transaction Ref', 'Recorded By', 'Date'])

    for row in records:
        writer.writerow([
            sanitize_csv_field(row['id']),
            sanitize_csv_field(row['reference']),
            sanitize_csv_field(row['amount']),
            sanitize_csv_field(row['payment_method']),
            sanitize_csv_field(row['payment_status']),
            sanitize_csv_field(row['reference_id']),
            sanitize_csv_field(row['recorded_by']),
            sanitize_csv_field(row['created_at'])
        ])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=fixify_payments_export.csv"}
    )
