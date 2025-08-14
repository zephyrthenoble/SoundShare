/**
 * SoundShare Media Player Component
 * Reusable media player for previewing songs across the application
 */
class SoundShareMediaPlayer {
    constructor() {
        this.audioPlayer = null;
        this.currentlyPlaying = null;
        this.onSongChangeCallback = null;
        this.init();
    }
    
    init() {
        // Create hidden audio element if it doesn't exist
        if (!document.getElementById('soundshare-audio-player')) {
            const audio = document.createElement('audio');
            audio.id = 'soundshare-audio-player';
            audio.style.display = 'none';
            document.body.appendChild(audio);
        }
        
        this.audioPlayer = document.getElementById('soundshare-audio-player');
    }
    
    /**
     * Play a song preview
     * @param {number} songId - The ID of the song to play
     * @param {Object} options - Additional options
     * @param {string} options.endpoint - Custom endpoint (default: '/api/songs/{songId}/preview')
     * @param {number} options.startTime - Start time in seconds (default: 0)
     */
    play(songId, options = {}) {
        // Stop current song if playing
        this.stop();
        
        const endpoint = options.endpoint || `/api/songs/${songId}/preview`;
        const startTime = options.startTime || 0;
        
        this.currentlyPlaying = songId;
        
        // Update UI to show playing state
        this.updatePlayButton(songId, 'playing');
        this.showProgressBar(songId);
        
        // Setup audio
        this.audioPlayer.src = endpoint;
        this.audioPlayer.currentTime = startTime;
        
        // Setup event listeners
        this.audioPlayer.onloadedmetadata = () => {
            this.updateTimeDisplay(songId);
        };
        
        this.audioPlayer.ontimeupdate = () => {
            this.updateProgress(songId);
            this.updateTimeDisplay(songId);
        };
        
        this.audioPlayer.onended = () => {
            this.stop();
        };
        
        this.audioPlayer.onerror = () => {
            console.error('Audio preview error for song', songId);
            this.stop();
        };
        
        // Play the audio
        this.audioPlayer.play().catch(error => {
            console.error('Failed to play audio:', error);
            this.stop();
        });
        
        // Call callback if set
        if (this.onSongChangeCallback) {
            this.onSongChangeCallback(songId, 'playing');
        }
    }
    
    /**
     * Stop the currently playing song
     * @param {number} specificSongId - Optional: stop only if this specific song is playing
     */
    stop(specificSongId = null) {
        if (specificSongId && this.currentlyPlaying !== specificSongId) {
            return;
        }
        
        if (!this.currentlyPlaying) return;
        
        const songId = this.currentlyPlaying;
        
        // Stop audio
        this.audioPlayer.pause();
        this.audioPlayer.src = '';
        
        // Update UI to show stopped state
        this.updatePlayButton(songId, 'stopped');
        this.hideProgressBar(songId);
        
        // Call callback if set
        if (this.onSongChangeCallback) {
            this.onSongChangeCallback(songId, 'stopped');
        }
        
        this.currentlyPlaying = null;
    }
    
    /**
     * Toggle play/pause for a song
     * @param {number} songId - The ID of the song to toggle
     * @param {Object} options - Additional options (same as play method)
     */
    toggle(songId, options = {}) {
        if (this.currentlyPlaying === songId) {
            this.stop();
        } else {
            this.play(songId, options);
        }
    }
    
    /**
     * Check if a song is currently playing
     * @param {number} songId - The ID of the song to check
     * @returns {boolean}
     */
    isPlaying(songId = null) {
        if (songId) {
            return this.currentlyPlaying === songId;
        }
        return this.currentlyPlaying !== null;
    }
    
    /**
     * Get the currently playing song ID
     * @returns {number|null}
     */
    getCurrentSong() {
        return this.currentlyPlaying;
    }
    
    /**
     * Set a callback function that gets called when song state changes
     * @param {Function} callback - Function(songId, state) where state is 'playing' or 'stopped'
     */
    onSongChange(callback) {
        this.onSongChangeCallback = callback;
    }
    
    /**
     * Update the play button UI
     * @param {number} songId - The song ID
     * @param {string} state - 'playing' or 'stopped'
     */
    updatePlayButton(songId, state) {
        const btn = document.getElementById(`play-btn-${songId}`);
        if (!btn) return;
        
        if (state === 'playing') {
            btn.innerHTML = '<i class="fas fa-pause"></i>';
            btn.classList.remove('btn-outline-primary');
            btn.classList.add('btn-primary');
            btn.title = 'Pause Preview';
        } else {
            btn.innerHTML = '<i class="fas fa-play"></i>';
            btn.classList.remove('btn-primary');
            btn.classList.add('btn-outline-primary');
            btn.title = 'Play Preview';
        }
    }
    
