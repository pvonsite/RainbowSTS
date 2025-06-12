from typing import Callable

from component.stt import STTProcessor


class AudioSocketHandler:
    def __init__(self, stt : STTProcessor, tts = None):
        self.stt = stt

    def handle_audio_data(self, data: bytes):
        """
        Handle incoming audio data.
        This method should be called when new audio data is received.
        """
        if self.stt:
            self.stt.process_audio_data(bytes)
            print(f"Audio data sent to STT: {len(data)} bytes")