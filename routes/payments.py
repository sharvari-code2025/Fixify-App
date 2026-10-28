"""
Fixify — Payment Processing Routes (Safe Demo Simulation)
Simulates payment recording (demo UPI, demo card, or cash logged by staff) with persistent audit logs.
"""
import secrets
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from database.db import get_db, insert_db
from services.auth_service import login_required
from services.booking_service import get_booking_with_details, update_booking_status
from services.notification_service import create_notification

bp = Blueprint('payments', __name__, url_prefix='/payments')


@bp.route('/checkout/<int:booking_id>', methods=['GET', 'POST'])
@login_required()
def checkout(booking_id):
    """Customer demo checkout / payment settlement page."""
    user_id = session['user_id']
    user_role = session.get('user_role')
    booking = get_booking_with_details(booking_id)

    if not booking:
        flash('Booking not found.', 'danger')
        return redirect(url_for('customer.my_bookings'))

    # Access control: only booking customer or admin/technician can view checkout
    if user_role == 'customer' and booking['customer_id'] != user_id:
        flash('Unauthorized.', 'danger')
        return redirect(url_for('customer.my_bookings'))

    db = get_db()
    estimate = db.execute("SELECT * FROM estimates WHERE booking_id = ?", (booking_id,)).fetchone()
    total_cost = estimate['total_cost'] if estimate else 0.0

    # Total already paid
    past_payments = db.execute("SELECT * FROM payments WHERE booking_id = ? ORDER BY created_at DESC", (booking_id,)).fetchall()
    paid_sum = sum(p['amount'] for p in past_payments if p['payment_status'] == 'Completed')
    balance_due = max(0.0, total_cost - paid_sum)

    if request.method == 'POST':
        amount = float(request.form.get('amount', balance_due))
        payment_method = request.form.get('payment_method', 'demo_upi')
        notes = request.form.get('notes', '').strip()

        if amount <= 0:
            flash('Payment amount must be greater than zero.', 'danger')
            return render_template('payments/checkout.html', booking=booking, estimate=estimate, balance_due=balance_due, past_payments=past_payments)

        # Generate transaction reference
        txn_ref = f"PAY-{secrets.token_hex(4).upper()}"

        db.execute(
            """INSERT INTO payments (booking_id, amount, payment_method, payment_status, reference_id, recorded_by, notes)
               VALUES (?, ?, ?, 'Completed', ?, ?, ?)""",
            (booking_id, amount, payment_method, txn_ref, user_id, f"Demo payment via {payment_method}. {notes}")
        )
        db.commit()

        # Notify customer and admin
        create_notification(
            booking['customer_id'],
            'Payment Received',
            f'Demo payment of ₹{amount:.2f} for booking {booking["reference"]} was recorded (Ref: {txn_ref}).',
            f'/customer/bookings/{booking_id}'
        )

        flash(f'[DEMO MODE] Simulated payment of ₹{amount:.2f} recorded successfully (Ref: {txn_ref}). No real card or bank details were processed.', 'success')
        return redirect(url_for('customer.booking_detail', booking_id=booking_id))

    return render_template(
        'payments/checkout.html',
        booking=booking,
        estimate=estimate,
        balance_due=balance_due,
        past_payments=past_payments
    )
