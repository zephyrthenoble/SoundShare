/**
 * Song Management System for SoundShare
 * Handles song CRUD operations, filtering, and batch operations
 */

class SongManager {
    constructor() {
        this.songs = [];
        this.filteredSongs = [];
        this.tags = [];
        this.tagGroups = [];
        this.playlists = [];
        this.selectedSongs = new Set();
        this.batchSelectedTags = new Set();
        this.undoTimeout = null;
        this.lastDeletedSong = null;
        
        // Tag filtering state
        this.includeTags = new Set();
        this.excludeTags = new Set();
        this.includeTagGroups = new Set();
        this.excludeTagGroups = new Set();
        
        this.init();
    }

    init() {
        // Initialize page when DOM is loaded
        if (document.readyState === "loading") {
            document.addEventListener("DOMContentLoaded", () => this.initializePage());
        } else {
            this.initializePage();
        }
    }

    initializePage() {
        this.setupEventListeners();
        this.loadData();
    }

    setupEventListeners() {
        // Search input
        const searchInput = document.getElementById("searchInput");
        if (searchInput) {
            searchInput.addEventListener("input", () => this.applyFilters());
        }

        // Filter dropdowns
        const filters = ["artistFilter", "albumFilter", "folderFilter", "energyFilter", "valenceFilter", "danceabilityFilter", "durationFilter"];
        filters.forEach(filterId => {
            const element = document.getElementById(filterId);
            if (element) {
                element.addEventListener("change", () => this.applyFilters());
            }
        });

        // Select all checkbox
        const selectAllCheckbox = document.getElementById("selectAllCheckbox");
        if (selectAllCheckbox) {
            selectAllCheckbox.addEventListener("change", (e) => this.toggleSelectAll(e.target.checked));
        }
    }

    async loadData() {
        try {
            await Promise.all([
                this.loadSongs(),
                this.loadTags(),
                this.loadTagGroups(),
                this.loadPlaylists()
            ]);
            this.populateFilters();
            this.populateTagFilters();
            this.displaySongs();
        } catch (error) {
            notificationSystem.error("Error", "Failed to load data: " + error.message);
        }
    }

    async loadSongs() {
        try {
            const response = await fetch("/api/songs");
            if (!response.ok) throw new Error("Failed to fetch songs");
            this.songs = await response.json();
            this.filteredSongs = [...this.songs];
        } catch (error) {
            notificationSystem.error("Error", "Failed to load songs");
            throw error;
        }
    }

    async loadTags() {
        try {
            const response = await fetch("/api/tags");
            if (!response.ok) throw new Error("Failed to fetch tags");
            this.tags = await response.json();
        } catch (error) {
            notificationSystem.error("Error", "Failed to load tags");
            throw error;
        }
    }

    async loadTagGroups() {
        try {
            const response = await fetch("/api/groups/");
            if (!response.ok) throw new Error("Failed to fetch tag groups");
            this.tagGroups = await response.json();
        } catch (error) {
            notificationSystem.error("Error", "Failed to load tag groups");
            throw error;
        }
    }

    async loadPlaylists() {
        try {
            const response = await fetch("/api/playlists");
            if (!response.ok) throw new Error("Failed to fetch playlists");
            const allPlaylists = await response.json();
            this.playlists = allPlaylists.filter(p => p.type === "static");
        } catch (error) {
            notificationSystem.error("Error", "Failed to load playlists");
            throw error;
        }
    }

    populateFilters() {
        // Populate artist filter
        const artists = [...new Set(this.songs.map(s => s.artist).filter(Boolean))].sort();
        this.populateSelect("artistFilter", artists);

        // Populate album filter
        const albums = [...new Set(this.songs.map(s => s.album).filter(Boolean))].sort();
        this.populateSelect("albumFilter", albums);

        // Populate folder filter
        const folders = [...new Set(this.songs.map(s => s.folder_name).filter(Boolean))].sort();
        this.populateSelect("folderFilter", folders);
    }

