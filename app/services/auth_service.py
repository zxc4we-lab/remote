from app.models.user import User
from app import db
from sqlalchemy.exc import IntegrityError
import re
import logging

class AuthService:
    """Service for user authentication and management"""
    
    def authenticate_user(self, username_or_email, password):
        """Authenticate a user with username/email and password"""
        # Try to find the user by username or email
        user = User.query.filter((User.username == username_or_email) | 
                                 (User.email == username_or_email)).first()
        
        if user and user.check_password(password) and user.is_active:
            return user
        return None
    
    def register_user(self, username, email, password):
        """Register a new user"""
        # Validate input
        if not username or not email or not password:
            raise ValueError("Username, email, and password are required")
        
        # Validate email format
        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            raise ValueError("Invalid email format")
        
        # Validate username format
        if not re.match(r"^[a-zA-Z0-9_-]{3,20}$", username):
            raise ValueError("Username must be 3-20 characters and contain only letters, numbers, underscores, and hyphens")
        
        # Validate password strength
        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters long")
        
        # Check for existing username or email
        existing_user = User.query.filter((User.username == username) | 
                                          (User.email == email)).first()
        if existing_user:
            if existing_user.username == username:
                raise ValueError("Username already exists")
            else:
                raise ValueError("Email already in use")
        
        # Create the user
        user = User(username=username, email=email)
        user.set_password(password)
        
        try:
            db.session.add(user)
            db.session.commit()
            logging.info(f"New user created: {username}")
            return user
        except IntegrityError as e:
            db.session.rollback()
            logging.error(f"Error creating user: {str(e)}")
            raise ValueError("Error creating user account")
    
    def update_profile(self, user_id, first_name, last_name, email):
        """Update user profile information"""
        user = User.query.get(user_id)
        
        if not user:
            raise ValueError("User not found")
        
        # Validate email format
        if email and not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            raise ValueError("Invalid email format")
        
        # Check if email is already in use
        if email and email != user.email:
            existing_user = User.query.filter_by(email=email).first()
            if existing_user:
                raise ValueError("Email already in use")
            user.email = email
        
        if first_name is not None:
            user.first_name = first_name
        
        if last_name is not None:
            user.last_name = last_name
        
        try:
            db.session.commit()
            logging.info(f"Profile updated for user: {user.username}")
            return user
        except IntegrityError as e:
            db.session.rollback()
            logging.error(f"Error updating profile: {str(e)}")
            raise ValueError("Error updating profile")
    
    def change_password(self, user_id, current_password, new_password):
        """Change a user's password"""
        user = User.query.get(user_id)
        
        if not user:
            raise ValueError("User not found")
        
        # Verify current password
        if not user.check_password(current_password):
            raise ValueError("Current password is incorrect")
        
        # Validate password strength
        if len(new_password) < 8:
            raise ValueError("Password must be at least 8 characters long")
        
        # Update password
        user.set_password(new_password)
        
        try:
            db.session.commit()
            logging.info(f"Password changed for user: {user.username}")
            return True
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error changing password: {str(e)}")
            raise ValueError("Error changing password")
    
    def generate_api_key(self, user_id):
        """Generate a new API key for a user"""
        user = User.query.get(user_id)
        
        if not user:
            raise ValueError("User not found")
        
        new_key = user.generate_new_api_key()
        
        try:
            db.session.commit()
            logging.info(f"New API key generated for user: {user.username}")
            return new_key
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error generating API key: {str(e)}")
            raise ValueError("Error generating API key")
