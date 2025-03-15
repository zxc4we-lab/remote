"""
Dashboard routes module.
Handles dashboard views, client management, and executable building functionality.
"""

import os
import sys
import io
import json
import time
import uuid
import zipfile
import tempfile
import threading
import shutil
import logging
import traceback
import subprocess
from datetime import datetime
from pathlib import Path
from flask import Blueprint, render_template, redirect, url_for, jsonify, flash, send_file, current_app, request
from flask import Response, stream_with_context, make_response
from flask_login import login_required, current_user
from app import db, csrf
from app.services.client_manager import ClientManager

# Set up logger
logger = logging.getLogger(__name__)

# Create blueprint
dashboard_bp = Blueprint('dashboard', __name__)

# Create client manager instance
client_manager = ClientManager()

# Dictionary to track build status and results
build_tasks = {}

@dashboard_bp.route('/')
@login_required
def index():
    """Dashboard home page with overview of connections and system status."""
    # Get recent connections
    recent_connections = client_manager.get_user_recent_connections(current_user.id)
    
    # Get connection statistics
    connections_count = client_manager.get_connection_count(current_user.id)
    active_sessions = client_manager.count_user_active_sessions(current_user.id)
    total_connection_time = client_manager.get_user_connection_time(current_user.id)
    
    # Get system stats
    system_stats = client_manager.get_system_stats()
    
    return render_template('dashboard/index.html',
                          recent_connections=recent_connections,
                          connections_count=connections_count,
                          active_sessions=active_sessions,
                          total_connection_time=total_connection_time,
                          system_load=system_stats['system_load'],
                          memory_usage=system_stats['memory_usage'])

@dashboard_bp.route('/admin')
@login_required
def admin():
    """Admin dashboard for system management."""
    # Check if user is an admin
    if not current_user.is_admin:
        flash('You do not have permission to access the admin dashboard.', 'danger')
        return redirect(url_for('dashboard.index'))
    
    # Admin dashboard logic would go here
    
    return render_template('dashboard/admin.html')

@dashboard_bp.route('/clients')
@login_required
def clients():
    """Client management dashboard page."""
    # Get all connected clients 
    active_clients = client_manager.get_active_direct_connections()
    
    # Get path to client template files
    client_py_path = os.path.join(current_app.root_path, 'static', 'client_templates', 'remote_client.py')
    builder_py_path = os.path.join(current_app.root_path, 'static', 'client_templates', 'build_exe.py')
    exe_path = os.path.join(current_app.root_path, 'static', 'client_templates', 'remote_client.exe')
    
    client_exists = os.path.exists(client_py_path)
    builder_exists = os.path.exists(builder_py_path)
    exe_exists = os.path.exists(exe_path)
    
    # Check if PyInstaller is installed on the server
    pyinstaller_installed = False
    try:
        subprocess.check_call([sys.executable, '-m', 'pip', 'show', 'pyinstaller'], 
                             stdout=subprocess.DEVNULL, 
                             stderr=subprocess.DEVNULL)
        pyinstaller_installed = True
    except:
        pass
    
    return render_template('dashboard/clients.html', 
                          active_clients=active_clients,
                          client_exists=client_exists,
                          builder_exists=builder_exists,
                          exe_exists=exe_exists,
                          pyinstaller_installed=pyinstaller_installed)

@dashboard_bp.route('/download/client')
@login_required
def download_client():
    """Download the Python client script."""
    client_py_path = os.path.join(current_app.root_path, 'static', 'client_templates', 'remote_client.py')
    
    if not os.path.exists(client_py_path):
        flash('Client script not found', 'danger')
        return redirect(url_for('dashboard.clients'))
    
    return send_file(client_py_path, as_attachment=True)

@dashboard_bp.route('/download/builder')
@login_required
def download_builder():
    """Download the EXE builder script."""
    builder_py_path = os.path.join(current_app.root_path, 'static', 'client_templates', 'build_exe.py')
    
    if not os.path.exists(builder_py_path):
        flash('Builder script not found', 'danger')
        return redirect(url_for('dashboard.clients'))
    
    return send_file(builder_py_path, as_attachment=True)

