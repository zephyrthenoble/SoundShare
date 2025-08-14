/**
 * Reusable Song Search and Display Component for SoundShare
 * Provides filtering, search, and display functionality that can be embedded in any page
 */

class SongSearchComponent {
    constructor(options = {}) {
        // Generate unique component ID
        this.componentId = 'songSearchComponent_' + Math.random().toString(36).substr(2, 9);
        
        this.options = {
            containerSelector: '#songSearchComponent',
            showBatchActions: true,
            showSongCount: true,
            showTagFilters: true,
            showAudioFeatures: true,
            tableId: 'songsTable',
            selectionMode: 'multiple', // 'multiple', 'single', 'none'
            onSelectionChange: null,
            onSongAction: null,
            additionalFilters: [], // Custom filter functions
            ...options
        };

        this.songs = [];
        this.filteredSongs = [];
        this.tags = [];
        this.tagGroups = [];
        this.playlists = [];
        this.selectedSongs = new Set();
        
        // Tag filtering state
        this.includeTags = new Set();
        this.excludeTags = new Set();
        this.includeTagGroups = new Set();
        this.excludeTagGroups = new Set();
        
        // Register this component globally for event handling
        window[this.componentId] = this;
        
        this.init();
    }

    init() {
        if (document.readyState === "loading") {
            document.addEventListener("DOMContentLoaded", () => this.initializeComponent());
        } else {
            this.initializeComponent();
        }
    }

    async initializeComponent() {
        await this.render();
        this.setupEventListeners();
        await this.loadData();
    }

    render() {
        const container = document.querySelector(this.options.containerSelector);
        if (!container) {
            console.error(`Container ${this.options.containerSelector} not found`);
            return;
        }

        container.innerHTML = this.getComponentHTML();
    }

    getComponentHTML() {
        return `
            <!-- Song Search and Filter Component -->
            ${this.options.showSongCount ? this.getSongCountHTML() : ''}
            ${this.getSearchFiltersHTML()}
            ${this.options.showBatchActions ? this.getBatchActionsHTML() : ''}
            ${this.getSongTableHTML()}
        `;
    }

    getSongCountHTML() {
        return `
            <div class="d-flex justify-content-between align-items-center mb-3">
                <div class="text-muted">
                    <span id="filteredSongCount">0 songs</span>
                </div>
            </div>
        `;
    }

    getSearchFiltersHTML() {
        return `
            <div class="card mb-4">
                <div class="card-body">
                    <!-- Basic Search and Filters -->
                    <div class="row">
                        <div class="col-md-4">
                            <div class="mb-3">
                                <label for="searchInput" class="form-label">Search Songs</label>
                                <input type="text" class="form-control" id="searchInput" placeholder="Search by name, artist, album...">
                            </div>
                        </div>
                        <div class="col-md-2">
                            <div class="mb-3">
                                <label for="artistFilter" class="form-label">Artist</label>
                                <select class="form-select" id="artistFilter">
                                    <option value="">All Artists</option>
                                </select>
                            </div>
                        </div>
                        <div class="col-md-2">
                            <div class="mb-3">
                                <label for="albumFilter" class="form-label">Album</label>
                                <select class="form-select" id="albumFilter">
                                    <option value="">All Albums</option>
                                </select>
                            </div>
                        </div>
                        <div class="col-md-2">
                            <div class="mb-3">
                                <label for="folderFilter" class="form-label">Folder</label>
                                <select class="form-select" id="folderFilter">
                                    <option value="">All Folders</option>
                                </select>
                            </div>
                        </div>
                        <div class="col-md-2">
                            <div class="mb-3">
                                <label class="form-label">&nbsp;</label>
                                <div>
                                    <button class="btn btn-outline-secondary w-100" onclick="window.${this.componentId}.clearFilters()">
                                        <i class="fas fa-times"></i> Clear
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    ${this.options.showAudioFeatures ? this.getAudioFeaturesHTML() : ''}
                    ${this.options.showTagFilters ? this.getTagFiltersHTML() : ''}
                </div>
            </div>
        `;
    }