    populateTagFilters() {
        // Populate tag filters
        this.populateSelect("includeTagSelect", this.tags.map(t => t.name).sort());
        this.populateSelect("excludeTagSelect", this.tags.map(t => t.name).sort());
        
        // Populate tag group filters
        this.populateSelect("includeTagGroupSelect", this.tagGroups.map(g => g.name).sort());
        this.populateSelect("excludeTagGroupSelect", this.tagGroups.map(g => g.name).sort());
    }

    populateSelect(selectId, options) {
        const select = document.getElementById(selectId);
        if (!select) return;

        // Keep the first option (usually "All ...")
        const firstOption = select.children[0];
        select.innerHTML = "";
        select.appendChild(firstOption);

        // Add new options
        options.forEach(option => {
            const optionElement = document.createElement("option");
            optionElement.value = option;
            optionElement.textContent = option;
            select.appendChild(optionElement);
        });
    }

    applyFilters() {
        const searchTerm = document.getElementById("searchInput")?.value.toLowerCase() || "";
        const artistFilter = document.getElementById("artistFilter")?.value || "";
        const albumFilter = document.getElementById("albumFilter")?.value || "";
        const folderFilter = document.getElementById("folderFilter")?.value || "";
        const energyFilter = document.getElementById("energyFilter")?.value || "";
        const valenceFilter = document.getElementById("valenceFilter")?.value || "";
        const danceabilityFilter = document.getElementById("danceabilityFilter")?.value || "";
        const durationFilter = document.getElementById("durationFilter")?.value || "";

        this.filteredSongs = this.songs.filter(song => {
            // Search term filter
            if (searchTerm) {
                const searchFields = [song.display_name, song.artist, song.album, song.genre].join(" ").toLowerCase();
                if (!searchFields.includes(searchTerm)) return false;
            }

            // Dropdown filters
            if (artistFilter && song.artist !== artistFilter) return false;
            if (albumFilter && song.album !== albumFilter) return false;
            if (folderFilter && song.folder_name !== folderFilter) return false;

            // Audio feature filters
            if (energyFilter) {
                const energy = song.energy || 0;
                if (energyFilter === "high" && energy < 0.7) return false;
                if (energyFilter === "medium" && (energy < 0.3 || energy >= 0.7)) return false;
                if (energyFilter === "low" && energy >= 0.3) return false;
            }

            if (valenceFilter) {
                const valence = song.valence || 0;
                if (valenceFilter === "positive" && valence < 0.7) return false;
                if (valenceFilter === "neutral" && (valence < 0.3 || valence >= 0.7)) return false;
                if (valenceFilter === "melancholy" && valence >= 0.3) return false;
            }

            if (danceabilityFilter) {
                const danceability = song.danceability || 0;
                if (danceabilityFilter === "high" && danceability < 0.7) return false;
                if (danceabilityFilter === "medium" && (danceability < 0.3 || danceability >= 0.7)) return false;
                if (danceabilityFilter === "low" && danceability >= 0.3) return false;
            }

            if (durationFilter) {
                const duration = song.duration || 0;
                if (durationFilter === "sound_effects" && duration >= 10) return false;
                if (durationFilter === "short" && duration >= 60) return false;
                if (durationFilter === "long" && duration < 60) return false;
            }

            // Tag filtering
            const songTags = song.tags || [];
            const songTagNames = songTags.map(t => t.name);
            
            // Include tags (AND) - song must have ALL included tags
            if (this.includeTags.size > 0) {
                const hasAllIncludeTags = Array.from(this.includeTags).every(tagName => 
                    songTagNames.includes(tagName)
                );
                if (!hasAllIncludeTags) return false;
            }
            
            // Exclude tags (NOT) - song must not have ANY excluded tags
            if (this.excludeTags.size > 0) {
                const hasAnyExcludeTag = Array.from(this.excludeTags).some(tagName => 
                    songTagNames.includes(tagName)
                );
                if (hasAnyExcludeTag) return false;
            }
            
            // Include tag groups (OR within group) - song must have at least one tag from ANY included group
            if (this.includeTagGroups.size > 0) {
                const hasTagFromAnyIncludeGroup = Array.from(this.includeTagGroups).some(groupName => {
                    const group = this.tagGroups.find(g => g.name === groupName);
                    if (!group) return false;
                    const groupTagNames = this.tags.filter(t => t.group_id === group.id).map(t => t.name);
                    return groupTagNames.some(tagName => songTagNames.includes(tagName));
                });
                if (!hasTagFromAnyIncludeGroup) return false;
            }
            
            // Exclude tag groups (NOT any in group) - song must not have ANY tag from excluded groups
            if (this.excludeTagGroups.size > 0) {
                const hasTagFromAnyExcludeGroup = Array.from(this.excludeTagGroups).some(groupName => {
                    const group = this.tagGroups.find(g => g.name === groupName);
                    if (!group) return false;
                    const groupTagNames = this.tags.filter(t => t.group_id === group.id).map(t => t.name);
                    return groupTagNames.some(tagName => songTagNames.includes(tagName));
                });
                if (hasTagFromAnyExcludeGroup) return false;
            }

            return true;
        });

        this.displaySongs();
        this.updateFilteredSongCount();
    }

