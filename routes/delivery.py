"""
Fixify — Delivery Routes
Handles pickup and delivery tasks for assigned delivery staff.
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from database.db import get_db, query_db
from services.auth_service import login_required
from services.booking_service import update_booking_status
from services.notification_service import create_notification

bp = Blueprint('delivery', __name__, url_prefix='/delivery')


@bp.route('/dashboard')
@login_required(roles=['delivery'])
def dashboard():
    """Delivery personnel dashboard with daily tasks."""
    staff_id = session['user_id']
    db = get_db()

    total_tasks = db.execute("SELECT COUNT(*) as c FROM delivery_tasks WHERE delivery_staff_id = ?", (staff_id,)).fetchone()['c']
    pending_pickups = db.execute(
        "SELECT COUNT(*) as c FROM delivery_tasks WHERE delivery_staff_id = ? AND task_type = 'pickup' AND status IN ('Assigned', 'In Transit')",
        (staff_id,)
    ).fetchone()['c']
    pending_deliveries = db.execute(
        "SELECT COUNT(*) as c FROM delivery_tasks WHERE delivery_staff_id = ? AND task_type = 'delivery' AND status IN ('Assigned', 'In Transit')",
        (staff_id,)
    ).fetchone()['c']
    completed_tasks = db.execute(
        "SELECT COUNT(*) as c FROM delivery_tasks WHERE delivery_staff_id = ? AND status = 'Completed'",
        (staff_id,)
    ).fetchone()['c']

    # Active tasks
    active_tasks = db.execute(
        """SELECT dt.*, b.reference, b.phone_brand, b.phone_model, b.status as booking_status,
                  u.full_name as customer_name, u.mobile as customer_mobile
           FROM delivery_tasks dt
           JOIN bookings b ON dt.booking_id = b.id
           JOIN users u ON b.customer_id = u.id
           WHERE dt.delivery_staff_id = ? AND dt.status IN ('Assigned', 'In Transit')
           ORDER BY dt.created_at ASC""",
        (staff_id,)
    ).fetchall()

    return render_template(
        'delivery/dashboard.html',
        total_tasks=total_tasks,
        pending_pickups=pending_pickups,
        pending_deliveries=pending_deliveries,
        completed_tasks=completed_tasks,
        active_tasks=active_tasks
    )


@bp.route('/tasks')
@login_required(roles=['delivery'])
def tasks():
    """View all delivery tasks with status filters."""
    staff_id = session['user_id']
    status_filter = request.args.get('status', '').strip()
    task_type = request.args.get('type', '').strip()

    db = get_db()
    query = """
        SELECT dt.*, b.reference, b.phone_brand, b.phone_model, b.status as booking_status,
               u.full_name as customer_name, u.mobile as customer_mobile
        FROM delivery_tasks dt
        JOIN bookings b ON dt.booking_id = b.id
        JOIN users u ON b.customer_id = u.id
        WHERE dt.delivery_staff_id = ?
    """
    params = [staff_id]

    if status_filter:
        query += " AND dt.status = ?"
        params.append(status_filter)

    if task_type:
        query += " AND dt.task_type = ?"
        params.append(task_type)

    query += " ORDER BY dt.created_at DESC"
    all_tasks = db.execute(query, params).fetchall()

    return render_template('delivery/tasks.html', tasks=all_tasks, current_status=status_filter, current_type=task_type)


@bp.route('/tasks/<int:task_id>/update', methods=['POST'])
@login_required(roles=['delivery'])
def update_task(task_id):
    """Update delivery task status and synchronize with booking lifecycle."""
    staff_id = session['user_id']
    db = get_db()

    task = db.execute(
        """SELECT dt.*, b.reference, b.customer_id, b.status as booking_status
           FROM delivery_tasks dt
           JOIN bookings b ON dt.booking_id = b.id
           WHERE dt.id = ? AND dt.delivery_staff_id = ?""",
        (task_id, staff_id)
    ).fetchone()

    if not task:
        flash('Delivery task not found or not assigned to you.', 'danger')
        return redirect(url_for('delivery.tasks'))

    new_status = request.form.get('status')
    notes = request.form.get('notes', '').strip()

    if new_status not in ('In Transit', 'Completed', 'Failed'):
        flash('Invalid status update.', 'danger')
        return redirect(url_for('delivery.tasks'))

    # Update delivery task
    completed_at = "datetime('now')" if new_status == 'Completed' else "NULL"
    db.execute(
        f"""UPDATE delivery_tasks 
            SET status = ?, notes = COALESCE(?, notes),
                completed_at = {completed_at}, updated_at = datetime('now')
            WHERE id = ?""",
        (new_status, notes, task_id)
    )
    db.commit()

    # Synchronize with main repair booking status
    booking_id = task['booking_id']

    if task['task_type'] == 'pickup':
        if new_status == 'Completed':
            update_booking_status(booking_id, 'Diagnosis', staff_id, f'Device picked up successfully by delivery staff. Notes: {notes or "None"}')
            flash(f'Pickup task for {task["reference"]} marked as Completed.', 'success')
        elif new_status == 'Failed':
            flash(f'Pickup failed for {task["reference"]}. Admin and customer will be notified.', 'warning')
            create_notification(task['customer_id'], 'Pickup Attempt Failed', f'Pickup attempt failed for {task["reference"]}: {notes or "Customer unavailable"}')

    elif task['task_type'] == 'delivery':
        if new_status == 'In Transit':
            update_booking_status(booking_id, 'Out for Delivery', staff_id, f'Device out for delivery with {session["user_name"]}. Notes: {notes or "None"}')
            flash(f'Delivery status updated to Out for Delivery for {task["reference"]}.', 'info')
        elif new_status == 'Completed':
            update_booking_status(booking_id, 'Delivered', staff_id, f'Device delivered to customer. Notes: {notes or "None"}')
            update_booking_status(booking_id, 'Completed', staff_id, 'Repair service completed')
            flash(f'Delivery completed for {task["reference"]}!', 'success')
        elif new_status == 'Failed':
            flash(f'Delivery attempt failed for {task["reference"]}. Notes recorded.', 'warning')
            create_notification(task['customer_id'], 'Delivery Attempt Failed', f'Delivery attempt failed for {task["reference"]}: {notes or "Customer unavailable"}')

    return redirect(url_for('delivery.tasks'))
