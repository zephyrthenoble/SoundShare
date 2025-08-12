/**
 * Tag Management System for SoundShare
 * Handles tag and tag group CRUD operations using the modal manager
 */

class TagManager {
    constructor() {
        this.tags = [];
        this.groups = [];
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
        this.loadData();
    }

    async loadData() {
        try {
            await Promise.all([
                this.loadTags(),
                this.loadGroups()
            ]);
            this.displayData();
        } catch (error) {
            notificationSystem.error("Error", "Failed to load data: " + error.message);
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

    async loadGroups() {
        try {
            const response = await fetch("/api/groups/");
            if (!response.ok) throw new Error("Failed to fetch tag groups");
            this.groups = await response.json();
        } catch (error) {
            notificationSystem.error("Error", "Failed to load tag groups");
            throw error;
        }
    }

    displayData() {
        this.displayGroups();
        this.displayTags();
    }

    displayGroups() {
        const container = document.getElementById("groupsList");
        if (!container) return;

        container.innerHTML = "";

        if (this.groups.length === 0) {
            container.innerHTML = `
                <div class="text-center text-muted py-4">
                    <i class="fas fa-folder-open fa-2x mb-2"></i>
                    <p>No tag groups created yet</p>
                </div>
            `;
            return;
        }

        this.groups.forEach(group => {
            const groupCard = this.createGroupCard(group);
            container.appendChild(groupCard);
        });
    }

    createGroupCard(group) {
        const card = document.createElement("div");
        card.className = "card mb-3";
        
        const tagsInGroup = this.tags.filter(tag => tag.group_id === group.id);
        
        card.innerHTML = `
            <div class="card-header" style="background-color: ${group.color}20; border-left: 4px solid ${group.color};">
                <div class="d-flex justify-content-between align-items-center">
                    <div>
                        <h6 class="mb-0" style="color: ${group.color};">${this.escapeHtml(group.name)}</h6>
                        <small class="text-muted">${tagsInGroup.length} tag${tagsInGroup.length === 1 ? "" : "s"}</small>
                    </div>
                    <div class="btn-group">
                        <button class="btn btn-sm btn-outline-primary" onclick="tagManager.editGroup(${group.id})" title="Edit Group">
                            <i class="fas fa-edit"></i>
                        </button>
                        <button class="btn btn-sm btn-outline-danger" onclick="tagManager.deleteGroup(${group.id})" title="Delete Group">
                            <i class="fas fa-trash"></i>
                        </button>
                    </div>
                </div>
            </div>
            <div class="card-body">
                <p class="text-muted small mb-2">${this.escapeHtml(group.description || "No description")}</p>
                <div class="d-flex flex-wrap gap-2">
                    ${tagsInGroup.map(tag => `
                        <span class="badge" style="background-color: ${group.color}; cursor: pointer;" 
                              onclick="tagManager.editTag(${tag.id})" title="Click to edit">
                            ${this.escapeHtml(tag.name)}
                        </span>
                    `).join("")}
                </div>
            </div>
        `;

        return card;
    }

    displayTags() {
        const container = document.getElementById("tagsList");
        if (!container) return;

        const unGroupedTags = this.tags.filter(tag => !tag.group_id);

        if (unGroupedTags.length === 0) {
            return; // Don't show anything if no ungrouped tags
        }

        const card = document.createElement("div");
        card.className = "card mb-3";
        
        card.innerHTML = `
            <div class="card-header bg-light">
                <h6 class="mb-0 text-secondary">Ungrouped Tags</h6>
                <small class="text-muted">${unGroupedTags.length} tag${unGroupedTags.length === 1 ? "" : "s"}</small>
            </div>
            <div class="card-body">
                <div class="d-flex flex-wrap gap-2">
                    ${unGroupedTags.map(tag => `
                        <span class="badge bg-secondary" style="cursor: pointer;" 
                              onclick="tagManager.editTag(${tag.id})" title="Click to edit">
                            ${this.escapeHtml(tag.name)}
                        </span>
                    `).join("")}
                </div>
            </div>
        `;

        container.innerHTML = "";
        container.appendChild(card);
    }

    // Group Operations
    createGroup() {
        const modal = modalManager.createFormModal(
            "Create Tag Group",
            [
                { type: "text", id: "groupName", label: "Group Name", required: true },
                { type: "textarea", id: "groupDescription", label: "Description" },
                { type: "color", id: "groupColor", label: "Color", value: "#007bff" }
            ],
            (data) => this.saveGroup(data)
        );
        modal.show();
    }

    editGroup(groupId) {
        const group = this.groups.find(g => g.id === groupId);
        if (!group) return;

        const modal = modalManager.createFormModal(
            "Edit Tag Group",
            [
                { type: "hidden", id: "groupId", value: group.id },
                { type: "text", id: "groupName", label: "Group Name", value: group.name, required: true },
                { type: "textarea", id: "groupDescription", label: "Description", value: group.description || "" },
                { type: "color", id: "groupColor", label: "Color", value: group.color }
            ],
            (data) => this.saveGroup(data)
        );
        modal.show();
    }

    async saveGroup(data) {
        try {
            const isEdit = !!data.groupId;
            const url = isEdit ? `/api/groups/${data.groupId}` : "/api/groups/";
            const method = isEdit ? "PUT" : "POST";

            const response = await fetch(url, {
                method: method,
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    name: data.groupName,
                    description: data.groupDescription || null,
                    color: data.groupColor
                })
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || "Failed to save group");
            }

            notificationSystem.success("Success", `Tag group ${isEdit ? "updated" : "created"} successfully`);
            await this.loadData();
        } catch (error) {
            notificationSystem.error("Error", "Failed to save group: " + error.message);
        }
    }