    getAudioFeaturesHTML() {
        return `
            <!-- Audio Features -->
            <div class="row">
                <div class="col-md-3">
                    <div class="mb-3">
                        <label for="energyFilter" class="form-label">Energy Range</label>
                        <select class="form-select" id="energyFilter">
                            <option value="">Any Energy</option>
                            <option value="high">High Energy (70%+)</option>
                            <option value="medium">Medium Energy (30-70%)</option>
                            <option value="low">Low Energy (0-30%)</option>
                        </select>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="mb-3">
                        <label for="valenceFilter" class="form-label">Mood Range</label>
                        <select class="form-select" id="valenceFilter">
                            <option value="">Any Mood</option>
                            <option value="positive">Positive (70%+)</option>
                            <option value="neutral">Neutral (30-70%)</option>
                            <option value="melancholy">Melancholy (0-30%)</option>
                        </select>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="mb-3">
                        <label for="danceabilityFilter" class="form-label">Danceability</label>
                        <select class="form-select" id="danceabilityFilter">
                            <option value="">Any Danceability</option>
                            <option value="high">High Danceability (70%+)</option>
                            <option value="medium">Medium Danceability (30-70%)</option>
                            <option value="low">Low Danceability (0-30%)</option>
                        </select>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="mb-3">
                        <label for="durationFilter" class="form-label">Duration</label>
                        <select class="form-select" id="durationFilter">
                            <option value="">Any Duration</option>
                            <option value="sound_effects">Sound Effects (&lt; 10 seconds)</option>
                            <option value="short">Short (&lt; 1 minute)</option>
                            <option value="long">Songs (&gt; 1 minute)</option>
                        </select>
                    </div>
                </div>
            </div>
        `;
    }

    getTagFiltersHTML() {
        return `
            <!-- Tag Filtering Section -->
            <div class="row">
                <div class="col-md-6">
                    <div class="mb-3">
                        <label class="form-label">Include Tags (AND)</label>
                        <div class="d-flex flex-wrap gap-2 mb-2" id="includeTags">
                            <!-- Selected include tags will appear here -->
                        </div>
                        <select class="form-select" id="includeTagSelect">
                            <option value="">Add tag to include...</option>
                        </select>
                    </div>
                </div>
                <div class="col-md-6">
                    <div class="mb-3">
                        <label class="form-label">Exclude Tags (NOT)</label>
                        <div class="d-flex flex-wrap gap-2 mb-2" id="excludeTags">
                            <!-- Selected exclude tags will appear here -->
                        </div>
                        <select class="form-select" id="excludeTagSelect">
                            <option value="">Add tag to exclude...</option>
                        </select>
                    </div>
                </div>
            </div>
            
            <div class="row">
                <div class="col-md-6">
                    <div class="mb-3">
                        <label class="form-label">Include Tag Groups (OR within group)</label>
                        <div class="d-flex flex-wrap gap-2 mb-2" id="includeTagGroups">
                            <!-- Selected include tag groups will appear here -->
                        </div>
                        <select class="form-select" id="includeTagGroupSelect">
                            <option value="">Add tag group to include...</option>
                        </select>
                    </div>
                </div>
                <div class="col-md-6">
                    <div class="mb-3">
                        <label class="form-label">Exclude Tag Groups (NOT any in group)</label>
                        <div class="d-flex flex-wrap gap-2 mb-2" id="excludeTagGroups">
                            <!-- Selected exclude tag groups will appear here -->
                        </div>
                        <select class="form-select" id="excludeTagGroupSelect">
                            <option value="">Add tag group to exclude...</option>
                        </select>
                    </div>
                </div>
            </div>
        `;
    }

