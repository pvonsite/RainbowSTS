class TranscribeView {
  constructor(websocketHandler) {
    this.websocketHandler = websocketHandler;

    // Bind event listeners
    this.websocketHandler.addEventListener("realtime", (data) =>
      this.handleTranscription(data),
    );
    this.websocketHandler.addEventListener("fullSentence", (data) =>
      this.finalizeSentence(data),
    );
    this.websocketHandler.addEventListener("connection", (data) =>
      this.handleConnection(data),
    );
    this.fullSentences = "";
    this.buildingSentence = "";
  }

  handleConnection(data) {
    if (data && data.status === "connected") {
      console.log("WebSocket connected:", data);
    }
  }

  handleTranscription(data) {
    console.log("Transcription data received:", data);
    if (data && data.text) {
      this.buildingSentence = data.text;
      state.pushLiveToken(data.text);
    }
  }

  finalizeSentence(data) {
    console.log("Full sentence received:", data);
    if (data && data.text) {
      this.fullSentences += data.text;
      this.buildingSentence = "";
      this.render();
    }
  }

  render() {
    this.fullSentences.concat(" ", this.buildingSentence).concat("...");
  }
}