@dashboard_bp.route('/download/client-package')
@login_required
def download_client_package():
    """Download a ZIP package with client and builder script."""
    client_py_path = os.path.join(current_app.root_path, 'static', 'client_templates', 'remote_client.py')
    builder_py_path = os.path.join(current_app.root_path, 'static', 'client_templates', 'build_exe.py')
    icon_path = os.path.join(current_app.root_path, 'static', 'client_templates', 'terminal_icon.ico')
    
    if not os.path.exists(client_py_path) or not os.path.exists(builder_py_path):
        flash('Client package files are missing', 'danger')
        return redirect(url_for('dashboard.clients'))
    
    # Create in-memory ZIP file
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w') as zf:
        # Add client script
        zf.write(client_py_path, os.path.basename(client_py_path))
        
        # Add builder script
        zf.write(builder_py_path, os.path.basename(builder_py_path))
        
        # Add icon if it exists
        if os.path.exists(icon_path):
            zf.write(icon_path, os.path.basename(icon_path))
        
        # Add a README file
        readme_content = """# Remote Access Client

## Usage
1. Run the Python script directly:
   python remote_client.py <server_ip> <port>

2. Or build an executable using the builder:
   python build_exe.py

## Building the Executable
The build_exe.py script provides a GUI to create a Windows executable.
Requirements: PyInstaller (will be installed automatically if missing)
"""
        zf.writestr('README.md', readme_content)
    
    # Prepare the ZIP file for download
    memory_file.seek(0)
    return send_file(memory_file, 
                    mimetype='application/zip',
                    as_attachment=True,
                    attachment_filename='remote_client_package.zip')

@dashboard_bp.route('/download/exe')
@login_required
def download_exe():
    """Download the pre-built executable."""
    exe_path = os.path.join(current_app.root_path, 'static', 'client_templates', 'remote_client.exe')
    
    if not os.path.exists(exe_path):
        flash('Executable not found', 'danger')
        return redirect(url_for('dashboard.clients'))
    
    return send_file(exe_path, as_attachment=True)

@dashboard_bp.route('/build-and-download', methods=['POST'])
@csrf.exempt
@login_required
def build_and_download():
    """Build client executable and prepare it for download."""
    logger.info(f"Build requested by user: {current_user.username}")
    try:
        if not current_user.is_admin:
            return jsonify({
                'success': False,
                'message': 'Admin permission required to build executables'
            }), 403
        
        # Generate a unique task ID
        task_id = str(uuid.uuid4())
        
        # Create task entry
        build_tasks[task_id] = {
            'status': 'initializing',
            'progress': 0,
            'message': 'Build initialized',
            'output_path': None,
            'started_at': datetime.now(),
            'completed_at': None,
            'download_ready': False,
            'log': []
        }
        
        # Start the build in a background thread
        build_thread = threading.Thread(
            target=run_build_task,
            args=(task_id,),
            daemon=True
        )
        build_thread.start()
        
        return jsonify({
            'success': True,
            'task_id': task_id,
            'message': 'Build started'
        })
    except Exception as e:
        logger.error(f"Error in build_and_download: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'message': f'Server error: {str(e)}'
        }), 500

@dashboard_bp.route('/build-status/<task_id>')
@login_required
def build_status(task_id):
    """Get the status of a build task."""
    if task_id not in build_tasks:
        return jsonify({
            'success': False,
            'message': 'Build task not found'
        })
    
    task = build_tasks[task_id]
    
    return jsonify({
        'success': True,
        'status': task['status'],
        'progress': task['progress'],
        'message': task['message'],
        'download_ready': task['download_ready'],
        'log': task['log'][-10:] if len(task['log']) > 10 else task['log']  # Return last 10 log entries
    })

@dashboard_bp.route('/download-build/<task_id>')
@login_required
def download_build(task_id):
    """Download a completed build."""
    if task_id not in build_tasks:
        flash('Build task not found', 'danger')
        return redirect(url_for('dashboard.clients'))
    
    task = build_tasks[task_id]
    
    if not task['download_ready'] or not task['output_path'] or not os.path.exists(task['output_path']):
        flash('Build not ready for download or file not found', 'danger')
        return redirect(url_for('dashboard.clients'))
    
    # Generate a more user-friendly filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    download_filename = f"remote_client_{timestamp}.exe"
    
    return send_file(
        task['output_path'],
        as_attachment=True,
        attachment_filename=download_filename,
        mimetype='application/octet-stream'
    )