    getBatchActionsHTML() {
        if (this.options.selectionMode === 'none') return '';
        
        return `
            <!-- Batch Actions Section -->
            <div class="card mb-4" id="batchActionsCard" style="display: none;">
                <div class="card-body">
                    <div class="row align-items-center">
                        <div class="col-md-4">
                            <span id="selectedCount" class="fw-bold">0 songs selected</span>
                        </div>
                        <div class="col-md-8">
                            <div class="btn-group">
                                <button class="btn btn-success" onclick="window.${this.componentId}.openBatchTagModal()">
                                    <i class="fas fa-tags"></i> Batch Tag
                                </button>
                                <button class="btn btn-primary" onclick="window.${this.componentId}.openBatchPlaylistModal()">
                                    <i class="fas fa-list"></i> Add to Playlist
                                </button>
                                <button class="btn btn-danger" onclick="window.${this.componentId}.batchDeleteSongs()">
                                    <i class="fas fa-trash"></i> Delete Selected
                                </button>
                                <button class="btn btn-outline-primary" onclick="window.${this.componentId}.selectAll()">
                                    <i class="fas fa-check-square"></i> Select All
                                </button>
                                <button class="btn btn-outline-secondary" onclick="window.${this.componentId}.selectNone()">
                                    <i class="fas fa-square"></i> Select None
                                </button>
                                <button class="btn btn-outline-info" onclick="window.${this.componentId}.invertSelection()">
                                    <i class="fas fa-random"></i> Invert Selection
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    getSongTableHTML() {
        const selectionColumn = this.options.selectionMode !== 'none' ? `
            <th width="50">
                ${this.options.selectionMode === 'multiple' ? 
                    '<input type="checkbox" id="selectAllCheckbox">' : 
                    ''
                }
            </th>
        ` : '';

        return `
            <div class="row">
                <div class="col-12">
                    <div class="card">
                        <div class="card-body">
                            <table class="table table-striped" id="${this.options.tableId}">
                                <thead>
                                    <tr>
                                        ${selectionColumn}
                                        <th width="250">Name</th>
                                        <th width="140">Folder</th>
                                        <th width="160">Album</th>
                                        <th width="80">Track #</th>
                                        <th width="80">Duration</th>
                                        <th width="180">Mood</th>
                                        <th width="100">Actions</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <!-- Songs will be loaded here -->
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>
        `;
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

        // Tag filter dropdowns
        const tagFilters = {
            "includeTagSelect": () => this.addIncludeTag(),
            "excludeTagSelect": () => this.addExcludeTag(),
            "includeTagGroupSelect": () => this.addIncludeTagGroup(),
            "excludeTagGroupSelect": () => this.addExcludeTagGroup()
        };

        Object.entries(tagFilters).forEach(([id, handler]) => {
            const element = document.getElementById(id);
            if (element) {
                element.addEventListener("change", handler);
            }
        });

        // Select all checkbox
        const selectAllCheckbox = document.getElementById("selectAllCheckbox");
        if (selectAllCheckbox) {
            selectAllCheckbox.addEventListener("change", () => this.toggleSelectAll());
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
            if (window.notificationSystem) {
                notificationSystem.error("Error", "Failed to load data: " + error.message);
            } else {
                console.error("Failed to load data:", error);
            }
        }
    }

    async loadSongs() {
        try {
            const response = await fetch("/api/songs");
            if (!response.ok) throw new Error("Failed to fetch songs");
            this.songs = await response.json();
            this.filteredSongs = [...this.songs];
        } catch (error) {
            console.error("Failed to load songs:", error);
            throw error;
        }
    }

    async loadTags() {
        try {
            const response = await fetch("/api/tags");
            if (!response.ok) throw new Error("Failed to fetch tags");
            this.tags = await response.json();
        } catch (error) {
            console.error("Failed to load tags:", error);
            throw error;
        }
    }

    async loadTagGroups() {
        try {
            const response = await fetch("/api/groups/");
            if (!response.ok) throw new Error("Failed to fetch tag groups");
            this.tagGroups = await response.json();
        } catch (error) {
            console.error("Failed to load tag groups:", error);
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
            console.error("Failed to load playlists:", error);
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
            if (this.options.showTagFilters) {
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
            }

            // Apply additional custom filters
            if (this.options.additionalFilters.length > 0) {
                return this.options.additionalFilters.every(filter => filter(song));
            }

            return true;
        });

        this.displaySongs();
        this.updateFilteredSongCount();
    }

    displaySongs() {
        const tableBody = document.querySelector(`#${this.options.tableId} tbody`);
        if (!tableBody) return;

        tableBody.innerHTML = "";

        this.filteredSongs.forEach(song => {
            const row = this.createSongRow(song);
            tableBody.appendChild(row);
        });

        this.updateBatchActionsVisibility();
    }

