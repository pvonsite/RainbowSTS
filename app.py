import asyncio
import logging
import sys
import uuid

from flask import Flask, render_template, request, jsonify

import utils
from ws_session import WebsocketSession

#logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
#logging.getLogger().setLevel(logging.INFO)

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

logger = logging.getLogger(__name__)
app = Flask(__name__, static_folder='static')

# Store active sessions
active_sessions = {}


@app.route('/')
def index():
    """Serve the main web interface"""
    return render_template('index.html')

@app.route('/models')
def get_models():
    try:
        return jsonify({'status': 'success', 'models': {
            'speechtotext': utils.STT_MODELS,
            'translation': [model['name'] for model in utils.TRANSLATE_MODELS if model['supported']],
            'texttospeech': utils.TTS_SUPPORTED_ENGINES,
            }})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/models/tts_engine/<engine_name>')
def get_tts_engine_supported_voices(engine_name):
    """Return supported voices for a specific TTS engine"""
    language = None
    if request.args.get('lang'):
        language = request.args.get('lang')
    try:
        voices = utils.get_supported_voices(engine_name, language)
        voices = [voice.name for voice in voices if hasattr(voice, 'name')]   # Convert to dict if needed
        return jsonify({'status': 'success', 'voices': voices })
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
            'model': config.get('stt_model', 'base'),
            'language': config.get('source_language', 'en'),
        }

        translation_config = {
            'model': config.get('translation_model', 'facebook/m2m100_418M'),
            'source_language': config.get('source_language', 'en'),
            'target_language': config.get('target_language', 'vi'),
        }

        # TODO: fill this later
        tts_config = {
            'tts_engine': 'edge',
            'language': config.get('target_language', 'vi'),
        }

        # Determine which WebSocket port to use
        port = config.get('websocket_port', 8765)

        session_config = {
            'stt': stt_config,
            'translation': translation_config,
            'tts': tts_config,
        }
        print(f"Starting session with config: {session_config}")
        ws_session = WebsocketSession(
            stt_config=stt_config,
            translation_config=translation_config,
            tts_config=tts_config,
            websocket_port=port,
        )
        print(f"Starting WebSocket session on port {port}")
        ws_session.start()
        print("WebSocket session creation is success")

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
        session['ws_session'].stop()
        del active_sessions[session_id]
        return jsonify({'status': 'success', 'message': 'Session stopped'})
    else:
        return jsonify({'status': 'error', 'message': 'Session not found'}), 404


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3000, debug=True)
