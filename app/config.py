import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'hard-to-guess-string'

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///remote_access.db'
    
    # Remote access settings
    REMOTE_SESSION_TIMEOUT = 3600  # 1 hour
    MAX_CONCURRENT_CONNECTIONS = 5
    ENCRYPTION_ENABLED = True

class DevelopmentConfig(Config):
    DEBUG = True

class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'

class ProductionConfig(Config):
    # Production-specific settings
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    SSL_REQUIRED = True

config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