    // Tag filtering methods
    addIncludeTag() {
        const select = document.getElementById("includeTagSelect");
        if (!select || !select.value) return;
        
        const tagName = select.value;
        this.includeTags.add(tagName);
        this.renderTagFilter("includeTags", this.includeTags, this.removeIncludeTag.bind(this));
        select.value = "";
        this.applyFilters();
    }
    
    addExcludeTag() {
        const select = document.getElementById("excludeTagSelect");
        if (!select || !select.value) return;
        
        const tagName = select.value;
        this.excludeTags.add(tagName);
        this.renderTagFilter("excludeTags", this.excludeTags, this.removeExcludeTag.bind(this));
        select.value = "";
        this.applyFilters();
    }
    
    addIncludeTagGroup() {
        const select = document.getElementById("includeTagGroupSelect");
        if (!select || !select.value) return;
        
        const groupName = select.value;
        this.includeTagGroups.add(groupName);
        this.renderTagGroupFilter("includeTagGroups", this.includeTagGroups, this.removeIncludeTagGroup.bind(this));
        select.value = "";
        this.applyFilters();
    }
    
    addExcludeTagGroup() {
        const select = document.getElementById("excludeTagGroupSelect");
        if (!select || !select.value) return;
        
        const groupName = select.value;
        this.excludeTagGroups.add(groupName);
        this.renderTagGroupFilter("excludeTagGroups", this.excludeTagGroups, this.removeExcludeTagGroup.bind(this));
        select.value = "";
        this.applyFilters();
    }
    
    removeIncludeTag(tagName) {
        this.includeTags.delete(tagName);
        this.renderTagFilter("includeTags", this.includeTags, this.removeIncludeTag.bind(this));
        this.applyFilters();
    }
    
    removeExcludeTag(tagName) {
        this.excludeTags.delete(tagName);
        this.renderTagFilter("excludeTags", this.excludeTags, this.removeExcludeTag.bind(this));
        this.applyFilters();
    }
    
    removeIncludeTagGroup(groupName) {
        this.includeTagGroups.delete(groupName);
        this.renderTagGroupFilter("includeTagGroups", this.includeTagGroups, this.removeIncludeTagGroup.bind(this));
        this.applyFilters();
    }
    
    removeExcludeTagGroup(groupName) {
        this.excludeTagGroups.delete(groupName);
        this.renderTagGroupFilter("excludeTagGroups", this.excludeTagGroups, this.removeExcludeTagGroup.bind(this));
        this.applyFilters();
    }
    
