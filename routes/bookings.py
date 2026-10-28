"""
Fixify — Booking Creation and Public Tracking Routes
"""
import os
import secrets
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from werkzeug.utils import secure_filename
from database.db import get_db, insert_db
from services.auth_service import login_required
from services.booking_service import create_booking, get_booking_with_details, get_status_history
from services.repair_service import get_diagnosis, get_estimate

bp = Blueprint('bookings', __name__, url_prefix='/bookings')


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in current_app.config.get('ALLOWED_EXTENSIONS', {'png', 'jpg', 'jpeg', 'webp'})


@bp.route('/new', methods=['GET', 'POST'])
@login_required(roles=['customer'])
def create():
    """Customer repair booking form."""
    db = get_db()
    categories = db.execute("SELECT * FROM repair_categories WHERE is_active = 1 ORDER BY name ASC").fetchall()

    if request.method == 'POST':
        phone_brand = request.form.get('phone_brand', '').strip()
        phone_model = request.form.get('phone_model', '').strip()
        category_id = request.form.get('category_id')
        problem_description = request.form.get('problem_description', '').strip()
        device_condition = request.form.get('device_condition', '').strip()
        service_type = request.form.get('service_type', 'walk_in')
        pickup_address = request.form.get('pickup_address', '').strip()
        preferred_date = request.form.get('preferred_date', '').strip()
        additional_notes = request.form.get('additional_notes', '').strip()

        errors = []
        if not phone_brand:
            errors.append('Please specify the phone brand.')
        if not phone_model:
            errors.append('Please specify the phone model.')
        if not problem_description or len(problem_description) < 10:
            errors.append('Please provide a descriptive explanation of the problem (at least 10 characters).')
        if service_type == 'pickup_delivery' and not pickup_address:
            errors.append('Pickup address is required for Pickup & Delivery service.')

        if errors:
            for err in errors:
                flash(err, 'danger')
            return render_template(
                'bookings/new.html',
                categories=categories,
                form=request.form
            )

        customer_id = session['user_id']
        booking_id, reference = create_booking(
            customer_id=customer_id,
            phone_brand=phone_brand,
            phone_model=phone_model,
            category_id=category_id if category_id else None,
            problem_description=problem_description,
            device_condition=device_condition,
            service_type=service_type,
            pickup_address=pickup_address if service_type == 'pickup_delivery' else None,
            preferred_date=preferred_date,
            additional_notes=additional_notes
        )

        # Handle optional image uploads securely
        if 'device_images' in request.files:
            files = request.files.getlist('device_images')
            upload_dir = current_app.config['UPLOAD_FOLDER']
            os.makedirs(upload_dir, exist_ok=True)

            for file in files:
                if file and file.filename and allowed_file(file.filename):
                    orig_name = secure_filename(file.filename)
                    ext = orig_name.rsplit('.', 1)[1].lower() if '.' in orig_name else 'jpg'
                    stored_name = f"{reference}_{secrets.token_hex(6)}.{ext}"
                    filepath = os.path.join(upload_dir, stored_name)
                    file.save(filepath)

                    db.execute(
                        "INSERT INTO booking_images (booking_id, filename, original_name) VALUES (?, ?, ?)",
                        (booking_id, stored_name, orig_name)
                    )
            db.commit()

        flash(f'Repair booking successfully submitted! Your tracking reference is {reference}', 'success')
        return redirect(url_for('bookings.confirmation', reference=reference))

    return render_template('bookings/new.html', categories=categories, form={})


@bp.route('/confirmation/<reference>')
@login_required()
def confirmation(reference):
    """Booking confirmation page with reference and immediate next steps."""
    db = get_db()
    booking = db.execute("SELECT * FROM bookings WHERE reference = ?", (reference,)).fetchone()
    if not booking:
        flash('Booking not found.', 'danger')
        return redirect(url_for('index'))

    return render_template('bookings/confirmation.html', booking=booking)


@bp.route('/track', methods=['GET', 'POST'])
def track():
    """Public or customer tracking portal by booking reference."""
    reference = request.args.get('ref', '').strip()
    if request.method == 'POST':
        reference = request.form.get('reference', '').strip().upper()
        return redirect(url_for('bookings.track', ref=reference))

    booking = None
    history = []
    diagnosis = None
    estimate = None

    if reference:
        db = get_db()
        raw_booking = db.execute("SELECT id FROM bookings WHERE reference = ?", (reference,)).fetchone()
        if raw_booking:
            booking = get_booking_with_details(raw_booking['id'])
            history = get_status_history(raw_booking['id'])
            diagnosis = get_diagnosis(raw_booking['id'])
            estimate = get_estimate(raw_booking['id'])
        else:
            flash(f'No repair found with reference code "{reference}". Please verify and try again.', 'warning')

    return render_template(
        'bookings/track.html',
        reference=reference,
        booking=booking,
        history=history,
        diagnosis=diagnosis,
        estimate=estimate
    )
