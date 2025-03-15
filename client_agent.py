#!/usr/bin/env python3
"""
Remote Access Client Agent
Connects to the remote access server and provides desktop streaming,
file management, and remote command execution.
"""

import os
import shutil
import sys
import io
import re
import ssl
import json
import time
import base64
import uuid
import socket
import logging
import argparse
import platform
import subprocess
import threading
import tempfile
from datetime import datetime
from pathlib import Path

# Third-party imports - install with pip
import socketio
import psutil
import pyautogui
import PIL.Image
import PIL.ImageGrab

# Configure logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('RemoteClient')

VERSION = "1.0.0"

class RemoteClient:
    """Client agent for remote access and management."""
    
    def __init__(self, server_url, client_id=None, verify_ssl=True):
        self.server_url = server_url
        self.client_id = client_id or str(uuid.uuid4())
        self.verify_ssl = verify_ssl
        self.socket = None
        self.connected = False
        self.streaming = False
        self.stream_thread = None
        self.file_transfers = {}
        self.stopping = False
        
        # Determine capabilities
        self.capabilities = self._detect_capabilities()
        
        # Connect to server
        self._connect()
    
    def _detect_capabilities(self):
        """Detect what capabilities this client supports."""
        capabilities = ['file_management', 'command_execution', 'system_info']
        
        # Check if we can capture screenshots
        try:
            PIL.ImageGrab.grab()
            capabilities.append('screen_capture')
        except Exception as e:
            logger.warning("Screen capture not available")
        
        return capabilities
    
    def _connect(self):
        """Connect to the remote server."""
        try:
            # Create socket.io client
            if not self.verify_ssl:
                ssl_verify = False
                engineio_logger = True
            else:
                ssl_verify = True
                engineio_logger = False
            
            self.socket = socketio.Client(ssl_verify=ssl_verify, logger=engineio_logger)
            
            # Register event handlers
            self._register_event_handlers()
            
            # Connect to server
            logger.info(f"Connecting to server at {self.server_url}")
            self.socket.connect(self.server_url)
            self.connected = True
            
            # Start heartbeat thread
            self._start_heartbeat()
            
            logger.info("Connected to server")
            
        except Exception as e:
            logger.error(f"Failed to connect to server: {e}")
            self.connected = False
    
    def _register_event_handlers(self):
        """Register all socket.io event handlers."""
        # Connection events
        self.socket.on('connect', self._on_connect)
        self.socket.on('disconnect', self._on_disconnect)
        self.socket.on('registration_ack', self._on_registration_ack)
        
        # Streaming events
        self.socket.on('start_streaming', self._on_start_streaming)
        self.socket.on('stop_streaming', self._on_stop_streaming)
        
        # File management events
        self.socket.on('request_file_list', self._on_request_file_list)
        self.socket.on('file_upload_start', self._on_file_upload_start)
        self.socket.on('file_upload_chunk', self._on_file_upload_chunk)
        self.socket.on('file_download_request', self._on_file_download_request)
        self.socket.on('file_operation', self._on_file_operation)
        
        # Command execution events
        self.socket.on('execute_command', self._on_execute_command)
        self.socket.on('request_system_info', self._on_request_system_info)
    
    def _on_connect(self):
        """Handle connection to server."""
        logger.info("Socket connected, registering client...")
        self.connected = True
        
        # Register with server
        self.socket.emit('client_register', {
            'client_id': self.client_id,
            'hostname': socket.gethostname(),
            'platform': platform.system(),
            'username': os.getlogin() if hasattr(os, 'getlogin') else 'N/A',
            'ip_address': self._get_local_ip(),
            'capabilities': self.capabilities
        })
    
    def _on_disconnect(self):
        """Handle disconnection from server."""
        logger.info("Disconnected from server")
        self.connected = False
        self.streaming = False
        if self.stream_thread:
            self.stream_thread.join()
            self.stream_thread = None
        
        # Attempt to reconnect after a delay
        if not self.stopping:
            logger.info("Attempting to reconnect in 5 seconds...")
            time.sleep(5)
            self._connect()

    def _on_registration_ack(self, data):
        """Handle registration acknowledgment from server."""
        if data.get('success'):
            logger.info(f"Registration successful. Client ID: {data.get('client_id')}")
        else:
            logger.error(f"Registration failed: {data.get('message', 'Unknown error')}")
    
    def _on_start_streaming(self, data):
        """Handle request to start streaming desktop."""
        if 'screen_capture' not in self.capabilities:
            logger.warning("Streaming requested but screen capture not supported")
            self.socket.emit('stream_stopped', {
                'client_id': self.client_id,
                'session_id': data.get('session_id'),
                'reason': 'Screen capture not supported'
            })
            return
        
        session_id = data.get('session_id')
        quality = data.get('quality', 75)
        fps = data.get('fps', 10)
        
        if not session_id:
            logger.error("Streaming request missing session ID")
            return
        
        logger.info(f"Starting screen streaming (quality={quality}, fps={fps})")
        
        # Prevent multiple streams
        if self.streaming:
            logger.warning("Streaming already in progress. Ignoring new request.")
            return
        
        self.streaming = True
        
        # Start streaming thread
        self.stream_thread = threading.Thread(target=self._stream_desktop, 
                                             args=(session_id, quality, fps),
                                             daemon=True)
        self.stream_thread.start()
    
    def _on_stop_streaming(self, data):
        """Handle request to stop streaming desktop."""
        session_id = data.get('session_id')
        
        if not session_id:
            logger.error("Stop streaming request missing session ID")
            return
        
        logger.info("Stopping screen streaming")
        self.streaming = False
        
        if self.stream_thread and self.stream_thread.is_alive():
            self.stream_thread.join() # Ensure thread is stopped
        
        self.stream_thread = None
        
        # Send confirmation
        self.socket.emit('stream_stopped', {
            'client_id': self.client_id,
            'session_id': session_id,
            'reason': 'Streaming stopped by server'
        })
    
    def _stream_desktop(self, session_id, quality, fps):
        """Stream desktop frames to the server."""
        try:
            logger.info("Starting streaming thread")
            
            while self.connected and self.streaming:
                # Capture screenshot
                try:
                    screenshot = PIL.ImageGrab.grab()
                    
                    # Encode image
                    buffer = io.BytesIO()
                    screenshot.save(buffer, format='JPEG', quality=quality)
                    frame_data = base64.b64encode(buffer.getvalue()).decode('utf-8')
                    
                    # Send frame to server
                    self.socket.emit('screen_frame', {
                        'client_id': self.client_id,
                        'session_id': session_id,
                        'frame': frame_data
                    })
                except Exception as e:
                    logger.error(f"Error capturing/encoding screenshot: {e}")
                    self.streaming = False
                    break # Break out of loop
                
                # Wait for next frame
                time.sleep(1 / fps)
            
            logger.info("Streaming thread stopped")
        except Exception as e:
            logger.error(f"Streaming thread exception: {e}")
        finally:
            # Ensure streaming flag is reset and thread is cleaned up
            self.streaming = False
            self.stream_thread = None
            
            # Notify server if streaming stopped unexpectedly
            if self.connected:
                self.socket.emit('stream_stopped', {
                    'client_id': self.client_id,
                    'session_id': session_id,
                    'reason': 'Streaming stopped unexpectedly'
                })
    
    def _on_request_file_list(self, data):
        """Handle request for file listing."""
        request_id = data.get('request_id')
        path = data.get('path')
        
        if not request_id:
            logger.error("File list request missing request ID")
            return
        
        logger.info(f"Received file list request for path: {path}")
        
        try:
            files = []
            for entry in os.scandir(path):
                file_info = {
                    'name': entry.name,
                    'path': entry.path,
                    'is_dir': entry.is_dir(),
                    'size': entry.stat().st_size if not entry.is_dir() else 0,
                    'modified': datetime.fromtimestamp(entry.stat().st_mtime).isoformat()
                }
                files.append(file_info)
            
            # Send file list to server
            self.socket.emit('file_list', {
                'client_id': self.client_id,
                'request_id': request_id,
                'path': path,
                'files': files
            })
            
            logger.info(f"Sent file list for path: {path}")
        except Exception as e:
            logger.error(f"Error getting file list for path {path}: {e}")
            self.socket.emit('file_list', {
                'client_id': self.client_id,
                'request_id': request_id,
                'path': path,
                'files': [],
                'error': str(e)
            })
    
    def _on_file_upload_start(self, data):
        """Handle notification that server wants to upload a file to client."""
        transfer_id = data.get('transfer_id')
        filename = data.get('filename')
        dest_path = data.get('dest_path')
        file_size = data.get('file_size')
        chunk_size = data.get('chunk_size')
        
        if not transfer_id or not filename or not dest_path or not file_size or not chunk_size:
            logger.error("File upload start request missing required parameters")
            return
        
        logger.info(f"Received file upload start request: {filename} -> {dest_path}")
        
        # Create a temporary file to store the incoming data
        temp_file = tempfile.NamedTemporaryFile(delete=False)
        
        # Store transfer information
        self.file_transfers[transfer_id] = {
            'filename': filename,
            'dest_path': dest_path,
            'file_size': file_size,
            'chunk_size': chunk_size,
            'temp_file_path': temp_file.name,
            'temp_file': temp_file,
            'bytes_received': 0,
            'start_time': datetime.now()
        }
        
        # Send acknowledgment
        self.socket.emit('file_upload_ack', {
            'client_id': self.client_id,
            'transfer_id': transfer_id
        })
    
    def _on_file_upload_chunk(self, data):
        """Handle incoming file chunk from server."""
        transfer_id = data.get('transfer_id')
        chunk = data.get('chunk')
        
        if not transfer_id or not chunk:
            logger.error("File upload chunk missing transfer ID or chunk data")
            return
        
        if transfer_id not in self.file_transfers:
            logger.error(f"File transfer session not found: {transfer_id}")
            return
        
        try:
            transfer = self.file_transfers[transfer_id]
            chunk_data = base64.b64decode(chunk)
            
            # Write chunk to temporary file
            transfer['temp_file'].write(chunk_data)
            transfer['bytes_received'] += len(chunk_data)
            
            # Check if this is the last chunk
            if transfer['bytes_received'] >= transfer['file_size']:
                # Rename temporary file to final destination
                transfer['temp_file'].close()
                shutil.move(transfer['temp_file_path'], transfer['dest_path'])
                
                logger.info(f"File upload completed: {transfer['filename']} -> {transfer['dest_path']}")
                
                # Send completion notification
                self.socket.emit('file_upload_complete', {
                    'client_id': self.client_id,
                    'transfer_id': transfer_id,
                    'filename': transfer['filename'],
                    'dest_path': transfer['dest_path']
                })
                
                # Clean up transfer
                del self.file_transfers[transfer_id]
            
        except Exception as e:
            logger.error(f"Error handling file upload chunk: {e}")
            self.socket.emit('file_upload_error', {
                'client_id': self.client_id,
                'transfer_id': transfer_id,
                'error': str(e)
            })
            
            # Clean up transfer
            if transfer_id in self.file_transfers:
                try:
                    transfer['temp_file'].close()
                    os.remove(transfer['temp_file_path'])
                except:
                    pass
                del self.file_transfers[transfer_id]
    
    def _on_file_download_request(self, data):
        """Handle request to download a file from client."""
        transfer_id = data.get('transfer_id')
        path = data.get('path')
        chunk_size = data.get('chunk_size')
        
        if not transfer_id or not path or not chunk_size:
            logger.error("File download request missing required parameters")
            return
        
        if not os.path.exists(path):
            logger.error(f"File not found: {path}")
            self.socket.emit('file_download_error', {
                'client_id': self.client_id,
                'transfer_id': transfer_id,
                'error': 'File not found'
            })
            return
        
        file_size = os.path.getsize(path)
        
        logger.info(f"Starting file download: {path} (size={file_size})")
        
        try:
            with open(path, 'rb') as f:
                offset = 0
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    
                    chunk_b64 = base64.b64encode(chunk).decode('utf-8')
                    
                    # Send chunk to server
                    self.socket.emit('file_download_chunk', {
                        'client_id': self.client_id,
                        'transfer_id': transfer_id,
                        'offset': offset,
                        'chunk': chunk_b64,
                        'is_last': False, # Will be updated later
                        'file_size': file_size # Send file size with the first chunk
                    })
                    
                    offset += len(chunk)
            
            # Send last chunk
            self.socket.emit('file_download_chunk', {
                'client_id': self.client_id,
                'transfer_id': transfer_id,
                'offset': offset,
                'chunk': '',
                'is_last': True,
                'file_size': file_size
            })
            
            logger.info(f"File download completed: {path}")
            
        except Exception as e:
            logger.error(f"Error during file download: {e}")
            self.socket.emit('file_download_error', {
                'client_id': self.client_id,
                'transfer_id': transfer_id,
                'error': str(e)
            })
    
    def _on_file_operation(self, data):
        """Handle file operations (delete, rename, etc.)."""
        operation = data.get('operation')
        path = data.get('path')
        user_id = data.get('user_id')
        
        if not operation or not path:
            logger.error("File operation request missing required parameters")
            return
        
        try:
            if operation == 'delete':
                if os.path.isfile(path):
                    os.remove(path)
                    logger.info(f"Deleted file: {path}")
                elif os.path.isdir(path):
                    shutil.rmtree(path)
                    logger.info(f"Deleted directory: {path}")
                else:
                    raise FileNotFoundError(f"Path not found: {path}")
                
                self.socket.emit('file_operation_result', {
                    'client_id': self.client_id,
                    'operation': operation,
                    'success': True,
                    'path': path,
                })
            elif operation == 'rename':
                new_path = data.get('new_path')
                if not new_path:
                    raise ValueError("New path is required for rename operation")
                
                os.rename(path, new_path)
                logger.info(f"Renamed: {path} -> {new_path}")
                
                self.socket.emit('file_operation_result', {
                    'client_id': self.client_id,
                    'operation': operation,
                    'success': True,
                    'path': path,
                    'new_path': new_path
                })
            else:
                raise ValueError(f"Unsupported file operation: {operation}")
            
        except Exception as e:
            logger.error(f"Error during file operation ({operation}): {e}")
            self.socket.emit('file_operation_result', {
                'client_id': self.client_id,
                'operation': operation,
                'success': False,
                'path': path,
                'error': str(e)
            })
    
    # === Command Execution Methods ===
    
    def _on_execute_command(self, data):
        """Handle command execution request from server."""
        command_id = data.get('command_id')
        command = data.get('command')
        user_id = data.get('user_id')
        
        if not command_id or not command:
            logger.error("Command execution request missing command ID or command text")
            return
        
        logger.info(f"Executing command: {command}")
        
        try:
            # Use subprocess to execute command
            process = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )
            
            output, error = process.communicate()
            exit_code = process.returncode
            
            # Send command result to server
            self.socket.emit('command_result', {
                'client_id': self.client_id,
                'command_id': command_id,
                'output': output,
                'error': error,
                'exit_code': exit_code
            })
            
            logger.info(f"Command executed with exit code: {exit_code}")
            
        except Exception as e:
            logger.error(f"Error executing command: {e}")
            self.socket.emit('command_result', {
                'client_id': self.client_id,
                'command_id': command_id,
                'output': '',
                'error': str(e),
                'exit_code': 1 # Indicate failure
            })
    
    def _on_request_system_info(self):
        """Handle request for system information."""
        try:
            system_info = {
                'os_name': platform.system(),
                'os_version': platform.version(),
                'architecture': platform.machine(),
                'cpu_count': os.cpu_count(),
                'total_memory': psutil.virtual_memory().total,
                'disk_usage': psutil.disk_usage('/').total
            }
            
            # Send system information to server
            self.socket.emit('system_info', {
                'client_id': self.client_id,
                'system_info': system_info
            })
            
            logger.info("Sent system information to server")
        except Exception as e:
            logger.error(f"Error getting system information: {e}")
    
    # === Heartbeat ===
    
    def _start_heartbeat(self):
        """Start a thread to send heartbeats to the server."""
        def heartbeat_loop():
            while self.connected and not self.stopping:
                try:
                    # Get system metrics
                    system_metrics = {
                        'cpu_percent': psutil.cpu_percent(interval=None),
                        'memory_percent': psutil.virtual_memory().percent,
                        'disk_percent': psutil.disk_usage('/').percent
                    }
                    
                    self.socket.emit('client_heartbeat', {
                        'client_id': self.client_id,
                        'system_metrics': system_metrics
                    })
                    
                    time.sleep(10)
                except Exception as e:
                    logger.error(f"Error sending heartbeat: {e}")
                    break
        
        threading.Thread(target=heartbeat_loop, daemon=True).start()
    
    # === Helper Methods ===
    
    def _get_local_ip(self):
        """Get the local IP address."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip_address = s.getsockname()[0]
            s.close()
            return ip_address
        except Exception as e:
            logger.error(f"Could not get local IP address: {e}")
            return '127.0.0.1'
    
    def stop(self):
        """Stop the client agent."""
        self.stopping = True
        if self.connected:
            self.socket.disconnect()
        
        logger.info("Client agent stopped")

def main():
    parser = argparse.ArgumentParser(description='Remote Access Client Agent')
    parser.add_argument('server', help='Server URL (e.g., http://localhost:5000)')
    parser.add_argument('--client-id', help='Client ID (optional, will generate if not provided)')
    parser.add_argument('--no-verify-ssl', action='store_false', dest='verify_ssl', help='Disable SSL verification (unsafe, use for testing only)')
    parser.set_defaults(verify_ssl=True)
    args = parser.parse_args()
    
    # Create and run the client
    client = RemoteClient(
        server_url=args.server,
        client_id=args.client_id,
        verify_ssl=args.verify_ssl
    )
    
    # Keep the main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nExiting...")
        client.stop()

if __name__ == '__main__':
    sys.exit(main())
