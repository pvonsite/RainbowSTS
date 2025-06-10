from flask import Flask, render_template, request, jsonify
from stt import stt_socket
import threading
import uuid
import json

app = Flask(__name__, static_folder='static')

# Store active sessions
active_sessions = {}


@app.route('/')
def index():
    """Serve the main web interface"""
    return render_template('index.html')


@app.route('/start_session', methods=['POST'])
def start_session():
    """Start a new STT and translation session"""
    try:
        config = request.json

        # Generate a unique session ID
        session_id = str(uuid.uuid4())

        # Extract configuration parameters
        recorder_config = {
            'compute_type': 'int8_float32',
            'spinner': False,
            'use_microphone': True,
            'model': config.get('stt_model', 'base'),
            'language': config.get('source_language', 'en'),
            'silero_sensitivity': 0.05,
            'webrtc_sensitivity': 3,
            'min_length_of_recording': 1.1,
            'min_gap_between_recordings': 0,
            'enable_realtime_transcription': True,
            'realtime_processing_pause': 0.5,
            'silero_deactivity_detection': True,
            'early_transcription_on_silence': 0.2,
            'beam_size': 5,
            'beam_size_realtime': 3,
            'no_log_file': True,
            'initial_prompt': 'Add periods only for complete sentences. Use ellipsis (...) for unfinished thoughts or unclear endings.'
        }

        # Handle input device selection
        input_device_id = config.get('input_device_index')
        if input_device_id:
            recorder_config['input_device_index'] = input_device_id

        port = config.get('websocket_port', 8765)

        translation_config = {
            'target_language': config.get('target_language', 'fr')
        }

        # Start WebSocket server in a separate thread
        websocket_server = stt_socket.RealtimeSTTWebSocket(
            recorder_config=recorder_config,
            host="localhost",
            port=port,
            on_text_callback=None  # We can add a callback for translation if needed
        )
        websocket_server.start()

        # Save session information
        active_sessions[session_id] = {
            'websocket_server': websocket_server,
            'config': config,
            'websocket_port': port
        }

        return jsonify({
            'status': 'success',
            'session_id': session_id,
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