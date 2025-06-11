/**
 * WebSocket communication handler
 */
class WebSocketHandler {
    constructor() {
        this.socket = null;
        this.isConnected = false;
        this.listeners = {
            'transcription': [],
            'fullSentence': [],
            'translation': [],
            'recording_start': [],
            'recording_stop': [],
            'vad_detect_start': [],
            'vad_detect_stop': [],
            'transcription_start': [],
            'start_turn_detection': [],
            'stop_turn_detection': []
        };
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
    }

    /**
     * Connect to WebSocket server
     * @param {string} url - WebSocket URL
     */
    connect(url) {
        if (this.socket) {
            this.disconnect();
        }

        console.log(`Connecting to WebSocket: ${url}`);
        this.socket = new WebSocket(url);

        this.socket.onopen = () => {
            console.log('WebSocket connection established');
            this.isConnected = true;
            this.reconnectAttempts = 0;

            // Notify listeners about connection
            this._notifyListeners('connection', { status: 'connected' });
        };

        this.socket.onclose = (event) => {
            console.log(`WebSocket connection closed: ${event.code} - ${event.reason}`);
            this.isConnected = false;

            // Attempt to reconnect if connection was closed unexpectedly
            if (event.code !== 1000 && this.reconnectAttempts < this.maxReconnectAttempts) {
                this.reconnectAttempts++;
                console.log(`Attempting to reconnect (${this.reconnectAttempts}/${this.maxReconnectAttempts})...`);
                setTimeout(() => this.connect(url), 2000);
            }

            // Notify listeners about disconnection
            this._notifyListeners('connection', { status: 'disconnected', code: event.code, reason: event.reason });
        };

        this.socket.onerror = (error) => {
            console.error('WebSocket error:', error);
            // Notify listeners about error
            this._notifyListeners('error', { error: error });
        };

        this.socket.onmessage = (event) => {
            let data;

            // Handle binary data (audio chunks)
            if (event.data instanceof Blob) {
                // Handle binary data if needed
                // For example, for TTS audio playback
                this._notifyListeners('audio', { data: event.data });
                return;
            }

            // Handle text data (JSON messages)
            try {
                data = JSON.parse(event.data);

                // Process different message types
                if (data.type) {
                    switch (data.type) {
                        case 'realtime':
                        case 'transcription':
                            // Realtime transcription updates
                            this._notifyListeners('transcription', {
                                text: data.text,
                                isFinal: false
                            });

                            // Update UI with original text
                            const originalTextElement = document.getElementById('original-text');
                            if (originalTextElement) {
                                originalTextElement.textContent = data.text;
                            }
                            break;

                        case 'fullSentence':
                            // Complete sentence transcription
                            this._notifyListeners('fullSentence', {
                                text: data.text,
                                isFinal: true
                            });

                            // Update UI with final original text
                            const finalOriginalTextElement = document.getElementById('original-text');
                            if (finalOriginalTextElement) {
                                finalOriginalTextElement.textContent = data.text;
                            }
                            break;

                        case 'translation':
                            // Translation result
                            this._notifyListeners('translation', {
                                original: data.original,
                                translated: data.translated,
                                isFinal: data.is_final
                            });

                            // Update UI with translated text
                            const translatedTextElement = document.getElementById('translated-text');
                            if (translatedTextElement) {
                                translatedTextElement.textContent = data.translated;
                            }
                            break;

                        case 'recording_start':
                        case 'recording_stop':
                        case 'vad_detect_start':
                        case 'vad_detect_stop':
                        case 'transcription_start':
                        case 'start_turn_detection':
                        case 'stop_turn_detection':
                            // Handle various STT events
                            this._notifyListeners(data.type, data);
                            break;

                        default:
                            console.log('Received unknown message type:', data);
                    }
                }
            } catch (error) {
                console.error('Error parsing WebSocket message:', error, event.data);
            }
        };
    }

    /**
     * Disconnect from WebSocket server
     */
    disconnect() {
        if (this.socket) {
            this.socket.close(1000, 'Client disconnected');
            this.socket = null;
            this.isConnected = false;
        }
    }

    /**
     * Send a command to the server
     * @param {string} command - Command name
     * @param {object} params - Additional parameters
     */
    sendCommand(command, params = {}) {
        if (!this.isConnected) {
            console.error('Cannot send command: WebSocket not connected');
            return;
        }

        const message = {
            command: command,
            ...params
        };

        this.socket.send(JSON.stringify(message));
    }

    isSocketReady() {
        return this.socket && this.socket.readyState === WebSocket.OPEN;
    }

    getWebSocket() {
        return this.socket;
    }

    /**
     * Add event listener
     * @param {string} eventType - Event type
     * @param {function} callback - Callback function
     */
    addEventListener(eventType, callback) {
        if (this.listeners[eventType]) {
            this.listeners[eventType].push(callback);
        } else {
            this.listeners[eventType] = [callback];
        }
    }

    /**
     * Remove event listener
     * @param {string} eventType - Event type
     * @param {function} callback - Callback function
     */
    removeEventListener(eventType, callback) {
        if (this.listeners[eventType]) {
            this.listeners[eventType] = this.listeners[eventType]
                .filter(listener => listener !== callback);
        }
    }

    /**
     * Notify all listeners of an event
     * @param {string} eventType - Event type
     * @param {object} data - Event data
     * @private
     */
    _notifyListeners(eventType, data) {
        if (this.listeners[eventType]) {
            this.listeners[eventType].forEach(callback => {
                try {
                    callback(data);
                } catch (error) {
                    console.error(`Error in ${eventType} listener:`, error);
                }
            });
        }
    }

    /**
     * Check if WebSocket is connected
     * @returns {boolean} True if connected
     */
    getConnectionStatus() {
        return this.isConnected;
    }
}