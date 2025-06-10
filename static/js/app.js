document.addEventListener('DOMContentLoaded', () => {
    // Initialize components
    const audioDeviceManager = new AudioDeviceManager();
    const websocketHandler = new WebSocketHandler();
    const audioRecorder = new AudioRecorder(websocketHandler);
    const sessionManager = new SessionManager(audioDeviceManager, websocketHandler, audioRecorder);

    // Load audio devices on startup
    audioDeviceManager.loadDevices();

    // Set up any additional event listeners or global state

    console.log('Application initialized');
});