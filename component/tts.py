# component/tts.py
import asyncio
import logging
import threading
import time
import queue
import os
from collections import deque
from RealtimeTTS import TextToAudioStream, BaseEngine, EdgeEngine, SystemEngine, EdgeVoice
from sympy.physics.units import volume


class TTSProcessor(threading.Thread):
    """Text-to-Speech processor that runs in its own thread"""

    def __init__(self, config, input_queue: asyncio.Queue, output_queue: asyncio.Queue):
        """
        Initialize the TTS processor

        Args:
            config: Configuration dictionary for TTS
            input_queue: Queue for receiving text to synthesize
            output_queue: Queue for sending synthesized audio
        """
        super().__init__()
        self.config = config
        print(f"Config: {self.config}")
        self.input_queue: asyncio.Queue = input_queue
        self.output_queue: asyncio.Queue = output_queue
        self.daemon = True
        self.running = False

        # TTS queue for the worker thread
        self.tts_queue = queue.Queue()

        self.tts_engine : BaseEngine | None = None
        self.tts_stream : TextToAudioStream | None = None
        print("Initializing TTS engine...")
        self._init_tts_engine()

        # Batch configuration
        self.batch_size = config.get('batch_size', 3)  # Synthesize when buffer reaches this size
        self.max_wait_time = config.get('max_wait_time', 5.0)  # Seconds to wait before synthesizing
        self.min_previous_sentences = 2  # Minimum number of previous sentences to include

        self.loop = None  # Event loop for async processing
        self.flag_wait_last_sentence = False  # Flag to wait for the last sentence before streaming new one

        self.tts_worker_thread = threading.Thread(target=self._tts_worker, daemon=True)

        print(f"Initialized TTSProcessor with engine: {self.config.get('tts_engine', 'system')}")

    def _init_tts_engine(self):
        """Initialize the RealtimeTTS engine based on configuration"""
        try:
            engine_type = self.config.get('tts_engine', 'system')
            if engine_type == 'system':
                self.tts_engine = SystemEngine()
            elif engine_type == 'edge':
                self.tts_engine = EdgeEngine()
            else:
                # Default to system engine if not specified
                self.tts_engine = SystemEngine()

            self.tts_engine.set_voice(self.config.get('voice', 'vi-VN-HoaiMyNeural'))  # Set voice if specified

            self.tts_stream = TextToAudioStream(
                self.tts_engine,
                language=self.config.get('language', 'vi'),
                on_audio_stream_start=self._on_audio_stream_start,
                on_audio_stream_stop=self._on_audio_stream_stop,
                level=logging.DEBUG
            )
        except Exception as e:
            print(f"Error initializing TTS engine: {str(e)}")

    def _on_audio_stream_start(self):
        """Callback when audio stream starts"""
        print("Audio stream started")

    def _on_audio_stream_stop(self):
        """Callback when audio stream ends"""
        print("Audio stream ended")
        self.flag_wait_last_sentence = False

    def run(self):
        """Main thread execution"""
        try:
            self.running = True
            print("TTS processor starting...")
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.tts_worker_thread.start()
            self.loop.run_until_complete(self._process_input_queue())

        except Exception as e:
            print(f"Error in TTS processor: {str(e)}")
        finally:
            self.stop()
            print("TTS processor stopped")

    async def _process_input_queue(self):
        while self.running:
            try:
                # Wait for new messages in the input queue
                message = await self.input_queue.get()
                if message['command'] == 'synthesize':
                    # Add the sentence to the buffer with a timestamp
                    self.tts_queue.put(message['translated'])
                    print(f"Added sentence to TTS buffer: {message['translated']}")

            except asyncio.QueueEmpty:
                pass
            except Exception as e:
               print(f"Error processing input queue: {str(e)}")

    def _tts_worker(self):
        while self.running:
            if self.flag_wait_last_sentence or self.tts_stream.is_playing():
                # Wait for the last sentence to be added before processing
                if not self.tts_queue.empty():
                    self.flag_wait_last_sentence = False
                time.sleep(0.1)  # Small delay to prevent CPU thrashing
                continue

            # the last sentence is synthesized, so we can process the next one
            try:
                # Get the next sentence from the queue
                sentence = self.tts_queue.get(timeout=1)
                print(f"[TTSWorker] Got sentence: {sentence}")
                print(f"[TTSWorker] Stream playing? {self.tts_stream.is_playing()}")
                if not sentence:
                    continue

                if self.tts_stream:
                    self.flag_wait_last_sentence = True
                    # Use the same parameters as the debug method
                    self.tts_stream.feed(sentence).play(log_synthesized_text=True)

            except queue.Empty:
                continue
            except Exception as e:
                print(f"Error in TTS worker: {str(e)}")


    def stop(self):
        """Stop the TTS processor"""
        self.running = False
        if hasattr(self, 'loop') and self.loop:
            for task in asyncio.all_tasks(self.loop):
                task.cancel()

        if self.tts_stream:
            self.tts_stream.stop()

        self.tts_worker_thread.join()