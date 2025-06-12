class RecorderProcessor extends AudioWorkletProcessor {
    constructor() {
        super();
        this.buffer = [];
    }

    process(inputs) {
        const input = inputs[0];
        if (input.length > 0) {
            const channelData = input[0]; // Float32Array(128)
            this.buffer.push(...channelData); // accumulate

            if (this.buffer.length >= 1024) {
                const chunk = this.buffer.slice(0, 1024);
                this.buffer = this.buffer.slice(1024);
                this.port.postMessage(chunk);
            }
        }

        return true;
    }
}

registerProcessor('recorder-worklet', RecorderProcessor);
