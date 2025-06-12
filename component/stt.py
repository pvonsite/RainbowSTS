import asyncio
import json
import threading
import queue
import logging
import time
from typing import Callable

import numpy as np
import base64
from datetime import datetime
from difflib import SequenceMatcher
from collections import deque

import torch
from RealtimeSTT import AudioToTextRecorder


class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def _decode_and_resample(audio_data, original_sample_rate, target_sample_rate):
    """Decode and resample audio data if necessary"""
    from scipy.signal import resample

    # If sample rates match, no resampling needed
    if original_sample_rate == target_sample_rate:
        return audio_data

    # Convert bytes to numpy array
    audio_np = np.frombuffer(audio_data, dtype=np.int16)

    # Calculate the number of samples after resampling
    num_original_samples = len(audio_np)
    num_target_samples = int(num_original_samples * target_sample_rate / original_sample_rate)

    # Resample the audio
    resampled_audio = resample(audio_np, num_target_samples)

    # Convert back to bytes
    return resampled_audio.astype(np.int16).tobytes()


def _preprocess_text(text):
    """Preprocess the transcribed text"""
    # Remove leading whitespaces
    text = text.lstrip()

    # Remove starting ellipses if present
    if text.startswith("..."):
        text = text[3:]

    if text.endswith("...'."):
        text = text[:-1]

    if text.endswith("...'"):
        text = text[:-1]

    # Remove any leading whitespaces again after ellipses removal
    text = text.lstrip()

    # Uppercase the first letter
    if text:
        text = text[0].upper() + text[1:]

    return text


def _on_transcription_start(audio_bytes):
    """Handle transcription start event"""
    bytes_b64 = base64.b64encode(audio_bytes.tobytes()).decode('utf-8')
    message = json.dumps({
        'type': 'transcription_start',
        'audio_bytes_base64': bytes_b64
    })
    #asyncio.run_coroutine_threadsafe(self.websocket.send(message), self.loop)


