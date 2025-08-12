/**
 * Reusable File Browser Component
 * Shows a tree directory structure with checkboxes for file/directory selection
 */

class FileBrowser {
    constructor(options = {}) {
        this.options = {
            disableDirectories: false,
            disableFiles: false,
            disabledItems: [], // Array of full paths to disable
            multiSelect: true,
            ...options
        };
        
        this.currentPath = '';
        this.selectedItems = new Set();
        this.modal = null;
        this.onConfirm = null;
        this.onCancel = null;
    }
    
    /**
     * Show the file browser modal
     * @param {Object} config - Configuration for this instance
     * @param {Function} config.onConfirm - Callback when user clicks Add (receives array of selected paths)
     * @param {Function} config.onCancel - Callback when user cancels
     * @param {string} config.title - Modal title
     */
    show(config = {}) {
        this.onConfirm = config.onConfirm || (() => {});
        this.onCancel = config.onCancel || (() => {});
        
        // Create modal HTML
        const modalHtml = `
            <div class="modal fade" id="fileBrowserModal" tabindex="-1" data-bs-backdrop="static">
                <div class="modal-dialog modal-xl">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">${config.title || 'Browse Files'}</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body" style="height: 70vh;">
                            <div class="d-flex justify-content-between align-items-center mb-3">
                                <nav aria-label="breadcrumb">
                                    <ol class="breadcrumb mb-0" id="breadcrumb"></ol>
                                </nav>
                                <button class="btn btn-sm btn-outline-secondary" id="refreshBtn">
                                    <i class="fas fa-refresh"></i> Refresh
                                </button>
                            </div>
                            <div class="row h-100">
                                <div class="col-8 border-end">
                                    <div id="fileList" class="h-100 overflow-auto"></div>
                                </div>
                                <div class="col-4">
                                    <h6>Selected Items (<span id="selectedCount">0</span>)</h6>
                                    <div id="selectedList" class="h-75 overflow-auto border rounded p-2 bg-light"></div>
                                </div>
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                            <button type="button" class="btn btn-primary" id="confirmBtn">Add Selected</button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        // Remove existing modal if any
        const existing = document.getElementById('fileBrowserModal');
        if (existing) existing.remove();
        
        // Add modal to page
        document.body.insertAdjacentHTML('beforeend', modalHtml);
        
        // Initialize modal
        this.modal = new bootstrap.Modal(document.getElementById('fileBrowserModal'));
        
        // Bind events
        this.bindEvents();
        
        // Load initial directory
        this.loadDirectory();
        
        // Show modal
        this.modal.show();
    }
    
    bindEvents() {
        const modal = document.getElementById('fileBrowserModal');
        
        // Refresh button
        modal.querySelector('#refreshBtn').addEventListener('click', () => {
            this.loadDirectory();
        });
        
        // Confirm button
        modal.querySelector('#confirmBtn').addEventListener('click', () => {
            const selected = Array.from(this.selectedItems);
            this.modal.hide();
            this.onConfirm(selected);
        });
        
        // Cancel/close
        modal.addEventListener('hidden.bs.modal', () => {
            this.onCancel();
            modal.remove();
        });
    }
    
    async loadDirectory(path = '') {
        try {
            console.log(`Loading directory: ${path}`);
            const response = await fetch(`/api/library/browse?path=${encodeURIComponent(path)}`);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            this.currentPath = data.current_path;
            this.renderBreadcrumb(data.parent_path);
            this.renderFileList(data.items);
            
        } catch (error) {
            console.error('Error loading directory:', error);
            document.getElementById('fileList').innerHTML = 
                `<div class="alert alert-danger">Error loading directory: ${error.message}</div>`;
        }
    }
    
    renderBreadcrumb(parentPath) {
        const breadcrumb = document.getElementById('breadcrumb');
        const parts = this.currentPath ? this.currentPath.split('/') : [];
        
        let html = '<li class="breadcrumb-item"><a href="#" data-path="">Library</a></li>';
        
        let currentPath = '';
        for (const part of parts) {
            currentPath = currentPath ? `${currentPath}/${part}` : part;
            html += `<li class="breadcrumb-item"><a href="#" data-path="${currentPath}">${part}</a></li>`;
        }
        
        breadcrumb.innerHTML = html;
        
        // Bind breadcrumb clicks
        breadcrumb.querySelectorAll('a').forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                this.loadDirectory(e.target.dataset.path);
            });
        });
    }
    
    renderFileList(items) {
        const fileList = document.getElementById('fileList');
        
        if (items.length === 0) {
            fileList.innerHTML = '<div class="text-muted p-3">No files or directories found</div>';
            return;
        }
        
        let html = '<div class="list-group list-group-flush">';
        
        for (const item of items) {
            const isDisabled = this.isItemDisabled(item);
            const isChecked = this.selectedItems.has(item.full_path);
            const icon = item.type === 'directory' ? 'fa-folder' : 'fa-file-audio';
            const alreadyAddedBadge = item.already_added ? 
                '<span class="badge bg-secondary ms-2">Already Added</span>' : '';
            
            html += `
                <div class="list-group-item d-flex align-items-center">
                    <div class="form-check me-3">
                        <input type="checkbox" 
                               class="form-check-input" 
                               data-path="${item.full_path}"
                               data-type="${item.type}"
                               ${isChecked ? 'checked' : ''}
                               ${isDisabled ? 'disabled' : ''}>
                    </div>
                    <i class="fas ${icon} me-2"></i>
                    <div class="flex-grow-1">
                        ${item.type === 'directory' ? 
                            `<a href="#" class="text-decoration-none" data-path="${item.path}">${item.name}</a>` :
                            `<span>${item.name}</span>`
                        }
                        ${alreadyAddedBadge}
                    </div>
                </div>
            `;
        }
        
        html += '</div>';
        fileList.innerHTML = html;
        
        // Bind directory clicks
        fileList.querySelectorAll('a[data-path]').forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                this.loadDirectory(e.target.dataset.path);
            });
        });
        
        // Bind checkbox changes
        fileList.querySelectorAll('input[type="checkbox"]').forEach(checkbox => {
            checkbox.addEventListener('change', (e) => {
                const path = e.target.dataset.path;
                if (e.target.checked) {
                    this.selectedItems.add(path);
                } else {
                    this.selectedItems.delete(path);
                }
                this.updateSelectedList();
            });
        });
    }
    
    isItemDisabled(item) {
        // Check if item type is disabled
        if (item.type === 'directory' && this.options.disableDirectories) return true;
        if (item.type === 'file' && this.options.disableFiles) return true;
        
        // Check if already added
        if (item.already_added) return true;
        
        // Check if specifically disabled
        if (this.options.disabledItems.includes(item.full_path)) return true;
        
        return false;
    }
    
    updateSelectedList() {
        const selectedList = document.getElementById('selectedList');
        const selectedCount = document.getElementById('selectedCount');
        const addButton = document.getElementById('addSongsBtn') || document.getElementById('addDirectoriesBtn');
        
        selectedCount.textContent = this.selectedItems.size;
        
        // Update button state
        if (addButton) {
            addButton.disabled = this.selectedItems.size === 0;
        }
        
        if (this.selectedItems.size === 0) {
            selectedList.innerHTML = '<div class="text-muted">No items selected</div>';
            return;
        }
        
        const items = Array.from(this.selectedItems).map(path => {
            const name = path.split('/').pop() || path.split('\\\\').pop();
            return `
                <div class="d-flex justify-content-between align-items-center mb-1">
                    <small class="text-truncate" title="${path}">${name}</small>
                    <button class="btn btn-sm btn-outline-danger ms-2" 
                            onclick="(pageBrowser || fileBrowser).selectedItems.delete('${path}'); (pageBrowser || fileBrowser).updateSelectedList(); (pageBrowser || fileBrowser).updateCheckboxes();">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
            `;
        }).join('');
        
        selectedList.innerHTML = items;
    }
    
    updateCheckboxes() {
        document.querySelectorAll('#fileList input[type="checkbox"]').forEach(checkbox => {
            checkbox.checked = this.selectedItems.has(checkbox.dataset.path);
        });
    }
    
    /**
     * Initialize file browser for page-based usage (not modal)
     * Assumes the page has the required elements: breadcrumb, fileList, selectedList, selectedCount
     */
    initializePage() {
        this.loadDirectory();
    }
}

// Global instance for easy access
let fileBrowser = null;
