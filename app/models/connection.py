from app import db
import datetime

class Connection(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    hostname = db.Column(db.String(120), index=True)
    ip_address = db.Column(db.String(45), index=True)
    port = db.Column(db.Integer, default=22)
    connection_type = db.Column(db.String(20), default='ssh')  # ssh, vnc, rdp
    description = db.Column(db.String(200))
    last_connected = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    def __repr__(self):
        return f'<Connection {self.hostname}>'
    
    def update_last_connected(self):
        self.last_connected = datetime.datetime.utcnow()
        db.session.commit()
