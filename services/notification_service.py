"""
Fixify — Notification Service
Creates in-app notifications for users.
"""
from database.db import get_db


def create_notification(user_id, title, message, link=None):
    """Create an in-app notification for a user."""
    db = get_db()
    db.execute(
        "INSERT INTO notifications (user_id, title, message, link) VALUES (?, ?, ?, ?)",
        (user_id, title, message, link)
    )
    db.commit()


def get_user_notifications(user_id, limit=20, offset=0):
    """Get notifications for a user, newest first."""
    db = get_db()
    return db.execute(
        "SELECT * FROM notifications WHERE user_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
        (user_id, limit, offset)
    ).fetchall()


def get_unread_count(user_id):
    """Get count of unread notifications."""
    db = get_db()
    row = db.execute(
        "SELECT COUNT(*) as count FROM notifications WHERE user_id = ? AND is_read = 0",
        (user_id,)
    ).fetchone()
    return row['count'] if row else 0


def mark_as_read(notification_id, user_id):
    """Mark a notification as read (only by its owner)."""
    db = get_db()
    db.execute(
        "UPDATE notifications SET is_read = 1 WHERE id = ? AND user_id = ?",
        (notification_id, user_id)
    )
    db.commit()


def mark_all_as_read(user_id):
    """Mark all notifications as read for a user."""
    db = get_db()
    db.execute(
        "UPDATE notifications SET is_read = 1 WHERE user_id = ? AND is_read = 0",
        (user_id,)
    )
    db.commit()