    createSongRow(song) {
        const row = document.createElement("tr");
        
        let selectionCell = '';
        if (this.options.selectionMode === 'multiple') {
            const isSelected = this.selectedSongs.has(song.id);
            selectionCell = `
                <td>
                    <input type="checkbox" ${isSelected ? 'checked' : ''} 
                           onchange="window.${this.componentId}.toggleSongSelection(${song.id}, this.checked)">
                </td>
            `;
        } else if (this.options.selectionMode === 'single') {
            selectionCell = `
                <td>
                    <input type="radio" name="songSelection_${this.componentId}" value="${song.id}"
                           onchange="window.${this.componentId}.selectSingle(${song.id})">
                </td>
            `;
        }

        // Format duration
        const duration = song.duration ? SoundShareUtils.formatDuration(song.duration) : '--';
        
        // Format mood indicators
        const moodHTML = this.getMoodIndicators(song);

        row.innerHTML = `
            ${selectionCell}
            <td>
                <div class="d-flex align-items-center">
                    <div>
                        <div class="fw-bold">${song.display_name || song.filename}</div>
                        <small class="text-muted">${song.artist || 'Unknown Artist'}</small>
                    </div>
                </div>
            </td>
            <td>${song.folder_name || '--'}</td>
            <td>${song.album || '--'}</td>
            <td>${song.track_number || '--'}</td>
            <td>${duration}</td>
            <td>${moodHTML}</td>
            <td>
                <div class="btn-group btn-group-sm">
                    <button class="btn btn-outline-primary" onclick="window.${this.componentId}.playSong(${song.id})" title="Play">
                        <i class="fas fa-play"></i>
                    </button>
                    <button class="btn btn-outline-info" onclick="window.${this.componentId}.editSong(${song.id})" title="Edit">
                        <i class="fas fa-edit"></i>
                    </button>
                </div>
            </td>
        `;

        return row;
    }

    getMoodIndicators(song) {
        const energy = song.energy || 0;
        const valence = song.valence || 0;
        const danceability = song.danceability || 0;
        
        return `
            <div class="d-flex gap-1">
                <span class="badge bg-info" title="Energy: ${Math.round(energy * 100)}%">E</span>
                <span class="badge bg-warning" title="Valence: ${Math.round(valence * 100)}%">V</span>
                <span class="badge bg-success" title="Danceability: ${Math.round(danceability * 100)}%">D</span>
            </div>
        `;
    }

    updateFilteredSongCount() {
        const countElement = document.getElementById("filteredSongCount");
        if (countElement) {
            const count = this.filteredSongs.length;
            countElement.textContent = `${count} song${count !== 1 ? 's' : ''}`;
        }
    }

    updateBatchActionsVisibility() {
        const batchCard = document.getElementById("batchActionsCard");
        const selectedCount = document.getElementById("selectedCount");
        
        if (batchCard && this.options.showBatchActions) {
            const hasSelection = this.selectedSongs.size > 0;
            batchCard.style.display = hasSelection ? "block" : "none";
            
            if (selectedCount) {
                selectedCount.textContent = `${this.selectedSongs.size} song${this.selectedSongs.size !== 1 ? 's' : ''} selected`;
            }
        }
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
        
        container.innerHTML = Array.from(tagSet).map(tagName => `
            <span class="badge ${isInclude ? 'bg-success' : 'bg-danger'} d-flex align-items-center gap-1">
                <i class="fas fa-tag"></i>
                ${tagName}
                <button type="button" class="btn-close btn-close-white ms-1" 
                        style="font-size: 0.6em;" onclick="window.${this.componentId}.${isInclude ? 'removeIncludeTag' : 'removeExcludeTag'}('${tagName}')" 
                        title="Remove tag"></button>
            </span>
        `).join('');
    }
    
