/**
 * Reusable Modal System for SoundShare
 * Provides a consistent way to create and manage Bootstrap modals
 */

class ModalManager {
    constructor() {
        this.activeModals = new Map();
        this.modalContainer = null;
        this.init();
    }

    init() {
        // Create a container for dynamically generated modals
        this.modalContainer = document.createElement('div');
        this.modalContainer.id = 'modalContainer';
        document.body.appendChild(this.modalContainer);
    }

    /**
     * Create a modal with the specified configuration
     * @param {Object} config - Modal configuration
     * @param {string} config.id - Unique modal ID
     * @param {string} config.title - Modal title
     * @param {string} config.body - Modal body HTML content
     * @param {Array} config.buttons - Array of button configurations
     * @param {string} config.size - Modal size ('sm', 'lg', 'xl', or default)
     * @param {boolean} config.backdrop - Whether modal can be dismissed by clicking backdrop
     * @param {boolean} config.keyboard - Whether modal can be dismissed with escape key
     * @param {Function} config.onShow - Callback when modal is shown
     * @param {Function} config.onHide - Callback when modal is hidden
     */
    createModal(config) {
        const {
            id,
            title,
            body,
            buttons = [],
            size = '',
            backdrop = true,
            keyboard = true,
            onShow = null,
            onHide = null
        } = config;

        // Remove existing modal with same ID
        this.destroyModal(id);

        // Create modal HTML
        const sizeClass = size ? `modal-${size}` : '';
        const backdropAttr = backdrop === false ? 'data-bs-backdrop="static"' : '';
        const keyboardAttr = keyboard === false ? 'data-bs-keyboard="false"' : '';

        const modalHTML = `
            <div class="modal fade" id="${id}" tabindex="-1" ${backdropAttr} ${keyboardAttr}>
                <div class="modal-dialog ${sizeClass}">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">${title}</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            ${body}
                        </div>
                        <div class="modal-footer">
                            ${this.generateButtons(buttons)}
                        </div>
                    </div>
                </div>
            </div>
        `;

        // Add to container
        this.modalContainer.insertAdjacentHTML('beforeend', modalHTML);

        // Get modal element and create Bootstrap modal instance
        const modalElement = document.getElementById(id);
        const modalInstance = new bootstrap.Modal(modalElement);

        // Store modal info
        this.activeModals.set(id, {
            element: modalElement,
            instance: modalInstance,
            config: config
        });

        // Add event listeners
        if (onShow) {
            modalElement.addEventListener('shown.bs.modal', onShow);
        }
        if (onHide) {
            modalElement.addEventListener('hidden.bs.modal', onHide);
        }

        // Auto-cleanup on hide
        modalElement.addEventListener('hidden.bs.modal', () => {
            this.destroyModal(id);
        });

        return modalInstance;
    }

    /**
     * Generate button HTML from button configurations
     */
    generateButtons(buttons) {
        return buttons.map(button => {
            const {
                text,
                className = 'btn-secondary',
                action = null,
                dismiss = false
            } = button;

            const dismissAttr = dismiss ? 'data-bs-dismiss="modal"' : '';
            const onclickAttr = action ? `onclick="${action}"` : '';

            return `<button type="button" class="btn ${className}" ${dismissAttr} ${onclickAttr}>
                ${text}
            </button>`;
        }).join('');
    }

    /**
     * Show a modal
     */
    showModal(id) {
        const modal = this.activeModals.get(id);
        if (modal) {
            modal.instance.show();
        }
        return modal?.instance;
    }

    /**
     * Hide a modal
     */
    hideModal(id) {
        const modal = this.activeModals.get(id);
        if (modal) {
            modal.instance.hide();
        }
    }

    /**
     * Destroy a modal and clean up
     */
    destroyModal(id) {
        const modal = this.activeModals.get(id);
        if (modal) {
            modal.instance.dispose();
            modal.element.remove();
            this.activeModals.delete(id);
        }
    }

    /**
     * Update modal content
     */
    updateModalContent(id, content) {
        const modal = this.activeModals.get(id);
        if (modal) {
            const bodyElement = modal.element.querySelector('.modal-body');
            if (bodyElement) {
                bodyElement.innerHTML = content;
            }
        }
    }

    /**
     * Update modal title
     */
    updateModalTitle(id, title) {
        const modal = this.activeModals.get(id);
        if (modal) {
            const titleElement = modal.element.querySelector('.modal-title');
            if (titleElement) {
                titleElement.textContent = title;
            }
        }
    }

