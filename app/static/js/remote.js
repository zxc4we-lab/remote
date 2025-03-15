/**
 * Remote Access WebSocket Client
 * Handles terminal connections and command transmission
 */

class RemoteAccessClient {
    constructor(sessionId, hostname) {
        this.sessionId = sessionId;
        this.hostname = hostname;
        this.socket = null;
        this.connected = false;
        this.commandHistory = [];
        this.historyIndex = -1;
        this.dataTransferred = 0;
        this.connectionStartTime = Date.now();
        
        // DOM Elements
        this.terminalOutput = document.getElementById('terminal-output');
        this.terminalInput = document.getElementById('terminal-input');
        this.disconnectBtn = document.getElementById('disconnect-btn');
        this.fullscreenBtn = document.getElementById('fullscreen-btn');
        this.dataTransferredElement = document.getElementById('data-transferred');
        this.latencyElement = document.getElementById('latency');
    }
    
    /**
     * Initialize the client and connect to server
     */
    initialize() {
        // Create socket connection
        this.socket = io({
            transports: ['websocket'],
            upgrade: false,
            reconnection: true,
            reconnectionAttempts: 5,
            reconnectionDelay: 1000
        });
        
        this.setupEventListeners();
        this.showConnectionMessage();
    }
    
    /**
     * Set up all event listeners for the client
     */
    setupEventListeners() {
        // Socket events
        this.socket.on('connect', () => this.handleConnect());
        this.socket.on('disconnect', () => this.handleDisconnect());
        this.socket.on('connect_error', (error) => this.handleConnectionError(error));
        this.socket.on('terminal_output', (data) => this.handleTerminalOutput(data));
        
        // UI events
        this.terminalInput.addEventListener('keydown', (e) => this.handleInputKeydown(e));
        this.disconnectBtn.addEventListener('click', () => this.disconnect());
        this.fullscreenBtn.addEventListener('click', () => this.toggleFullscreen());
        
        // Handle window resize for terminal size adjustments
        window.addEventListener('resize', () => this.adjustTerminalSize());
    }
    
    /**
     * Display initial connection message
     */
    showConnectionMessage() {
        this.appendToTerminal(`Connecting to ${this.hostname}...`, 'system');
        this.appendToTerminal(`Session ID: ${this.sessionId}`, 'system');
    }
    
    /**
     * Handle successful connection
     */
    handleConnect() {
        this.connected = true;
        this.appendToTerminal('Connection established. Terminal ready.', 'success');
        
        // Send authentication message with session ID
        this.socket.emit('authenticate', { session_id: this.sessionId });
        
        // Start tracking stats
        this.startStatsTracking();
    }
    
    /**
     * Handle disconnection
     */
    handleDisconnect() {
        this.connected = false;
        this.appendToTerminal('Disconnected from server.', 'error');
    }
    
    /**
     * Handle connection errors
     */
    handleConnectionError(error) {
        this.connected = false;
        this.appendToTerminal(`Connection error: ${error.message}`, 'error');
    }
    
    /**
     * Process terminal input
     */
    processCommand(command) {
        if (!this.connected) {
            this.appendToTerminal('Not connected to server', 'error');
            return;
        }
        
        // Add command to history
        this.commandHistory.unshift(command);
        if (this.commandHistory.length > 50) {
            this.commandHistory.pop();
        }
        this.historyIndex = -1;
        
        // Display the command
        this.appendToTerminal(`${this.hostname}:~$ ${command}`, 'command');
        
        // Handle special local commands
        if (command === 'clear') {
            this.clearTerminal();
            return;
        }
        
        // Send to server
        this.socket.emit('terminal_input', {
            command: command,
            session_id: this.sessionId
        });
        
        // Update data transferred stats (estimation)
        this.dataTransferred += command.length;
    }
    
    /**
     * Handle terminal output from server
     */
    handleTerminalOutput(data) {
        if (data.session_id !== this.sessionId) {
            return;
        }
        
        this.appendToTerminal(data.output, 'output');
        
        // Update data transferred stats (estimation)
        this.dataTransferred += data.output.length;
        this.updateDataTransferredDisplay();
    }
    
