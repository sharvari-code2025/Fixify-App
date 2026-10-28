"""
Fixify — Smart Mobile Repair Management System
Main Application Factory & Entry Point
"""
import os
import secrets
from datetime import datetime
from flask import Flask, render_template, request, session, abort, redirect, url_for, flash
from config import Config
from database.db import close_db, init_db, seed_demo_data, seed_sample_records, get_db
from services.notification_service import get_unread_count, get_user_notifications, mark_as_read, mark_all_as_read


def create_app(config_class=Config):
    """Application factory for Fixify."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Ensure upload directory exists
    os.makedirs(app.config.get('UPLOAD_FOLDER', 'static/uploads'), exist_ok=True)

    # Database connection teardown
    app.teardown_appcontext(close_db)

    # ============================================================
    # CSRF PROTECTION
    # ============================================================
    @app.before_request
    def check_csrf():
        # Ensure session CSRF token exists
        if '_csrf_token' not in session:
            session['_csrf_token'] = secrets.token_hex(24)

        # Skip CSRF check in testing if disabled
        if app.config.get('TESTING') and app.config.get('WTF_CSRF_ENABLED') is False:
            return

        if request.method in ('POST', 'PUT', 'DELETE', 'PATCH'):
            token = request.form.get('csrf_token') or request.headers.get('X-CSRFToken')
            expected = session.get('_csrf_token')
            if not token or token != expected:
                abort(400, description="Invalid or missing CSRF token. Please refresh the page and try again.")

    # Context processors
    @app.context_processor
    def inject_globals():
        unread_count = 0
        if 'user_id' in session:
            try:
                unread_count = get_unread_count(session['user_id'])
            except Exception:
                unread_count = 0

        def csrf_token():
            if '_csrf_token' not in session:
                session['_csrf_token'] = secrets.token_hex(24)
            return session['_csrf_token']

        return {
            'csrf_token': csrf_token,
            'unread_notifications_count': unread_count,
            'current_year': datetime.now().year,
            'app_name': 'Fixify',
            'tagline': 'Your Device. Our Expertise. Zero Guesswork.'
        }

    # ============================================================
    # REGISTER BLUEPRINTS
    # ============================================================
    from routes.auth import bp as auth_bp
    from routes.customer import bp as customer_bp
    from routes.admin import bp as admin_bp
    from routes.technician import bp as technician_bp
    from routes.delivery import bp as delivery_bp
    from routes.bookings import bp as bookings_bp
    from routes.repairs import bp as repairs_bp
    from routes.payments import bp as payments_bp
    from routes.reviews import bp as reviews_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(customer_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(technician_bp)
    app.register_blueprint(delivery_bp)
    app.register_blueprint(bookings_bp)
    app.register_blueprint(repairs_bp)
    app.register_blueprint(payments_bp)
    app.register_blueprint(reviews_bp)

    # ============================================================
    # MAIN & PUBLIC ROUTES
    # ============================================================
    @app.route('/')
    def index():
        """Public homepage featuring services, genuine reviews, workflow, and tracking."""
        db = get_db()
        categories = db.execute("SELECT * FROM repair_categories WHERE is_active = 1 LIMIT 8").fetchall()

        # Real reviews from SQLite (no fabricated testimonials)
        reviews = db.execute(
            """SELECT r.rating, r.review_text, r.created_at, u.full_name as customer_name,
                      b.phone_brand, b.phone_model
               FROM reviews r
               JOIN users u ON r.customer_id = u.id
               JOIN bookings b ON r.booking_id = b.id
               ORDER BY r.created_at DESC LIMIT 6"""
        ).fetchall()

        # Aggregate live platform stats
        stats = {
            'repairs_completed': db.execute("SELECT COUNT(*) as c FROM bookings WHERE status = 'Completed'").fetchone()['c'],
            'active_repairs': db.execute("SELECT COUNT(*) as c FROM bookings WHERE status NOT IN ('Completed', 'Cancelled')").fetchone()['c'],
            'avg_rating': round(db.execute("SELECT COALESCE(AVG(rating), 5.0) as r FROM reviews").fetchone()['r'], 1),
            'satisfaction_count': db.execute("SELECT COUNT(*) as c FROM reviews WHERE rating >= 4").fetchone()['c']
        }

        return render_template('index.html', categories=categories, reviews=reviews, stats=stats)

    @app.route('/notifications')
    def notifications():
        """User notification center."""
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))

        user_id = session['user_id']
        items = get_user_notifications(user_id, limit=30)
        return render_template('notifications.html', notifications=items)

    @app.route('/notifications/read/<int:nid>', methods=['POST'])
    def read_notification(nid):
        """Mark single notification as read."""
        if 'user_id' not in session:
            abort(401)
        mark_as_read(nid, session['user_id'])
        return redirect(request.referrer or url_for('notifications'))

    @app.route('/notifications/read-all', methods=['POST'])
    def read_all_notifications():
        """Mark all notifications as read."""
        if 'user_id' not in session:
            abort(401)
        mark_all_as_read(session['user_id'])
        flash('All notifications marked as read.', 'info')
        return redirect(url_for('notifications'))

    # ============================================================
    # ERROR HANDLERS
    # ============================================================
    @app.errorhandler(400)
    def bad_request(e):
        return render_template('errors/400.html', description=getattr(e, 'description', 'Bad Request')), 400

    @app.errorhandler(403)
    def forbidden(e):
        return render_template('errors/403.html'), 403

    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def server_error(e):
        return render_template('errors/500.html'), 500

    return app


# Create default instance
app = create_app()

if __name__ == '__main__':
    with app.app_context():
        init_db()
        seed_demo_data()
        seed_sample_records()
    print("Fixify is running on http://127.0.0.1:5000")
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)
