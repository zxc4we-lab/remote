"""Client manager service for handling client connections and status."""

from venv import logger
from app.services.remote_service import RemoteConnectionManager
from app.models.connection import Connection
from app.models.user import User
from app import db
import datetime
import psutil

class ClientManager:
    """
    Class to manage client connections, status, and associated data.
    Provides an interface between the application and the remote connection manager.
    """
    
    def __init__(self):
        self.connection_manager = RemoteConnectionManager()
    
    def get_user_connections(self, user_id):
        """
        Get all connections for a specific user.
        
        Args:
            user_id: The user ID to get connections for
            
        Returns:
            list: List of Connection objects
        """
        return Connection.query.filter_by(user_id=user_id).all()
    
    def get_user_recent_connections(self, user_id, limit=5):
        """
        Get recent connections for a specific user.
        
        Args:
            user_id: The user ID to get connections for
            limit: Maximum number of connections to return
            
        Returns:
            list: List of Connection objects
        """
        return Connection.query.filter_by(user_id=user_id).order_by(
            Connection.last_connected.desc().nullslast()
        ).limit(limit).all()
    
    def get_connection_by_id(self, connection_id, user_id=None):
        """
        Get a connection by its ID, optionally filtering by owner.
        
        Args:
            connection_id: The connection ID to retrieve
            user_id: Optional user ID to verify ownership
            
        Returns:
            Connection: The connection object or None
        """
        query = Connection.query.filter_by(id=connection_id)
        if user_id is not None:
            query = query.filter_by(user_id=user_id)
        
        return query.first()
    
    def create_connection(self, connection_data, user_id):
        """
        Create a new connection.
        
        Args:
            connection_data: Dictionary with connection details
            user_id: The user ID that will own this connection
            
        Returns:
            Connection: The newly created connection
        """
        connection = Connection(
            hostname=connection_data.get('hostname'),
            ip_address=connection_data.get('ip_address'),
            port=connection_data.get('port', 22),
            connection_type=connection_data.get('connection_type', 'ssh'),
            description=connection_data.get('description', ''),
            user_id=user_id
        )
        
        db.session.add(connection)
        db.session.commit()
        return connection
    
    def update_connection(self, connection_id, connection_data, user_id=None):
        """
        Update an existing connection.
        
        Args:
            connection_id: The connection ID to update
            connection_data: Dictionary with updated connection details
            user_id: Optional user ID to verify ownership
            
        Returns:
            Connection: The updated connection or None if not found
        """
        connection = self.get_connection_by_id(connection_id, user_id)
        if connection is None:
            return None
        
        # Update fields
        if 'hostname' in connection_data:
            connection.hostname = connection_data['hostname']
        if 'ip_address' in connection_data:
            connection.ip_address = connection_data['ip_address']
        if 'port' in connection_data:
            connection.port = connection_data['port']
        if 'connection_type' in connection_data:
            connection.connection_type = connection_data['connection_type']
        if 'description' in connection_data:
            connection.description = connection_data['description']
        
        db.session.commit()
        return connection
    
    def delete_connection(self, connection_id, user_id=None):
        """
        Delete a connection.
        
        Args:
            connection_id: The connection ID to delete
            user_id: Optional user ID to verify ownership
            
        Returns:
            bool: True if successful, False otherwise
        """
        connection = self.get_connection_by_id(connection_id, user_id)
        if connection is None:
            return False
        
        db.session.delete(connection)
        db.session.commit()
        return True
    
    def establish_client_connection(self, connection_id, user_id):
        """
        Establish a connection to a remote client.
        
        Args:
            connection_id: The ID of the connection to establish
            user_id: The user ID requesting the connection
            
        Returns:
            str: Session ID or None if failed
        """
        connection = self.get_connection_by_id(connection_id, user_id)
        if connection is None:
            return None
        
        # Update the last connected timestamp
        connection.last_connected = datetime.datetime.utcnow()
        db.session.commit()
        
        # Use the connection manager to establish the actual connection
        return self.connection_manager.establish_connection(connection)
    
    def close_client_connection(self, session_id):
        """
        Close a client connection.
        
        Args:
            session_id: The session ID to close
            
        Returns:
            bool: True if successful, False otherwise
        """
        return self.connection_manager.close_connection(session_id)
    
    def get_user_active_sessions(self, user_id):
        """
        Get active sessions for a specific user.
        
        Args:
            user_id: The user ID to get sessions for
            
        Returns:
            list: List of active session information
        """
        return self.connection_manager.get_active_sessions(user_id)
    
    def count_user_active_sessions(self, user_id):
        """
        Count active sessions for a specific user.
        
        Args:
            user_id: The user ID to count sessions for
            
        Returns:
            int: Number of active sessions
        """
        return self.connection_manager.count_active_sessions(user_id)
    
    def get_user_connection_time(self, user_id):
        """
        Get total connection time for a specific user.
        
        Args:
            user_id: The user ID to get connection time for
            
        Returns:
            str: Formatted connection time (e.g., "2h 15m")
        """
        total_seconds = self.connection_manager.get_total_connection_time(user_id)
        
        # Format as hours and minutes
        hours = int(total_seconds // 3600)
        minutes = int((total_seconds % 3600) // 60)
        
        if hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"
    
    def get_system_stats(self):
        """
        Get system statistics for display in the dashboard.
        
        Returns:
            dict: System statistics
        """
        # In a real implementation, this would get actual system stats
        # For now, we'll return mock data
        return {
            'system_load': 45,  # percentage
            'memory_usage': 62,  # percentage
            'network_status': 'online'
        }
    
    def get_connection_count(self, user_id=None):
        """
        Count total connections, optionally filtered by user ID.
        
        Args:
            user_id: Optional user ID to filter connections by
            
        Returns:
            int: Number of connections
        """
        query = Connection.query
        if user_id is not None:
            query = query.filter_by(user_id=user_id)
        

        return query.count()
    
    def get_active_direct_connections(self):
        """
        Get all active direct connections (clients connecting without authentication).
        
        Returns:
            list: List of direct connection information
        """
        active_sessions = self.connection_manager.get_active_sessions()
        direct_connections = []
        
        for session in active_sessions:
            if session.get('connection_type') == 'direct':
                # Add some additional formatting for display
                connected_since = datetime.datetime.fromtimestamp(session.get('last_activity', 0))
                time_connected = datetime.datetime.now() - connected_since
                
                hours, remainder = divmod(int(time_connected.total_seconds()), 3600)
                minutes, seconds = divmod(remainder, 60)
                
                if hours > 0:
                    duration = f"{hours}h {minutes}m {seconds}s"
                else:
                    duration = f"{minutes}m {seconds}s"
                
                direct_connections.append({
                    'session_id': session.get('session_id'),
                    'ip_address': session.get('host'),
                    'connected_since': connected_since.strftime('%Y-%m-%d %H:%M:%S'),
                    'duration': duration,
                    'data_transferred': session.get('data_transferred', 0)
                })
        
        return direct_connections
    
    def get_system_stats(self):
        """
        Get system statistics for display in the dashboard.
        
        Returns:
            dict: System statistics
        """
        # In a real implementation, this would get actual system stats
        # For now, we'll return mock data
        try:
            
            cpu_percent = psutil.cpu_percent(interval=0.5)
            memory_percent = psutil.virtual_memory().percent
            disk_percent = psutil.disk_usage('/').percent
            network_status = 'Online'
            
            return {
                'system_load': round(cpu_percent),
                'memory_usage': round(memory_percent),
                'disk_usage': round(disk_percent),
                'network_status': network_status
            }
        except ImportError:
            # Fallback to mock data if psutil is not installed
            return {
                'system_load': 45,  # percentage
                'memory_usage': 62,  # percentage
                'disk_usage': 58,    # percentage
                'network_status': 'Online'
            }
    def get_active_user_ids(self):
        """
        Get IDs of users with active connections.
        
        Returns:
            list: List of user IDs with active connections
        """
        try:
            active_sessions = self.connection_manager.get_active_sessions()
            user_ids = set()
            
            for session in active_sessions:
                user_id = session.get('user_id')
                if user_id and user_id > 0:  # Ignore direct connections with user_id=0
                    user_ids.add(user_id)
            
            return list(user_ids)
        except Exception as e:
            logger.error(f"Error getting active user IDs: {e}")
            return []

# Create a singleton instance
client_manager = ClientManager()