    /**
     * Append text to terminal with specified class
     */
    appendToTerminal(text, className = '') {
        const line = document.createElement('div');
        line.className = `terminal-text ${className}`;
        line.textContent = text;
        this.terminalOutput.appendChild(line);
        
        // Scroll to bottom
        this.terminalOutput.scrollTop = this.terminalOutput.scrollHeight;
    }
    
    /**
     * Clear the terminal output
     */
    clearTerminal() {
        this.terminalOutput.innerHTML = '';
        this.appendToTerminal('Terminal cleared', 'system');
    }
    
    /**
     * Handle keydown events in the input field
     */
    handleInputKeydown(event) {
        // Enter key - process command
        if (event.key === 'Enter') {
            const command = this.terminalInput.value.trim();
            if (command) {
                this.processCommand(command);
                this.terminalInput.value = '';
            }
            event.preventDefault();
        }
        
        // Up arrow - previous command in history
        else if (event.key === 'ArrowUp') {
            if (this.historyIndex < this.commandHistory.length - 1) {
                this.historyIndex++;
                this.terminalInput.value = this.commandHistory[this.historyIndex];
                
                // Move cursor to end
                setTimeout(() => {
                    this.terminalInput.selectionStart = this.terminalInput.value.length;
                    this.terminalInput.selectionEnd = this.terminalInput.value.length;
                }, 0);
            }
            event.preventDefault();
        }
        
        // Down arrow - next command in history
        else if (event.key === 'ArrowDown') {
            if (this.historyIndex > 0) {
                this.historyIndex--;
                this.terminalInput.value = this.commandHistory[this.historyIndex];
            } else if (this.historyIndex === 0) {
                this.historyIndex = -1;
                this.terminalInput.value = '';
            }
            event.preventDefault();
        }
        
        // Tab key - autocomplete (could be implemented with server help)
        else if (event.key === 'Tab') {
            event.preventDefault();
        }
    }
    
    /**
     * Disconnect from the server
     */
    disconnect() {
        if (this.connected) {
            this.socket.emit('disconnect_session', { session_id: this.sessionId });
            this.socket.disconnect();
            this.connected = false;
        }
    }
    
    /**
     * Toggle fullscreen mode for the terminal
     */
    toggleFullscreen() {
        const terminal = document.getElementById('terminal');
        
        if (!document.fullscreenElement) {
            if (terminal.requestFullscreen) {
                terminal.requestFullscreen();
            } else if (terminal.mozRequestFullScreen) {
                terminal.mozRequestFullScreen();
            } else if (terminal.webkitRequestFullscreen) {
                terminal.webkitRequestFullscreen();
            } else if (terminal.msRequestFullscreen) {
                terminal.msRequestFullscreen();
            }
            this.fullscreenBtn.innerHTML = '<i data-feather="minimize-2"></i>';
        } else {
            if (document.exitFullscreen) {
                document.exitFullscreen();
            } else if (document.mozCancelFullScreen) {
                document.mozCancelFullScreen();
            } else if (document.webkitExitFullscreen) {
                document.webkitExitFullscreen();
            } else if (document.msExitFullscreen) {
                document.msExitFullscreen();
            }
            this.fullscreenBtn.innerHTML = '<i data-feather="maximize-2"></i>';
        }
        
        // Re-initialize feather icons
        feather.replace();
    }
    
    /**
     * Adjust terminal size based on window dimensions
     */
    adjustTerminalSize() {
        // Could implement terminal resizing logic here
    }
    
    /**
     * Start tracking stats like data transferred and latency
     */
    startStatsTracking() {
        // Update stats every 5 seconds
        setInterval(() => {
            this.updateStats();
        }, 5000);
    }
    
