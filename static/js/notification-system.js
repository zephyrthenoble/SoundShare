/**
 * Unified Notification System
 * Handles info, success, warning, error notifications with optional undo functionality
 * Supports stacking and custom actions
 */

class NotificationSystem {
    constructor() {
        this.notifications = new Map(); // Track active notifications by ID
        this.nextId = 1;
        this.container = null;
        this.initContainer();
    }

    initContainer() {
        // Create container if it doesn't exist
        this.container = document.getElementById('notification-container');
        if (!this.container) {
            this.container = document.createElement('div');
            this.container.id = 'notification-container';
            this.container.className = 'position-fixed';
            this.container.style.cssText = 'top: 20px; right: 20px; z-index: 1060; min-width: 350px; max-width: 400px;';
            document.body.appendChild(this.container);
        }
    }

    /**
     * Show a notification
     * @param {Object} options - Notification configuration
     * @param {string} options.type - 'info', 'success', 'warning', 'error'
     * @param {string} options.title - Notification title
     * @param {string} options.message - Notification message
     * @param {number} options.duration - Auto-dismiss after seconds (0 = no auto-dismiss)
     * @param {boolean} options.dismissible - Show close button
     * @param {Object} options.action - Optional action button
     * @param {string} options.action.label - Action button text
     * @param {Function} options.action.handler - Action button click handler
     * @param {boolean} options.action.isUndo - Whether this is an undo action (shows countdown)
     * @param {number} options.action.countdown - Countdown seconds for undo actions
     * @param {Function} options.action.onExpire - Called when countdown expires
     * @returns {string} Notification ID for later reference
     */
    show(options) {
        const id = `notification-${this.nextId++}`;
        
        const config = {
            type: 'info',
            title: '',
            message: '',
            duration: 0,
            dismissible: true,
            action: null,
            ...options
        };

        const notification = this.createNotification(id, config);
        this.container.appendChild(notification);
        
        // Track notification
        const notificationData = {
            id,
            element: notification,
            config,
            timer: null,
            countdownTimer: null
        };
        this.notifications.set(id, notificationData);

        // Trigger fade-in animation
        setTimeout(() => {
            notification.classList.add('show');
        }, 10);

        // Auto-dismiss timer
        if (config.duration > 0) {
            notificationData.timer = setTimeout(() => {
                this.dismiss(id);
            }, config.duration * 1000);
        }

        // Undo countdown timer
        if (config.action && config.action.isUndo && config.action.countdown) {
            this.startCountdown(id, config.action.countdown);
        }

        this.updatePositions();
        return id;
    }

    createNotification(id, config) {
        const notification = document.createElement('div');
        notification.id = id;
        notification.className = `alert alert-${this.getBootstrapType(config.type)} alert-dismissible fade mb-2`;
        notification.setAttribute('role', 'alert');

        const iconClass = this.getIconClass(config.type);
        const actionButton = config.action ? this.createActionButton(id, config.action) : '';
        const closeButton = config.dismissible ? `<button type="button" class="btn-close" onclick="notificationSystem.dismiss('${id}')"></button>` : '';

        notification.innerHTML = `
            <div class="d-flex align-items-start">
                <i class="fas ${iconClass} me-2 mt-1"></i>
                <div class="flex-grow-1">
                    ${config.title ? `<div class="fw-bold">${config.title}</div>` : ''}
                    ${config.message ? `<div>${config.message}</div>` : ''}
                    ${actionButton}
                </div>
                ${closeButton}
            </div>
        `;

        return notification;
    }

    createActionButton(notificationId, action) {
        const buttonId = `${notificationId}-action`;
        const countdownSpan = action.isUndo ? `<span id="${notificationId}-countdown">${action.countdown || 5}</span>` : '';
        const label = action.isUndo ? `${action.label || 'Undo'} (${countdownSpan}s)` : action.label;
        
        return `
            <button type="button" 
                    id="${buttonId}"
                    class="btn btn-sm btn-outline-${action.isUndo ? 'dark' : 'primary'} mt-2"
                    onclick="notificationSystem.handleAction('${notificationId}')">
                <i class="fas ${action.isUndo ? 'fa-undo' : 'fa-check'}"></i> ${label}
            </button>
        `;
    }

