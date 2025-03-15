from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, session
from flask_login import login_user, logout_user, login_required, current_user
from app.services.auth_service import AuthService
from app import db
from app.models.user import User
from werkzeug.urls import url_parse
from datetime import datetime
import logging
import uuid

auth = Blueprint('auth', __name__)
auth_service = AuthService()

@auth.route('/')
def index():
    """Redirect root URL to the login page"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    return redirect(url_for('auth.login'))

@auth.route('/login', methods=['GET', 'POST'])
def login():
    """Handle user login"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember_me = 'remember_me' in request.form
        
        user = auth_service.authenticate_user(username, password)
        
        if user:
            login_user(user, remember=remember_me)
            user.last_login = datetime.utcnow()
            db.session.commit()
            
            # Log successful login
            logging.info(f"User {username} logged in successfully from {request.remote_addr}")
            
            # Generate new session if needed
            if 'session_id' not in session:
                session['session_id'] = str(uuid.uuid4())
            
            # Redirect to the next page or dashboard
            next_page = request.args.get('next')
            if not next_page or url_parse(next_page).netloc != '':
                next_page = url_for('dashboard.index')
                
            return redirect(next_page)
        else:
            flash('Invalid username or password', 'error')
            logging.warning(f"Failed login attempt for {username} from {request.remote_addr}")
    
    return render_template('auth/login.html', title='Sign In')

@auth.route('/logout')
@login_required
def logout():
    """Handle user logout"""
    username = current_user.username
    logout_user()
    flash('You have been logged out successfully', 'info')
    logging.info(f"User {username} logged out")
    
    # Clear session
    session.clear()
    
    return redirect(url_for('auth.login'))

@auth.route('/register', methods=['GET', 'POST'])
def register():
    """Handle user registration"""
    # Check if registration is allowed in current environment
    if not current_app.config.get('ALLOW_REGISTRATION', True):
        flash('Registration is currently disabled', 'error')
        return redirect(url_for('auth.login'))
        
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return render_template('auth/register.html', title='Register')
        
        try:
            user = auth_service.register_user(username, email, password)
            flash('Registration successful! You can now log in.', 'success')
            logging.info(f"New user registered: {username}")
            return redirect(url_for('auth.login'))
        except ValueError as e:
            flash(str(e), 'error')
    
    return render_template('auth/register.html', title='Register')

@auth.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """User profile management"""
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'update_profile':
            first_name = request.form.get('first_name')
            last_name = request.form.get('last_name')
            email = request.form.get('email')
            
            try:
                auth_service.update_profile(current_user.id, first_name, last_name, email)
                flash('Profile updated successfully', 'success')
            except ValueError as e:
                flash(str(e), 'error')
        
        elif action == 'change_password':
            current_password = request.form.get('current_password')
            new_password = request.form.get('new_password')
            confirm_password = request.form.get('confirm_password')
            
            if new_password != confirm_password:
                flash('New passwords do not match', 'error')
            else:
                try:
                    auth_service.change_password(current_user.id, current_password, new_password)
                    flash('Password changed successfully', 'success')
                except ValueError as e:
                    flash(str(e), 'error')
        
        elif action == 'generate_api_key':
            new_key = auth_service.generate_api_key(current_user.id)
            flash(f'New API key generated', 'success')
    
    return render_template('auth/profile.html', title='Profile', user=current_user)

@auth.route('/reset-password', methods=['GET', 'POST'])
def reset_password_request():
    """Request password reset"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
        
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()
        
        if user:
            # In a real app, send reset password email
            # For this demo, we'll just show a message
            flash('If an account exists with that email, you will receive reset instructions.', 'info')
            logging.info(f"Password reset requested for email: {email}")
        else:
            # Don't reveal that the user doesn't exist
            flash('If an account exists with that email, you will receive reset instructions.', 'info')
            logging.warning(f"Password reset requested for non-existent email: {email}")
            
        return redirect(url_for('auth.login'))
        
    return render_template('auth/reset_password_request.html', title='Reset Password')
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, current_user, login_required
from app import db
from app.models.user import User
import datetime

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Handle user login."""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = 'remember' in request.form
        
        user = User.query.filter_by(username=username).first()
        
        if user is None or not user.check_password(password):
            flash('Invalid username or password', 'danger')
            return redirect(url_for('auth.login'))
        
        # Update last login time
        user.update_last_login()
        
        login_user(user, remember=remember)
        next_page = request.args.get('next')
        
        if not next_page or next_page.startswith('/'):
            next_page = url_for('dashboard.index')
            
        return redirect(next_page)
    
    return render_template('auth/login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """Handle user registration."""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        password_confirm = request.form.get('password_confirm')
        
        # Check if username or email already exists
        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'danger')
            return redirect(url_for('auth.register'))
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'danger')
            return redirect(url_for('auth.register'))
        
        # Check if passwords match
        if password != password_confirm:
            flash('Passwords do not match', 'danger')
            return redirect(url_for('auth.register'))
        
        # Create new user
        user = User(username=username, email=email)
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()
        
        flash('Registration successful! You can now log in.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/register.html')

@auth_bp.route('/logout')
@login_required
def logout():
    """Handle user logout."""
    logout_user()
    flash('You have been logged out', 'info')
    return redirect(url_for('auth.login'))
