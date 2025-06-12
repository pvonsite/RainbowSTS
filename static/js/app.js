document.addEventListener('DOMContentLoaded', () => {
    // Initialize components
    const audioDeviceManager = new AudioDeviceManager();
    const sttModelManager = new STTModelManager();
    const websocketHandler = new WebSocketHandler();
    const audioRecorder = new AudioRecorder(websocketHandler);
    const sessionManager = new SessionManager(audioDeviceManager, websocketHandler, audioRecorder);
    const transcribeView = new TranscribeView(websocketHandler);

    console.log('Load audio device list');
    // Load audio devices on startup
    audioDeviceManager.loadDevices()
    sttModelManager.loadModels()

    // Set up any additional event listeners or global state

    console.log('Application initialized');
});