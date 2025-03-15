#!/usr/bin/env python3
"""
Direct Socket Terminal Client
Connects to a remote access server using IP and port.
No authentication required - works with direct socket connections.

Usage: python remote_client.py <host> <port>
Example: python remote_client.py 192.168.1.100 5000
"""

import os
import sys
import json
import time
import argparse
import socketio
import threading
import platform
import readline
import atexit
from datetime import datetime

VERSION = "1.0.0"

class DirectSocketClient:
    def __init__(self, host, port, verbose=False):
        self.host = host
        self.port = port
        self.verbose = verbose
        self.socket = None
        self.connected = False
        self.session_id = None  # We'll generate this locally
        self.data_transferred = 0
        self.command_history_file = os.path.expanduser('~/.remote_access_history')
        
        # Set up command history
        self.setup_command_history()
        
    def setup_command_history(self):
        """Set up command history for better terminal experience"""
        try:
            # Create history file if it doesn't exist
            if not os.path.exists(self.command_history_file):
                open(self.command_history_file, 'a').close()
                
            readline.read_history_file(self.command_history_file)
            readline.set_history_length(1000)
            atexit.register(readline.write_history_file, self.command_history_file)
        except Exception as e:
            self.log(f"Couldn't set up command history: {e}")
    
    def log(self, message):
        """Log message if verbose mode is enabled"""
        if self.verbose:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{timestamp}] {message}")
    
    def generate_session_id(self):
        """Generate a pseudo-random session ID"""
        import uuid
        return str(uuid.uuid4())
    
    def connect(self):
        """Connect to the remote server"""
        try:
            self.log(f"Connecting to {self.host}:{self.port}...")
            
            # Create socket.io client
            self.socket = socketio.Client()
            
            # Register event handlers
            @self.socket.event
            def connect():
                self.connected = True
                self.log("Socket connected successfully")
                print(f"Connected to server at {self.host}:{self.port}")
                
                # Generate a session ID
                self.session_id = self.generate_session_id()
                self.log(f"Generated session ID: {self.session_id}")
                
                # For compatibility with the server, we register the session
                client_info = {
                    'hostname': platform.node(),
                    'platform': platform.system(),
                    'version': VERSION,
                    'python_version': platform.python_version(),
                    'architecture': platform.machine()
                }
                
                self.socket.emit('register_direct_connection', {
                    'session_id': self.session_id,
                    'client_info': client_info
                })
            
            @self.socket.event
            def connect_error(error):
                self.log(f"Connection error: {error}")
                print(f"Failed to connect: {error}")
                self.connected = False
            
            @self.socket.event
            def disconnect():
                self.log("Socket disconnected")
                self.connected = False
                print("\nDisconnected from server")
            
            @self.socket.event
            def terminal_output(data):
                # Only process output for our session
                if 'session_id' not in data or data['session_id'] == self.session_id:
                    print(data['output'])
                    
                    # Track data transferred
                    if 'output' in data:
                        self.data_transferred += len(data['output'])
            
            @self.socket.event
            def connection_accepted(data):
                if data.get('session_id') == self.session_id:
                    print(f"\nConnection established with {self.host}:{self.port}")
                    print(f"Session ID: {self.session_id}")
                    
                    if 'server_info' in data:
                        server_info = data['server_info']
                        print(f"Server: {server_info.get('name', 'Remote Access Server')} "
                              f"v{server_info.get('version', '1.0')}")
                    
                    # Start the terminal interface
                    self.start_terminal_interface()
            
            @self.socket.event
            def force_disconnect(data):
                print("\nConnection terminated by the server.")
                self.disconnect()
            
            @self.socket.event
            def authentication_result(data):
                if data.get('success'):
                    self.log("Authentication successful")
                else:
                    self.log(f"Authentication failed: {data.get('message', 'Unknown error')}")
            
            # Connect to the socket server
            socket_url = f"http://{self.host}:{self.port}"
            self.socket.connect(socket_url)
            
            return True
            
        except Exception as e:
            print(f"Error connecting to server: {e}")
            return False
    
    def start_terminal_interface(self):
        """Start the terminal interface in a separate thread"""
        terminal_thread = threading.Thread(target=self.terminal_interface)
        terminal_thread.daemon = True
        terminal_thread.start()
    
    def terminal_interface(self):
        """Run the terminal interface"""
        print("\n" + "="*50)
        print("Remote Access Terminal")
        print("Type 'help' for available commands. 'exit' to quit.")
        print("="*50 + "\n")
        
        try:
            while self.connected:
                # Get command from user
                prompt = f"remote:~$ "
                command = input(prompt)
                
                # Track data transferred
                self.data_transferred += len(command)
                
                # Check for exit command
                if command.lower() in ('exit', 'quit', 'logout'):
                    self.disconnect()
                    break
                
                # Check for clear command
                elif command.lower() == 'clear':
                    os.system('cls' if os.name == 'nt' else 'clear')
                    continue
                
                # Check for stats command
                elif command.lower() == 'stats':
                    self.show_stats()
                    continue
                
                # Local help command
                elif command.lower() == 'help':
                    self.show_help()
                    continue
                
                # Send command to server
                if command.strip():
                    self.socket.emit('terminal_input', {
                        'command': command,
                        'session_id': self.session_id
                    })
                
        except KeyboardInterrupt:
            print("\nDisconnecting...")
            self.disconnect()
        except EOFError:
            print("\nEnd of input. Disconnecting...")
            self.disconnect()
    
    def show_stats(self):
        """Show connection statistics"""
        if not self.connected:
            print("Not connected to server")
            return
            
        print("\n=== Connection Statistics ===")
        print(f"Connected to: {self.host}:{self.port}")
        print(f"Session ID: {self.session_id}")
        
        # Format data transferred
        if self.data_transferred < 1024:
            data_size = f"{self.data_transferred} bytes"
        elif self.data_transferred < 1024 * 1024:
            data_size = f"{self.data_transferred / 1024:.2f} KB"
        else:
            data_size = f"{self.data_transferred / (1024 * 1024):.2f} MB"
            
        print(f"Data transferred: {data_size}")
        print("============================\n")
    
    def show_help(self):
        """Show help information"""
        print("\n=== Available Commands ===")
        print("help    - Show this help message")
        print("clear   - Clear the terminal screen")
        print("stats   - Show connection statistics")
        print("exit    - Disconnect and exit (also: quit, logout)")
        print("Ctrl+C  - Force disconnect and exit")
        print("")
        print("All other commands are sent to the server for execution")
        print("==========================\n")
    
    def disconnect(self):
        """Disconnect from the server"""
        if self.socket and self.connected:
            try:
                self.socket.emit('disconnect_session', {'session_id': self.session_id})
                self.socket.disconnect()
                self.log("Disconnected from server")
            except Exception as e:
                self.log(f"Error during disconnect: {e}")
        
        self.connected = False
    
    def run(self):
        """Run the client"""
        try:
            # Connect to the server
            if not self.connect():
                return 1
            
            # Keep the main thread alive while the terminal thread runs
            while self.connected:
                time.sleep(0.1)
                
        except KeyboardInterrupt:
            print("\nExiting...")
        finally:
            if self.socket and self.connected:
                self.disconnect()
        
        return 0


def main():
    """Main entry point"""
    # Print banner
    print(f"""
  _____                      _         _                         
 |  __ \                    | |       /\\                        
 | |__) |___ _ __ ___   ___ | |_ ___ /  \\   ___ ___ ___  ___ ___ 
 |  _  // _ \\ '_ ` _ \\ / _ \\| __/ _ \\ /\\ \\ / __/ __/ _ \\/ __/ __|
 | | \\ \\  __/ | | | | | (_) | ||  __/ ____ \\ (_| (_|  __/\\__ \\__ \\
 |_|  \\_\\___|_| |_| |_|\\___/ \\__\\___/_/    \\_\\___\\___\\___||___/___/
                                                                 
 Direct Socket Client v{VERSION}
""")
    
    parser = argparse.ArgumentParser(description='Direct Socket Terminal Client')
    parser.add_argument('host', help='Server hostname or IP address')
    parser.add_argument('port', type=int, help='Server port number')
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose logging')
    args = parser.parse_args()

    # Create and run the client
    client = DirectSocketClient(
        host=args.host,
        port=args.port,
        verbose=args.verbose
    )
    return client.run()

if __name__ == '__main__':
    sys.exit(main())
