/**
 * Session management (start/stop)
 */
class SessionManager {
  constructor(audioDeviceManager, websocketHandler, audioRecorder) {
    this.audioDeviceManager = audioDeviceManager;
    this.websocketHandler = websocketHandler;
    this.audioRecorder = audioRecorder;
    this.sessionId = null;
  }

  async startSession() {
    try {
      const deviceId = state.selectedAudioCaptureDevice;

      if (!deviceId) {
        notificator.error("Session", "No audio capture device selected.");
        return false;
      }

      if (!state.srcLanguage || !state.dstLanguage) {
        notificator.error(
          "Session",
          "Source and destination languages must be selected.",
        );
        return false;
      }

      if (!state.selectedS2tModel) {
        notificator.error("Session", "No Speech-to-text model selected.");
        return false;
      }

      // Get configuration
      const config = {
        stt_model: state.selectedS2tModel,
        source_language: state.srcLanguage,
        target_language: state.dstLanguage,
        websocket_port: 8765, // Default port
        input_device_index: deviceId,
      };

      // Request to start a new session
      const response = await fetch("/start_session", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(config),
      });

      const data = await response.json();

      if (data.status !== "success") {
        console.error("Error starting session:", data.message);
        notificator.error("Session", `Error starting session: ${data.message}`);
        return false;
      }

      this.sessionId = data.session_id;
      this.websocketHandler.connect(data.websocket_url);
      this.websocketHandler.addEventListener("connection", (data) => {
        if (data && data.status === "connected") {
          console.log("WebSocket connected:", data);
          notificator.success(
            "WebSocket",
            "WebSocket connection established successfully.",
          );
        } else {
          console.error("WebSocket connection failed:", data);
          notificator.error("WebSocket", "WebSocket connection failed.");
        }
      });

      this.websocketHandler.addEventListener("error", (error) => {
        console.error("WebSocket error:", error);
        notificator.error("WebSocket", `Error: ${error.message}`);
      });

      this.websocketHandler.addEventListener(
        "translation",
        ({ original, translated, isFinal }) => {
          state.pushTranslatedToken(translated);
        },
      );

      notificator.success("Session", "Session started successfully.");
      return true;
    } catch (error) {
      console.error("Error starting session:", error);
      notificator.error("Session", "Error starting session");
      return false;
    }
  }

  async stopSession() {
    if (!this.sessionId) return false;

    try {
      await fetch(`/stop_session/${this.sessionId}`, {
        method: "POST",
      });

      // Clean up
      this.websocketHandler.disconnect();
      this.audioRecorder.stopRecording();

      // Update UI
      notificator.success("Session", "Session stopped successfully.");
      this.sessionId = null;
      return true;
    } catch (error) {
      console.error("Error stopping session:", error);
      notificator.error("Session", "Error stopping session");
      return false;
    }
  }

  async startListening() {
    if (this.websocketHandler.isSocketReady()) {
      try {
        const deviceId = state.selectedAudioCaptureDevice;
        await this.audioRecorder.startRecording(deviceId);
        this.websocketHandler.sendCommand("start_listening");
      } catch (error) {
        console.error("Error starting recording:", error);
        notificator.error("Session", "Error accessing microphone");
      }
    }
  }

  stopListening() {
    if (this.websocketHandler.isSocketReady()) {
      this.audioRecorder.stopRecording();
      this.websocketHandler.sendCommand("stop_listening");
    }
  }
}
