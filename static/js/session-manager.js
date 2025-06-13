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
      const deviceId = this.audioDeviceManager.getSelectedDeviceId();

      if (!deviceId) {
        return;
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

      if (data.status === "success") {
        this.sessionId = data.session_id;
        this.websocketHandler.connect(data.websocket_url);
        this.websocketHandler.addEventListener("connection", (data) => {
          if (data && data.status === "connected") {
            console.log("WebSocket connected:", data);
            this.statusElement.textContent = "Status: WebSocket connected";
            this.startListeningBtn.disabled = false;
          } else {
            console.error("WebSocket connection failed:", data);
            this.statusElement.textContent =
              "Status: WebSocket connection failed";
          }
        });
        this.websocketHandler.addEventListener("error", (error) => {
          console.error("WebSocket error:", error);
          this.statusElement.textContent = "Status: WebSocket error";
        });

        // Update UI
        this.startBtn.disabled = true;
        this.stopBtn.disabled = false;
        this.refreshDevicesBtn.disabled = true;
        this.statusElement.textContent = "Status: Session started";
      } else {
        this.statusElement.textContent = `Status: Error - ${data.message}`;
      }
    } catch (error) {
      console.error("Error starting session:", error);
      this.statusElement.textContent = "Status: Error starting session";
    }
  }

  async stopSession() {
    if (this.sessionId) {
      try {
        await fetch(`/stop_session/${this.sessionId}`, {
          method: "POST",
        });

        // Clean up
        this.websocketHandler.disconnect();
        this.audioRecorder.stopRecording();

        // Update UI
        this.startBtn.disabled = false;
        this.stopBtn.disabled = true;
        this.startListeningBtn.disabled = true;
        this.stopListeningBtn.disabled = true;
        this.refreshDevicesBtn.disabled = false;
        this.statusElement.textContent = "Status: Session stopped";

        this.sessionId = null;
      } catch (error) {
        console.error("Error stopping session:", error);
      }
    }
  }

  async startListening() {
    if (this.websocketHandler.isSocketReady()) {
      try {
        const deviceId = this.audioDeviceManager.getSelectedDeviceId();
        await this.audioRecorder.startRecording(deviceId);
        this.websocketHandler.sendCommand("start_listening");
        this.startListeningBtn.disabled = true;
        this.stopListeningBtn.disabled = false;
      } catch (error) {
        console.error("Error starting recording:", error);
        this.statusElement.textContent = "Status: Error accessing microphone";
      }
    }
  }

  stopListening() {
    if (this.websocketHandler.isSocketReady()) {
      this.audioRecorder.stopRecording();
      this.websocketHandler.sendCommand("stop_listening");
      this.startListeningBtn.disabled = false;
      this.stopListeningBtn.disabled = true;
    }
  }
}

