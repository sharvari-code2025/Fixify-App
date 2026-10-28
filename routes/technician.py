"""
Fixify — Technician Routes
Diagnosis recording, parts & labour cost estimation, and repair status management.
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from database.db import get_db, query_db
from services.auth_service import login_required
from services.booking_service import get_booking_with_details, get_status_history, update_booking_status
from services.repair_service import create_diagnosis, create_estimate, get_diagnosis, get_estimate

bp = Blueprint('technician', __name__, url_prefix='/technician')


@bp.route('/dashboard')
@login_required(roles=['technician'])
def dashboard():
    """Technician dashboard with workload metrics and assigned repair queue."""
    tech_id = session['user_id']
    db = get_db()

    total_assigned = db.execute("SELECT COUNT(*) as c FROM bookings WHERE technician_id = ?", (tech_id,)).fetchone()['c']
    pending_diagnosis = db.execute(
        "SELECT COUNT(*) as c FROM bookings WHERE technician_id = ? AND status IN ('Assigned', 'Diagnosis')",
        (tech_id,)
    ).fetchone()['c']
    awaiting_approval = db.execute(
        "SELECT COUNT(*) as c FROM bookings WHERE technician_id = ? AND status = 'Waiting for Approval'",
        (tech_id,)
    ).fetchone()['c']
    in_progress = db.execute(
        "SELECT COUNT(*) as c FROM bookings WHERE technician_id = ? AND status = 'In Progress'",
        (tech_id,)
    ).fetchone()['c']
    completed = db.execute(
        "SELECT COUNT(*) as c FROM bookings WHERE technician_id = ? AND status IN ('Ready for Pickup', 'Out for Delivery', 'Delivered', 'Completed')",
        (tech_id,)
    ).fetchone()['c']

    # Active repair tasks
    active_repairs = db.execute(
        """SELECT b.*, u.full_name as customer_name, u.mobile as customer_mobile,
                  rc.name as category_name, e.total_cost, e.approval_status as estimate_status
           FROM bookings b
           JOIN users u ON b.customer_id = u.id
           LEFT JOIN repair_categories rc ON b.category_id = rc.id
           LEFT JOIN estimates e ON b.id = e.booking_id
           WHERE b.technician_id = ? AND b.status NOT IN ('Completed', 'Cancelled')
           ORDER BY b.created_at ASC""",
        (tech_id,)
    ).fetchall()

    return render_template(
        'technician/dashboard.html',
        total_assigned=total_assigned,
        pending_diagnosis=pending_diagnosis,
        awaiting_approval=awaiting_approval,
        in_progress=in_progress,
        completed=completed,
        repairs=active_repairs
    )


@bp.route('/repairs')
@login_required(roles=['technician'])
def repairs():
    """All repairs assigned to this technician with filter."""
    tech_id = session['user_id']
    status_filter = request.args.get('status', '').strip()
    search = request.args.get('q', '').strip()

    db = get_db()
    query = """
        SELECT b.*, u.full_name as customer_name, u.mobile as customer_mobile,
               rc.name as category_name, e.total_cost, e.approval_status as estimate_status
        FROM bookings b
        JOIN users u ON b.customer_id = u.id
        LEFT JOIN repair_categories rc ON b.category_id = rc.id
        LEFT JOIN estimates e ON b.id = e.booking_id
        WHERE b.technician_id = ?
    """
    params = [tech_id]

    if status_filter:
        query += " AND b.status = ?"
        params.append(status_filter)

    if search:
        query += " AND (b.reference LIKE ? OR u.full_name LIKE ? OR b.phone_brand LIKE ? OR b.phone_model LIKE ?)"
        wildcard = f"%{search}%"
        params.extend([wildcard, wildcard, wildcard, wildcard])

    query += " ORDER BY b.created_at DESC"
    assigned_repairs = db.execute(query, params).fetchall()

    return render_template('technician/repairs.html', repairs=assigned_repairs, current_status=status_filter, search=search)


@bp.route('/repairs/<int:booking_id>', methods=['GET'])
@login_required(roles=['technician'])
def repair_detail(booking_id):
    """Technician repair workspace: inspection, diagnosis, cost estimation, and status update."""
    tech_id = session['user_id']
    booking = get_booking_with_details(booking_id)

    if not booking or booking['technician_id'] != tech_id:
        flash('Repair booking not found or not assigned to you.', 'danger')
        return redirect(url_for('technician.repairs'))

    history = get_status_history(booking_id)
    diagnosis = get_diagnosis(booking_id)
    estimate = get_estimate(booking_id)

    db = get_db()
    images = db.execute("SELECT * FROM booking_images WHERE booking_id = ?", (booking_id,)).fetchall()
    parts = db.execute("SELECT * FROM inventory WHERE stock_quantity > 0 ORDER BY part_name ASC").fetchall()

    return render_template(
        'technician/repair_detail.html',
        booking=booking,
        history=history,
        diagnosis=diagnosis,
        estimate=estimate,
        images=images,
        parts=parts
    )


@bp.route('/repairs/<int:booking_id>/diagnose', methods=['POST'])
@login_required(roles=['technician'])
def submit_diagnosis(booking_id):
    """Save or update diagnosis notes."""
    tech_id = session['user_id']
    booking = get_booking_with_details(booking_id)

    if not booking or booking['technician_id'] != tech_id:
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('technician.repairs'))

    diagnosis_text = request.form.get('diagnosis_text', '').strip()
    recommended_repair = request.form.get('recommended_repair', '').strip()

    if not diagnosis_text:
        flash('Please provide diagnosis findings.', 'danger')
        return redirect(url_for('technician.repair_detail', booking_id=booking_id))

    create_diagnosis(booking_id, tech_id, diagnosis_text, recommended_repair)

    # Transition from Assigned -> Diagnosis if needed
    if booking['status'] == 'Assigned':
        update_booking_status(booking_id, 'Diagnosis', tech_id, 'Diagnosis completed by technician')

    flash('Diagnosis recorded successfully.', 'success')
    return redirect(url_for('technician.repair_detail', booking_id=booking_id))


@bp.route('/repairs/<int:booking_id>/estimate', methods=['POST'])
@login_required(roles=['technician'])
def submit_estimate(booking_id):
    """Save cost estimate and send for customer approval."""
    tech_id = session['user_id']
    booking = get_booking_with_details(booking_id)

    if not booking or booking['technician_id'] != tech_id:
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('technician.repairs'))

    try:
        parts_cost = float(request.form.get('parts_cost', 0))
        labour_cost = float(request.form.get('labour_cost', 0))
        additional_charges = float(request.form.get('additional_charges', 0))
        estimated_completion = request.form.get('estimated_completion', '').strip()

        if parts_cost < 0 or labour_cost < 0 or additional_charges < 0:
            flash('Cost amounts cannot be negative.', 'danger')
            return redirect(url_for('technician.repair_detail', booking_id=booking_id))

        create_estimate(booking_id, tech_id, parts_cost, labour_cost, additional_charges, estimated_completion)

        # Advance to Waiting for Approval
        if booking['status'] in ('Assigned', 'Diagnosis', 'Estimate Rejected'):
            update_booking_status(booking_id, 'Waiting for Approval', tech_id, f'Estimate submitted: Parts ₹{parts_cost}, Labour ₹{labour_cost}, Total ₹{parts_cost+labour_cost+additional_charges:.2f}')

        flash('Cost estimate submitted and customer notified for approval.', 'success')
    except ValueError:
        flash('Please enter valid numeric costs.', 'danger')

    return redirect(url_for('technician.repair_detail', booking_id=booking_id))


@bp.route('/repairs/<int:booking_id>/status', methods=['POST'])
@login_required(roles=['technician'])
def update_status(booking_id):
    """Update repair status by technician (e.g., mark Ready for Pickup or Unable to Repair)."""
    tech_id = session['user_id']
    booking = get_booking_with_details(booking_id)

    if not booking or booking['technician_id'] != tech_id:
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('technician.repairs'))

    new_status = request.form.get('status')
    notes = request.form.get('notes', '').strip()

    # Allowed technician transitions
    allowed = ['In Progress', 'Ready for Pickup', 'Unable to Repair']
    if new_status not in allowed:
        flash(f'Technicians cannot set status to {new_status}.', 'danger')
        return redirect(url_for('technician.repair_detail', booking_id=booking_id))

    success, msg = update_booking_status(booking_id, new_status, tech_id, notes or f'Status updated by technician to {new_status}')
    if success:
        flash(f'Repair status successfully updated to {new_status}.', 'success')
    else:
        flash(f'Failed to update status: {msg}', 'danger')

    return redirect(url_for('technician.repair_detail', booking_id=booking_id))
