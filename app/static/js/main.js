// Theme switching functionality
document.addEventListener('DOMContentLoaded', () => {
    const themeSwitch = document.getElementById('theme-switch');
    const prefersDarkScheme = window.matchMedia('(prefers-color-scheme: dark)');
    
    // Set initial theme based on user preference or stored preference
    const currentTheme = localStorage.getItem('theme') || 
        (prefersDarkScheme.matches ? 'dark' : 'light');
    document.documentElement.setAttribute('data-theme', currentTheme);
    updateThemeButton(currentTheme);

    // Theme switch button click handler
    themeSwitch.addEventListener('click', () => {
        const currentTheme = document.documentElement.getAttribute('data-theme');
        const newTheme = currentTheme === 'light' ? 'dark' : 'light';
        
        document.documentElement.setAttribute('data-theme', newTheme);
        localStorage.setItem('theme', newTheme);
        updateThemeButton(newTheme);
    });

    // Update theme button text
    function updateThemeButton(theme) {
        const themeSwitch = document.getElementById('theme-switch');
        themeSwitch.textContent = theme === 'light' ? '🌙' : '☀️';
    }

    // Handle form submissions
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', (e) => {
            const submitButton = form.querySelector('button[type="submit"]');
            if (submitButton) {
                submitButton.disabled = true;
                submitButton.innerHTML = '<span class="spinner"></span> Processing...';
            }
        });
    });

    // Auto-hide alerts after 5 seconds
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            alert.style.opacity = '0';
            setTimeout(() => alert.remove(), 300);
        }, 5000);
    });
}); 

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
