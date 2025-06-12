# component/translation.py
import asyncio
import threading
import queue
import logging
import time
from collections import deque
import torch
from transformers import M2M100ForConditionalGeneration, M2M100Tokenizer


logger = logging.getLogger("TranslationProcessor")
logger.setLevel(logging.DEBUG)

class TranslationProcessor(threading.Thread):
    """Translation processor that runs in its own thread"""

    def __init__(self, config, input_queue : asyncio.Queue, output_queue : asyncio.Queue):
        """
        Initialize the translation processor

        Args:
            config: Configuration dictionary for translation
            input_queue: Queue for receiving text to translate
            output_queue: Queue for sending translated text
        """
        super().__init__()
        self.config = config
        self.input_queue : asyncio.Queue = input_queue
        self.output_queue : asyncio.Queue = output_queue
        self.daemon = True
        self.running = False

        # Translation buffer
        self.translation_buffer = []  # Buffer to store sentences for batch translation
        self.sentence_timestamps = []  # Timestamps for when sentences were added

        # Batch translation configuration
        self.batch_size = config.get('batch_size', 3)  # Translate when buffer reaches this size
        self.max_wait_time = config.get('max_wait_time', 2.0)  # Seconds to wait before translating

        # Translation model configuration
        self.model_name = config.get('model', 'facebook/m2m100_418M')
        self.source_language = config.get('source_language', 'en')
        self.target_language = config.get('target_language', 'vi')
        self.device = torch.device(
            "cuda" if torch.cuda.is_available() and not config.get('force_cpu', False) else "cpu")

        # Initialize model and tokenizer as None, will load in run()
        self.model = None
        self.tokenizer = None
        self.loop = None

        print(f"Initialized TranslationProcessor with device: {self.device}")

    def run(self):
        """Main thread execution"""
        try:
            self.running = True
            print("Translation processor starting...")
            self.loop = asyncio.new_event_loop()

            # Load model and tokenizer
            start_time = time.time()
            print(f"Loading translation model {self.model_name}...")
            self.model = M2M100ForConditionalGeneration.from_pretrained(self.model_name).to(self.device)
            self.tokenizer = M2M100Tokenizer.from_pretrained(self.model_name)
            self.tokenizer.src_lang = self.source_language
            print(f"Model loaded in {time.time() - start_time:.2f} seconds")

            # Process the input queue
            while self.running:
                try:
                    # Check for new messages
                    while not self.input_queue.empty():
                        message = self.input_queue.get(block=False)

                        if message['type'] == 'transcription' and message.get('is_final', False):
                            # Add the sentence to the buffer with a timestamp
                            self.translation_buffer.append(message['text'])
                            self.sentence_timestamps.append(time.time())
                            print(f"Added sentence to translation buffer: {message['text']}")

                        elif message['type'] == 'command':
                            command = message['command']
                            if command == 'translate':
                                # Force translation of current buffer
                                self.translation_buffer.append(message['text'])
                                self.sentence_timestamps.append(time.time())
                            elif command == 'shutdown':
                                # Translate any remaining text and exit
                                if self.translation_buffer:
                                    self._translate_buffer()
                                self.running = False

                    # Check if we should translate based on buffer size or time
                    current_time = time.time()
                    should_translate = False

                    # Translate if buffer has reached batch size
                    if len(self.translation_buffer) >= self.batch_size:
                        should_translate = True

                    # Translate if oldest sentence has been waiting too long
                    elif self.translation_buffer and (current_time - self.sentence_timestamps[0] >= self.max_wait_time):
                        should_translate = True

                    if should_translate:
                        self._translate_buffer()

                    # Small sleep to prevent CPU hogging
                    time.sleep(0.1)

                except queue.Empty:
                    pass
                except Exception as e:
                    logger.error(f"Error in translation processing: {str(e)}", exc_info=True)

        except Exception as e:
            logger.error(f"Error in translation processor: {str(e)}", exc_info=True)
        finally:
            self.stop()
            print("Translation processor stopped")

    def _translate_buffer(self):
        """Translate all sentences in the buffer"""
        if not self.translation_buffer:
            return

        try:
            print(f"Translating batch of {len(self.translation_buffer)} sentences")

            results = []
            # Process each sentence
            for i, sentence in enumerate(self.translation_buffer):
                start_time = time.time()

                # Encode and translate
                encoded = self.tokenizer(sentence, return_tensors="pt").to(self.device)
                generated_tokens = self.model.generate(
                    **encoded,
                    forced_bos_token_id=self.tokenizer.get_lang_id(self.target_language)
                )

                # Decode the result
                translated_text = self.tokenizer.batch_decode(generated_tokens, skip_special_tokens=True)[0]

                # Create result object
                result = {
                    'original': sentence,
                    'translated': translated_text,
                    'processing_time': time.time() - start_time
                }
                results.append(result)

                print(f"Translated: {sentence} → {translated_text}")

            # Send all results to output queue
            for result in results:
                self.output_queue.put({
                    'type': 'translation',
                    'original': result['original'],
                    'translated': result['translated'],
                    'is_final': True,
                    'processing_time': result['processing_time']
                })

            # Clear the buffer and timestamps
            self.translation_buffer = []
            self.sentence_timestamps = []

        except Exception as e:
            logger.error(f"Error translating buffer: {str(e)}", exc_info=True)

    def stop(self):
        """Stop the translation processor"""
        if not self.running:
            return

        print("Stopping translation processor")
        self.running = False

        # Translate any remaining sentences
        if self.translation_buffer:
            try:
                self._translate_buffer()
            except:
                pass

        # Release resources
        self.model = None
        self.tokenizer = None
        torch.cuda.empty_cache()  # Free GPU memory if using CUDA