@dashboard_bp.route('/simple-build-exe', methods=['POST'])
@csrf.exempt
@login_required
def simple_build_exe():
    """Simple route to build the client executable with streamed response."""
    if not current_user.is_admin:
        return jsonify({'type': 'error', 'message': 'Admin permission required'})
    
    # Get path to client source file
    client_py_path = os.path.join(current_app.root_path, 'static', 'client_templates', 'remote_client.py')
    
    if not os.path.exists(client_py_path):
        return jsonify({'type': 'error', 'message': 'Client source file not found'})
    
    # Check if PyInstaller is installed
    try:
        subprocess.check_call([sys.executable, '-m', 'pip', 'show', 'pyinstaller'], 
                            stdout=subprocess.DEVNULL, 
                            stderr=subprocess.DEVNULL)
    except:
        return jsonify({'type': 'error', 'message': 'PyInstaller not installed on the server'})
    
    # Create a timestamp for the build
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    build_id = f"build_{timestamp}"
    
    # Create output directory 
    output_dir = os.path.join(current_app.root_path, 'static', 'builds')
    os.makedirs(output_dir, exist_ok=True)
    
    # Create a function to stream the build process
    def generate():
        try:
            # Send initial progress
            yield json.dumps({
                'type': 'progress',
                'progress': 0,
                'message': 'Starting build...'
            }) + '\n'
            
            # Find icon file if available
            icon_path = os.path.join(current_app.root_path, 'static', 'client_templates', 'terminal_icon.ico')
            icon_option = []
            if os.path.exists(icon_path):
                icon_option = ['--icon', icon_path]
                yield json.dumps({
                    'type': 'log',
                    'message': f'Using icon: {icon_path}'
                }) + '\n'
            
            # Create PyInstaller command
            cmd = [
                sys.executable, 
                '-m', 
                'PyInstaller',
                '--onefile',
                '--name', f'remote_client_{timestamp}',
                '--distpath', output_dir,
                '--workpath', os.path.join(tempfile.gettempdir(), build_id),
                '--specpath', os.path.join(tempfile.gettempdir(), build_id),
                '--hidden-import', 'socketio',
                '--hidden-import', 'socketio.client',
                '--hidden-import', 'engineio',
                '--hidden-import', 'readline',
                *icon_option,
                client_py_path
            ]
            
            yield json.dumps({
                'type': 'log',
                'message': f'Running command: {" ".join(cmd)}'
            }) + '\n'
            
            # Update progress
            yield json.dumps({
                'type': 'progress',
                'progress': 10,
                'message': 'Analyzing dependencies...'
            }) + '\n'
            
            # Start the build process
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True
            )
            
            # Progress tracking
            progress = 10
            
            # Process output
            for line in process.stdout:
                line = line.strip()
                
                # Send line as log
                yield json.dumps({
                    'type': 'log',
                    'message': line
                }) + '\n'
                
                # Update progress based on output
                if "Analyzing" in line and progress < 30:
                    progress = 30
                    yield json.dumps({
                        'type': 'progress',
                        'progress': progress,
                        'message': 'Analyzing dependencies...'
                    }) + '\n'
                elif "Processing" in line and progress < 50:
                    progress = 50
                    yield json.dumps({
                        'type': 'progress',
                        'progress': progress,
                        'message': 'Processing modules...'
                    }) + '\n'
                elif "Checking EXE" in line and progress < 70:
                    progress = 70
                    yield json.dumps({
                        'type': 'progress',
                        'progress': progress,
                        'message': 'Building executable...'
                    }) + '\n'
                elif "Building EXE" in line and progress < 80:
                    progress = 80
                    yield json.dumps({
                        'type': 'progress',
                        'progress': progress,
                        'message': 'Finalizing executable...'
                    }) + '\n'
                elif "Completed" in line and progress < 90:
                    progress = 90
                    yield json.dumps({
                        'type': 'progress',
                        'progress': progress,
                        'message': 'Completing build...'
                    }) + '\n'
            
            # Wait for process to complete
            process.wait()
            
            # Check if build was successful
            if process.returncode == 0:
                exe_path = os.path.join(output_dir, f'remote_client_{timestamp}.exe')
                if os.path.exists(exe_path):
                    # Get file size
                    size_bytes = os.path.getsize(exe_path)
                    size_mb = size_bytes / (1024 * 1024)
                    
                    # Log completion
                    yield json.dumps({
                        'type': 'log',
                        'message': f'Build successful! Executable size: {size_mb:.2f} MB'
                    }) + '\n'
                    
                    # Send completion with download URL
                    download_url = url_for('dashboard.download_built_exe', filename=f'remote_client_{timestamp}.exe')
                    yield json.dumps({
                        'type': 'complete',
                        'progress': 100,
                        'message': 'Build completed successfully!',
                        'download_url': download_url
                    }) + '\n'
                else:
                    yield json.dumps({
                        'type': 'error',
                        'message': 'Build process completed but executable not found'
                    }) + '\n'
            else:
                yield json.dumps({
                    'type': 'error',
                    'message': f'Build failed with exit code {process.returncode}'
                }) + '\n'
                
        except Exception as e:
            # Send error
            yield json.dumps({
                'type': 'error',
                'message': str(e)
            }) + '\n'
    
    # Stream the response
    return Response(stream_with_context(generate()), mimetype='application/json')