    /**
     * Update connection statistics
     */
    updateStats() {
        // Update data transferred
        this.updateDataTransferredDisplay();
        
        // Calculate connection time
        const connectionTime = Math.floor((Date.now() - this.connectionStartTime) / 1000);
        
        // Simulate latency calculation (in a real app, you'd measure actual round-trip time)
        const latency = Math.floor(Math.random() * 30 + 10); // Random value between 10-40ms
        if (this.latencyElement) {
            this.latencyElement.textContent = `${latency} ms`;
        }
    }
    
    /**
     * Update data transferred display
     */
    updateDataTransferredDisplay() {
        if (!this.dataTransferredElement) return;
        
        let displayValue = '';
        if (this.dataTransferred < 1024) {
            displayValue = `${this.dataTransferred} B`;
        } else if (this.dataTransferred < 1024 * 1024) {
            displayValue = `${(this.dataTransferred / 1024).toFixed(2)} KB`;
        } else {
            displayValue = `${(this.dataTransferred / (1024 * 1024)).toFixed(2)} MB`;
        }
        
        this.dataTransferredElement.textContent = displayValue;
    }
}

// Initialize client when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    const sessionId = document.getElementById('session-id').textContent.trim();
    const hostname = document.querySelector('.connection-info h1').textContent.trim();
    
    const client = new RemoteAccessClient(sessionId, hostname);
    client.initialize();
});

/**
 * Data Refresh Manager
 * Handles automatic and manual data refresh across the application
 */
class DataRefreshManager {
    constructor(config = {}) {
        // Configuration with defaults
        this.config = {
            defaultInterval: 30000,  // Default: 30 seconds
            endpoints: {},           // API endpoints to refresh
            onRefresh: null,         // Global refresh callback
            toastEnabled: true,      // Show toast notifications
            storageName: 'refreshSettings', // Local storage key
            ...config
        };
        
        // State
        this.autoRefreshEnabled = true;
        this.lastRefreshed = new Date();
        this.refreshInterval = this.config.defaultInterval;
        this.refreshTimers = {};
        this.isRefreshing = false;
        
        // DOM Elements
        this.elements = {
            lastUpdatedTime: document.getElementById('last-updated-time'),
            autoRefreshToggle: document.getElementById('auto-refresh-toggle'),
            refreshIntervalSelect: document.getElementById('refresh-interval'),
            refreshNowBtn: document.getElementById('refresh-now-btn'),
            realtimeIndicator: document.getElementById('realtime-indicator')
        };
        
        // Initialize
        this.init();
    }
    
    /**
     * Initialize the refresh manager
     */
    init() {
        // Load saved settings
        this.loadSettings();
        
        // Set up event listeners
        this.setupEventListeners();
        
        // Update the UI to match current state
        this.updateUI();
        
        // Start auto-refresh if enabled
        if (this.autoRefreshEnabled) {
            this.startAutoRefresh();
        }
    }
    
    /**
     * Load settings from local storage
     */
    loadSettings() {
        try {
            const savedSettings = localStorage.getItem(this.config.storageName);
            if (savedSettings) {
                const settings = JSON.parse(savedSettings);
                this.autoRefreshEnabled = settings.autoRefreshEnabled !== undefined ? 
                    settings.autoRefreshEnabled : true;
                this.refreshInterval = settings.refreshInterval || this.config.defaultInterval;
            }
        } catch (e) {
            console.error('Error loading refresh settings:', e);
        }
    }
    
    /**
     * Save settings to local storage
     */
    saveSettings() {
        try {
            const settings = {
                autoRefreshEnabled: this.autoRefreshEnabled,
                refreshInterval: this.refreshInterval
            };
            localStorage.setItem(this.config.storageName, JSON.stringify(settings));
        } catch (e) {
            console.error('Error saving refresh settings:', e);
        }
    }
    