class STTProcessor(threading.Thread):
    """Speech-to-Text processor that runs in its own thread"""

    def __init__(self, config, output_queue : queue.Queue):
        """
        Initialize the STT processor

        Args:
            config: Configuration dictionary for STT
            output_queue: Queue for sending transcribed text
        """
        super().__init__()

        self.config = config
        self.output_queue = output_queue
        self.daemon = True
        self.running = False
        self.recorder = None
        self.logger = logging.getLogger("STTProcessor")

        # Initialize state variables
        self.prev_text = ""
        self.text_time_deque = deque()

        # Configuration for silence timing
        self.silence_timing = config.get('silence_timing', False)
        self.hard_break_even_on_background_noise = config.get('hard_break_even_on_background_noise', 10)
        self.hard_break_even_on_background_noise_min_texts = config.get('hard_break_even_on_background_noise_min_texts', 5)
        self.hard_break_even_on_background_noise_min_similarity = config.get('hard_break_even_on_background_noise_min_similarity', 0.99)
        self.hard_break_even_on_background_noise_min_chars = config.get('hard_break_even_on_background_noise_min_chars', 15)
        print("Constructing STT completed")


    def register_commands(self, register_func : Callable[[str, Callable], None]):
        print("STT processor registering commands")
        register_func('start_listening', self._start_listening)
        register_func('stop_listening', self._stop_listening)


    def run(self):
        """Main thread execution"""
        try:
            self.running = True
            print("STT processor starting...")

            # Print initialization info
            print(f"{bcolors.OKGREEN}Initializing STT processor with parameters:{bcolors.ENDC}")
            for key, value in self.config.items():
                print(f"    {bcolors.OKBLUE}{key}{bcolors.ENDC}: {value}")

            # Check if GPU is available
            device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            print(f"Using device: {device}")

            compute_type = 'int8_float32' if device.type == 'cpu' else 'float32'

            # Configure STT recorder
            self.recorder = AudioToTextRecorder(
                use_microphone=False,  # Set to False for WebSocket input
                level=logging.INFO,
                spinner=False,
                compute_type=compute_type,
                device=device.type,
                model=self.config.get('model', 'base'),
                realtime_model_type=self.config.get('model', 'base'),
                language=self.config.get('language', 'en'),
                silero_sensitivity=self.config.get('silero_sensitivity', 0.05),
                webrtc_sensitivity=self.config.get('webrtc_sensitivity', 3),
                min_length_of_recording=self.config.get('min_length_of_recording', 1.1),
                min_gap_between_recordings=self.config.get('min_gap_between_recordings', 0),
                enable_realtime_transcription=self.config.get('enable_realtime_transcription', True),
                realtime_processing_pause=self.config.get('realtime_processing_pause', 0.5),
                silero_deactivity_detection=self.config.get('silero_deactivity_detection', True),
                early_transcription_on_silence=self.config.get('early_transcription_on_silence', 0.2),
                beam_size=self.config.get('beam_size', 5),
                beam_size_realtime=self.config.get('beam_size_realtime', 3),
                no_log_file=self.config.get('no_log_file', True),
                initial_prompt=self.config.get('initial_prompt',
                                               'Add periods only for complete sentences. Use ellipsis (...) for unfinished thoughts or unclear endings.'),
                on_realtime_transcription_update=self._on_realtime_transcription,
                on_recording_start=self._on_recording_start,
                on_recording_stop=self._on_recording_stop,
                on_vad_detect_start=self._on_vad_detect_start,
                on_vad_detect_stop=self._on_vad_detect_stop,
                on_transcription_start=_on_transcription_start,
                on_turn_detection_start=self._on_turn_detection_start,
                on_turn_detection_stop=self._on_turn_detection_stop,
            )

            print(f"{bcolors.OKGREEN}{bcolors.BOLD}STT processor initialized{bcolors.ENDC}")
            # Run the coroutine in this thread's event loop
            while self.running:
                self.recorder.text(self._process_text)

        except Exception as e:
            print(f"Error in STT processor: {str(e)}")
        finally:
            self.stop()
            print("STT processor stopped")

    def _process_text(self, full_sentence):
        self.prev_text = ""
        full_sentence = _preprocess_text(full_sentence)
        print(f"Sentence: {full_sentence}")
        self.output_queue.put({
            'type': 'fullSentence',
            'as_command': True,
            'command': 'translate',
            'text': full_sentence
        })

    def process_audio_data(self, audio_data):
        """Process audio data received from WebSocket"""
        try:
            # Check if audio data contains metadata
            if isinstance(audio_data, bytes) and len(audio_data) > 4:
                # Check for metadata header
                metadata_length = int.from_bytes(audio_data[:4], byteorder='little')

                if 0 < metadata_length < len(audio_data) - 4:
                    # Extract metadata and audio
                    metadata_bytes = audio_data[4:4 + metadata_length]
                    audio_bytes = audio_data[4 + metadata_length:]

                    try:
                        # Parse metadata
                        metadata = json.loads(metadata_bytes.decode('utf-8'))
                        sample_rate = metadata.get('sampleRate', 48000)
                        format_type = metadata.get('format', 'webm')
                        channels = metadata.get('channels', 1)

                        # Process the audio with the recorder
                        if self.recorder:
                            # Resample if needed and feed to recorder
                            processed_audio = _decode_and_resample(
                                audio_bytes,
                                sample_rate,
                                self.recorder.sample_rate
                            )
                            self.recorder.feed_audio(processed_audio)
                    except json.JSONDecodeError:
                        print("Failed to parse audio metadata JSON")
                else:
                    # No metadata, assume default format
                    self.recorder.feed_audio(audio_data)
            else:
                # No metadata, assume default format
                self.recorder.feed_audio(audio_data)

        except Exception as e:
            print(f"Error processing audio data: {str(e)}")

    def _start_listening(self):
        """Start listening for audio"""
        if self.recorder:
            # Clear any previous state
            self.recorder.clear_audio_queue()
            # Start the recorder in listening mode
            self.recorder.start()

    def _stop_listening(self):
        """Stop listening for audio"""
        if self.recorder:
            self.recorder.stop()
            self.recorder.clear_audio_queue()

    def _on_realtime_transcription(self, text):
        """Handle real-time transcription updates"""
        text = _preprocess_text(text)

        if self.silence_timing:
            def ends_with_ellipsis(t):
                if t.endswith("..."):
                    return True
                if len(t) > 1 and t[:-1].endswith("..."):
                    return True
                return False

            def sentence_end(t):
                sentence_end_marks = ['.', '!', '?', '。']
                if t and t[-1] in sentence_end_marks:
                    return True
                return False

            if ends_with_ellipsis(text):
                self.recorder.post_speech_silence_duration = self.config.get('mid_sentence_detection_pause', 1.0)
            elif sentence_end(text) and sentence_end(self.prev_text) and not ends_with_ellipsis(self.prev_text):
                self.recorder.post_speech_silence_duration = self.config.get('end_of_sentence_detection_pause', 2.0)
            else:
                self.recorder.post_speech_silence_duration = self.config.get('unknown_sentence_detection_pause', 1.5)

            # Append the new text with its timestamp
            current_time = time.time()
            self.text_time_deque.append((current_time, text))

            # Remove texts older than hard_break_even_on_background_noise seconds
            while self.text_time_deque and self.text_time_deque[0][
                0] < current_time - self.hard_break_even_on_background_noise:
                self.text_time_deque.popleft()

            # Check if we have enough texts in the queue and they're similar
            if len(self.text_time_deque) >= self.hard_break_even_on_background_noise_min_texts:
                texts = [t[1] for t in self.text_time_deque]
                first_text = texts[0]
                last_text = texts[-1]

                # Compute the similarity ratio between the first and last texts
                similarity = SequenceMatcher(None, first_text, last_text).ratio()

                if (similarity > self.hard_break_even_on_background_noise_min_similarity and
                        len(first_text) > self.hard_break_even_on_background_noise_min_chars):
                    self.recorder.stop()
                    self.recorder.clear_audio_queue()
                    self.prev_text = ""

        self.prev_text = text

        # Put the message in the output queue
        self.output_queue.put({
            'type': 'transcription',
            'text': text,
            'is_final': False
        })

        # Log the message
        timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
        if self.config.get('extended_logging', False):
            print(f"  [{timestamp}] Realtime text: {bcolors.OKCYAN}{text}{bcolors.ENDC}\n", flush=True, end="")
        else:
            print(f"\r[{timestamp}] {bcolors.OKCYAN}{text}{bcolors.ENDC}", flush=True, end='')

    def _on_recording_start(self):
        """Handle recording start event"""
        self.output_queue.put({
            'type': 'recording_start'
        })

    def _on_recording_stop(self):
        """Handle recording stop event"""
        self.output_queue.put({
            'type': 'recording_stop'
        })

    def _on_vad_detect_start(self):
        """Handle VAD detection start event"""
        self.output_queue.put({
            'type': 'vad_detect_start'
        })

    def _on_vad_detect_stop(self):
        """Handle VAD detection stop event"""
        self.output_queue.put({
            'type': 'vad_detect_stop'
        })

    def _on_turn_detection_start(self):
        print("&&& stt_server on_turn_detection_start")
        self.output_queue.put({
            'type': 'start_turn_detection'
        })

    def _on_turn_detection_stop(self):
        print("&&& stt_server on_turn_detection_stop")
        self.output_queue.put({
            'type': 'stop_turn_detection'
        })

    def stop(self):
        """Stop the STT processor"""
        if not self.running:
            return

        self.running = False
        print("Stopping STT processor...")
        if self.recorder:
            try:
                self.recorder.clear_audio_queue()
                print("Call stop")
                self.recorder.stop()
                print("Call shutdown")
                self.recorder.shutdown()
                print("STT recorder stopped")
            except Exception as e:
                print(f"Error stopping recorder: {str(e)}")

        self.join(500)