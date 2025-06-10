/**
 * Audio recording and processing
 */
class AudioRecorder {
    constructor(websocketHandler) {
        this.websocketHandler = websocketHandler;
        this.mediaRecorder = null;
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

            const stream = await navigator.mediaDevices.getUserMedia(constraints);

            this.mediaRecorder = new MediaRecorder(stream);
            this.audioChunks = [];

            this.mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0) {
                    this.audioChunks.push(event.data);

                    // Process and send audio data
                    this.processAudioChunk(event.data);
                }
            };

            // Use small time slices for real-time processing
            this.mediaRecorder.start(100);
            this.isRecording = true;

            this.statusElement.textContent = 'Status: Recording...';
            return true;
        } catch (error) {
            console.error('Error accessing microphone:', error);
            this.statusElement.textContent = 'Status: Error accessing microphone';
            throw error;
        }
    }

    stopRecording() {
        if (this.mediaRecorder && this.isRecording) {
            this.mediaRecorder.stop();
            this.mediaRecorder.stream.getTracks().forEach(track => track.stop());
            this.isRecording = false;
            this.statusElement.textContent = 'Status: Recording stopped';
        }
    }

    processAudioChunk(audioChunk) {
        // Convert audio chunk to format expected by server
        const audioBlob = new Blob([audioChunk], { type: 'audio/webm' });
        const reader = new FileReader();

        reader.onloadend = () => {
            // Get the audio data as ArrayBuffer
            const audioData = reader.result;

            // Create metadata
            const metadata = {
                sampleRate: 48000, // Standard sample rate, adjust if needed
                channels: 1,       // Mono audio
                format: 'webm'
            };
            const metadataStr = JSON.stringify(metadata);
            const metadataBytes = new TextEncoder().encode(metadataStr);

            // Create a buffer with metadata length (4 bytes) + metadata + audio data
            const metadataLength = new ArrayBuffer(4);
            new DataView(metadataLength).setInt32(0, metadataBytes.length, true);

            // Combine all parts into a single ArrayBuffer
            const combined = new Uint8Array([
                ...new Uint8Array(metadataLength),
                ...metadataBytes,
                ...new Uint8Array(audioData)
            ]);

            // Send the combined data
            this.websocketHandler.sendAudioData(combined.buffer);
        };

        reader.readAsArrayBuffer(audioBlob);
    }
}