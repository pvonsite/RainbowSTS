class TranscribeView {
    constructor(websocketHandler) {
        this.websocketHandler = websocketHandler;
        this.view = document.getElementById('original-text');

        // Bind event listeners
        this.websocketHandler.addEventListener('realtime', (data) => this.handleTranscription(data));
        this.websocketHandler.addEventListener('fullSentence', (data) => this.finalizeSentence(data));
        this.websocketHandler.addEventListener('connection', (data) => this.handleConnection(data));
        this.fullSentences = '';
        this.buildingSentence = ''
    }

    handleConnection(data) {
        if (data && data.status === 'connected') {
            console.log('WebSocket connected:', data);
            this.view.textContent = '';
        }
    }

    handleTranscription(data) {
        if (data && data.text) {
            this.buildingSentence = data.text;
            this.render()
        }
    }

    finalizeSentence(data) {
        console.log('Full sentence received:', data);
        if (data && data.text) {
            this.fullSentences = this.fullSentences.concat(data.text);
            this.buildingSentence = '';
            this.render()
        }
    }

    render() {
        this.view.textContent = this.fullSentences.concat(' ', this.buildingSentence).concat('...');
        console.log(this.view.textContent)
    }
}