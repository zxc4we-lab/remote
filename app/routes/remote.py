from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db, socketio
from app.models.connection import Connection
from app.services.client_manager import ClientManager
from app.services.remote_service import connection_manager
from app.services.remote_management import remote_manager
import datetime
import json
import logging

# Set up logger
logger = logging.getLogger(__name__)

# Create blueprint
remote_bp = Blueprint('remote', __name__, url_prefix='/remote')

# Create client manager instance
client_manager = ClientManager()
 
# Dictionary to track connected sockets by session ID
active_sockets = {}

# ===== Regular Routes =====

@remote_bp.route('/connections')
@login_required
def connections():
    """Display all saved connections for the current user."""
    user_connections = client_manager.get_user_connections(current_user.id)
    return render_template('remote/connections.html', connections=user_connections)

@remote_bp.route('/new-connection', methods=['GET', 'POST'])
@login_required
def new_connection():
    """Create a new connection."""
    if request.method == 'POST':
        connection_data = {
            'hostname': request.form.get('hostname'),
            'ip_address': request.form.get('ip_address'),
            'port': int(request.form.get('port', 22)),
            'connection_type': request.form.get('connection_type', 'ssh'),
            'description': request.form.get('description', '')
        }
        
        connection = client_manager.create_connection(connection_data, current_user.id)
        
        flash('Connection saved successfully', 'success')
        return redirect(url_for('remote.connections'))
        
    return render_template('remote/new_connection.html')

@remote_bp.route('/edit-connection/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_connection(id):
    """Edit an existing connection."""
    connection = client_manager.get_connection_by_id(id, current_user.id)
    
    if connection is None:
        flash('Connection not found', 'danger')
        return redirect(url_for('remote.connections'))
    
    if request.method == 'POST':
        connection_data = {
            'hostname': request.form.get('hostname'),
            'ip_address': request.form.get('ip_address'),
            'port': int(request.form.get('port', 22)),
            'connection_type': request.form.get('connection_type', 'ssh'),
            'description': request.form.get('description', '')
        }
        
        updated_connection = client_manager.update_connection(id, connection_data, current_user.id)
        
        flash('Connection updated successfully', 'success')
        return redirect(url_for('remote.connections'))
    
    return render_template('remote/edit_connection.html', connection=connection)

@remote_bp.route('/delete-connection/<int:id>', methods=['POST'])
@login_required
def delete_connection(id):
    """Delete a connection."""
    success = client_manager.delete_connection(id, current_user.id)
    
    if success:
        flash('Connection deleted successfully', 'success')
    else:
        flash('Failed to delete connection', 'danger')
    
    return redirect(url_for('remote.connections'))

@remote_bp.route('/connect/<int:id>')
@login_required
def connect(id):
    """Connect to a remote server."""
    # Security check - ensure user owns this connection
    connection = client_manager.get_connection_by_id(id, current_user.id)
    if connection is None:
        flash('You do not have permission to access this connection', 'danger')
        return redirect(url_for('remote.connections'))
    
    # Establish the connection
    session_id = client_manager.establish_client_connection(id, current_user.id)
    
    if session_id is None:
        flash('Failed to establish connection', 'danger')
        return redirect(url_for('remote.connections'))
    
    return render_template('remote/terminal.html', 
                          connection=connection, 
                          session_id=session_id,
                          now=datetime.datetime.now())

@remote_bp.route('/sessions')
@login_required
def sessions():
    """Display active sessions for the current user."""
    active_sessions = client_manager.get_user_active_sessions(current_user.id)
    system_stats = client_manager.get_system_stats()
    
    return render_template('remote/sessions.html', 
                          sessions=active_sessions,
                          system_stats=system_stats)

@remote_bp.route('/disconnect/<session_id>', methods=['POST'])
@login_required
def disconnect(session_id):
    """Disconnect a session."""
    # Check if this session belongs to the current user
    session_info = connection_manager.get_session_info(session_id)
    
    if session_info is None:
        flash('Session not found', 'danger')
        return redirect(url_for('remote.sessions'))
    
    if session_info['user_id'] != current_user.id and not current_user.is_admin:
        flash('You do not have permission to disconnect this session', 'danger')
        return redirect(url_for('remote.sessions'))
    
    # Disconnect the session
    success = client_manager.close_client_connection(session_id)
    
    if success:
        # Notify the socket to disconnect
        socketio.emit('force_disconnect', room=session_id)
        flash('Session disconnected successfully', 'success')
    else:
        flash('Failed to disconnect session', 'danger')
    
    return redirect(url_for('remote.sessions'))

# ===== API Routes =====

@remote_bp.route('/api/connections', methods=['GET'])
@login_required
def api_connections():
    """API endpoint to get connections."""
    connections = client_manager.get_user_connections(current_user.id)
    
    connections_data = []
    for conn in connections:
        connections_data.append({
            'id': conn.id,
            'hostname': conn.hostname,
            'ip_address': conn.ip_address,
            'port': conn.port,
            'connection_type': conn.connection_type,
            'description': conn.description,
            'last_connected': conn.last_connected.isoformat() if conn.last_connected else None
        })
    
    return jsonify({
        'success': True,
        'connections': connections_data
    })

@remote_bp.route('/api/sessions', methods=['GET'])
@login_required
def api_sessions():
    """API endpoint to get active sessions."""
    sessions = client_manager.get_user_active_sessions(current_user.id)
    
    return jsonify({
        'success': True,
        'sessions': sessions
    })

# === Helper Functions ===

def get_connection_stats():
    """Get statistics about connections."""
    total_connections = Connection.query.count()
    active_sessions_count = len(connection_manager.get_active_sessions())
    
    return {
        'total_connections': total_connections,
        'active_sessions': active_sessions_count
    }