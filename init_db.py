"""
Fixify — Database Initialization CLI
Sets up tables and seeds default demo data.
"""
from app import create_app
from database.db import init_db, seed_demo_data, seed_sample_records

app = create_app()

with app.app_context():
    print("Initializing Fixify SQLite database...")
    init_db()
    print("Database schema created.")
    print("Seeding initial demo data (Admin, Techs, Delivery, Customer)...")
    seed_demo_data()
    print("Seeding sample demonstration records (bookings, inventory, reviews)...")
    seed_sample_records()
    print("Database setup complete! Fixify is ready to run.")
