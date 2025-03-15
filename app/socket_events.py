"""WebSocket event handlers for the application."""

from flask import request
from flask_socketio import emit
from flask_login import current_user
from app import socketio
from app.refresh_manager import refresh_manager

@socketio.on('connect')
def handle_connect():
    """Handle client connection."""
    print(f"Client connected: {request.sid}")
    
    # Emit initial data
    if current_user.is_authenticated:
        refresh_manager.refresh_system_stats()
        refresh_manager.refresh_active_sessions()

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection."""
    print(f"Client disconnected: {request.sid}")

@socketio.on('request_refresh')
def handle_request_refresh(data):
    """Handle client request for data refresh."""
    if not current_user.is_authenticated:
        return
    
    refresh_type = data.get('type', 'all')
    
    if refresh_type == 'system_stats' or refresh_type == 'all':
        refresh_manager.refresh_system_stats()
    
    if refresh_type == 'active_sessions' or refresh_type == 'all':
        refresh_manager.refresh_active_sessions()
    
    if refresh_type == 'connections' or refresh_type == 'all':
        refresh_manager.refresh_connections()
    
    emit('refresh_acknowledged', {
        'success': True,
        'refresh_type': refresh_type,
        'message': f'Refresh of {refresh_type} initiated'
    })

@socketio.on('set_refresh_interval')
def handle_set_refresh_interval(data):
    """Handle client request to change refresh interval."""
    if not current_user.is_authenticated:
        return
    
    refresh_type = data.get('type')
    interval = data.get('interval')
    
    if not refresh_type or not interval:
        emit('refresh_interval_error', {
            'success': False,
            'message': 'Missing type or interval'
        })
        return
    
    try:
        interval = int(interval)
        
        # Convert from milliseconds to seconds for server-side scheduler
        interval_seconds = max(5, interval / 1000)  # Minimum 5 seconds
        
        if refresh_type == 'system_stats':
            refresh_manager.add_refresh_job('system_stats', 
                                          refresh_manager.refresh_system_stats, 
                                          seconds=interval_seconds)
        
        elif refresh_type == 'active_sessions':
            refresh_manager.add_refresh_job('active_sessions', 
                                          refresh_manager.refresh_active_sessions, 
                                          seconds=interval_seconds)
        
        emit('refresh_interval_updated', {
            'success': True,
            'refresh_type': refresh_type,
            'interval': interval,
            'message': f'Refresh interval for {refresh_type} updated to {interval_seconds} seconds'
        })
        
    except Exception as e:
        emit('refresh_interval_error', {
            'success': False,
            'message': f'Error: {str(e)}'
        })