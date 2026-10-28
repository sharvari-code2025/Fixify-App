"""
Fixify — Repair Overview Routes
Provides repair search and status lookup shortcuts.
"""
from flask import Blueprint, redirect, url_for, request

bp = Blueprint('repairs', __name__, url_prefix='/repairs')


@bp.route('/')
def index():
    """Redirect to public tracking or appropriate role dashboard."""
    return redirect(url_for('bookings.track'))