    /**
     * Set up event listeners for UI controls
     */
    setupEventListeners() {
        // Auto-refresh toggle
        if (this.elements.autoRefreshToggle) {
            this.elements.autoRefreshToggle.checked = this.autoRefreshEnabled;
            this.elements.autoRefreshToggle.addEventListener('change', () => {
                this.autoRefreshEnabled = this.elements.autoRefreshToggle.checked;
                this.saveSettings();
                
                if (this.autoRefreshEnabled) {
                    this.startAutoRefresh();
                    this.showToast('Auto-refresh enabled', 'success');
                } else {
                    this.stopAutoRefresh();
                    this.showToast('Auto-refresh disabled', 'info');
                }
                
                this.updateUI();
            });
        }
        
        // Refresh interval selector
        if (this.elements.refreshIntervalSelect) {
            this.elements.refreshIntervalSelect.value = this.refreshInterval;
            this.elements.refreshIntervalSelect.addEventListener('change', () => {
                this.refreshInterval = parseInt(this.elements.refreshIntervalSelect.value);
                this.saveSettings();
                
                if (this.autoRefreshEnabled) {
                    this.restartAutoRefresh();
                }
                
                // Show toast with human-readable interval
                const intervalText = this.elements.refreshIntervalSelect.options[
                    this.elements.refreshIntervalSelect.selectedIndex
                ].text;
                this.showToast(`Refresh interval set to ${intervalText}`, 'info');
            });
        }
        
        // Refresh now button
        if (this.elements.refreshNowBtn) {
            this.elements.refreshNowBtn.addEventListener('click', () => {
                this.manualRefresh();
            });
        }
    }
    
    /**
     * Update UI elements to match current state
     */
    updateUI() {
        // Update last refreshed time
        this.updateLastRefreshedTime();
        
        // Show/hide real-time indicator
        if (this.elements.realtimeIndicator) {
            this.elements.realtimeIndicator.style.display = 
                this.autoRefreshEnabled ? 'inline-flex' : 'none';
        }
    }
    
    /**
     * Start automatic refresh
     */
    startAutoRefresh() {
        this.stopAutoRefresh(); // Clear any existing timers
        
        // Set up refresh timers for each endpoint
        Object.keys(this.config.endpoints).forEach(key => {
            this.refreshTimers[key] = setInterval(() => {
                this.refreshData(key);
            }, this.refreshInterval);
        });
        
        // If no specific endpoints, use a general refresh timer
        if (Object.keys(this.config.endpoints).length === 0 && this.config.onRefresh) {
            this.refreshTimers['general'] = setInterval(() => {
                this.refreshAll();
            }, this.refreshInterval);
        }
    }
    
    /**
     * Stop automatic refresh
     */
    stopAutoRefresh() {
        // Clear all timers
        Object.values(this.refreshTimers).forEach(timer => clearInterval(timer));
        this.refreshTimers = {};
    }
    
    /**
     * Restart automatic refresh (after interval change)
     */
    restartAutoRefresh() {
        this.stopAutoRefresh();
        this.startAutoRefresh();
    }
    
    /**
     * Update the last refreshed time display
     */
    updateLastRefreshedTime() {
        if (this.elements.lastUpdatedTime) {
            const timeString = this.formatTime(this.lastRefreshed);
            
            // Add real-time indicator if auto-refresh is on
            if (this.autoRefreshEnabled) {
                this.elements.lastUpdatedTime.innerHTML = `${timeString} <span class="live-text">• live</span>`;
            } else {
                this.elements.lastUpdatedTime.textContent = timeString;
            }
        }
    }
    
    /**
     * Format a time string (just now, X minutes ago, etc.)
     */
    formatTime(date) {
        const now = new Date();
        const diffInSeconds = Math.floor((now - date) / 1000);
        
        if (diffInSeconds < 10) {
            return 'just now';
        } else if (diffInSeconds < 60) {
            return `${diffInSeconds} seconds ago`;
        } else if (diffInSeconds < 3600) {
            const minutes = Math.floor(diffInSeconds / 60);
            return `${minutes} minute${minutes !== 1 ? 's' : ''} ago`;
        } else {
            return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        }
    }
    