@dashboard_bp.route('/direct-build-and-download', methods=['POST'])
@csrf.exempt
@login_required
def direct_build_and_download():
    """Build and automatically download the client executable."""
    if not current_user.is_admin:
        return jsonify({'type': 'error', 'message': 'Admin permission required'})
    
    # Get path to client source file
    client_py_path = os.path.join(current_app.root_path, 'static', 'client_templates', 'remote_client.py')
    
    if not os.path.exists(client_py_path):
        return jsonify({'type': 'error', 'message': 'Client source file not found'})
    
    # Check if PyInstaller is installed
    try:
        subprocess.check_call([sys.executable, '-m', 'pip', 'show', 'pyinstaller'], 
                            stdout=subprocess.DEVNULL, 
                            stderr=subprocess.DEVNULL)
    except:
        return jsonify({'type': 'error', 'message': 'PyInstaller not installed on the server'})
    
    # Create a timestamp for the build
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    build_id = f"build_{timestamp}"
    
    # Create output directory 
    output_dir = os.path.join(current_app.root_path, 'static', 'builds')
    os.makedirs(output_dir, exist_ok=True)
    
    # Create a function to stream the build process
    def generate():
        try:
            # Send initial progress
            yield json.dumps({
                'type': 'progress',
                'progress': 0,
                'message': 'Starting build...'
            }) + '\n'
            
            # Find icon file if available
            icon_path = os.path.join(current_app.root_path, 'static', 'client_templates', 'terminal_icon.ico')
            icon_option = []
            if os.path.exists(icon_path):
                icon_option = ['--icon', icon_path]
                yield json.dumps({
                    'type': 'log',
                    'message': f'Using icon: {icon_path}'
                }) + '\n'
            
            # Create PyInstaller command
            cmd = [
                sys.executable, 
                '-m', 
                'PyInstaller',
                '--onefile',
                '--name', f'remote_client_{timestamp}',
                '--distpath', output_dir,
                '--workpath', os.path.join(tempfile.gettempdir(), build_id),
                '--specpath', os.path.join(tempfile.gettempdir(), build_id),
                '--hidden-import', 'socketio',
                '--hidden-import', 'socketio.client',
                '--hidden-import', 'engineio',
                '--hidden-import', 'readline',
                *icon_option,
                client_py_path
            ]
            
            yield json.dumps({
                'type': 'log',
                'message': f'Running command: {" ".join(cmd)}'
            }) + '\n'
            
            # Update progress
            yield json.dumps({
                'type': 'progress',
                'progress': 10,
                'message': 'Analyzing dependencies...'
            }) + '\n'
            
            # Start the build process
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True
            )
            
            # Progress tracking
            progress = 10
            
            # Process output
            for line in process.stdout:
                line = line.strip()
                
                # Send line as log
                yield json.dumps({
                    'type': 'log',
                    'message': line
                }) + '\n'
                
                # Update progress based on output
                if "Analyzing" in line and progress < 30:
                    progress = 30
                    yield json.dumps({
                        'type': 'progress',
                        'progress': progress,
                        'message': 'Analyzing dependencies...'
                    }) + '\n'
                elif "Processing" in line and progress < 50:
                    progress = 50
                    yield json.dumps({
                        'type': 'progress',
                        'progress': progress,
                        'message': 'Processing modules...'
                    }) + '\n'
                elif "Checking EXE" in line and progress < 70:
                    progress = 70
                    yield json.dumps({
                        'type': 'progress',
                        'progress': progress,
                        'message': 'Building executable...'
                    }) + '\n'
                elif "Building EXE" in line and progress < 80:
                    progress = 80
                    yield json.dumps({
                        'type': 'progress',
                        'progress': progress,
                        'message': 'Finalizing executable...'
                    }) + '\n'
                elif "Completed" in line and progress < 90:
                    progress = 90
                    yield json.dumps({
                        'type': 'progress',
                        'progress': progress,
                        'message': 'Completing build...'
                    }) + '\n'
            
            # Wait for process to complete
            process.wait()
            
            # Check if build was successful
            if process.returncode == 0:
                exe_path = os.path.join(output_dir, f'remote_client_{timestamp}.exe')
                if os.path.exists(exe_path):
                    # Get file size
                    size_bytes = os.path.getsize(exe_path)
                    size_mb = size_bytes / (1024 * 1024)
                    
                    # Log completion
                    yield json.dumps({
                        'type': 'log',
                        'message': f'Build successful! Executable size: {size_mb:.2f} MB'
                    }) + '\n'
                    
                    # Trigger download automatically
                    download_url = url_for('dashboard.download_built_exe', filename=f'remote_client_{timestamp}.exe')
                    yield json.dumps({
                        'type': 'download',
                        'message': 'Build completed successfully! Starting download...',
                        'download_url': download_url
                    }) + '\n'
                else:
                    yield json.dumps({
                        'type': 'error',
                        'message': 'Build process completed but executable not found'
                    }) + '\n'
            else:
                yield json.dumps({
                    'type': 'error',
                    'message': f'Build failed with exit code {process.returncode}'
                }) + '\n'
                
        except Exception as e:
            # Send error
            yield json.dumps({
                'type': 'error',
                'message': str(e)
            }) + '\n'
    
    # Stream the response
    return Response(stream_with_context(generate()), mimetype='application/json')

