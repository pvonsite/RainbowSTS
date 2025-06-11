import logging
import uuid

from flask import Flask, render_template, request, jsonify

from ws_session import WebsocketSession

MODELS = [
    'tiny',
    'tiny.en',
    'base',
    'base.en',
    'small',
    'small.en',
    'medium',
    'medium.en',
    'large-v1',
    'large-v2',
    'large-v3',
    'large',
    'distil-large-v2',
    'distil-medium',
    'larget-v3-turbo',
    'turbo',
]

app = Flask(__name__, static_folder='static')

# Store active sessions
active_sessions = {}


@app.route('/')
def index():
    """Serve the main web interface"""
    return render_template('index.html')


@app.route('/models')
def get_models():
    """Return available STT models"""
    try:
        return jsonify({'status': 'success', 'models': MODELS})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/start_session', methods=['POST'])
def start_session():
    """Start a new STT and translation session"""
    try:
        config = request.json
        # Generate a unique session ID
        session_id = str(uuid.uuid4())

        # Extract configuration parameters
        # TODO: fill this later
        stt_config = {
            'input_device_id': config.get('input_device_index'),
        }

        translation_config = {
            'model': config.get('translation_model', 'm2m100_418m'),
            'source_language': config.get('source_language', 'en'),
            'target_language': config.get('target_language', 'vi'),
        }

        # TODO: fill this later
        tts_config = {}

        # Determine which WebSocket port to use
        port = config.get('websocket_port', 8765)

        session_config = {
            'stt': stt_config,
            'translation': translation_config,
            'tts': tts_config,
        }

        ws_session = WebsocketSession(
            config=session_config,
            websocket_port=port,
        )
        logging.log(logging.INFO, f"Starting WebSocket session on port {port}")
        ws_session.start()

        # Save session information
        active_sessions[session_id] = {
            'ws_session': ws_session,
            'websocket_port': port
        }

        return jsonify({
            'status': 'success',
            'session_id': session_id,
            'message': 'Session creation completed, waiting for WebSocket connection',
            'websocket_url': f"ws://localhost:{port}"
        })

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/stop_session/<session_id>', methods=['POST'])
def stop_session(session_id):
    """Stop an active session"""
    if session_id in active_sessions:
        session = active_sessions[session_id]
        session['websocket_server'].stop()
        del active_sessions[session_id]
        return jsonify({'status': 'success', 'message': 'Session stopped'})
    else:
        return jsonify({'status': 'error', 'message': 'Session not found'}), 404


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)