    /**
     * Manual refresh of all data
     */
    manualRefresh() {
        if (this.isRefreshing) return;
        
        // Set the button to loading state
        if (this.elements.refreshNowBtn) {
            this.elements.refreshNowBtn.classList.add('loading');
            this.elements.refreshNowBtn.disabled = true;
        }
        
        this.isRefreshing = true;
        
        // If we have specific endpoints, refresh each one
        if (Object.keys(this.config.endpoints).length > 0) {
            const refreshPromises = Object.keys(this.config.endpoints).map(key => 
                this.refreshData(key, true)
            );
            
            // When all refreshes complete
            Promise.all(refreshPromises)
                .finally(() => {
                    this.finishRefresh();
                });
        } 
        // Otherwise use the global refresh callback
        else if (this.config.onRefresh) {
            Promise.resolve(this.config.onRefresh())
                .finally(() => {
                    this.finishRefresh();
                });
        }
        // No refresh method configured
        else {
            console.warn('No refresh endpoints or callback configured');
            this.finishRefresh();
        }
    }
    
    /**
     * Finish a refresh operation
     */
    finishRefresh() {
        this.isRefreshing = false;
        this.lastRefreshed = new Date();
        this.updateLastRefreshedTime();
        
        // Reset the refresh button
        if (this.elements.refreshNowBtn) {
            setTimeout(() => {
                this.elements.refreshNowBtn.classList.remove('loading');
                this.elements.refreshNowBtn.disabled = false;
            }, 300);
        }
        
        // Show success toast
        this.showToast('Data refreshed successfully', 'success');
    }
    
    /**
     * Refresh data for a specific endpoint
     */
    refreshData(key, isManual = false) {
        if (!this.config.endpoints[key]) {
            console.warn(`No endpoint configured for key: ${key}`);
            return Promise.reject('No endpoint configured');
        }
        
        const endpoint = this.config.endpoints[key];
        
        // Add loading class to target elements
        if (endpoint.targetSelector) {
            document.querySelectorAll(endpoint.targetSelector).forEach(el => {
                el.classList.add('data-refreshing');
            });
        }
        
        return fetch(endpoint.url)
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                // Call the success handler if provided
                if (endpoint.onSuccess) {
                    endpoint.onSuccess(data);
                }
                
                // Show toast only for manual refreshes
                if (isManual && this.config.toastEnabled) {
                    this.showToast(endpoint.successMessage || 'Data refreshed successfully', 'success');
                }
                
                return data;
            })
            .catch(error => {
                console.error(`Error refreshing ${key}:`, error);
                
                // Call the error handler if provided
                if (endpoint.onError) {
                    endpoint.onError(error);
                }
                
                // Show toast for errors
                if (this.config.toastEnabled) {
                    this.showToast(endpoint.errorMessage || `Failed to refresh ${key}`, 'error');
                }
                
                throw error;
            })
            .finally(() => {
                // Remove loading class from target elements
                if (endpoint.targetSelector) {
                    document.querySelectorAll(endpoint.targetSelector).forEach(el => {
                        el.classList.remove('data-refreshing');
                    });
                }
                
                // Update last refreshed time
                this.lastRefreshed = new Date();
                this.updateLastRefreshedTime();
            });
    }
    
    /**
     * Refresh all data using the global refresh callback
     */
    refreshAll() {
        if (this.config.onRefresh) {
            // Add loading class to body to indicate refresh
            document.body.classList.add('refreshing-data');
            
            Promise.resolve(this.config.onRefresh())
                .finally(() => {
                    document.body.classList.remove('refreshing-data');
                    this.lastRefreshed = new Date();
                    this.updateLastRefreshedTime();
                });
        }
    }
    
    /**
     * Show a toast notification
     */
    showToast(message, type = 'info', duration = 3000) {
        if (!this.config.toastEnabled) return;
        
        // Get or create toast container
        let container = document.querySelector('.toast-container');
        if (!container) {
            container = document.createElement('div');
            container.className = 'toast-container';
            document.body.appendChild(container);
        }
        
        // Create toast element
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        
        // Add icon based on type
        let iconName;
        switch (type) {
            case 'success': iconName = 'check-circle'; break;
            case 'error': iconName = 'alert-circle'; break;
            default: iconName = 'info'; break;
        }
        
        toast.innerHTML = `
            <div class="toast-icon">
                <i data-feather="${iconName}"></i>
            </div>
            <div class="toast-content">${message}</div>
        `;
        
        // Add to container
        container.appendChild(toast);
        
        // Initialize feather icon
        if (window.feather) {
            feather.replace();
        }
        
        // Trigger animation
        setTimeout(() => toast.classList.add('show'), 10);
        
        // Remove after duration
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 300);
        }, duration);
    }
}
// Extend the DataRefreshManager with WebSocket support
class WebSocketRefreshManager extends DataRefreshManager {
    constructor(config = {}) {
        // Default WebSocket configuration
        const wsConfig = {
            wsUrl: null,                    // WebSocket URL
            wsEnabled: true,                // WebSocket enabled by default
            wsReconnectDelay: 5000,         // Reconnect delay in ms
            wsEvents: {},                   // Event handlers
            ...config
        };
        
        super(wsConfig);
        
        // WebSocket state
        this.socket = null;
        this.wsConnected = false;
        this.wsReconnectTimer = null;
        
        // Initialize WebSocket if URL is provided
        if (this.config.wsUrl && this.config.wsEnabled) {
            this.initWebSocket();
        }
    }
    
