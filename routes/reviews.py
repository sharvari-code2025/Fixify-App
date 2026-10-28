"""
Fixify — Reviews and Feedback Routes
Handles customer review submission for completed bookings with eligibility enforcement.
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from database.db import get_db, insert_db
from services.auth_service import login_required
from services.booking_service import get_booking_with_details
from services.notification_service import create_notification

bp = Blueprint('reviews', __name__, url_prefix='/reviews')


@bp.route('/submit/<int:booking_id>', methods=['GET', 'POST'])
@login_required(roles=['customer'])
def submit(booking_id):
    """Customer submits feedback for an eligible completed repair booking."""
    customer_id = session['user_id']
    booking = get_booking_with_details(booking_id)

    if not booking or booking['customer_id'] != customer_id:
        flash('Booking not found or access denied.', 'danger')
        return redirect(url_for('customer.my_bookings'))

    # Eligibility check: must be Delivered or Completed or Ready for Pickup
    if booking['status'] not in ('Delivered', 'Completed'):
        flash('Reviews can only be submitted after the device has been delivered or marked completed.', 'warning')
        return redirect(url_for('customer.booking_detail', booking_id=booking_id))

    db = get_db()
    existing = db.execute("SELECT id FROM reviews WHERE booking_id = ?", (booking_id,)).fetchone()
    if existing:
        flash('You have already submitted a review for this repair booking.', 'info')
        return redirect(url_for('customer.booking_detail', booking_id=booking_id))

    if request.method == 'POST':
        try:
            rating = int(request.form.get('rating', 5))
            review_text = request.form.get('review_text', '').strip()

            if rating < 1 or rating > 5:
                flash('Rating must be between 1 and 5 stars.', 'danger')
                return render_template('reviews/submit.html', booking=booking)

            db.execute(
                "INSERT INTO reviews (booking_id, customer_id, rating, review_text) VALUES (?, ?, ?, ?)",
                (booking_id, customer_id, rating, review_text)
            )
            db.commit()

            # Notify admins
            admins = db.execute("SELECT id FROM users WHERE role = 'admin' AND is_active = 1").fetchall()
            for admin in admins:
                create_notification(
                    admin['id'],
                    'New Customer Review',
                    f'{session["user_name"]} gave a {rating}-star review for booking {booking["reference"]}.',
                    f'/admin/reviews'
                )

            flash('Thank you for your valuable feedback! Your review has been recorded.', 'success')
            return redirect(url_for('customer.booking_detail', booking_id=booking_id))

        except ValueError:
            flash('Invalid rating value.', 'danger')

    return render_template('reviews/submit.html', booking=booking)
