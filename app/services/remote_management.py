"""
Remote Management Service for controlling client systems.
Provides desktop streaming, file management, and system monitoring.
"""

import os
import io
import base64
import json
import time
import uuid
import logging
import threading
from datetime import datetime
from flask import request
from flask_socketio import emit, join_room, leave_room
from app import socketio, db

logger = logging.getLogger(__name__)

class RemoteManagementService:
    """Service for managing remote client connections and capabilities."""
    
    def __init__(self):
        self.active_clients = {}  # Dictionary of active client connections
        self.streaming_sessions = {}  # Active desktop streaming sessions
        self.file_transfer_sessions = {}  # Active file transfer sessions
        self.command_responses = {}  # Store command responses from clients
        
        # Register socket event handlers
        self._register_socket_handlers()
    
    def _register_socket_handlers(self):
        """Register all socket.io event handlers."""
        # Client registration and heartbeat
        socketio.on_event('client_register', self.handle_client_register)
        socketio.on_event('client_heartbeat', self.handle_client_heartbeat)
        socketio.on_event('client_disconnect', self.handle_client_disconnect)
        
        # Desktop streaming
        socketio.on_event('screen_frame', self.handle_screen_frame)
        socketio.on_event('stream_started', self.handle_stream_started)
        socketio.on_event('stream_stopped', self.handle_stream_stopped)
        
        # File management
        socketio.on_event('file_list', self.handle_file_list)
        socketio.on_event('file_upload_chunk', self.handle_file_upload_chunk)
        socketio.on_event('file_download_request', self.handle_file_download_request())
        socketio.on_event('file_download_chunk', self.handle_file_download_chunk)
        socketio.on_event('file_operation_result', self.handle_file_operation_result)
        
        # Command execution
        socketio.on_event('command_result', self.handle_command_result)
        socketio.on_event('system_info', self.handle_system_info)
    
    def handle_client_register(self, data):
        """Handle client registration."""
        try:
            client_id = data.get('client_id')
            if not client_id:
                client_id = str(uuid.uuid4())
            
            hostname = data.get('hostname', 'Unknown')
            platform = data.get('platform', 'Unknown')
            username = data.get('username', 'Unknown')
            ip_address = data.get('ip_address', request.remote_addr)
            
            # Store client information
            self.active_clients[client_id] = {
                'client_id': client_id,
                'hostname': hostname,
                'platform': platform,
                'username': username,
                'ip_address': ip_address,
                'socket_id': request.sid,
                'connected_at': datetime.now(),
                'last_heartbeat': datetime.now(),
                'capabilities': data.get('capabilities', []),
                'status': 'online'
            }
            
            # Join a room with the client ID for direct communication
            join_room(client_id)
            
            logger.info(f"Client registered: {hostname} ({client_id})")
            
            # Acknowledge registration
            emit('registration_ack', {
                'success': True,
                'client_id': client_id,
                'message': 'Registration successful'
            })
            
            # Notify all admin users about the new client
            socketio.emit('client_connected', {
                'client_id': client_id,
                'hostname': hostname,
                'platform': platform,
                'username': username,
                'ip_address': ip_address,
                'connected_at': datetime.now().isoformat(),
                'capabilities': data.get('capabilities', [])
            }, room='admin_room')
            
        except Exception as e:
            logger.error(f"Error registering client: {e}")
            emit('registration_ack', {
                'success': False,
                'message': f"Registration error: {str(e)}"
            })
    
    def handle_client_heartbeat(self, data):
        """Handle client heartbeat to keep connection alive."""
        client_id = data.get('client_id')
        if client_id in self.active_clients:
            self.active_clients[client_id]['last_heartbeat'] = datetime.now()
            self.active_clients[client_id]['status'] = 'online'
            
            # Update system metrics if provided
            if 'system_metrics' in data:
                self.active_clients[client_id]['system_metrics'] = data['system_metrics']
    
    def handle_client_disconnect(self, data):
        """Handle client disconnect notification."""
        client_id = data.get('client_id')
        if client_id in self.active_clients:
            # Stop any active streams
            if client_id in self.streaming_sessions:
                self.stop_streaming(client_id)
            
            # Clean up any file transfers
            if client_id in self.file_transfer_sessions:
                del self.file_transfer_sessions[client_id]
            
            # Update client status
            self.active_clients[client_id]['status'] = 'offline'
            
            # Notify admin users
            socketio.emit('client_disconnected', {
                'client_id': client_id,
                'hostname': self.active_clients[client_id]['hostname'],
                'disconnected_at': datetime.now().isoformat()
            }, room='admin_room')
            
            # Remove client after a delay (to keep history)
            def remove_client():
                if client_id in self.active_clients:
                    del self.active_clients[client_id]
            
            threading.Timer(300, remove_client).start()  # Remove after 5 minutes
    
    # === Desktop Streaming Methods ===
    
    def start_streaming(self, client_id, quality=75, fps=10):
        """Request a client to start streaming its desktop."""
        if client_id not in self.active_clients:
            return False, "Client not found"
        
        if self.active_clients[client_id]['status'] != 'online':
            return False, "Client is offline"
        
        # Check if streaming is already active
        if client_id in self.streaming_sessions:
            return False, "Streaming already active for this client"
        
        # Create streaming session
        session_id = str(uuid.uuid4())
        self.streaming_sessions[client_id] = {
            'session_id': session_id,
            'started_at': datetime.now(),
            'quality': quality,
            'fps': fps,
            'frames_received': 0,
            'viewers': set()
        }
        
        # Request client to start streaming
        socketio.emit('start_streaming', {
            'session_id': session_id,
            'quality': quality,
            'fps': fps
        }, room=client_id)
        
        logger.info(f"Requested screen streaming from {client_id} with session {session_id}")
        return True, session_id
    
    def stop_streaming(self, client_id):
        """Request a client to stop streaming its desktop."""
        if client_id not in self.active_clients:
            return False, "Client not found"
        
        if client_id not in self.streaming_sessions:
            return False, "No active streaming session"
        
        session_id = self.streaming_sessions[client_id]['session_id']
        
        # Request client to stop streaming
        socketio.emit('stop_streaming', {
            'session_id': session_id
        }, room=client_id)
        
        # Clean up streaming session
        del self.streaming_sessions[client_id]
        
        logger.info(f"Stopped screen streaming from {client_id}")
        return True, "Streaming stopped"
    
    def add_stream_viewer(self, client_id, user_id):
        """Add a user as a viewer of a client's stream."""
        if client_id not in self.streaming_sessions:
            return False, "No active streaming session"
        
        self.streaming_sessions[client_id]['viewers'].add(user_id)
        return True, "Viewer added"
    
    def remove_stream_viewer(self, client_id, user_id):
        """Remove a user as a viewer of a client's stream."""
        if client_id not in self.streaming_sessions:
            return False, "No active streaming session"
        
        if user_id in self.streaming_sessions[client_id]['viewers']:
            self.streaming_sessions[client_id]['viewers'].remove(user_id)
        
        # If no more viewers, stop the stream
        if not self.streaming_sessions[client_id]['viewers']:
            self.stop_streaming(client_id)
        
        return True, "Viewer removed"
    
    def handle_screen_frame(self, data):
        """Handle incoming screen frame from client."""
        client_id = data.get('client_id')
        session_id = data.get('session_id')
        frame_data = data.get('frame')
        
        if client_id not in self.streaming_sessions:
            # Streaming was stopped on server side
            socketio.emit('stop_streaming', {'session_id': session_id}, room=client_id)
            return
        
        if self.streaming_sessions[client_id]['session_id'] != session_id:
            # Session ID mismatch
            return
        
        # Update frame counter
        self.streaming_sessions[client_id]['frames_received'] += 1
        
        # Forward frame to all viewers
        for user_id in self.streaming_sessions[client_id]['viewers']:
            socketio.emit('screen_frame', {
                'client_id': client_id,
                'frame': frame_data,
                'timestamp': datetime.now().isoformat()
            }, room=f"user_{user_id}")
    
    def handle_stream_started(self, data):
        """Handle notification that streaming has started."""
        client_id = data.get('client_id')
        session_id = data.get('session_id')
        
        if client_id in self.streaming_sessions and self.streaming_sessions[client_id]['session_id'] == session_id:
            # Notify all viewers that streaming has started
            for user_id in self.streaming_sessions[client_id]['viewers']:
                socketio.emit('stream_started', {
                    'client_id': client_id,
                    'session_id': session_id,
                    'resolution': data.get('resolution'),
                    'fps': data.get('fps')
                }, room=f"user_{user_id}")
    
    def handle_stream_stopped(self, data):
        """Handle notification that streaming has stopped."""
        client_id = data.get('client_id')
        session_id = data.get('session_id')
        
        if client_id in self.streaming_sessions and self.streaming_sessions[client_id]['session_id'] == session_id:
            # Notify all viewers that streaming has stopped
            for user_id in self.streaming_sessions[client_id]['viewers']:
                socketio.emit('stream_stopped', {
                    'client_id': client_id,
                    'session_id': session_id,
                    'reason': data.get('reason', 'Client stopped streaming')
                }, room=f"user_{user_id}")
            
            # Clean up streaming session
            del self.streaming_sessions[client_id]
    
    # === File Management Methods ===
    
    def request_file_listing(self, client_id, path=None):
        """Request a directory listing from a client."""
        if client_id not in self.active_clients:
            return False, "Client not found"
        
        if self.active_clients[client_id]['status'] != 'online':
            return False, "Client is offline"
        
        request_id = str(uuid.uuid4())
        
        # Request file listing
        socketio.emit('request_file_list', {
            'request_id': request_id,
            'path': path or '/'
        }, room=client_id)
        
        logger.info(f"Requested file listing from {client_id} for path: {path or '/'}")
        return True, request_id
    
    def handle_file_list(self, data):
        """Handle file listing response from client."""
        client_id = data.get('client_id')
        request_id = data.get('request_id')
        path = data.get('path')
        files = data.get('files', [])
        error = data.get('error')
        
        # Forward to admin user who requested it
        socketio.emit('file_list_result', {
            'client_id': client_id,
            'request_id': request_id,
            'path': path,
            'files': files,
            'error': error,
            'timestamp': datetime.now().isoformat()
        }, room=f"request_{request_id}")
    
    def start_file_upload(self, client_id, source_path, dest_path):
        """Start uploading a file to a client."""
        if client_id not in self.active_clients:
            return False, "Client not found"
        
        if self.active_clients[client_id]['status'] != 'online':
            return False, "Client is offline"
        
        if not os.path.exists(source_path):
            return False, "Source file not found"
        
        # Create file transfer session
        transfer_id = str(uuid.uuid4())
        file_size = os.path.getsize(source_path)
        
        self.file_transfer_sessions[transfer_id] = {
            'client_id': client_id,
            'type': 'upload',
            'source_path': source_path,
            'dest_path': dest_path,
            'file_size': file_size,
            'bytes_transferred': 0,
            'chunk_size': 1024 * 1024,  # 1MB chunks
            'status': 'starting',
            'started_at': datetime.now()
        }
        
        # Notify client about upcoming file
        socketio.emit('file_upload_start', {
            'transfer_id': transfer_id,
            'filename': os.path.basename(source_path),
            'dest_path': dest_path,
            'file_size': file_size,
            'chunk_size': self.file_transfer_sessions[transfer_id]['chunk_size']
        }, room=client_id)
        
        logger.info(f"Starting file upload to {client_id}: {source_path} -> {dest_path}")
        return True, transfer_id
    
    def handle_file_upload_chunk(self, data):
        """Handle file upload chunk request from client."""
        transfer_id = data.get('transfer_id')
        offset = data.get('offset', 0)
        
        if transfer_id not in self.file_transfer_sessions:
            socketio.emit('file_upload_error', {
                'transfer_id': transfer_id,
                'error': 'Transfer session not found'
            }, room=data.get('client_id'))
            return
        
        transfer = self.file_transfer_sessions[transfer_id]
        
        # Read chunk from file
        try:
            with open(transfer['source_path'], 'rb') as f:
                f.seek(offset)
                chunk = f.read(transfer['chunk_size'])
            
            # Encode chunk as base64
            chunk_b64 = base64.b64encode(chunk).decode('utf-8')
            
            # Update transfer status
            transfer['bytes_transferred'] = offset + len(chunk)
            transfer['status'] = 'in_progress'
            
            # Check if this is the last chunk
            is_last = transfer['bytes_transferred'] >= transfer['file_size']
            
            # Send chunk to client
            socketio.emit('file_upload_chunk', {
                'transfer_id': transfer_id,
                'offset': offset,
                'chunk': chunk_b64,
                'is_last': is_last
            }, room=transfer['client_id'])
            
            # If this was the last chunk, update status
            if is_last:
                transfer['status'] = 'completed'
                transfer['completed_at'] = datetime.now()
                
                # Clean up after a delay
                def cleanup_transfer():
                    if transfer_id in self.file_transfer_sessions:
                        del self.file_transfer_sessions[transfer_id]
                
                threading.Timer(300, cleanup_transfer).start()  # Clean up after 5 minutes
                
                logger.info(f"File upload completed: {transfer['source_path']} -> {transfer['dest_path']}")
            
        except Exception as e:
            logger.error(f"Error during file upload: {e}")
            socketio.emit('file_upload_error', {
                'transfer_id': transfer_id,
                'error': str(e)
            }, room=transfer['client_id'])
            
            # Mark transfer as failed
            transfer['status'] = 'failed'
            transfer['error'] = str(e)
    
    def request_file_download(self, client_id, remote_path, local_path):
        """Request to download a file from a client."""
        if client_id not in self.active_clients:
            return False, "Client not found"
        
        if self.active_clients[client_id]['status'] != 'online':
            return False, "Client is offline"
        
        # Create file transfer session
        transfer_id = str(uuid.uuid4())
        
        self.file_transfer_sessions[transfer_id] = {
            'client_id': client_id,
            'type': 'download',
            'remote_path': remote_path,
            'local_path': local_path,
            'file_size': 0,  # Will be set when client responds
            'bytes_transferred': 0,
            'chunk_size': 1024 * 1024,  # 1MB chunks
            'status': 'starting',
            'started_at': datetime.now(),
            'chunks': []  # Store chunks until complete
        }
        
        # Request file from client
        socketio.emit('file_download_request', {
            'transfer_id': transfer_id,
            'path': remote_path,
            'chunk_size': self.file_transfer_sessions[transfer_id]['chunk_size']
        }, room=client_id)
        
        logger.info(f"Requested file download from {client_id}: {remote_path}")
        return True, transfer_id
    
    def handle_file_download_chunk(self, data):
        """Handle file chunk sent by client during download."""
        transfer_id = data.get('transfer_id')
        chunk_b64 = data.get('chunk')
        offset = data.get('offset', 0)
        is_last = data.get('is_last', False)
        file_size = data.get('file_size', 0)
        
        if transfer_id not in self.file_transfer_sessions:
            return
        
        transfer = self.file_transfer_sessions[transfer_id]
        
        # Update file size if this is the first chunk
        if offset == 0:
            transfer['file_size'] = file_size
        
        # Decode chunk
        chunk = base64.b64decode(chunk_b64)
        
        # Store chunk
        transfer['chunks'].append((offset, chunk))
        transfer['bytes_transferred'] += len(chunk)
        transfer['status'] = 'in_progress'
        
        # Notify admin about progress
        progress = (transfer['bytes_transferred'] / transfer['file_size']) * 100 if transfer['file_size'] > 0 else 0
        socketio.emit('file_download_progress', {
            'transfer_id': transfer_id,
            'client_id': transfer['client_id'],
            'bytes_transferred': transfer['bytes_transferred'],
            'file_size': transfer['file_size'],
            'progress': progress
        }, room=f"user_{data.get('user_id')}")
        
        # If this is the last chunk, save the complete file
        if is_last:
            try:
                # Sort chunks by offset
                transfer['chunks'].sort(key=lambda x: x[0])
                
                # Create directory if it doesn't exist
                os.makedirs(os.path.dirname(transfer['local_path']), exist_ok=True)
                
                # Write file
                with open(transfer['local_path'], 'wb') as f:
                    for _, chunk_data in transfer['chunks']:
                        f.write(chunk_data)
                
                # Update transfer status
                transfer['status'] = 'completed'
                transfer['completed_at'] = datetime.now()
                
                # Notify admin
                socketio.emit('file_download_complete', {
                    'transfer_id': transfer_id,
                    'client_id': transfer['client_id'],
                    'local_path': transfer['local_path'],
                    'file_size': transfer['file_size']
                }, room=f"user_{data.get('user_id')}")
                
                logger.info(f"File download completed: {transfer['remote_path']} -> {transfer['local_path']}")
                
                # Clean up after a delay
                def cleanup_transfer():
                    if transfer_id in self.file_transfer_sessions:
                        del self.file_transfer_sessions[transfer_id]
                
                threading.Timer(300, cleanup_transfer).start()  # Clean up after 5 minutes
                
            except Exception as e:
                logger.error(f"Error saving downloaded file: {e}")
                transfer['status'] = 'failed'
                transfer['error'] = str(e)
                
                socketio.emit('file_download_error', {
                    'transfer_id': transfer_id,
                    'client_id': transfer['client_id'],
                    'error': str(e)
                }, room=f"user_{data.get('user_id')}")
    
    def handle_file_operation_result(self, data):
        """Handle result of file operations (delete, rename, etc.)."""
        client_id = data.get('client_id')
        operation = data.get('operation')
        success = data.get('success', False)
        error = data.get('error')
        path = data.get('path')
        
        # Forward to admin user who requested it
        socketio.emit('file_operation_result', {
            'client_id': client_id,
            'operation': operation,
            'success': success,
            'error': error,
            'path': path,
            'timestamp': datetime.now().isoformat()
        }, room=f"user_{data.get('user_id')}")
    
    # === Command Execution Methods ===
    
    def execute_command(self, client_id, command, user_id):
        """Execute a command on a remote client."""
        if client_id not in self.active_clients:
            return False, "Client not found"
        
        if self.active_clients[client_id]['status'] != 'online':
            return False, "Client is offline"
        
        command_id = str(uuid.uuid4())
        
        # Create a room for this specific command response
        join_room(f"cmd_{command_id}")
        
        # Send command to client
        socketio.emit('execute_command', {
            'command_id': command_id,
            'command': command,
            'user_id': user_id
        }, room=client_id)
        
        logger.info(f"Sent command to {client_id}: {command}")
        return True, command_id
    
    def handle_command_result(self, data):
        """Handle command execution result from client."""
        client_id = data.get('client_id')
        command_id = data.get('command_id')
        output = data.get('output')
        error = data.get('error')
        exit_code = data.get('exit_code')
        
        # Store command response
        self.command_responses[command_id] = {
            'client_id': client_id,
            'output': output,
            'error': error,
            'exit_code': exit_code,
            'timestamp': datetime.now()
        }
        
        # Forward to user who requested it
        socketio.emit('command_result', {
            'command_id': command_id,
            'client_id': client_id,
            'output': output,
            'error': error,
            'exit_code': exit_code,
            'timestamp': datetime.now().isoformat()
        }, room=f"cmd_{command_id}")
    
    def handle_system_info(self, data):
        """Handle system information from client."""
        client_id = data.get('client_id')
        
        if client_id in self.active_clients:
            # Update client system info
            self.active_clients[client_id]['system_info'] = data.get('system_info', {})
            
            # Forward to admin users
            socketio.emit('client_system_info', {
                'client_id': client_id,
                'system_info': data.get('system_info', {}),
                'timestamp': datetime.now().isoformat()
            }, room='admin_room')
    
    # === Client Management Methods ===
    
    def get_active_clients(self):
        """Get list of active clients."""
        clients = []
        for client_id, client in self.active_clients.items():
            clients.append({
                'client_id': client_id,
                'hostname': client['hostname'],
                'platform': client['platform'],
                'username': client['username'],
                'ip_address': client['ip_address'],
                'connected_at': client['connected_at'].isoformat(),
                'last_heartbeat': client['last_heartbeat'].isoformat(),
                'status': client['status'],
                'capabilities': client['capabilities']
            })
        return clients
    
    def get_client_info(self, client_id):
        """Get detailed information about a specific client."""
        if client_id not in self.active_clients:
            return None
        
        client = self.active_clients[client_id]
        return {
            'client_id': client_id,
            'hostname': client['hostname'],
            'platform': client['platform'],
            'username': client['username'],
            'ip_address': client['ip_address'],
            'connected_at': client['connected_at'].isoformat(),
            'last_heartbeat': client['last_heartbeat'].isoformat(),
            'status': client['status'],
            'capabilities': client['capabilities'],
            'system_info': client.get('system_info', {}),
            'system_metrics': client.get('system_metrics', {})
        }
    
    def check_clients_status(self):
        """Check status of all clients and mark inactive ones as offline."""
        now = datetime.now()
        for client_id, client in list(self.active_clients.items()):
            # If last heartbeat was more than 30 seconds ago, mark as offline
            if (now - client['last_heartbeat']).total_seconds() > 30 and client['status'] == 'online':
                client['status'] = 'offline'
                
                # Notify admin users
                socketio.emit('client_disconnected', {
                    'client_id': client_id,
                    'hostname': client['hostname'],
                    'disconnected_at': now.isoformat()
                }, room='admin_room')

# Create a singleton instance
remote_manager = RemoteManagementService()
