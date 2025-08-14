// Shared Playlist Player JavaScript Library
// Common functionality for static and dynamic playlist info pages

class PlaylistPlayer {
    constructor() {
        // Global variables
        this.playlistId = null;
        this.playlist = null;
        this.songs = [];
        this.currentSongIndex = -1;
        this.isPlaying = false;
        this.isShuffleMode = false;
        this.isAutoplay = true;
        this.sessionHistory = [];
        this.playlistTracking = [];
        
        // Audio player
        this.audioPlayer = null;
        this.progressInterval = null;
    }

    // Initialize the player
    init(playlistId) {
        this.playlistId = playlistId;
        this.audioPlayer = document.getElementById('audioPlayer');
        this.setupAudioEventListeners();
        this.setupCollapseHandlers();
    }

    // Audio event listeners
    setupAudioEventListeners() {
        this.audioPlayer.addEventListener('loadedmetadata', () => {
            this.updateTimeDisplay();
        });
        
        this.audioPlayer.addEventListener('timeupdate', () => {
            this.updateProgressBar();
            this.updateTimeDisplay();
        });
        
        this.audioPlayer.addEventListener('ended', () => {
            this.onSongEnded();
        });
        
        this.audioPlayer.addEventListener('error', () => {
            console.error('Audio playback error');
            this.nextSong();
        });
    }

    // Setup collapse handlers for UI
    setupCollapseHandlers() {
        // History collapse handler
        const historyCollapse = document.getElementById('sessionHistoryCollapse');
        const historyChevron = document.getElementById('historyChevron');
        
        if (historyCollapse && historyChevron) {
            historyCollapse.addEventListener('show.bs.collapse', () => {
                historyChevron.classList.remove('fa-chevron-right');
                historyChevron.classList.add('fa-chevron-left');
            });
            
            historyCollapse.addEventListener('hide.bs.collapse', () => {
                historyChevron.classList.remove('fa-chevron-left');
                historyChevron.classList.add('fa-chevron-right');
            });
        }
        
        // Session history collapse handler for expanding playlist songs
        if (historyCollapse) {
            historyCollapse.addEventListener('hidden.bs.collapse', () => {
                document.getElementById('playlistSongsCol').className = 'col-lg-12';
            });
            
            historyCollapse.addEventListener('shown.bs.collapse', () => {
                document.getElementById('playlistSongsCol').className = 'col-lg-8';
            });
        }
    }

    // Media player controls
    togglePlayPause() {
        if (this.currentSongIndex === -1) {
            // Start playing first song
            this.playSong(0);
            return;
        }
        
        if (this.isPlaying) {
            this.pauseSong();
        } else {
            this.resumeSong();
        }
    }

    playSong(index) {
        if (index < 0 || index >= this.songs.length) return;
        
        const song = this.songs[index];
        this.currentSongIndex = index;
        
        // Update current song display
        document.getElementById('currentSongTitle').textContent = song.display_name;
        document.getElementById('currentSongArtist').textContent = song.artist || 'Unknown Artist';
        
        // Load and play audio
        this.audioPlayer.src = `/api/songs/${song.id}/stream`;
        this.audioPlayer.play();
        this.isPlaying = true;
        
        // Update play button
        document.getElementById('playPauseBtn').innerHTML = '<i class="fas fa-pause"></i>';
        
        // Enable controls
        this.enablePlayerControls();
        
        // Add to history
        this.addToSessionHistory(song);
        this.addToPlaylistTracking(song);
        
        // Update statistics
        this.updateStatistics();
        
        // Highlight current song
        this.highlightCurrentSong();
    }

    pauseSong() {
        this.audioPlayer.pause();
        this.isPlaying = false;
        document.getElementById('playPauseBtn').innerHTML = '<i class="fas fa-play"></i>';
    }

    resumeSong() {
        this.audioPlayer.play();
        this.isPlaying = true;
        document.getElementById('playPauseBtn').innerHTML = '<i class="fas fa-pause"></i>';
    }

    nextSong() {
        if (this.songs.length === 0) return;
        
        let nextIndex;
        
        if (this.isShuffleMode) {
            nextIndex = this.getNextShuffleSong();
        } else {
            nextIndex = (this.currentSongIndex + 1) % this.songs.length;
            if (nextIndex === 0) {
                // Reached end of playlist
                this.resetPlaylistTracking();
            }
        }
        
        this.playSong(nextIndex);
    }

