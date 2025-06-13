# component/translation.py
import asyncio
import logging
import threading
import time
import queue
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

        # Translation queue for the worker thread
        self.translation_queue = queue.Queue()

        # Keep track of previously translated sentences
        self.previous_sentences = deque(maxlen=10)  # Store last 10 translated sentences

        # Batch translation configuration
        self.batch_size = config.get('batch_size', 3)  # Translate when buffer reaches this size
        self.max_wait_time = config.get('max_wait_time', 5.0)  # Seconds to wait before translating
        self.min_previous_sentences = 2  # Minimum number of previous sentences to include

        # Translation model configuration
        self.model_name = config.get('model', 'facebook/m2m100_418M')
        self.source_language = config.get('source_language', 'en')
        self.target_language = config.get('target_language', 'vi')
        self.device = torch.device(
            "cuda" if torch.cuda.is_available() and not config.get('force_cpu', False) else "cpu")

        # Initialize model and tokenizer as None, will load in run()
        # Load model and tokenizer
        start_time = time.time()
        print(f"Loading translation model {self.model_name}...")
        self.model = M2M100ForConditionalGeneration.from_pretrained(self.model_name).to(self.device)
        self.tokenizer = M2M100Tokenizer.from_pretrained(self.model_name)
        self.tokenizer.src_lang = self.source_language
        print(f"Model loaded in {time.time() - start_time:.2f} seconds")

        # Start the translation worker thread
        self.translation_thread = threading.Thread(target=self._translation_worker, daemon=True)
        self.loop = None

        print(f"Initialized TranslationProcessor with device: {self.device}")

    def run(self):
        """Main thread execution"""
        try:
            self.running = True
            print("Translation processor starting...")
            self.translation_thread.start()
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.loop.run_until_complete(self._process_input_queue())

        except Exception as e:
            logger.error(f"Error in translation processor: {str(e)}", exc_info=True)
        finally:
            self.stop()
            print("Translation processor stopped")

    async def _process_input_queue(self):
        while self.running:
            try:
                # Wait for new messages in the input queue
                message = await self.input_queue.get()
                if message['command'] == 'translate':
                    # Add the sentence to the buffer with a timestamp
                    self.translation_buffer.append(message['text'])
                    self.sentence_timestamps.append(time.time())
                    print(f"Added sentence to translation buffer: {message['text']}")

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
                    self._prepare_translation_batch()

            except asyncio.QueueEmpty:
                pass
            except Exception as e:
                logger.error(f"Error processing input queue: {str(e)}", exc_info=True)

    def _prepare_translation_batch(self):
        """Prepare a batch for translation and send to the translation queue"""
        if not self.translation_buffer:
            return

        try:
            batch = []
            timestamps = []

            # Add current sentences to the batch
            batch.extend(self.translation_buffer)
            timestamps.extend(self.sentence_timestamps)

            # Add previous sentences to ensure continuity
            prev_count = min(len(self.previous_sentences), self.min_previous_sentences)
            if prev_count > 0:
                # Get the most recent previous sentences
                prev_sentences = list(self.previous_sentences)[-prev_count:]
                # Add them to the beginning of the batch
                batch = prev_sentences + batch
                # Add dummy timestamps for previous sentences
                timestamps = [timestamps[0] - 0.1] * prev_count + timestamps

            print(f"Sending batch of {len(batch)} sentences to translation queue")

            # Send to translation queue with timestamps
            self.translation_queue.put((batch, timestamps, prev_count))

            # Clear the buffer and timestamps
            self.translation_buffer = []
            self.sentence_timestamps = []

        except Exception as e:
            logger.error(f"Error preparing translation batch: {str(e)}", exc_info=True)

    def _translation_worker(self):
        """Worker thread that processes the translation queue"""
        while self.running or not self.translation_queue.empty():
            try:
                # Get the next batch from the queue
                batch, timestamps, prev_count = self.translation_queue.get(timeout=1.0)

                if not batch:
                    continue

                print(f"Translating batch of {len(batch)} sentences (including {prev_count} previous sentences)")

                results = []
                # Process each sentence
                for i, sentence in enumerate(batch):
                    start_time = time.time()

                    # Skip re-translating previous sentences
                    if i < prev_count:
                        # This is a previous sentence, already translated
                        results.append({
                            'original': sentence,
                            'translated': None,  # Will be filtered out later
                            'processing_time': 0.0,
                            'is_previous': True
                        })
                        continue

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
                        'processing_time': time.time() - start_time,
                        'is_previous': False
                    }
                    results.append(result)
                    print(f"Translated: {sentence} → {translated_text}")

                    # Add to previous sentences for future batches
                    self.previous_sentences.append(sentence)

                # Send new results to output queue (skip previous sentences)
                for result in results:
                    if not result.get('is_previous', False):
                        asyncio.run_coroutine_threadsafe(
                            self.output_queue.put({
                                'type': 'translation',
                                'original': result['original'],
                                'translated': result['translated'],
                                'is_final': True,
                                'processing_time': result['processing_time']
                            }), self.loop)

                self.translation_queue.task_done()

            except queue.Empty:
                # No translations to process, continue waiting
                pass
            except Exception as e:
                logger.error(f"Error in translation worker thread: {str(e)}", exc_info=True)

    def stop(self):
        """Stop the translation processor"""
        self.running = False
        if hasattr(self, 'loop') and self.loop:
            for task in asyncio.all_tasks(self.loop):
                task.cancel()

        self.translation_thread.join()

