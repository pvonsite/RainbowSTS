
/**
 * Class that manages STT models fetching and selection
 */
class STTModelManager {
    constructor() {
        this.models = [];
        this.selectElement = document.getElementById('stt-model');
        this.isLoading = false;
        this.initialized = false;
    }

    /**
     * Initialize the model manager
     * @returns {Promise<boolean>} Promise resolving to true when initialization is complete
     */
    async initialize() {
        if (!this.initialized) {
            await this.loadModels();
            this.initialized = true;
            return true;
        }
        return true;
    }

    /**
     * Load available STT models from API
     * @returns {Promise<Array>} Promise resolving to the loaded models
     */
    async loadModels() {
        try {
            this.isLoading = true;
            this.updateSelectStatus('Loading models...');

            const response = await fetch('/models');
            const data = await response.json();

            if (data.status === 'success') {
                this.models = data.models;
                this.populateModelSelect();
                console.log('STT models loaded successfully:', this.models.length, 'models found');
                return this.models;
            } else {
                console.error('Failed to load models:', data.message);
                this.updateSelectStatus('Error loading models');
                return [];
            }
        } catch (error) {
            console.error('Error fetching STT models:', error);
            this.updateSelectStatus('Error: Could not load models');
            return [];
        } finally {
            this.isLoading = false;
        }
    }

    /**
     * Update the select element to show a status message
     * @param {string} message - Status message to display
     */
    updateSelectStatus(message) {
        if (this.selectElement) {
            // Clear current options
            this.selectElement.innerHTML = '';
            
            // Add status message option
            const option = document.createElement('option');
            option.value = '';
            option.textContent = message;
            option.disabled = true;
            option.selected = true;
            this.selectElement.appendChild(option);
        }
    }

    /**
     * Populate the select element with available models
     */
    populateModelSelect() {
        if (!this.selectElement || !this.models.length) {
            return;
        }

        // Clear current options
        this.selectElement.innerHTML = '';

        // Add models as options
        this.models.forEach(model => {
            const option = document.createElement('option');
            option.value = model;
            
            // Add .en suffix explanation if present
            if (model.includes('.en')) {
                const baseName = model.replace('.en', '');
                option.textContent = `${baseName} (English only)`;
            } else {
                option.textContent = model;
            }
            
            this.selectElement.appendChild(option);
        });

        // Select a default model (base or base.en if available)
        const defaultModel = this.models.includes('base') ? 'base' : 
                           (this.models.includes('base.en') ? 'base.en' : this.models[0]);
        
        if (defaultModel) {
            this.selectElement.value = defaultModel;
        }

        // Dispatch change event to notify other components
        const event = new Event('change');
        this.selectElement.dispatchEvent(event);
    }

    /**
     * Get the currently selected model
     * @returns {string} The selected model
     */
    getSelectedModel() {
        return this.selectElement ? this.selectElement.value : null;
    }
}

// Export the class for use in other modules
window.STTModelManager = STTModelManager;