    previousSong() {
        if (this.sessionHistory.length > 1) {
            // Remove current song from history
            this.sessionHistory.pop();
            
            // Get previous song
            const prevSong = this.sessionHistory[this.sessionHistory.length - 1];
            const prevIndex = this.songs.findIndex(s => s.id === prevSong.id);
            
            if (prevIndex !== -1) {
                this.currentSongIndex = prevIndex;
                this.playSong(prevIndex);
            }
        }
    }

    getNextShuffleSong() {
        // Get songs not yet played in this playlist cycle
        const unplayedSongs = this.songs.filter(song => 
            !this.playlistTracking.some(tracked => tracked.id === song.id)
        );
        
        if (unplayedSongs.length === 0) {
            // All songs played, reset and start over
            this.resetPlaylistTracking();
            return Math.floor(Math.random() * this.songs.length);
        }
        
        // Pick random unplayed song
        const randomUnplayed = unplayedSongs[Math.floor(Math.random() * unplayedSongs.length)];
        return this.songs.findIndex(song => song.id === randomUnplayed.id);
    }

    skipForward() {
        this.audioPlayer.currentTime = Math.min(this.audioPlayer.currentTime + 20, this.audioPlayer.duration);
    }

    skipBackward() {
        this.audioPlayer.currentTime = Math.max(this.audioPlayer.currentTime - 20, 0);
    }

    toggleShuffle() {
        this.isShuffleMode = !this.isShuffleMode;
        const shuffleBtn = document.getElementById('shuffleBtn');
        
        if (this.isShuffleMode) {
            shuffleBtn.classList.remove('btn-outline-secondary');
            shuffleBtn.classList.add('btn-secondary');
        } else {
            shuffleBtn.classList.remove('btn-secondary');
            shuffleBtn.classList.add('btn-outline-secondary');
        }
    }

    toggleAutoplay() {
        this.isAutoplay = !this.isAutoplay;
        const autoplayBtn = document.getElementById('autoplayBtn');
        
        if (this.isAutoplay) {
            autoplayBtn.classList.remove('btn-outline-secondary');
            autoplayBtn.classList.add('btn-secondary');
        } else {
            autoplayBtn.classList.remove('btn-secondary');
            autoplayBtn.classList.add('btn-outline-secondary');
        }
    }

    onSongEnded() {
        if (this.isAutoplay) {
            this.nextSong();
        } else {
            this.isPlaying = false;
            document.getElementById('playPauseBtn').innerHTML = '<i class="fas fa-play"></i>';
        }
    }

    // Session management
    addToSessionHistory(song) {
        this.sessionHistory.push({
            ...song,
            playedAt: new Date()
        });
        this.renderSessionHistory();
    }

    addToPlaylistTracking(song) {
        if (!this.playlistTracking.some(tracked => tracked.id === song.id)) {
            this.playlistTracking.push(song);
        }
    }

    resetPlaylistTracking() {
        this.playlistTracking = [];
        this.updateStatistics();
    }

    renderSessionHistory() {
        const container = document.getElementById('sessionHistory');
        
        if (this.sessionHistory.length === 0) {
            container.innerHTML = `
                <div class="text-center py-4 text-muted">
                    <i class="fas fa-history fa-2x mb-2"></i>
                    <p>No songs played yet</p>
                </div>
            `;
            return;
        }
        
        const recentHistory = this.sessionHistory.slice(-10).reverse(); // Show last 10, most recent first
        
        container.innerHTML = recentHistory.map((entry, index) => `
            <div class="d-flex align-items-center p-2 mb-2 border rounded">
                <div class="me-2">
                    <small class="badge bg-secondary">${this.sessionHistory.length - index}</small>
                </div>
                <div class="flex-grow-1">
                    <div class="fw-bold small">${entry.display_name}</div>
                    <small class="text-muted">${entry.artist || 'Unknown Artist'}</small>
                </div>
                <div class="ms-2">
                    <small class="text-muted">${entry.playedAt.toLocaleTimeString()}</small>
                </div>
            </div>
        `).join('');
    }

    updateStatistics() {
        document.getElementById('totalSongs').textContent = this.songs.length;
        document.getElementById('sessionPlayed').textContent = this.sessionHistory.length;
        document.getElementById('playlistProgress').textContent = `${this.playlistTracking.length}/${this.songs.length}`;
    }

    enablePlayerControls() {
        document.getElementById('prevBtn').disabled = this.sessionHistory.length <= 1;
        document.getElementById('skipBackBtn').disabled = false;
        document.getElementById('skipForwardBtn').disabled = false;
        document.getElementById('nextBtn').disabled = this.songs.length <= 1;
    }