@dashboard_bp.route('/download-built-exe/<filename>')
@login_required
def download_built_exe(filename):
    """Download a built executable."""
    builds_dir = os.path.join(current_app.root_path, 'static', 'builds')
    return send_file(
        os.path.join(builds_dir, filename),
        as_attachment=True,
        attachment_filename=filename
    )

@dashboard_bp.route('/build-exe', methods=['POST'])
@login_required
def build_exe():
    """Build the client executable on the server."""
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Admin permission required'})
    
    client_py_path = os.path.join(current_app.root_path, 'static', 'client_templates', 'remote_client.py')
    exe_output_dir = os.path.join(current_app.root_path, 'static', 'client_templates')
    
    if not os.path.exists(client_py_path):
        return jsonify({'success': False, 'message': 'Client script not found'})
    
    # Check if PyInstaller is installed
    try:
        subprocess.check_call([sys.executable, '-m', 'pip', 'show', 'pyinstaller'], 
                             stdout=subprocess.DEVNULL, 
                             stderr=subprocess.DEVNULL)
    except:
        return jsonify({'success': False, 'message': 'PyInstaller not installed on the server'})
    
    # Build the executable
    try:
        # Create a response stream
        def generate():
            # Clean old files
            spec_file = os.path.join(exe_output_dir, 'remote_client.spec')
            if os.path.exists(spec_file):
                os.remove(spec_file)
                yield "Removed old spec file\n"
            
            build_dir = os.path.join(exe_output_dir, 'build')
            if os.path.exists(build_dir):
                import shutil
                shutil.rmtree(build_dir)
                yield "Removed old build directory\n"
            
            # Build command
            cmd = [
                sys.executable, 
                '-m', 
                'PyInstaller',
                '--onefile',
                '--name', 'remote_client',
                '--distpath', exe_output_dir,
                '--workpath', os.path.join(exe_output_dir, 'build'),
                '--specpath', exe_output_dir,
                '--hidden-import', 'socketio',
                '--hidden-import', 'socketio.client',
                '--hidden-import', 'engineio',
                client_py_path
            ]
            
            # Add icon if available
            icon_path = os.path.join(current_app.root_path, 'static', 'client_templates', 'terminal_icon.ico')
            if os.path.exists(icon_path):
                cmd.extend(['--icon', icon_path])
                yield f"Using icon from {icon_path}\n"
            
            yield f"Starting build with command: {' '.join(cmd)}\n"
            
            # Run PyInstaller
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True
            )
            
            for line in process.stdout:
                yield line
            
            # Wait for process to complete
            process.wait()
            
            if process.returncode == 0:
                yield "\nBuild completed successfully!\n"
                
                # Get file size
                exe_path = os.path.join(exe_output_dir, 'remote_client.exe')
                if os.path.exists(exe_path):
                    size_bytes = os.path.getsize(exe_path)
                    size_display = size_bytes
                    for unit in ['B', 'KB', 'MB', 'GB']:
                        if size_display < 1024.0:
                            yield f"Executable size: {size_display:.2f} {unit}\n"
                            break
                        size_display /= 1024.0
            else:
                yield "\nBuild failed with errors.\n"
        
        return Response(generate(), mimetype='text/plain')
    
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error building executable: {str(e)}'})

