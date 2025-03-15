"""
Server-side refresh manager for handling data updates and broadcasting.
"""

import time
import logging
import threading
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from flask_socketio import SocketIO

logger = logging.getLogger(__name__)

class RefreshManager:
    """Server-side manager for data refresh operations."""
    
    def __init__(self, app=None, socketio=None):
        self.app = app
        self.socketio = socketio
        self.scheduler = BackgroundScheduler()
        self.refresh_jobs = {}
        self.client_manager = None
        
        # Initialize if app is provided
        if app is not None:
            self.init_app(app, socketio)
    
    def init_app(self, app, socketio=None):
        """Initialize with Flask app and optional SocketIO."""
        self.app = app
        self.socketio = socketio
        
        # Register extension with app
        app.refresh_manager = self
        
        try:
            # Get client manager from app context
            from app.services.client_manager import client_manager
            self.client_manager = client_manager
            
            # Start the scheduler
            self.start_scheduler()
        except Exception as e:
            logger.error(f"Error initializing refresh manager: {e}")
    
    def start_scheduler(self):
        """Start the background scheduler."""
        if not self.scheduler.running:
            try:
                self.scheduler.start()
                logger.info("Background scheduler started")
                
                # Add default refresh jobs
                self.add_refresh_job('system_stats', self.refresh_system_stats, seconds=10)
                self.add_refresh_job('active_sessions', self.refresh_active_sessions, seconds=15)
            except Exception as e:
                logger.error(f"Error starting scheduler: {e}")
    
    def add_refresh_job(self, job_id, func, **trigger_args):
        """Add a job to the scheduler."""
        try:
            if job_id in self.refresh_jobs:
                self.refresh_jobs[job_id].remove()
            
            job = self.scheduler.add_job(func, 'interval', **trigger_args)
            self.refresh_jobs[job_id] = job
            logger.info(f"Added refresh job: {job_id}")
            return job
        except Exception as e:
            logger.error(f"Error adding refresh job {job_id}: {e}")
            return None
    
    def remove_refresh_job(self, job_id):
        """Remove a job from the scheduler."""
        if job_id in self.refresh_jobs:
            try:
                self.refresh_jobs[job_id].remove()
                del self.refresh_jobs[job_id]
                logger.info(f"Removed refresh job: {job_id}")
                return True
            except Exception as e:
                logger.error(f"Error removing refresh job {job_id}: {e}")
        return False
    
    def refresh_system_stats(self):
        """Refresh and broadcast system stats."""
        if not self.client_manager:
            logger.warning("Client manager not available")
            return
        
        try:
            stats = self.client_manager.get_system_stats()
            
            # Broadcast via WebSocket if available
            if self.socketio:
                self.socketio.emit('system_stats', {
                    'type': 'system_stats',
                    'timestamp': datetime.now().isoformat(),
                    'system_load': stats['system_load'],
                    'memory_usage': stats['memory_usage'],
                    'disk_usage': stats.get('disk_usage', 50),
                    'network_status': stats.get('network_status', 'Online')
                })
                
            logger.debug("System stats refreshed and broadcast")
        except Exception as e:
            logger.error(f"Error refreshing system stats: {str(e)}")
    
    def refresh_active_sessions(self):
        """Refresh and broadcast active sessions."""
        if not self.client_manager:
            logger.warning("Client manager not available")
            return
        
        try:
            # Get all active sessions
            all_sessions = []
            
            # This method might not exist - let's handle it safely
            if hasattr(self.client_manager, 'get_active_user_ids'):
                for user_id in self.client_manager.get_active_user_ids():
                    sessions = self.client_manager.get_user_active_sessions(user_id)
                    all_sessions.extend(sessions)
            else:
                # Fallback to just getting all sessions
                all_sessions = self.client_manager.get_active_direct_connections()
            
            # Broadcast via WebSocket if available
            if self.socketio and all_sessions:
                self.socketio.emit('active_sessions', {
                    'type': 'active_sessions',
                    'timestamp': datetime.now().isoformat(),
                    'count': len(all_sessions),
                    'sessions': all_sessions
                })
                
            logger.debug(f"Active sessions refreshed and broadcast: {len(all_sessions)} sessions")
        except Exception as e:
            logger.error(f"Error refreshing active sessions: {str(e)}")
    
    def shutdown(self):
        """Shutdown the refresh manager."""
        if self.scheduler.running:
            try:
                self.scheduler.shutdown()
                logger.info("Background scheduler stopped")
            except Exception as e:
                logger.error(f"Error shutting down scheduler: {e}")

# Create singleton instance
refresh_manager = RefreshManager()
