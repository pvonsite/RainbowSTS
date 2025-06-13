(() => {
  // Initialize components
  window.audioDeviceManager = new AudioDeviceManager();
  window.modelManager = new ModelManager();
  window.websocketHandler = new WebSocketHandler();
  window.audioRecorder = new AudioRecorder(websocketHandler);
  window.state = new State();
  window.sessionManager = new SessionManager(
    audioDeviceManager,
    websocketHandler,
    audioRecorder,
  );
  window.transcribeView = new TranscribeView(websocketHandler);

  console.log("Load audio device list");
  // Load audio devices on startup
  audioDeviceManager.loadDevices();
  modelManager.loadModels();

  // Set up any additional event listeners or global state

  console.log("Application initialized");
})();