@dashboard_bp.route('/api/clients')
@login_required
def api_clients():
    """API endpoint to get active client connections."""
    active_clients = client_manager.get_active_direct_connections()
    return jsonify({
        'success': True,
        'clients': active_clients
    })

def run_build_task(task_id):
    """Run the client build process in the background."""
    task = build_tasks[task_id]
    
    try:
        task['status'] = 'running'
        task['message'] = 'Build process started'
        task['log'].append('Starting build process...')
        
        # Get paths to source and output
        client_py_path = os.path.join(current_app.root_path, 'static', 'client_templates', 'remote_client.py')
        
        # Create a temporary directory for output
        temp_dir = tempfile.mkdtemp(prefix='client_build_')
        task['log'].append(f'Using temporary directory: {temp_dir}')
        
        # Check if PyInstaller is installed
        try:
            task['log'].append('Checking for PyInstaller...')
            subprocess.check_call([sys.executable, '-m', 'pip', 'show', 'pyinstaller'], 
                                stdout=subprocess.DEVNULL, 
                                stderr=subprocess.DEVNULL)
            task['log'].append('PyInstaller is installed')
        except:
            task['status'] = 'failed'
            task['message'] = 'PyInstaller not installed on the server'
            task['log'].append('ERROR: PyInstaller not installed on the server')
            return
        
        # Check if source file exists
        if not os.path.exists(client_py_path):
            task['status'] = 'failed'
            task['message'] = 'Client source file not found'
            task['log'].append(f'ERROR: Client source file not found at {client_py_path}')
            return
        
        task['progress'] = 10
        task['log'].append('Preparing build environment...')
        
        # Find icon file if available
        icon_path = os.path.join(current_app.root_path, 'static', 'client_templates', 'terminal_icon.ico')
        icon_option = []
        if os.path.exists(icon_path):
            icon_option = ['--icon', icon_path]
            task['log'].append(f'Using icon: {icon_path}')
        
        # Prepare PyInstaller command
        cmd = [
            sys.executable, 
            '-m', 
            'PyInstaller',
            '--onefile',
            '--name', 'remote_client',
            '--distpath', temp_dir,
            '--workpath', os.path.join(temp_dir, 'build'),
            '--specpath', temp_dir,
            '--hidden-import', 'socketio',
            '--hidden-import', 'socketio.client',
            '--hidden-import', 'engineio',
            '--hidden-import', 'readline',
            *icon_option,
            client_py_path
        ]
        
        task['progress'] = 20
        task['log'].append(f'Running command: {" ".join(cmd)}')
        
        # Execute PyInstaller
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True
        )
        
        # Process and log output
        for line in process.stdout:
            line = line.strip()
            task['log'].append(line)
            
            # Update progress based on output patterns
            if "Analyzing" in line:
                task['progress'] = 30
                task['message'] = 'Analyzing dependencies'
            elif "Processing" in line:
                task['progress'] = 50
                task['message'] = 'Processing modules'
            elif "Checking EXE" in line:
                task['progress'] = 70
                task['message'] = 'Building executable'
            elif "Building EXE" in line:
                task['progress'] = 80
                task['message'] = 'Finalizing executable'
            elif "Completed" in line:
                task['progress'] = 90
                task['message'] = 'Build completed'
        
        # Wait for process to finish
        process.wait()
        
        output_path = os.path.join(temp_dir, 'remote_client.exe')
        
        if process.returncode == 0 and os.path.exists(output_path):
            # Success! 
            task['status'] = 'completed'
            task['progress'] = 100
            task['message'] = 'Build completed successfully'
            task['output_path'] = output_path
            task['download_ready'] = True
            task['completed_at'] = datetime.now()
            
            # Get file size
            size_bytes = os.path.getsize(output_path)
            size_mb = size_bytes / (1024 * 1024)
            task['log'].append(f'Build successful! Executable size: {size_mb:.2f} MB')
            
            # Also copy to the static client_templates directory for future direct downloads
            static_exe_path = os.path.join(current_app.root_path, 'static', 'client_templates', 'remote_client.exe')
            shutil.copy2(output_path, static_exe_path)
            task['log'].append(f'Executable copied to static directory for future downloads')
        else:
            # Build failed
            task['status'] = 'failed'
            task['progress'] = 100
            task['message'] = 'Build failed'
            task['completed_at'] = datetime.now()
            task['log'].append('Build process failed with errors')
    
    except Exception as e:
        task['status'] = 'failed'
        task['progress'] = 100
        task['message'] = f'Error: {str(e)}'
        task['completed_at'] = datetime.now()
        task['log'].append(f'ERROR: {str(e)}')
        
        # Log exception details
        task['log'].append(traceback.format_exc())
        
