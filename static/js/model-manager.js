/**
 * Class that manages models fetching
 */
class ModelManager {
  selectedModel = "";
  models = {};
  isLoading = false;
  initialized = false;

  /**
   * Initialize the model manager
   * @returns {Promise<boolean>} Promise resolving to true when initialization is complete
   */
  async initialize() {
    if (!this.initialized) {
      this.models = await this.loadModels();
      const stt_list = this.models.speechtotext;
      state.setSpeechToTextModel(stt_list[0])
      const trans_list = this.models.translation
      state.setTranslationModel(trans_list[0])
      const tts_list = this.models.texttospeech
      state.setTextToSpeechModel(tts_list[0])
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

      return models;
    } catch (error) {
      console.error("Error fetching STT models:", error);
      return [];
    } finally {
      this.isLoading = false;
    }
  }
}
