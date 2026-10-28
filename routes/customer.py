"""
Fixify — Customer Routes
Handles customer dashboard, booking list, detailed booking tracking, and estimate approval/rejection.
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, abort
from database.db import get_db, query_db
from services.auth_service import login_required
from services.booking_service import get_booking_with_details, get_status_history, update_booking_status
from services.repair_service import get_diagnosis, get_estimate, approve_estimate
from services.notification_service import get_user_notifications, mark_as_read, mark_all_as_read

bp = Blueprint('customer', __name__, url_prefix='/customer')


@bp.route('/dashboard')
@login_required(roles=['customer'])
def dashboard():
    """Customer overview dashboard with active repairs, pending actions, and recent history."""
    customer_id = session['user_id']
    db = get_db()

    # Metrics
    total_bookings = db.execute("SELECT COUNT(*) as c FROM bookings WHERE customer_id = ?", (customer_id,)).fetchone()['c']
    active_repairs = db.execute(
        """SELECT COUNT(*) as c FROM bookings 
           WHERE customer_id = ? AND status NOT IN ('Completed', 'Cancelled', 'Unable to Repair')""",
        (customer_id,)
    ).fetchone()['c']
    pending_approvals = db.execute(
        """SELECT COUNT(*) as c FROM bookings b
           JOIN estimates e ON b.id = e.booking_id
           WHERE b.customer_id = ? AND e.approval_status = 'Pending' AND b.status = 'Waiting for Approval'""",
        (customer_id,)
    ).fetchone()['c']
    completed_repairs = db.execute(
        "SELECT COUNT(*) as c FROM bookings WHERE customer_id = ? AND status = 'Completed'",
        (customer_id,)
    ).fetchone()['c']

    # Active and recent bookings
    recent_bookings = db.execute(
        """SELECT b.*, rc.name as category_name, e.total_cost, e.approval_status as estimate_status
           FROM bookings b
           LEFT JOIN repair_categories rc ON b.category_id = rc.id
           LEFT JOIN estimates e ON b.id = e.booking_id
           WHERE b.customer_id = ?
           ORDER BY b.created_at DESC LIMIT 5""",
        (customer_id,)
    ).fetchall()

    return render_template(
        'customer/dashboard.html',
        total_bookings=total_bookings,
        active_repairs=active_repairs,
        pending_approvals=pending_approvals,
        completed_repairs=completed_repairs,
        recent_bookings=recent_bookings
    )


@bp.route('/bookings')
@login_required(roles=['customer'])
def my_bookings():
    """List all bookings for the logged-in customer with filtering."""
    customer_id = session['user_id']
    status_filter = request.args.get('status', '').strip()
    search = request.args.get('q', '').strip()

    db = get_db()
    query = """
        SELECT b.*, rc.name as category_name, e.total_cost, e.approval_status as estimate_status,
               r.id as review_id
        FROM bookings b
        LEFT JOIN repair_categories rc ON b.category_id = rc.id
        LEFT JOIN estimates e ON b.id = e.booking_id
        LEFT JOIN reviews r ON b.id = r.booking_id
        WHERE b.customer_id = ?
    """
    params = [customer_id]

    if status_filter:
        query += " AND b.status = ?"
        params.append(status_filter)

    if search:
        query += " AND (b.reference LIKE ? OR b.phone_brand LIKE ? OR b.phone_model LIKE ?)"
        wildcard = f"%{search}%"
        params.extend([wildcard, wildcard, wildcard])

    query += " ORDER BY b.created_at DESC"

    bookings = db.execute(query, params).fetchall()

    return render_template('customer/bookings.html', bookings=bookings, current_status=status_filter, search=search)


@bp.route('/bookings/<int:booking_id>')
@login_required(roles=['customer'])
def booking_detail(booking_id):
    """Detailed booking tracking page with visual timeline, diagnosis, estimate, delivery, and review."""
    customer_id = session['user_id']
    booking = get_booking_with_details(booking_id)

    if not booking or booking['customer_id'] != customer_id:
        flash('Booking not found or access denied.', 'danger')
        return redirect(url_for('customer.my_bookings'))

    history = get_status_history(booking_id)
    diagnosis = get_diagnosis(booking_id)
    estimate = get_estimate(booking_id)

    db = get_db()
    # Delivery task if any
    delivery_task = db.execute(
        "SELECT * FROM delivery_tasks WHERE booking_id = ? ORDER BY created_at DESC LIMIT 1",
        (booking_id,)
    ).fetchone()

    # Payments
    payments = db.execute(
        "SELECT * FROM payments WHERE booking_id = ? ORDER BY created_at DESC",
        (booking_id,)
    ).fetchall()
    total_paid = sum(p['amount'] for p in payments if p['payment_status'] == 'Completed')

    # Existing review
    review = db.execute("SELECT * FROM reviews WHERE booking_id = ?", (booking_id,)).fetchone()

    # Device images
    images = db.execute("SELECT * FROM booking_images WHERE booking_id = ?", (booking_id,)).fetchall()

    return render_template(
        'customer/booking_detail.html',
        booking=booking,
        history=history,
        diagnosis=diagnosis,
        estimate=estimate,
        delivery_task=delivery_task,
        payments=payments,
        total_paid=total_paid,
        review=review,
        images=images
    )


@bp.route('/bookings/<int:booking_id>/estimate', methods=['POST'])
@login_required(roles=['customer'])
def handle_estimate(booking_id):
    """Customer approves or rejects the repair estimate."""
    customer_id = session['user_id']
    booking = get_booking_with_details(booking_id)

    if not booking or booking['customer_id'] != customer_id:
        flash('Booking not found.', 'danger')
        return redirect(url_for('customer.my_bookings'))

    action = request.form.get('action')  # 'approve' or 'reject'
    notes = request.form.get('notes', '').strip()

    if action == 'approve':
        success, msg = approve_estimate(booking_id, customer_id, approved=True, notes=notes)
        if success:
            update_booking_status(booking_id, 'In Progress', customer_id, f'Estimate approved by customer: {notes or "Proceed with repair"}')
            flash('Repair estimate approved! The technician will now proceed with the repair.', 'success')
        else:
            flash(msg, 'danger')
    elif action == 'reject':
        success, msg = approve_estimate(booking_id, customer_id, approved=False, notes=notes)
        if success:
            update_booking_status(booking_id, 'Estimate Rejected', customer_id, f'Estimate rejected by customer: {notes or "Cancelled or re-evaluate"}')
            flash('Repair estimate rejected. Our team will contact you regarding next steps.', 'warning')
        else:
            flash(msg, 'danger')
    else:
        flash('Invalid action specified.', 'danger')

    return redirect(url_for('customer.booking_detail', booking_id=booking_id))
