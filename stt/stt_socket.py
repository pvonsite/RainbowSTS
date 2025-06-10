from RealtimeSTT import AudioToTextRecorder
import asyncio
import websockets
import threading
import numpy as np
from scipy.signal import resample
import json
import logging
import sys
from typing import Dict, Any, Optional, Callable


class RealtimeSTTWebSocket:
    """
    A class to manage a RealtimeSTT WebSocket server in a daemon thread.
    It handles audio streaming, speech-to-text conversion, and sending results to clients.
    """

    def __init__(self,
                 recorder_config: Dict[str, Any],
                 host: str = "localhost",
                 port: int = 8001,
                 on_text_callback: Optional[Callable[[str, str], None]] = None):
        """
        Initialize the RealtimeSTT WebSocket server.

        Args:
            recorder_config: Configuration dictionary for the AudioToTextRecorder
            host: Host address to bind the WebSocket server to
            port: Port number for the WebSocket server
            on_text_callback: Optional callback function that receives text type and content
        """
        # Set up logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[logging.StreamHandler(sys.stdout)]
        )
        logging.getLogger('websockets').setLevel(logging.WARNING)

        self.logger = logging.getLogger('RealtimeSTTWebSocket')

        # Store configuration
        self.recorder_config = recorder_config
        self.host = host
        self.port = port
        self.on_text_callback = on_text_callback

        # Initialize state variables
        self.is_running = False
        self.recorder = None
        self.recorder_ready = threading.Event()
        self.client_websocket = None
        self.main_loop = None
        self.server_task = None
        self.server_thread = None

        # Make sure the realtime transcription callback is set
        if 'on_realtime_transcription_update' not in self.recorder_config:
            self.recorder_config['on_realtime_transcription_update'] = self._text_detected

    def _text_detected(self, text: str) -> None:
        """
        Callback function for realtime text detection from RealtimeSTT.

        Args:
            text: The detected text
        """
        if self.main_loop is not None:
            # Schedule the sending on the main event loop
            asyncio.run_coroutine_threadsafe(
                self._send_to_client(json.dumps({
                    'type': 'realtime',
                    'text': text
                })), self.main_loop)

        self.logger.info(f"Realtime text: {text}")

        # Call user-provided callback if available
        if self.on_text_callback:
            self.on_text_callback('realtime', text)

    async def _send_to_client(self, message: str) -> None:
        """
        Send a message to the connected client.

        Args:
            message: The message to send
        """
        if self.client_websocket:
            try:
                await self.client_websocket.send(message)
            except websockets.exceptions.ConnectionClosed:
                self.client_websocket = None
                self.logger.info("Client disconnected")

    def _run_recorder(self) -> None:
        """
        Run the AudioToTextRecorder in a loop, handling full sentence detection.
        """
        self.logger.info("Initializing RealtimeSTT...")
        self.recorder = AudioToTextRecorder(**self.recorder_config)
        self.logger.info("RealtimeSTT initialized")
        self.recorder_ready.set()

        # Loop indefinitely checking for full sentence output.
        while self.is_running:
            try:
                full_sentence = self.recorder.text()
                if full_sentence:
                    if self.main_loop is not None:
                        asyncio.run_coroutine_threadsafe(
                            self._send_to_client(json.dumps({
                                'type': 'fullSentence',
                                'text': full_sentence
                            })), self.main_loop)

                    self.logger.info(f"Full sentence: {full_sentence}")

                    # Call user-provided callback if available
                    if self.on_text_callback:
                        self.on_text_callback('fullSentence', full_sentence)
            except Exception as e:
                self.logger.error(f"Error in recorder thread: {e}")
                continue

    def _decode_and_resample(self, audio_data: bytes, original_sample_rate: int,
                             target_sample_rate: int = 16000) -> bytes:
        """
        Decode and resample audio data to the target sample rate.

        Args:
            audio_data: The raw audio data bytes
            original_sample_rate: The original sample rate of the audio
            target_sample_rate: The target sample rate (default: 16000)

        Returns:
            Resampled audio data as bytes
        """
        try:
            audio_np = np.frombuffer(audio_data, dtype=np.int16)
            num_original_samples = len(audio_np)
            num_target_samples = int(num_original_samples * target_sample_rate / original_sample_rate)
            resampled_audio = resample(audio_np, num_target_samples)
            return resampled_audio.astype(np.int16).tobytes()
        except Exception as e:
            self.logger.error(f"Error in resampling: {e}")
            return audio_data

    async def _handle_client(self, websocket) -> None:
        """
        Handle WebSocket client connection and process incoming audio data.

        Args:
            websocket: The WebSocket connection
        """
        self.logger.info("Client connected")
        self.client_websocket = websocket

        try:
            async for message in websocket:
                if not self.recorder_ready.is_set():
                    self.logger.warning("Recorder not ready")
                    continue

                try:
                    # Read the metadata length (first 4 bytes)
                    metadata_length = int.from_bytes(message[:4], byteorder='little')
                    # Get the metadata JSON string
                    metadata_json = message[4:4 + metadata_length].decode('utf-8')
                    metadata = json.loads(metadata_json)
                    sample_rate = metadata['sampleRate']
                    # Get the audio chunk following the metadata
                    chunk = message[4 + metadata_length:]
                    resampled_chunk = self._decode_and_resample(chunk, sample_rate)
                    self.recorder.feed_audio(resampled_chunk)
                except Exception as e:
                    self.logger.error(f"Error processing message: {e}")
                    continue
        except websockets.exceptions.ConnectionClosed:
            self.logger.info("Client disconnected")
        finally:
            if self.client_websocket == websocket:
                self.client_websocket = None

    async def _main_server_loop(self) -> None:
        """
        Main server loop that initializes the recorder and starts the WebSocket server.
        """
        self.main_loop = asyncio.get_running_loop()

        # Start the recorder thread
        recorder_thread = threading.Thread(target=self._run_recorder)
        recorder_thread.daemon = True
        recorder_thread.start()
        self.recorder_ready.wait()

        self.logger.info(f"Server started on {self.host}:{self.port}. Use stop() to stop the server.")
        async with websockets.serve(self._handle_client, self.host, self.port):
            try:
                await asyncio.Future()  # run forever
            except asyncio.CancelledError:
                self.logger.info("Shutting down server...")
            finally:
                self.is_running = False

    def start(self) -> None:
        """
        Start the WebSocket server in a daemon thread.
        """
        if self.is_running:
            self.logger.warning("Server is already running")
            return

        self.is_running = True

        # Create a new event loop for the server thread
        def run_server():
            asyncio.run(self._main_server_loop())

        # Start the server thread
        self.server_thread = threading.Thread(target=run_server)
        self.server_thread.daemon = True
        self.server_thread.start()

        # Wait a bit to ensure server is starting properly
        import time
        time.sleep(0.5)

        self.logger.info(f"Server thread started on {self.host}:{self.port}")

    def stop(self) -> None:
        """
        Stop the WebSocket server and clean up resources.
        """
        if not self.is_running:
            self.logger.warning("Server is not running")
            return

        self.is_running = False

        # Stop and clean up the recorder
        if self.recorder:
            try:
                self.recorder.stop()
                self.recorder.shutdown()
                del self.recorder
                self.recorder = None
            except Exception as e:
                self.logger.error(f"Error stopping recorder: {e}")

        self.logger.info("Server stopped")

    def __del__(self):
        """
        Clean up resources when the object is garbage collected.
        """
        self.stop()


# Example usage
if __name__ == '__main__':
    # Example recorder configuration
    recorder_config = {
        'compute_type': 'int8_float32',
        'spinner': False,
        'use_microphone': True,
        'model': 'base',
        'input_device_index': 1,
        'realtime_model_type': 'base',
        'language': 'en',
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


    # Optional callback function
    def text_callback(text_type, text):
        print(f"Callback received: {text_type} - {text}")


    # Create and start the server
    server = RealtimeSTTWebSocket(
        recorder_config=recorder_config,
        host="localhost",
        port=8001,
        on_text_callback=text_callback
    )

    try:
        server.start()
        print("Press Ctrl+C to stop the server")
        import time

        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping server...")
    finally:
        server.stop()