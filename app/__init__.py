from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_socketio import SocketIO
from flask_wtf.csrf import CSRFProtect

# Initialize extensions
db = SQLAlchemy()
login_manager = LoginManager()
socketio = SocketIO()
csrf = CSRFProtect()

def create_app(config_name='default'):
    app = Flask(__name__)
    
    # Load config
    from app.config import config
    app.config.from_object(config[config_name])
    
    # Initialize extensions with app
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    
    # Initialize SocketIO with default async mode
    socketio.init_app(app, cors_allowed_origins="*")
    
    login_manager.login_view = 'auth.login'
    login_manager.login_message_category = 'info'
    
    # Register blueprints
    from app.routes.auth import auth_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.remote import remote_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(remote_bp)
    
    # Enable dark mode by default
    @app.context_processor
    def inject_theme():
        return dict(theme='dark')
    
    # Initialize refresh manager
    with app.app_context():
        from app.refresh_manager import refresh_manager
        refresh_manager.init_app(app, socketio)
    
    return app
