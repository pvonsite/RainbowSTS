/**
 * Class that manages STT models fetching and selection
 */
class STTModelManager {
  selectedModel = "";
  models = [];
  isLoading = false;
  initialized = false;

  /**
   * Initialize the model manager
   * @returns {Promise<boolean>} Promise resolving to true when initialization is complete
   */
  async initialize() {
    if (!this.initialized) {
      this.models = await this.loadModels();
      return (this.initialized = true);
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

      const response = await fetch("/models").then((res) => res.json());

      if (response.status !== "success") {
        console.error("Failed to load models:", response.message);
        return [];
      }

      const { models } = response;

      console.log(
        "STT models loaded successfully:",
        models.length,
        "models found",
      );

      return models;
    } catch (error) {
      console.error("Error fetching STT models:", error);
      return [];
    } finally {
      this.isLoading = false;
    }
  }

  setModel(model) {
    this.selectedModel = model;
  }
}

