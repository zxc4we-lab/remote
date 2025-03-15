from datetime import datetime
from app import db
from sqlalchemy.ext.hybrid import hybrid_property
import uuid

class Client(db.Model):
    """Client model for remote connection targets"""
    __tablename__ = 'client'  # Explicitly define table name
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    host = db.Column(db.String(100), nullable=False)
    port = db.Column(db.Integer, default=22)
    username = db.Column(db.String(100), nullable=False)
    password = db.Column(db.String(255))  # Encrypted in production
    key_file = db.Column(db.String(255))
    connection_type = db.Column(db.String(20), default='ssh')  # ssh, rdp, vnc, etc.
    tags = db.Column(db.String(255))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_connected = db.Column(db.DateTime)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    
    # Relationships
    connection_logs = db.relationship('ConnectionLog', backref='client', lazy='dynamic', cascade='all, delete-orphan')
    
    @hybrid_property
    def is_connected(self):
        """Check if the client is currently connected"""
        return ConnectionLog.query.filter_by(
            client_id=self.id, 
            status='connected',
            disconnection_time=None
        ).first() is not None
    
    @hybrid_property
    def connection_count(self):
        """Get the total connection count"""
        return ConnectionLog.query.filter_by(client_id=self.id).count()
    
    @hybrid_property
    def successful_connections(self):
        """Get successful connection count"""
        return ConnectionLog.query.filter_by(
            client_id=self.id,
            status='disconnected'
        ).count()
    
    @hybrid_property
    def failed_connections(self):
        """Get failed connection count"""
        return ConnectionLog.query.filter_by(
            client_id=self.id,
            status='failed'
        ).count()
    
    @hybrid_property
    def recent_connection(self):
        """Get the most recent connection"""
        return ConnectionLog.query.filter_by(
            client_id=self.id
        ).order_by(ConnectionLog.connection_time.desc()).first()
    
    def update_last_connected(self):
        """Update the last connected timestamp"""
        self.last_connected = datetime.utcnow()
        db.session.commit()
    
    def __repr__(self):
        return f'<Client {self.name} - {self.host}>'


class ConnectionLog(db.Model):
    """Connection log model to track remote access sessions"""
    __tablename__ = 'connection_log'  # Explicitly define table name
    
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    connection_time = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    disconnection_time = db.Column(db.DateTime)
    status = db.Column(db.String(20), default='connected', index=True)  # connected, disconnected, failed
    error_message = db.Column(db.Text)
    ip_address = db.Column(db.String(45))  # To log the IP from which connection was made
    session_id = db.Column(db.String(64), default=lambda: str(uuid.uuid4()), unique=True, index=True)
    
    # Additional fields for auditing
    commands_executed = db.Column(db.Integer, default=0)
    bytes_transferred = db.Column(db.BigInteger, default=0)
    
    @hybrid_property
    def duration(self):
        """Calculate the duration of the connection in seconds"""
        if self.disconnection_time:
            return (self.disconnection_time - self.connection_time).total_seconds()
        elif self.status == 'connected':
            return (datetime.utcnow() - self.connection_time).total_seconds()
        return 0
    
    @hybrid_property
    def formatted_duration(self):
        """Format the duration in a human-readable format"""
        seconds = self.duration
        if seconds is None or seconds == 0:
            return '-'
            
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            remaining_seconds = int(seconds % 60)
            return f"{minutes}m {remaining_seconds}s"
        else:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            return f"{hours}h {minutes}m"
    
    def __repr__(self):
        return f'<ConnectionLog {self.client_id} - {self.connection_time}>'