    startCountdown(notificationId, seconds) {
        const notificationData = this.notifications.get(notificationId);
        if (!notificationData) return;

        let remaining = seconds;
        const countdownElement = document.getElementById(`${notificationId}-countdown`);
        
        notificationData.countdownTimer = setInterval(() => {
            remaining--;
            if (countdownElement) {
                countdownElement.textContent = remaining;
            }
            
            if (remaining <= 0) {
                clearInterval(notificationData.countdownTimer);
                if (notificationData.config.action.onExpire) {
                    notificationData.config.action.onExpire();
                }
                this.dismiss(notificationId);
            }
        }, 1000);
    }

    handleAction(notificationId) {
        const notificationData = this.notifications.get(notificationId);
        if (!notificationData || !notificationData.config.action) return;

        // Clear countdown if this is an undo action
        if (notificationData.config.action.isUndo && notificationData.countdownTimer) {
            clearInterval(notificationData.countdownTimer);
        }

        // Call the action handler
        if (notificationData.config.action.handler) {
            notificationData.config.action.handler();
        }

        // Dismiss the notification
        this.dismiss(notificationId);
    }

    dismiss(notificationId) {
        const notificationData = this.notifications.get(notificationId);
        if (!notificationData) return;

        // Clear timers
        if (notificationData.timer) clearTimeout(notificationData.timer);
        if (notificationData.countdownTimer) clearInterval(notificationData.countdownTimer);

        // Fade out animation
        notificationData.element.classList.remove('show');
        
        // Remove from DOM after animation
        setTimeout(() => {
            if (notificationData.element.parentNode) {
                notificationData.element.parentNode.removeChild(notificationData.element);
            }
            this.notifications.delete(notificationId);
            this.updatePositions();
        }, 150);
    }

    dismissAll() {
        for (const [id] of this.notifications) {
            this.dismiss(id);
        }
    }

    updatePositions() {
        // Notifications automatically stack due to container layout
        // This method can be extended for custom positioning logic if needed
    }

    getBootstrapType(type) {
        const typeMap = {
            'info': 'info',
            'success': 'success', 
            'warning': 'warning',
            'error': 'danger'
        };
        return typeMap[type] || 'info';
    }

    getIconClass(type) {
        const iconMap = {
            'info': 'fa-info-circle',
            'success': 'fa-check-circle',
            'warning': 'fa-exclamation-triangle', 
            'error': 'fa-exclamation-circle'
        };
        return iconMap[type] || 'fa-info-circle';
    }

    // Convenience methods
    info(title, message, options = {}) {
        return this.show({ type: 'info', title, message, ...options });
    }

    success(title, message, options = {}) {
        return this.show({ type: 'success', title, message, ...options });
    }

    warning(title, message, options = {}) {
        return this.show({ type: 'warning', title, message, ...options });
    }

    error(title, message, options = {}) {
        return this.show({ type: 'error', title, message, ...options });
    }

    undo(title, message, undoHandler, onExpire, countdown = 5) {
        return this.show({
            type: 'warning',
            title,
            message,
            action: {
                label: 'Undo',
                handler: undoHandler,
                isUndo: true,
                countdown,
                onExpire
            }
        });
    }
}

// Global instance
const notificationSystem = new NotificationSystem();

// For backward compatibility and convenience
function showNotification(type, title, message, options = {}) {
    return notificationSystem.show({ type, title, message, ...options });
}

function showUndo(title, message, undoHandler, onExpire, countdown = 5) {
    return notificationSystem.undo(title, message, undoHandler, onExpire, countdown);
}
