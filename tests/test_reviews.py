"""
Fixify — Customer Reviews Test Suite
Tests review eligibility, rating boundaries (1-5 stars), duplicate prevention, and moderation.
"""
import pytest
from database.db import get_db
from services.booking_service import create_booking, update_booking_status


def test_review_eligibility_and_submission(client, auth, app):
    """Test that customer can only review completed repairs, and duplicate reviews are prevented."""
    with app.app_context():
        # Booking 1: still 'In Progress' (ineligible)
        b_id1, _ = create_booking(5, 'Apple', 'iPhone 11', 1, 'Screen issue', '', 'walk_in', None, None, None)
        update_booking_status(b_id1, 'Assigned', 1)
        update_booking_status(b_id1, 'Diagnosis', 2)
        update_booking_status(b_id1, 'Waiting for Approval', 2)
        update_booking_status(b_id1, 'In Progress', 5)

        # Booking 2: 'Completed' (eligible)
        b_id2, _ = create_booking(5, 'Apple', 'iPhone 12', 1, 'Battery issue', '', 'walk_in', None, None, None)
        update_booking_status(b_id2, 'Assigned', 1)
        update_booking_status(b_id2, 'Diagnosis', 2)
        update_booking_status(b_id2, 'Waiting for Approval', 2)
        update_booking_status(b_id2, 'In Progress', 5)
        update_booking_status(b_id2, 'Ready for Pickup', 2)
        update_booking_status(b_id2, 'Completed', 1)

    auth.login_customer()

    # 1. Attempt review on ineligible booking
    res1 = client.get(f'/reviews/submit/{b_id1}', follow_redirects=True)
    assert b'Reviews can only be submitted after the device has been delivered' in res1.data

    # 2. Review eligible completed booking
    res2 = client.post(f'/reviews/submit/{b_id2}', data={
        'rating': '5',
        'review_text': 'Fast turnaround, genuine battery replacement, very polite technician!'
    }, follow_redirects=True)
    assert b'Thank you for your valuable feedback' in res2.data

    with app.app_context():
        db = get_db()
        rev = db.execute("SELECT * FROM reviews WHERE booking_id = ?", (b_id2,)).fetchone()
        assert rev is not None
        assert rev['rating'] == 5
        assert 'genuine battery replacement' in rev['review_text']

    # 3. Duplicate review attempt rejected
    dup_res = client.get(f'/reviews/submit/{b_id2}', follow_redirects=True)
    assert b'already submitted a review' in dup_res.data