from flask import jsonify, current_app
from app.refresh_manager import refresh_manager

# Add these API endpoints to your dashboard.py file

@dashboard_bp.route('/api/system_stats')
@login_required
def api_system_stats():
    """API endpoint to get system statistics."""
    system_stats = client_manager.get_system_stats()
    
    # Add disk usage if not already present
    if 'disk_usage' not in system_stats:
        system_stats['disk_usage'] = 58  # Example value
    
    return jsonify({
        'success': True,
        'timestamp': datetime.now().isoformat(),
        'system_load': system_stats['system_load'],
        'memory_usage': system_stats['memory_usage'],
        'disk_usage': system_stats['disk_usage'],
        'network_status': system_stats.get('network_status', 'Online')
    })

@dashboard_bp.route('/api/active_sessions')
@login_required
def api_active_sessions():
    """API endpoint to get active sessions for the current user."""
    sessions = client_manager.get_user_active_sessions(current_user.id)
    
    return jsonify({
        'success': True,
        'timestamp': datetime.now().isoformat(),
        'count': len(sessions),
        'sessions': sessions
    })

@dashboard_bp.route('/api/refresh_intervals')
@login_required
def api_refresh_intervals():
    """API endpoint to get available refresh intervals."""
    return jsonify({
        'success': True,
        'intervals': [
            {'value': 5000, 'label': '5 seconds'},
            {'value': 10000, 'label': '10 seconds'},
            {'value': 30000, 'label': '30 seconds'},
            {'value': 60000, 'label': '1 minute'},
            {'value': 300000, 'label': '5 minutes'}
        ]
    })

@dashboard_bp.route('/api/manual_refresh', methods=['POST'])
@login_required
def api_manual_refresh():
    """API endpoint to manually trigger a refresh of all data."""
    try:
        # Trigger immediate refresh of all data
        refresh_manager.refresh_system_stats()
        refresh_manager.refresh_active_sessions()
        
        return jsonify({
            'success': True,
            'message': 'Manual refresh completed',
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        current_app.logger.error(f"Error in manual refresh: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500