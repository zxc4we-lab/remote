from app import create_app, db
from app.models.user import User
from app.models.client import Client, ConnectionLog
from werkzeug.security import generate_password_hash
import os

app = create_app()

with app.app_context():
    # Drop all tables and recreate them
    db.drop_all()
    db.create_all()
    
    # Create an admin user
    admin = User(
        username='admin',
        email='admin@example.com',
        is_active=True,
        is_admin=True
    )
    admin.set_password('password')
    
    # Add the user to the database
    db.session.add(admin)
    db.session.commit()
    
    print("Database initialized with admin user created.")
    print("Username: admin")
    print("Password: password")
