// Common Playlist Edit JavaScript Functions
// These functions are shared between static and dynamic playlist edit pages

/**
 * Show song information in the modal
 * @param {number} songId - The ID of the song to show info for
 * @param {Array} allSongs - Array of all songs
 * @param {Array} includeTags - Array of included tag IDs (for dynamic playlists)
 * @param {Array} excludeTags - Array of excluded tag IDs (for dynamic playlists)
 */
function showSongInfo(songId, allSongs = window.allSongs, includeTags = [], excludeTags = []) {
    const song = allSongs.find(s => s.id === songId);
    if (!song) return;
    
    // Store current modal song globally
    window.currentModalSong = song;
    
    // Populate modal with song information
    document.getElementById('modalSongTitle').textContent = song.display_name || '-';
    document.getElementById('modalSongArtist').textContent = song.artist || '-';
    document.getElementById('modalSongAlbum').textContent = song.album || '-';
    document.getElementById('modalSongTrack').textContent = song.track_number ? `Track ${song.track_number}` : '-';
    document.getElementById('modalSongDuration').textContent = song.duration ? mediaPlayer.formatTime(song.duration) : '-';
    
    // Audio features
    document.getElementById('modalSongEnergy').textContent = song.energy ? `${(song.energy * 100).toFixed(1)}%` : '-';
    document.getElementById('modalSongValence').textContent = song.valence ? `${(song.valence * 100).toFixed(1)}%` : '-';
    document.getElementById('modalSongDanceability').textContent = song.danceability ? `${(song.danceability * 100).toFixed(1)}%` : '-';
    
    // Tags
    const tagsContainer = document.getElementById('modalSongTags');
    if (song.tags && song.tags.length > 0) {
        tagsContainer.innerHTML = song.tags.map(tag => {
            let badgeClass = 'bg-secondary';
            if (includeTags && includeTags.includes && includeTags.includes(tag.id)) badgeClass = 'bg-success';
            if (excludeTags && excludeTags.includes && excludeTags.includes(tag.id)) badgeClass = 'bg-danger';
            return `<span class="badge ${badgeClass} me-1">${tag.name}</span>`;
        }).join('');
    } else {
        tagsContainer.innerHTML = '<span class="text-muted">No tags</span>';
    }
    
    // File information
    document.getElementById('modalSongPath').textContent = song.file_path || '-';
    document.getElementById('modalSongSize').textContent = song.file_size ? formatFileSize(song.file_size) : '-';
    
    // Show modal
    const modal = new bootstrap.Modal(document.getElementById('songPreviewModal'));
    modal.show();
}

/**
 * Format file size in human readable format
 * @param {number} bytes - File size in bytes
 * @returns {string} Formatted file size
 */
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

/**
 * Helper function to extract folder name from file path
 * @param {string} filePath - Full file path
 * @returns {string} Folder name
 */
function getFolder(filePath) {
    if (!filePath) return '';
    const parts = filePath.split('/');
    return parts.length > 1 ? parts[parts.length - 2] : '';
}

/**
 * Setup collapse toggle icons for card sections
 * @param {Array} sections - Array of section objects with sectionId and toggleId
 */
function setupCollapseToggles(sections = []) {
    sections.forEach(({ sectionId, toggleId }) => {
        const section = document.getElementById(sectionId);
        if (!section) return;
        
        section.addEventListener('shown.bs.collapse', function () {
            const toggle = document.getElementById(toggleId);
            if (toggle) toggle.className = 'fas fa-chevron-up';
        });
        
        section.addEventListener('hidden.bs.collapse', function () {
            const toggle = document.getElementById(toggleId);
            if (toggle) toggle.className = 'fas fa-chevron-down';
        });
    });
}

/**
 * Generate HTML for a song tag with appropriate styling
 * @param {Object} tag - Tag object with id and name
 * @param {Array} includeTags - Array of included tag IDs
 * @param {Array} excludeTags - Array of excluded tag IDs
 * @returns {string} HTML string for tag badge
 */
function generateTagBadge(tag, includeTags = [], excludeTags = []) {
    let badgeClass = 'bg-secondary';
    if (includeTags.includes && includeTags.includes(tag.id)) badgeClass = 'bg-success';
    if (excludeTags.includes && excludeTags.includes(tag.id)) badgeClass = 'bg-danger';
    return `<span class="badge ${badgeClass} me-1" style="font-size: 0.65em;">${tag.name}</span>`;
}

/**
 * Generate HTML for a song card with media controls
 * @param {Object} song - Song object
 * @param {Object} options - Configuration options
 * @param {Array} options.includeTags - Array of included tag IDs
 * @param {Array} options.excludeTags - Array of excluded tag IDs
 * @param {boolean} options.showAdd - Show add to playlist button
 * @param {string} options.addAction - Action for add button
 * @param {string} options.infoAction - Action for info button
 * @param {number} options.index - Song index (for drag and drop)
 * @returns {string} HTML string for song card
 */
function generateSongCard(song, options = {}) {
    const {
        includeTags = [],
        excludeTags = [],
        showAdd = false,
        addAction = 'addToPlaylist',
        infoAction = 'showSongInfo',
        index = null
    } = options;
    
    const indexAttr = index !== null ? `data-index="${index}"` : '';
    
    return `
        <div class="song-item card mb-2" data-song-id="${song.id}" ${indexAttr}>
            <div class="card-body p-2">
                <div class="d-flex align-items-center">
                    <div class="flex-grow-1">
                        <div class="fw-bold">${song.display_name}</div>
                        <div class="text-muted small">${song.album || 'Unknown Album'} • ${getFolder(song.file_path) || 'Unknown Folder'}</div>
                        ${song.tags && song.tags.length > 0 ? `
                            <div class="mt-1">
                                ${song.tags.map(tag => generateTagBadge(tag, includeTags, excludeTags)).join('')}
                            </div>
                        ` : ''}
                    </div>
                    ${mediaPlayer.generatePlayer(song.id, { 
                        showInfo: true, 
                        showAdd: showAdd, 
                        addAction: addAction, 
                        infoAction: infoAction 
                    })}
                </div>
            </div>
        </div>
    `;
}

/**
 * Update playlist statistics in the options panel
 * @param {Object} stats - Statistics object
 * @param {number} stats.songCount - Number of songs
 * @param {number} stats.totalDuration - Total duration in seconds
 * @param {number} stats.matchingCount - Number of matching songs (for dynamic playlists)
 */
function updatePlaylistStats(stats) {
    const songCountEl = document.getElementById('statsSongCount');
    const durationEl = document.getElementById('statsTotalDuration');
    const matchingCountEl = document.getElementById('statsMatchingCount');
    
    if (songCountEl) {
        songCountEl.textContent = stats.songCount || 0;
    }
    
    if (durationEl) {
        durationEl.textContent = SoundShareUtils.formatDuration(stats.totalDuration || 0);
    }
    
    if (matchingCountEl && stats.matchingCount !== undefined) {
        matchingCountEl.textContent = stats.matchingCount || 0;
    }
}

/**
 * Generic export playlist function (to be overridden by specific implementations)
 */
function exportPlaylist() {
    alert('Export functionality coming soon!');
}

/**
 * Update playback settings (to be overridden by specific implementations)
 */
function updatePlaybackSettings() {
    // This function should be overridden in specific playlist pages
    console.log('updatePlaybackSettings called - should be overridden');
}
