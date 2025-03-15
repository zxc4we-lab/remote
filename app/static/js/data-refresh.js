/**
 * Data Refresh Manager
 * Handles automatic and manual data refresh across the application
 * Supports both AJAX polling and WebSockets
 */
class DataRefreshManager {
    constructor(config = {}) {
        // Configuration with defaults
        this.config = {
            defaultInterval: 30000,     // Default: 30 seconds
            endpoints: {},              // API endpoints to refresh
            onRefresh: null,            // Global refresh callback
            toastEnabled: true,         // Show toast notifications
            storageName: 'refreshSettings', // Local storage key
            wsEnabled: true,            // WebSocket enabled
            wsUrl: null,                // WebSocket URL (derived from current host if null)
            wsEvents: {},               // WebSocket event handlers
            ...config
        };
        
        // State
        this.autoRefreshEnabled = true;
        this.lastRefreshed = new Date();
        this.refreshInterval = this.config.defaultInterval;
        this.refreshTimers = {};
        this.isRefreshing = false;
        
        // WebSocket state
        this.socket = null;
        this.wsConnected = false;
        this.wsReconnectTimer = null;
        
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
        
        // Initialize WebSocket if enabled
        if (this.config.wsEnabled) {
            this.initWebSocket();
        }
        
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
            // Set initial value
            if (this.elements.refreshIntervalSelect.querySelector(`option[value="${this.refreshInterval}"]`)) {
                this.elements.refreshIntervalSelect.value = this.refreshInterval;
            }
            
            this.elements.refreshIntervalSelect.addEventListener('change', () => {
                this.refreshInterval = parseInt(this.elements.refreshIntervalSelect.value);
                this.saveSettings();
                
                if (this.autoRefreshEnabled) {
                    this.restartAutoRefresh();
                }
                
                // Update WebSocket if connected
                if (this.wsConnected && this.socket) {
                    this.socket.emit('set_refresh_interval', {
                        type: 'all',
                        interval: this.refreshInterval
                    });
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
            
            // Update connected status
            if (this.wsConnected) {
                this.elements.realtimeIndicator.classList.add('connected');
            } else {
                this.elements.realtimeIndicator.classList.remove('connected');
            }
        }
    }
    
    /**
     * Initialize WebSocket connection
     */
    initWebSocket() {
        // Determine WebSocket URL
        let wsUrl = this.config.wsUrl;
        if (!wsUrl) {
            // Auto-derive from current location
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const host = window.location.host;
            wsUrl = `${protocol}//${host}/socket.io/?EIO=4&transport=websocket`;
        }
        
        try {
            // Use Socket.IO client if available
            if (typeof io !== 'undefined') {
                this.socket = io();
                
                this.socket.on('connect', () => {
                    this.wsConnected = true;
                    console.log('WebSocket connected');
                    clearTimeout(this.wsReconnectTimer);
                    this.updateUI();
                });
                
                this.socket.on('disconnect', () => {
                    this.wsConnected = false;
                    console.log('WebSocket disconnected');
                    this.updateUI();
                });
                
                // Set up event handlers for data updates
                this.setupSocketEvents();
            } else {
                console.warn('Socket.IO not available, WebSocket functionality disabled');
            }
        } catch (e) {
            console.error('Error initializing WebSocket:', e);
        }
    }
    
    /**
     * Set up Socket.IO event handlers
     */
    setupSocketEvents() {
        if (!this.socket) return;
        
        // Set up handlers for system stats updates
        this.socket.on('system_stats', (data) => {
            console.log('Received system stats update:', data);
            this.lastRefreshed = new Date();
            this.updateLastRefreshedTime();
            
            // Call custom handler if provided
            if (this.config.wsEvents.system_stats) {
                this.config.wsEvents.system_stats(data);
            }
        });
        
        // Set up handlers for active sessions updates
        this.socket.on('active_sessions', (data) => {
            console.log('Received active sessions update:', data);
            this.lastRefreshed = new Date();
            this.updateLastRefreshedTime();
            
            // Call custom handler if provided
            if (this.config.wsEvents.active_sessions) {
                this.config.wsEvents.active_sessions(data);
            }
        });
        
        // Set up handlers for connections updates
        this.socket.on('connections', (data) => {
            console.log('Received connections update:', data);
            this.lastRefreshed = new Date();
            this.updateLastRefreshedTime();
            
            // Call custom handler if provided
            if (this.config.wsEvents.connections) {
                this.config.wsEvents.connections(data);
            }
        });
        
        // Set up generic handler for any other events
        this.socket.onAny((eventName, ...args) => {
            if (this.config.wsEvents[eventName]) {
                this.config.wsEvents[eventName](...args);
            }
        });
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
        
        // If WebSocket is connected, use it for refresh
        if (this.wsConnected && this.socket) {
            this.socket.emit('request_refresh', { type: 'all' });
            
            // Set a timeout to ensure we finish even if no response
            setTimeout(() => {
                this.finishRefresh();
            }, 2000);
            
            return;
        }
        
        // Otherwise use AJAX
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