    /**
     * Initialize WebSocket connection
     */
    initWebSocket() {
        if (!this.config.wsUrl) return;
        
        try {
            this.socket = new WebSocket(this.config.wsUrl);
            
            this.socket.onopen = () => {
                this.wsConnected = true;
                clearTimeout(this.wsReconnectTimer);
                console.log('WebSocket connected');
                this.showToast('Real-time updates connected', 'success');
                
                // Update UI to show connected state
                if (this.elements.realtimeIndicator) {
                    this.elements.realtimeIndicator.classList.add('connected');
                }
            };
            
            this.socket.onclose = () => {
                this.wsConnected = false;
                console.log('WebSocket disconnected');
                
                // Update UI to show disconnected state
                if (this.elements.realtimeIndicator) {
                    this.elements.realtimeIndicator.classList.remove('connected');
                }
                
                // Attempt to reconnect
                this.wsReconnectTimer = setTimeout(() => {
                    this.initWebSocket();
                }, this.config.wsReconnectDelay);
            };
            
            this.socket.onerror = (error) => {
                console.error('WebSocket error:', error);
            };
            
            this.socket.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    const eventType = data.type || data.event;
                    
                    // Handle the event if we have a handler for it
                    if (eventType && this.config.wsEvents[eventType]) {
                        this.config.wsEvents[eventType](data);
                        
                        // Update last refreshed time as we received new data
                        this.lastRefreshed = new Date();
                        this.updateLastRefreshedTime();
                    }
                } catch (e) {
                    console.error('Error processing WebSocket message:', e);
                }
            };
        } catch (e) {
            console.error('Error initializing WebSocket:', e);
        }
    }
    
    /**
     * Send a message over WebSocket
     */
    sendWsMessage(message) {
        if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
            console.warn('WebSocket not connected');
            return false;
        }
        
        try {
            this.socket.send(typeof message === 'string' ? message : JSON.stringify(message));
            return true;
        } catch (e) {
            console.error('Error sending WebSocket message:', e);
            return false;
        }
    }
}
// Initialize with WebSocket support
const refreshManager = new WebSocketRefreshManager({
    defaultInterval: 30000,
    endpoints: {
        // API endpoints as before
    },
    // WebSocket configuration
    wsUrl: 'ws://{{ request.host }}/ws',
    wsEvents: {
        // Define handlers for different event types
        'system_stats': function(data) {
            updateSystemMetrics(data);
        },
        'session_update': function(data) {
            // Update a single session
            updateSession(data.session);
        },
        'session_closed': function(data) {
            // Remove a session that was closed
            removeSession(data.session_id);
        }
    }
});
