class State extends EventTarget {
  static TITLES = [
    "Let's speak",
    "Connecting to server",
    "I'm listening",
    "Taking break",
  ];

  static STATES = { WAITING: 0, CONNECTING: 1, PLAYING: 2, PAUSED: 3 };

  title = State.TITLES[State.STATES.WAITING];
  state = State.STATES.WAITING;
  selectedS2tModel = "";
  selectedT2sModel = "";
  selectedTransModel = "";
  selectedAudioCaptureDevice = "";
  selectedAudioPlaybackDevice = "";
  srcLanguage = "";
  dstLanguage = "";
  session = null;

  async play() {
    if (this.state !== State.STATES.WAITING) return;

    if (this.session) {
      this.session.play();
    }

    this.state = State.STATES.CONNECTING;
    this.title = State.TITLES[this.state];

    this.dispatchEvent(new Event("titleChanged"));
    this.dispatchEvent(new Event("stateChanged"));

    console.log(await sessionManager.startSession());
  }

  async pause() {
    if (this.state !== State.STATES.PLAYING) return;

    this.state = State.STATES.PAUSED;
    this.title = State.TITLES[this.state];

    this.dispatchEvent(new Event("titleChanged"));
    this.dispatchEvent(new Event("stateChanged"));
  }

  async stop() {
    if (this.state !== State.STATES.PAUSED) {
      return;
    }
  }

  setSourceLanguage(language) {
    this.srcLanguage = language;
    this.dispatchEvent(new Event("sourceLanguageChanged"));
  }

  setDestinationLanguage(language) {
    this.dstLanguage = language;
    this.dispatchEvent(new Event("destinationLanguageChanged"));
  }

  setModel(model) {
    this.selectedModel = model;
    this.dispatchEvent(new Event("modelChanged"));
  }

  setAudioCaptureDevice(deviceId) {
    this.selectedAudioCaptureDevice = deviceId;
    this.dispatchEvent(new Event("audioCaptureDeviceChanged"));
  }

  setAudioPlaybackDevice(deviceId) {
    this.selectedAudioPlaybackDevice = deviceId;
    this.dispatchEvent(new Event("audioPlaybackDeviceChanged"));
  }

  setSpeechToTextModel(model) {
    this.selectedS2tModel = model;
    this.dispatchEvent(new Event("speechToTextModelChanged"));
  }

  setTextToSpeechModel(model) {
    this.selectedT2sModel = model;
    this.dispatchEvent(new Event("textToSpeechModelChanged"));
  }

  setTranslationModel(model) {
    this.selectedTransModel = model;
    this.dispatchEvent(new Event("translationModelChanged"));
  }

  get isWaiting() {
    return this.state === State.STATES.WAITING;
  }
  get isConnecting() {
    return this.state === State.STATES.CONNECTING;
  }
  get isPlaying() {
    return this.state === State.STATES.PLAYING;
  }
  get isPaused() {
    return this.state === State.STATES.PAUSED;
  }
}
