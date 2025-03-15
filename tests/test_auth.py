import pytest
from app import create_app, db
from app.models.user import User
from app.services.auth_service import AuthService

@pytest.fixture
def app():
    app = create_app()
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def auth_service():
    return AuthService()

def test_create_user(auth_service):
    assert auth_service.create_user('testuser', 'test@example.com', 'password123')
    user = User.query.filter_by(username='testuser').first()
    assert user is not None
    assert user.email == 'test@example.com'
    assert user.check_password('password123')

def test_authenticate_user(auth_service):
    auth_service.create_user('testuser', 'test@example.com', 'password123')
    user = auth_service.authenticate_user('testuser', 'password123')
    assert user is not None
    assert user.username == 'testuser'

def test_duplicate_username(auth_service):
    auth_service.create_user('testuser', 'test@example.com', 'password123')
    assert not auth_service.create_user('testuser', 'another@example.com', 'password123')

def test_duplicate_email(auth_service):
    auth_service.create_user('testuser', 'test@example.com', 'password123')
    assert not auth_service.create_user('anotheruser', 'test@example.com', 'password123') 