    updateProgressBar() {
        if (this.audioPlayer.duration) {
            const progress = (this.audioPlayer.currentTime / this.audioPlayer.duration) * 100;
            document.getElementById('progressBar').style.width = progress + '%';
        }
    }

    updateTimeDisplay() {
        const current = SoundShareUtils.formatTime(this.audioPlayer.currentTime);
        const total = SoundShareUtils.formatTime(this.audioPlayer.duration);
        
        document.getElementById('currentTime').textContent = current;
        document.getElementById('totalTime').textContent = total;
    }

    highlightCurrentSong() {
        // Remove previous highlights
        document.querySelectorAll('.song-item').forEach(item => {
            item.classList.remove('bg-primary', 'text-white');
        });
        
        // Highlight current song
        if (this.currentSongIndex >= 0) {
            const currentItem = document.querySelector(`[data-index="${this.currentSongIndex}"]`);
            if (currentItem) {
                currentItem.classList.add('bg-primary', 'text-white');
            }
        }
    }

    // Utility functions
    updatePlaylistInfo() {
        document.getElementById('playlistTitle').textContent = this.playlist.name;
        document.getElementById('playlistDescription').textContent = this.playlist.description || 'No description';
    }

    // Song info modal functionality
    async showPlaylistSongInfo(songId) {
        try {
            const response = await fetch(`/api/songs/${songId}`);
            if (!response.ok) {
                throw new Error('Failed to load song details');
            }
            
            const song = await response.json();
            
            // Populate modal with song information
            document.getElementById('modalSongTitle').textContent = song.display_name || '-';
            document.getElementById('modalSongArtist').textContent = song.artist || '-';
            document.getElementById('modalSongAlbum').textContent = song.album || '-';
            document.getElementById('modalSongTrack').textContent = song.track_number ? `Track ${song.track_number}` : '-';
            document.getElementById('modalSongDuration').textContent = song.duration ? SoundShareUtils.formatTime(song.duration) : '-';
            document.getElementById('modalSongGenre').textContent = song.genre || '-';
            document.getElementById('modalSongYear').textContent = song.year || '-';
            
            // Audio features
            document.getElementById('modalSongEnergy').textContent = song.energy ? `${(song.energy * 100).toFixed(1)}%` : '-';
            document.getElementById('modalSongValence').textContent = song.valence ? `${(song.valence * 100).toFixed(1)}%` : '-';
            document.getElementById('modalSongDanceability').textContent = song.danceability ? `${(song.danceability * 100).toFixed(1)}%` : '-';
            
            // Tags
            const tagsContainer = document.getElementById('modalSongTags');
            if (song.tags && song.tags.length > 0) {
                tagsContainer.innerHTML = song.tags.map(tag => 
                    `<span class="badge bg-secondary me-1">${tag.name}</span>`
                ).join('');
            } else {
                tagsContainer.innerHTML = '<span class="text-muted">No tags</span>';
            }
            
            // File info
            document.getElementById('modalSongPath').textContent = song.file_path || '-';
            document.getElementById('modalSongSize').textContent = song.file_size ? this.formatFileSize(song.file_size) : '-';
            
            // Show modal
            const modal = new bootstrap.Modal(document.getElementById('songInfoModal'));
            modal.show();
            
        } catch (error) {
            console.error('Error loading song details:', error);
            alert('Error loading song details');
        }
    }

    // Format file size
    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    // Helper function to extract folder from file path
    getFolder(filePath) {
        if (!filePath) return '';
        const parts = filePath.split('/');
        if (parts.length > 1) {
            parts.pop(); // Remove filename
            return parts[parts.length - 1]; // Return last folder name
        }
        return '';
    }
}

// Create global instance
window.playlistPlayer = new PlaylistPlayer();

// Global functions for backward compatibility with onclick handlers
function togglePlayPause() { window.playlistPlayer.togglePlayPause(); }
function playSong(index) { window.playlistPlayer.playSong(index); }
function nextSong() { window.playlistPlayer.nextSong(); }
function previousSong() { window.playlistPlayer.previousSong(); }
function skipForward() { window.playlistPlayer.skipForward(); }
function skipBackward() { window.playlistPlayer.skipBackward(); }
function toggleShuffle() { window.playlistPlayer.toggleShuffle(); }
function toggleAutoplay() { window.playlistPlayer.toggleAutoplay(); }
function resetPlaylistTracking() { window.playlistPlayer.resetPlaylistTracking(); }
function showPlaylistSongInfo(songId) { window.playlistPlayer.showPlaylistSongInfo(songId); }