    renderTagFilter(containerId, tagSet, removeCallback) {
        const container = document.getElementById(containerId);
        if (!container) return;
        
        const isInclude = containerId === "includeTags";
        const methodName = isInclude ? "removeIncludeTag" : "removeExcludeTag";
        
        container.innerHTML = Array.from(tagSet).map(tagName => `
            <span class="badge ${isInclude ? 'bg-success' : 'bg-danger'} d-flex align-items-center gap-1">
                <i class="fas fa-tag"></i>
                ${tagName}
                <button type="button" class="btn-close btn-close-white ms-1" 
                        style="font-size: 0.6em;" onclick="songManager.${methodName}('${tagName}')" 
                        title="Remove tag"></button>
            </span>
        `).join('');
    }
    
    renderTagGroupFilter(containerId, groupSet, removeCallback) {
        const container = document.getElementById(containerId);
        if (!container) return;
        
        const isInclude = containerId === "includeTagGroups";
        const methodName = isInclude ? "removeIncludeTagGroup" : "removeExcludeTagGroup";
        
        container.innerHTML = Array.from(groupSet).map(groupName => {
            const group = this.tagGroups.find(g => g.name === groupName);
            const color = group?.color || '#007bff';
            return `
                <span class="badge d-flex align-items-center gap-1" style="background-color: ${color}; opacity: ${isInclude ? '1' : '0.7'}">
                    <i class="fas fa-folder"></i>
                    ${groupName}
                    <button type="button" class="btn-close btn-close-white ms-1" 
                            style="font-size: 0.6em;" onclick="songManager.${methodName}('${groupName}')" 
                            title="Remove tag group"></button>
                </span>
            `;
        }).join('');
    }

    clearFilters() {
        // Clear search input
        const searchInput = document.getElementById("searchInput");
        if (searchInput) searchInput.value = "";

        // Reset all filter dropdowns to first option
        const filterIds = ["artistFilter", "albumFilter", "folderFilter", "energyFilter", "valenceFilter", "danceabilityFilter", "durationFilter"];
        filterIds.forEach(id => {
            const element = document.getElementById(id);
            if (element) element.selectedIndex = 0;
        });

        // Clear tag filters
        this.includeTags.clear();
        this.excludeTags.clear();
        this.includeTagGroups.clear();
        this.excludeTagGroups.clear();
        
        // Clear tag filter displays
        document.getElementById("includeTags").innerHTML = "";
        document.getElementById("excludeTags").innerHTML = "";
        document.getElementById("includeTagGroups").innerHTML = "";
        document.getElementById("excludeTagGroups").innerHTML = "";

        this.applyFilters();
    }

    displaySongs() {
        const tbody = document.querySelector("#songsTable tbody");
        if (!tbody) return;

        tbody.innerHTML = "";

        this.filteredSongs.forEach(song => {
            const row = this.createSongRow(song);
            tbody.appendChild(row);
        });

        this.updateBatchActionsDisplay();
    }

    createSongRow(song) {
        const row = document.createElement("tr");
        const isSelected = this.selectedSongs.has(song.id);
        
        row.innerHTML = `
            <td>
                <input type="checkbox" ${isSelected ? "checked" : ""} 
                       onchange="songManager.toggleSongSelection(${song.id}, this.checked)">
            </td>
            <td>
                <div class="d-flex align-items-center">
                    <div class="flex-grow-1">
                        <div class="fw-bold">${this.escapeHtml(song.display_name)}</div>
                        <div class="text-muted small">${this.escapeHtml(song.artist || "Unknown Artist")}</div>
                        <audio controls class="w-100 mt-1" style="height: 32px;">
                            <source src="/api/songs/${song.id}/stream" type="audio/mpeg">
                            Your browser does not support the audio element.
                        </audio>
                    </div>
                    <div class="btn-group-vertical ms-2">
                        <button class="btn btn-sm btn-outline-primary" onclick="songManager.editSong(${song.id})" title="Edit">
                            <i class="fas fa-edit"></i>
                        </button>
                        <button class="btn btn-sm btn-outline-success" onclick="songManager.openTagModal(${song.id})" title="Tags">
                            <i class="fas fa-tags"></i>
                        </button>
                        <button class="btn btn-sm btn-outline-info" onclick="songManager.openPlaylistModal(${song.id})" title="Add to Playlist">
                            <i class="fas fa-list"></i>
                        </button>
                        <button class="btn btn-sm btn-outline-danger" onclick="songManager.deleteSong(${song.id})" title="Delete">
                            <i class="fas fa-trash"></i>
                        </button>
                    </div>
                </div>
            </td>
            <td>${this.escapeHtml(song.folder_name || "")}</td>
            <td>${this.escapeHtml(song.album || "")}</td>
            <td>${song.track_number || ""}</td>
            <td>${SoundShareUtils.formatDuration(song.duration)}</td>
            <td>${this.formatMoodInfo(song)}</td>
        `;

        return row;
    }