    /**
     * Create a simple confirmation modal
     */
    createConfirmModal(title, message, onConfirm, onCancel = null) {
        const id = 'confirmModal_' + Date.now();
        
        // Store callbacks
        this.callbacks[id] = {
            confirm: onConfirm,
            cancel: onCancel
        };
        
        return this.createModal({
            id: id,
            title: title,
            body: `<p>${message}</p>`,
            buttons: [
                {
                    text: 'Cancel',
                    className: 'btn-secondary',
                    dismiss: true,
                    action: onCancel ? `modalManager.runCallback('${id}', 'cancel')` : null
                },
                {
                    text: 'Confirm',
                    className: 'btn-primary',
                    dismiss: true,
                    action: onConfirm ? `modalManager.runCallback('${id}', 'confirm')` : null
                }
            ],
            onHide: () => {
                delete this.callbacks[id];
            }
        });
    }

    /**
     * Create a simple form modal
     */
    createFormModal(title, fields, onSubmit, onCancel = null) {
        const id = 'formModal_' + Date.now();
        
        // Store callbacks
        this.callbacks[id] = {
            submit: onSubmit,
            cancel: onCancel
        };
        
        const formHTML = `
            <form id="${id}_form">
                ${fields.map(field => this.generateFormField(field)).join('')}
            </form>
        `;

        return this.createModal({
            id: id,
            title: title,
            body: formHTML,
            buttons: [
                {
                    text: 'Cancel',
                    className: 'btn-secondary',
                    dismiss: true,
                    action: onCancel ? `modalManager.runCallback('${id}', 'cancel')` : null
                },
                {
                    text: 'Save',
                    className: 'btn-primary',
                    action: `modalManager.runCallback('${id}', 'submit')`
                }
            ],
            onHide: () => {
                delete this.callbacks[id];
            }
        });
    }

    /**
     * Generate form field HTML
     */
    generateFormField(field) {
        const {
            type = 'text',
            id,
            label,
            placeholder = '',
            required = false,
            value = '',
            options = []
        } = field;

        const requiredAttr = required ? 'required' : '';

        switch (type) {
            case 'select':
                const optionsHTML = options.map(opt => 
                    `<option value="${opt.value}" ${opt.value === value ? 'selected' : ''}>${opt.text}</option>`
                ).join('');
                return `
                    <div class="mb-3">
                        <label for="${id}" class="form-label">${label}</label>
                        <select class="form-select" id="${id}" name="${id}" ${requiredAttr}>
                            ${optionsHTML}
                        </select>
                    </div>
                `;

            case 'textarea':
                return `
                    <div class="mb-3">
                        <label for="${id}" class="form-label">${label}</label>
                        <textarea class="form-control" id="${id}" name="${id}" placeholder="${placeholder}" ${requiredAttr}>${value}</textarea>
                    </div>
                `;

            case 'color':
                return `
                    <div class="mb-3">
                        <label for="${id}" class="form-label">${label}</label>
                        <input type="color" class="form-control" id="${id}" name="${id}" value="${value || '#007bff'}" ${requiredAttr}>
                    </div>
                `;

            case 'hidden':
                return `<input type="hidden" id="${id}" name="${id}" value="${value}">`;

            default:
                return `
                    <div class="mb-3">
                        <label for="${id}" class="form-label">${label}</label>
                        <input type="${type}" class="form-control" id="${id}" name="${id}" placeholder="${placeholder}" value="${value}" ${requiredAttr}>
                    </div>
                `;
        }
    }

    /**
     * Handle callbacks for dynamically created modals
     */
    runCallback(modalId, action) {
        const callback = this.callbacks?.[modalId]?.[action];
        if (callback) {
            let result;
            if (action === 'submit') {
                // Collect form data
                const form = document.getElementById(`${modalId}_form`);
                if (form) {
                    const formData = new FormData(form);
                    const data = Object.fromEntries(formData);
                    result = callback(data, modalId);
                } else {
                    result = callback(null, modalId);
                }
            } else {
                result = callback();
            }
            
            // Only hide modal if callback doesn't return false
            if (result !== false) {
                this.hideModal(modalId);
            }
        } else {
            this.hideModal(modalId);
        }
    }
}

// Initialize callbacks storage at the class level
ModalManager.prototype.callbacks = {};

// Global instance
const modalManager = new ModalManager();
