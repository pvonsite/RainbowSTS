(() => {
  // Initialize components
  window.audioDeviceManager = new AudioDeviceManager();
  window.sttModelManager = new STTModelManager();
  window.websocketHandler = new WebSocketHandler();
  window.audioRecorder = new AudioRecorder(websocketHandler);
  window.sessionManager = new SessionManager(
    audioDeviceManager,
    websocketHandler,
    audioRecorder,
  );
  window.transcribeView = new TranscribeView(websocketHandler);

  console.log("Load audio device list");
  // Load audio devices on startup
  audioDeviceManager.loadDevices();
  sttModelManager.loadModels();

  // Set up any additional event listeners or global state

  console.log("Application initialized");
})();