    formatMoodInfo(song) {
        const features = [];
        if (song.energy !== null) features.push(`Energy: ${Math.round(song.energy * 100)}%`);
        if (song.valence !== null) features.push(`Mood: ${Math.round(song.valence * 100)}%`);
        if (song.danceability !== null) features.push(`Dance: ${Math.round(song.danceability * 100)}%`);
        return features.join("<br>");
    }

    escapeHtml(unsafe) {
        if (!unsafe) return "";
        return unsafe
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    updateFilteredSongCount() {
        const countElement = document.getElementById("filteredSongCount");
        if (countElement) {
            const count = this.filteredSongs.length;
            countElement.textContent = `${count} song${count === 1 ? "" : "s"}`;
        }
    }

    // Selection Management
    toggleSongSelection(songId, selected) {
        if (selected) {
            this.selectedSongs.add(songId);
        } else {
            this.selectedSongs.delete(songId);
        }
        this.updateBatchActionsDisplay();
        this.updateSelectAllCheckbox();
    }

    toggleSelectAll(selectAll) {
        this.filteredSongs.forEach(song => {
            if (selectAll) {
                this.selectedSongs.add(song.id);
            } else {
                this.selectedSongs.delete(song.id);
            }
        });
        this.displaySongs();
        this.updateBatchActionsDisplay();
    }

    selectAll() {
        const selectAllCheckbox = document.getElementById("selectAllCheckbox");
        if (selectAllCheckbox) {
            selectAllCheckbox.checked = true;
            this.toggleSelectAll(true);
        }
    }

    selectNone() {
        const selectAllCheckbox = document.getElementById("selectAllCheckbox");
        if (selectAllCheckbox) {
            selectAllCheckbox.checked = false;
            this.toggleSelectAll(false);
        }
    }

    invertSelection() {
        const newSelection = new Set();
        this.filteredSongs.forEach(song => {
            if (!this.selectedSongs.has(song.id)) {
                newSelection.add(song.id);
            }
        });
        this.selectedSongs = newSelection;
        this.displaySongs();
        this.updateBatchActionsDisplay();
        this.updateSelectAllCheckbox();
    }

    updateSelectAllCheckbox() {
        const selectAllCheckbox = document.getElementById("selectAllCheckbox");
        if (!selectAllCheckbox) return;

        const visibleSongIds = this.filteredSongs.map(s => s.id);
        const selectedVisibleSongs = visibleSongIds.filter(id => this.selectedSongs.has(id));

        if (selectedVisibleSongs.length === 0) {
            selectAllCheckbox.checked = false;
            selectAllCheckbox.indeterminate = false;
        } else if (selectedVisibleSongs.length === visibleSongIds.length) {
            selectAllCheckbox.checked = true;
            selectAllCheckbox.indeterminate = false;
        } else {
            selectAllCheckbox.checked = false;
            selectAllCheckbox.indeterminate = true;
        }
    }

    updateBatchActionsDisplay() {
        const batchActionsCard = document.getElementById("batchActionsCard");
        const selectedCount = document.getElementById("selectedCount");

        if (this.selectedSongs.size > 0) {
            if (batchActionsCard) batchActionsCard.style.display = "block";
            if (selectedCount) {
                selectedCount.textContent = `${this.selectedSongs.size} song${this.selectedSongs.size === 1 ? "" : "s"} selected`;
            }
        } else {
            if (batchActionsCard) batchActionsCard.style.display = "none";
        }

        this.updateSelectAllCheckbox();
    }

    // Song CRUD Operations
    editSong(songId) {
        const song = this.songs.find(s => s.id === songId);
        if (!song) return;

        const modal = modalManager.createFormModal(
            "Edit Song",
            [
                { type: "hidden", id: "songId", value: song.id },
                { type: "text", id: "displayName", label: "Display Name", value: song.display_name, required: true },
                { type: "text", id: "artist", label: "Artist", value: song.artist || "" },
                { type: "text", id: "album", label: "Album", value: song.album || "" },
                { type: "number", id: "year", label: "Year", value: song.year || "" },
                { type: "text", id: "genre", label: "Genre", value: song.genre || "" }
            ],
            (data) => this.updateSong(data)
        );
        modal.show();
    }

    async updateSong(data) {
        try {
            const response = await fetch(`/api/songs/${data.songId}`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    display_name: data.displayName,
                    artist: data.artist || null,
                    album: data.album || null,
                    year: data.year ? parseInt(data.year) : null,
                    genre: data.genre || null
                })
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || "Failed to update song");
            }