    /**
     * Show the progress bar for a song
     * @param {number} songId - The song ID
     */
    showProgressBar(songId) {
        const progress = document.getElementById(`progress-${songId}`);
        if (progress) {
            progress.style.display = 'block';
        }
    }
    
    /**
     * Hide the progress bar for a song
     * @param {number} songId - The song ID
     */
    hideProgressBar(songId) {
        const progress = document.getElementById(`progress-${songId}`);
        if (progress) {
            progress.style.display = 'none';
            // Reset progress bar
            const progressBar = progress.querySelector('.progress-bar');
            if (progressBar) {
                progressBar.style.width = '0%';
            }
        }
    }
    
    /**
     * Update the progress bar for a song
     * @param {number} songId - The song ID
     */
    updateProgress(songId) {
        if (!this.audioPlayer.duration) return;
        
        const progress = (this.audioPlayer.currentTime / this.audioPlayer.duration) * 100;
        const progressBar = document.querySelector(`#progress-${songId} .progress-bar`);
        if (progressBar) {
            progressBar.style.width = progress + '%';
        }
    }
    
    /**
     * Update the time display for a song
     * @param {number} songId - The song ID
     */
    updateTimeDisplay(songId) {
        const currentTimeEl = document.getElementById(`current-time-${songId}`);
        const totalTimeEl = document.getElementById(`total-time-${songId}`);
        
        if (currentTimeEl) {
            currentTimeEl.textContent = SoundShareUtils.formatTime(this.audioPlayer.currentTime);
        }
        
        if (totalTimeEl) {
            totalTimeEl.textContent = SoundShareUtils.formatTime(this.audioPlayer.duration);
        }
    }
    
    /**
     * Generate HTML for media controls
     * @param {number} songId - The song ID
     * @param {Object} options - Configuration options
     * @param {boolean} options.showInfo - Show info button (default: true)
     * @param {boolean} options.showAdd - Show add to playlist button (default: false)
     * @param {string} options.addAction - Action for add button (default: 'addToPlaylist')
     * @param {string} options.infoAction - Action for info button (default: 'showSongInfo')
     * @param {string} options.size - Button size: 'sm', 'lg', or '' (default: 'sm')
     * @returns {string} HTML string for media controls
     */
    generateControls(songId, options = {}) {
        const showInfo = options.showInfo !== false;
        const showAdd = options.showAdd === true;
        const addAction = options.addAction || 'addToPlaylist';
        const infoAction = options.infoAction || 'showSongInfo';
        const size = options.size ? `btn-${options.size}` : 'btn-sm';
        
        return `
            <div class="media-controls">
                <div class="btn-group" role="group">
                    <button type="button" class="btn ${size} btn-outline-primary" 
                            onclick="mediaPlayer.toggle(${songId})" 
                            id="play-btn-${songId}" 
                            title="Play Preview">
                        <i class="fas fa-play"></i>
                    </button>
                    ${showInfo ? `
                        <button type="button" class="btn ${size} btn-outline-info" 
                                onclick="${infoAction}(${songId})" 
                                title="Song Info">
                            <i class="fas fa-info"></i>
                        </button>
                    ` : ''}
                    ${showAdd ? `
                        <button type="button" class="btn ${size} btn-outline-success" 
                                onclick="${addAction}(${songId})" 
                                title="Add to Playlist">
                            <i class="fas fa-plus"></i>
                        </button>
                    ` : ''}
                </div>
            </div>
        `;
    }
    
    /**
     * Generate HTML for progress bar
     * @param {number} songId - The song ID
     * @returns {string} HTML string for progress bar
     */
    generateProgressBar(songId) {
        return `
            <div class="preview-progress mt-2" id="progress-${songId}" style="display: none;">
                <div class="progress" style="height: 3px;">
                    <div class="progress-bar bg-primary" role="progressbar" style="width: 0%"></div>
                </div>
                <div class="d-flex justify-content-between small text-muted mt-1">
                    <span id="current-time-${songId}">0:00</span>
                    <span id="total-time-${songId}">0:00</span>
                </div>
            </div>
        `;
    }
    
    /**
     * Generate complete media player HTML for a song card
     * @param {number} songId - The song ID
     * @param {Object} options - Configuration options (same as generateControls)
     * @returns {string} Complete HTML string for media player
     */
    generatePlayer(songId, options = {}) {
        return `
            <div class="d-flex align-items-center gap-2">
                ${this.generateControls(songId, options)}
            </div>
            ${this.generateProgressBar(songId)}
        `;
    }
}

// Create global media player instance
const mediaPlayer = new SoundShareMediaPlayer();

// Make it globally available
window.mediaPlayer = mediaPlayer;

// Legacy function support for backward compatibility
function playPreview(songId) {
    mediaPlayer.toggle(songId);
}

function stopPreview(songId) {
    mediaPlayer.stop(songId);
}
