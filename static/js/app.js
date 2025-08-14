// Global JavaScript utilities for SoundShare

// Utility functions
class SoundShareUtils {
    static formatDuration(seconds) {
        if (!seconds || isNaN(seconds) || seconds < 0) return '--:--';
        
        const hours = Math.floor(seconds / 3600);
        const mins = Math.floor((seconds % 3600) / 60);
        const secs = Math.floor(seconds % 60);
        
        if (hours > 0) {
            return `${hours}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
        } else {
            return `${mins}:${secs.toString().padStart(2, '0')}`;
        }
    }
    
    // Alias for compatibility with existing code
    static formatTime(seconds) {
        return this.formatDuration(seconds);
    }
    
    static formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }
    
    static getMoodColor(value) {
        if (value >= 0.7) return 'success';
        if (value >= 0.4) return 'warning';
        return 'danger';
    }
    
    static getMoodIndicator(value) {
        const color = this.getMoodColor(value);
        return `<span class="mood-indicator mood-${color === 'success' ? 'high' : color === 'warning' ? 'medium' : 'low'}"></span>`;
    }
}

// Audio player management
class AudioPlayer {
    constructor() {
        this.currentAudio = null;
        this.currentSegment = null;
    }
    
    play(src, onEnd = null) {
        this.stop();
        this.currentAudio = new Audio(src);
        this.currentAudio.play();
        
        if (onEnd) {
            this.currentAudio.addEventListener('ended', onEnd);
        }
        
        return this.currentAudio;
    }
    
    stop() {
        if (this.currentAudio) {
            this.currentAudio.pause();
            this.currentAudio = null;
        }
    }
    
    playSegment(songId, segment, callback = null) {
        const src = `/api/songs/${songId}/preview?segment=${segment}`;
        this.currentSegment = segment;
        return this.play(src, callback);
    }
}

// Global audio player instance
window.audioPlayer = new AudioPlayer();

// Notification system
class NotificationManager {
    static show(message, type = 'info', duration = 3000) {
        const notification = document.createElement('div');
        notification.className = `alert alert-${type} alert-dismissible fade show position-fixed`;
        notification.style.cssText = `
            top: 20px;
            right: 20px;
            z-index: 9999;
            max-width: 400px;
        `;
        
        notification.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        document.body.appendChild(notification);
        
        setTimeout(() => {
            if (notification.parentNode) {
                notification.remove();
            }
        }, duration);
    }
    
    static success(message) {
        this.show(message, 'success');
    }
    
    static error(message) {
        this.show(message, 'danger');
    }
    
    static warning(message) {
        this.show(message, 'warning');
    }
    
    static info(message) {
        this.show(message, 'info');
    }
}

// Global notification manager
window.notify = NotificationManager;

// API helper functions
class APIClient {
    static async request(url, options = {}) {
        const defaultOptions = {
            headers: {
                'Content-Type': 'application/json',
            },
        };
        
        const config = { ...defaultOptions, ...options };
        
        try {
            const response = await fetch(url, config);
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            return await response.json();
        } catch (error) {
            console.error('API request failed:', error);
            throw error;
        }
    }
    
    static async get(url) {
        return this.request(url);
    }
    
    static async post(url, data) {
        return this.request(url, {
            method: 'POST',
            body: JSON.stringify(data),
        });
    }
    
    static async put(url, data) {
        return this.request(url, {
            method: 'PUT',
            body: JSON.stringify(data),
        });
    }
    
    static async delete(url) {
        return this.request(url, {
            method: 'DELETE',
        });
    }
    
    static async upload(url, formData) {
        const response = await fetch(url, {
            method: 'POST',
            body: formData,
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        return await response.json();
    }
}

// Global API client
window.api = APIClient;

// Form validation helpers
class FormValidator {
    static validateRequired(value, fieldName) {
        if (!value || value.trim() === '') {
            throw new Error(`${fieldName} is required`);
        }
        return true;
    }
    
    static validateEmail(email) {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!emailRegex.test(email)) {
            throw new Error('Please enter a valid email address');
        }
        return true;
    }
    
    static validateFileType(file, allowedTypes) {
        if (!allowedTypes.includes(file.type)) {
            throw new Error(`File type ${file.type} is not allowed`);
        }
        return true;
    }
    
    static validateFileSize(file, maxSizeInMB) {
        const maxSizeInBytes = maxSizeInMB * 1024 * 1024;
        if (file.size > maxSizeInBytes) {
            throw new Error(`File size must be less than ${maxSizeInMB}MB`);
        }
        return true;
    }
}

// Global form validator
window.validator = FormValidator;

// Loading state management
class LoadingManager {
    static show(element, message = 'Loading...') {
        element.classList.add('loading');
        
        const loader = document.createElement('div');
        loader.className = 'loading-overlay d-flex justify-content-center align-items-center';
        loader.style.cssText = `
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(255, 255, 255, 0.8);
            z-index: 1000;
        `;
        
        loader.innerHTML = `
            <div class="text-center">
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
                <div class="mt-2">${message}</div>
            </div>
        `;
        
        element.style.position = 'relative';
        element.appendChild(loader);
    }
    
    static hide(element) {
        element.classList.remove('loading');
        const loader = element.querySelector('.loading-overlay');
        if (loader) {
            loader.remove();
        }
    }
}

// Global loading manager
window.loading = LoadingManager;

// Keyboard shortcuts
document.addEventListener('keydown', function(event) {
    // Ctrl/Cmd + K for search (if implemented)
    if ((event.ctrlKey || event.metaKey) && event.key === 'k') {
        event.preventDefault();
        const searchInput = document.querySelector('input[type="search"]');
        if (searchInput) {
            searchInput.focus();
        }
    }
    
    // Escape to close modals
    if (event.key === 'Escape') {
        const openModal = document.querySelector('.modal.show');
        if (openModal) {
            const modal = bootstrap.Modal.getInstance(openModal);
            if (modal) {
                modal.hide();
            }
        }
    }
});

// Initialize tooltips and popovers
document.addEventListener('DOMContentLoaded', function() {
    // Initialize Bootstrap tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Initialize Bootstrap popovers
    const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });
});

// Export utilities for use in other scripts
window.SoundShare = {
    utils: SoundShareUtils,
    audioPlayer: AudioPlayer,
    notify: NotificationManager,
    api: APIClient,
    validator: FormValidator,
    loading: LoadingManager
};