            notificationSystem.success("Success", "Song updated successfully");
            await this.loadSongs();
            this.applyFilters();
        } catch (error) {
            notificationSystem.error("Error", "Failed to update song: " + error.message);
        }
    }

    deleteSong(songId) {
        const song = this.songs.find(s => s.id === songId);
        if (!song) return;

        const modal = modalManager.createConfirmModal(
            "Delete Song",
            `Are you sure you want to delete "${song.display_name}"? This action cannot be undone.`,
            () => this.performDeleteSong(songId)
        );
        modal.show();
    }

    async performDeleteSong(songId) {
        try {
            const response = await fetch(`/api/songs/${songId}`, {
                method: "DELETE"
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || "Failed to delete song");
            }

            notificationSystem.success("Success", "Song deleted successfully");
            await this.loadSongs();
            this.applyFilters();
            this.selectedSongs.delete(songId);
            this.updateBatchActionsDisplay();
        } catch (error) {
            notificationSystem.error("Error", "Failed to delete song: " + error.message);
        }
    }

    // Global functions for onclick handlers
    clearFilters() {
        songManager.clearFilters();
    }

    toggleSelectAll() {
        const checkbox = document.getElementById("selectAllCheckbox");
        songManager.toggleSelectAll(checkbox.checked);
    }

    selectAll() {
        songManager.selectAll();
    }

    selectNone() {
        songManager.selectNone();
    }

    invertSelection() {
        songManager.invertSelection();
    }

    openBatchTagModal() {
        // TODO: Implement batch tag modal
        notificationSystem.info("Coming Soon", "Batch tagging functionality will be implemented next");
    }

    openBatchPlaylistModal() {
        // TODO: Implement batch playlist modal
        notificationSystem.info("Coming Soon", "Batch playlist functionality will be implemented next");
    }

    batchDeleteSongs() {
        // TODO: Implement batch delete
        notificationSystem.info("Coming Soon", "Batch delete functionality will be implemented next");
    }
}

// Global instance
const songManager = new SongManager();

// Export global functions for onclick handlers and dropdown changes
window.addIncludeTag = () => songManager.addIncludeTag();
window.addExcludeTag = () => songManager.addExcludeTag();
window.addIncludeTagGroup = () => songManager.addIncludeTagGroup();
window.addExcludeTagGroup = () => songManager.addExcludeTagGroup();
window.clearFilters = () => songManager.clearFilters();
window.toggleSelectAll = () => {
    const checkbox = document.getElementById("selectAllCheckbox");
    songManager.toggleSelectAll(checkbox.checked);
};
window.selectAll = () => songManager.selectAll();
window.selectNone = () => songManager.selectNone();
window.invertSelection = () => songManager.invertSelection();
window.openBatchTagModal = () => songManager.openBatchTagModal();
window.openBatchPlaylistModal = () => songManager.openBatchPlaylistModal();
window.batchDeleteSongs = () => songManager.batchDeleteSongs();