    renderTagGroupFilter(containerId, groupSet, removeCallback) {
        const container = document.getElementById(containerId);
        if (!container) return;
        
        const isInclude = containerId === "includeTagGroups";
        
        container.innerHTML = Array.from(groupSet).map(groupName => {
            const group = this.tagGroups.find(g => g.name === groupName);
            const color = group?.color || '#007bff';
            return `
                <span class="badge d-flex align-items-center gap-1" style="background-color: ${color}; opacity: ${isInclude ? '1' : '0.7'}">
                    <i class="fas fa-folder"></i>
                    ${groupName}
                    <button type="button" class="btn-close btn-close-white ms-1" 
                            style="font-size: 0.6em;" onclick="window.${this.componentId}.${isInclude ? 'removeIncludeTagGroup' : 'removeExcludeTagGroup'}('${groupName}')" 
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
        const containers = ["includeTags", "excludeTags", "includeTagGroups", "excludeTagGroups"];
        containers.forEach(id => {
            const element = document.getElementById(id);
            if (element) element.innerHTML = "";
        });

        this.applyFilters();
    }

    // Selection methods
    toggleSongSelection(songId, isSelected) {
        if (isSelected) {
            this.selectedSongs.add(songId);
        } else {
            this.selectedSongs.delete(songId);
        }
        
        this.updateBatchActionsVisibility();
        
        if (this.options.onSelectionChange) {
            this.options.onSelectionChange(Array.from(this.selectedSongs));
        }
    }

    selectSingle(songId) {
        this.selectedSongs.clear();
        this.selectedSongs.add(songId);
        
        if (this.options.onSelectionChange) {
            this.options.onSelectionChange([songId]);
        }
    }

    toggleSelectAll() {
        const checkbox = document.getElementById("selectAllCheckbox");
        if (!checkbox) return;

        if (checkbox.checked) {
            this.selectAll();
        } else {
            this.selectNone();
        }
    }

    selectAll() {
        this.filteredSongs.forEach(song => this.selectedSongs.add(song.id));
        this.updateCheckboxes();
        this.updateBatchActionsVisibility();
        
        if (this.options.onSelectionChange) {
            this.options.onSelectionChange(Array.from(this.selectedSongs));
        }
    }

    selectNone() {
        this.selectedSongs.clear();
        this.updateCheckboxes();
        this.updateBatchActionsVisibility();
        
        if (this.options.onSelectionChange) {
            this.options.onSelectionChange([]);
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
        this.updateCheckboxes();
        this.updateBatchActionsVisibility();
        
        if (this.options.onSelectionChange) {
            this.options.onSelectionChange(Array.from(this.selectedSongs));
        }
    }

    updateCheckboxes() {
        const checkboxes = document.querySelectorAll(`#${this.options.tableId} tbody input[type="checkbox"]`);
        checkboxes.forEach(checkbox => {
            const songId = parseInt(checkbox.getAttribute('onchange').match(/\d+/)[0]);
            checkbox.checked = this.selectedSongs.has(songId);
        });

        const selectAllCheckbox = document.getElementById("selectAllCheckbox");
        if (selectAllCheckbox) {
            const allSelected = this.filteredSongs.length > 0 && 
                this.filteredSongs.every(song => this.selectedSongs.has(song.id));
            selectAllCheckbox.checked = allSelected;
        }
    }

    // Action methods (to be overridden or implemented)
    playSong(songId) {
        if (this.options.onSongAction) {
            this.options.onSongAction('play', songId);
        } else {
            console.log('Play song:', songId);
        }
    }

    editSong(songId) {
        if (this.options.onSongAction) {
            this.options.onSongAction('edit', songId);
        } else {
            console.log('Edit song:', songId);
        }
    }

    openBatchTagModal() {
        if (this.options.onSongAction) {
            this.options.onSongAction('batchTag', Array.from(this.selectedSongs));
        } else {
            console.log('Batch tag songs:', Array.from(this.selectedSongs));
        }
    }

    openBatchPlaylistModal() {
        if (this.options.onSongAction) {
            this.options.onSongAction('batchPlaylist', Array.from(this.selectedSongs));
        } else {
            console.log('Batch add to playlist:', Array.from(this.selectedSongs));
        }
    }

    batchDeleteSongs() {
        if (this.options.onSongAction) {
            this.options.onSongAction('batchDelete', Array.from(this.selectedSongs));
        } else {
            console.log('Batch delete songs:', Array.from(this.selectedSongs));
        }
    }

    // Public API methods
    getSelectedSongs() {
        return Array.from(this.selectedSongs);
    }

    getFilteredSongs() {
        return [...this.filteredSongs];
    }

    getAllSongs() {
        return [...this.songs];
    }

    refreshData() {
        return this.loadData();
    }

    addCustomFilter(filterFunction) {
        this.options.additionalFilters.push(filterFunction);
        this.applyFilters();
    }

    removeCustomFilter(filterFunction) {
        const index = this.options.additionalFilters.indexOf(filterFunction);
        if (index > -1) {
            this.options.additionalFilters.splice(index, 1);
            this.applyFilters();
        }
    }
}

// Export for global use
window.SongSearchComponent = SongSearchComponent;
