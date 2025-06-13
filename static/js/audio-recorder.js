/**
 * Audio recording and processing
 */
class AudioRecorder {
    constructor(websocketHandler) {
        this.websocketHandler = websocketHandler;
        this.recorderNode = null;
        this.audioChunks = [];
        this.isRecording = false;
        this.statusElement = document.getElementById('status');
    }

    async startRecording(deviceId) {
        if (this.isRecording) return;

        try {
            // Use the selected audio device
            const constraints = {
                audio: {
                    deviceId: deviceId ? { exact: deviceId } : undefined
                }
            };

            const audioContext = new AudioContext();
            await audioContext.audioWorklet.addModule('static/js/recorder-worklet.js');
            const stream = await navigator.mediaDevices.getUserMedia(constraints);
            const input = audioContext.createMediaStreamSource(stream);
            this.recorderNode = new AudioWorkletNode(audioContext, 'recorder-worklet');

            this.recorderNode.port.onmessage = (event) => {
                this.processAudioChunk(event.data, audioContext.sampleRate)
            }

            input.connect(this.recorderNode);
            this.recorderNode.connect(audioContext.destination);

            this.isRecording = true

            this.statusElement.textContent = 'Status: Recording...';
            return true;
        } catch (error) {
            console.error('Error accessing microphone:', error);
            this.statusElement.textContent = 'Status: Error accessing microphone';
            throw error;
        }
    }

    stopRecording() {
        if (this.recorderNode && this.isRecording) {
            this.recorderNode.stopRecording()
            this.isRecording = false;
            this.statusElement.textContent = 'Status: Recording stopped';
        }
    }

    processAudioChunk(audioChunk) {
        if (this.websocketHandler.isSocketReady()) {
            const float32Array = new Float32Array(audioChunk);
            const pcm16Data = new Int16Array(float32Array.length);

            for (let i = 0; i < float32Array.length; i++) {
                pcm16Data[i] = Math.max(-1, Math.min(1, float32Array[i])) * 0x7FFF;
            }

            const metadata = JSON.stringify({ sampleRate: 48000, channels: 1, format: 'webm' });
            const metadataLength = new Uint32Array([metadata.length]);
            const metadataBuffer = new TextEncoder().encode(metadata);

            const message = new Uint8Array(
                metadataLength.byteLength + metadataBuffer.byteLength + pcm16Data.byteLength
            );

            message.set(new Uint8Array(metadataLength.buffer), 0);
            message.set(metadataBuffer, metadataLength.byteLength);
            message.set(new Uint8Array(pcm16Data.buffer), metadataLength.byteLength + metadataBuffer.byteLength);

            this.websocketHandler.getWebSocket().send(message);
        }
    }
}