    deleteGroup(groupId) {
        const group = this.groups.find(g => g.id === groupId);
        if (!group) return;

        const tagsInGroup = this.tags.filter(tag => tag.group_id === groupId);
        const message = tagsInGroup.length > 0 
            ? `Delete "${group.name}"? This will also ungroup ${tagsInGroup.length} tag${tagsInGroup.length === 1 ? "" : "s"}.`
            : `Delete "${group.name}"? This action cannot be undone.`;

        const modal = modalManager.createConfirmModal(
            "Delete Tag Group",
            message,
            () => this.performDeleteGroup(groupId)
        );
        modal.show();
    }

    async performDeleteGroup(groupId) {
        try {
            const response = await fetch(`/api/groups/${groupId}`, {
                method: "DELETE"
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || "Failed to delete group");
            }

            notificationSystem.success("Success", "Tag group deleted successfully");
            await this.loadData();
        } catch (error) {
            notificationSystem.error("Error", "Failed to delete group: " + error.message);
        }
    }

    // Tag Operations
    createTag() {
        const groupOptions = [
            { value: "", text: "No Group" },
            ...this.groups.map(g => ({ value: g.id, text: g.name }))
        ];

        const modal = modalManager.createFormModal(
            "Create Tag",
            [
                { type: "text", id: "tagName", label: "Tag Name", required: true },
                { type: "textarea", id: "tagDescription", label: "Description" },
                { type: "select", id: "tagGroupSelect", label: "Group", options: groupOptions }
            ],
            (data) => this.saveTag(data)
        );
        modal.show();
    }

    editTag(tagId) {
        const tag = this.tags.find(t => t.id === tagId);
        if (!tag) return;

        const groupOptions = [
            { value: "", text: "No Group" },
            ...this.groups.map(g => ({ value: g.id, text: g.name }))
        ];

        const modal = modalManager.createFormModal(
            "Edit Tag",
            [
                { type: "hidden", id: "tagId", value: tag.id },
                { type: "text", id: "tagName", label: "Tag Name", value: tag.name, required: true },
                { type: "textarea", id: "tagDescription", label: "Description", value: tag.description || "" },
                { type: "select", id: "tagGroupSelect", label: "Group", value: tag.group_id || "", options: groupOptions }
            ],
            (data) => this.saveTag(data)
        );
        modal.show();
    }

    async saveTag(data) {
        try {
            const isEdit = !!data.tagId;
            const url = isEdit ? `/api/tags/${data.tagId}` : "/api/tags";
            const method = isEdit ? "PUT" : "POST";

            const response = await fetch(url, {
                method: method,
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    name: data.tagName,
                    description: data.tagDescription || null,
                    group_id: data.tagGroupSelect || null
                })
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || "Failed to save tag");
            }

            notificationSystem.success("Success", `Tag ${isEdit ? "updated" : "created"} successfully`);
            await this.loadData();
        } catch (error) {
            notificationSystem.error("Error", "Failed to save tag: " + error.message);
        }
    }

    deleteTag(tagId) {
        const tag = this.tags.find(t => t.id === tagId);
        if (!tag) return;

        const modal = modalManager.createConfirmModal(
            "Delete Tag",
            `Delete "${tag.name}"? This will remove it from all songs. This action cannot be undone.`,
            () => this.performDeleteTag(tagId)
        );
        modal.show();
    }

    async performDeleteTag(tagId) {
        try {
            const response = await fetch(`/api/tags/${tagId}`, {
                method: "DELETE"
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || "Failed to delete tag");
            }

            notificationSystem.success("Success", "Tag deleted successfully");
            await this.loadData();
        } catch (error) {
            notificationSystem.error("Error", "Failed to delete tag: " + error.message);
        }
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
}

// Global instance
const tagManager = new TagManager();

// Export global functions for onclick handlers
window.createGroup = () => tagManager.createGroup();
window.createTag = () => tagManager.createTag();
window.editGroup = (id) => tagManager.editGroup(id);
window.editTag = (id) => tagManager.editTag(id);
window.deleteGroup = (id) => tagManager.deleteGroup(id);
window.deleteTag = (id) => tagManager.deleteTag(id);
