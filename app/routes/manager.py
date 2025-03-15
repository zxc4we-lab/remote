from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user
from app.services.remote_management import remote_manager
import logging

manage_bp = Blueprint('manage', __name__, url_prefix='/manage')

@manage_bp.route('/')
@login_required
def index():
    """Remote management dashboard."""
    clients = remote_manager.get_active_clients()
    
    return render_template('manage/dashboard.html', clients=clients)

@manage_bp.route('/client/<client_id>')
@login_required
def client_details(client_id):
    """Detailed information about a specific client."""
    client_info = remote_manager.get_client_info(client_id)
    
    if not client_info:
        flash('Client not found', 'danger')
        return redirect(url_for('manage.index'))
    
    return render_template('manage/client_details.html', client=client_info)

@manage_bp.route('/client/<client_id>/files', methods=['GET', 'POST'])
@login_required
def client_files(client_id):
    """Manage files on a remote client."""
    client_info = remote_manager.get_client_info(client_id)
    if not client_info:
        flash('Client not found', 'danger')
        return redirect(url_for('manage.index'))
    
    # Get requested path
    path = request.args.get('path', '/')
    
    # Send request to the client
    success, request_id = remote_manager.request_file_listing(client_id, path)
    
    if not success:
        flash(request_id, 'danger')  # Request ID will contain error message
        return redirect(url_for('manage.client_details