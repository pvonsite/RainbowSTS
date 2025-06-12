# stt/session_manager.py
import threading
import queue
import logging
import json
import asyncio
import time

import websockets
from component import stt, translation


class WebsocketSession:
    """Manages the complete STT, translation, and TTS pipeline"""

    def __init__(self, stt_config, translation_config, tts_config, websocket_port=8765):
        """
        Initialize the session manager
        
        Args:
            stt_config: Configuration for the STT processor
            translation_config: Configuration for the translation processor
            tts_config: Configuration for the TTS processor
            websocket_port: Port for the WebSocket server
        """
        self.websocket_port = websocket_port
        self.logger = logging.getLogger("WebsocketSession")

        # Set up queues for communication between components
        self.stt_input_queue = asyncio.Queue()  # Audio data in
        self.stt_to_translator_queue = queue.Queue()  # Transcribed text
        self.translator_to_tts_queue = queue.Queue()  # Translated text
        self.tts_output_queue = queue.Queue()  # Audio data out
        self.websocket_output_queue = queue.Queue()  # Messages to send to client
        self.shared_queue = queue.Queue()  # Shared queue for inter-component communication

        # Start the queue monitor in a separate thread
        self.queue_monitor_thread = threading.Thread(
            target=self._monitor_component_queues,
            daemon=True
        )

        print("Create STT processor")
        # Create component instances
        self.stt_processor = stt.STTProcessor(
            stt_config,
            self.stt_input_queue,
            self.shared_queue
        )

        print("Create Translation processor")
        self.translator = translation.TranslationProcessor(
            translation_config,
            self.stt_to_translator_queue,
            self.translator_to_tts_queue
        )

        # self.tts_processor = TTSProcessor(
        #     config.get('tts_config', {}),
        #     self.translator_to_tts_queue,
        #     self.tts_output_queue
        # )
        self.tts_processor = None

        # WebSocket server
        self.websocket_server = None
        self.websocket_thread = None
        self.clients = set()
        self.running = False

    async def _handle_websocket_client(self, websocket : websockets.ServerConnection):
        """Handle a WebSocket client connection"""
        print(f"Client connected: {websocket}")
        self.clients.add(websocket)

        try:
            # Set up a task to send messages to this client
            send_task = asyncio.create_task(self._send_messages_to_client(websocket))

            # Process incoming messages from the client
            async for message in websocket:
                try:
                    # Handle binary data (audio)
                    if isinstance(message, bytes):
                        asyncio.run_coroutine_threadsafe(
                            self.stt_input_queue.put({
                                'type': 'audio_data',
                                'data': message
                            }), self.stt_processor.loop)
                    # Handle text messages (commands)
                    else:
                        data = json.loads(message)
                        command = data.get('command')

                        if command == 'start_listening':
                            print("Received start_listening command")
                            asyncio.run_coroutine_threadsafe(
                                self.stt_input_queue.put({
                                    'type': 'command',
                                    'command': 'start_listening'
                                }), self.stt_processor.loop)

                        elif command == 'stop_listening':
                            self.logger.info("Received stop_listening command")
                            print("Received stop_listening command")
                            asyncio.run_coroutine_threadsafe(
                                self.stt_input_queue.put({
                                    'type': 'command',
                                    'command': 'stop_listening'
                                }), self.stt_processor.loop)

                except json.JSONDecodeError:
                    self.logger.warning(f"Received invalid JSON: {message}")
                except Exception as e:
                    self.logger.error(f"Error processing client message: {str(e)}")

        except websockets.exceptions.ConnectionClosed:
            self.logger.info(f"Client disconnected: {websocket.remote_address}")
        except Exception as e:
            self.logger.error(f"WebSocket error: {str(e)}")
        finally:
            self.clients.remove(websocket)
            if not self.clients:
                self.logger.info("Last client disconnected, initiating shutdown")
                # Schedule the shutdown in a separate task to avoid deadlocks
                asyncio.create_task(self._shutdown_after_disconnect())

            send_task.cancel()

    async def _send_messages_to_client(self, websocket):
        """Send messages from the output queue to the client"""
        while True:
            try:
                while not self.shared_queue.empty():
                    message = self.shared_queue.get(block=False)
                    if message['type'] == 'transcription':
                        print(f"Sending transcription to client: {message}")
                        # request translation for the transcription
                        self.stt_to_translator_queue.put(message)
                        # Currently, we're not sending audio back to client
                        # But you could implement this if needed
                        pass

                # Check if there are messages to process from STT or translation
                while not self.stt_to_translator_queue.empty():
                    message = self.stt_to_translator_queue.get(block=False)
                    if message['type'] == 'transcription':
                        print(f"Sending transcription to client: {message}")
                        # Send transcription to client
                        await websocket.send(json.dumps({
                            'type': 'transcription',
                            'text': message['text'],
                            'is_final': message.get('is_final', False)
                        }))

                while not self.translator_to_tts_queue.empty():
                    message = self.translator_to_tts_queue.get(block=False)
                    if message['type'] == 'translation':
                        # Send translation to client
                        await websocket.send(json.dumps({
                            'type': 'translation',
                            'original': message['original'],
                            'translated': message['translated'],
                            'is_final': message.get('is_final', False)
                        }))

                # Check the dedicated websocket queue
                while not self.websocket_output_queue.empty():
                    message = self.websocket_output_queue.get(block=False)
                    await websocket.send(json.dumps(message))

                # Short delay to prevent CPU hogging
                await asyncio.sleep(0.05)
            except queue.Empty:
                await asyncio.sleep(0.05)
            except Exception as e:
                self.logger.error(f"Error sending message to client: {str(e)}")
                await asyncio.sleep(0.1)

    async def _run_websocket_server(self):
        """Run the WebSocket server"""
        print(f"Starting WebSocket server on port {self.websocket_port}")
        async with websockets.serve(
                self._handle_websocket_client,
                "localhost",
                self.websocket_port
        ) as server:
            self.websocket_server = server
            await asyncio.Future()  # Run forever

    def _monitor_component_queues(self):
        """Monitor and forward messages between component queues"""
        while self.running:
            try:
                # Check TTS output queue and forward to websocket
                if not self.tts_output_queue.empty():
                    message = self.tts_output_queue.get(block=False)
                    if message['type'] == 'tts_audio':
                        # Currently, we're not sending audio back to client
                        # But you could implement this if needed
                        pass

                time.sleep(0.01)  # Small sleep to prevent CPU hogging
            except queue.Empty:
                pass
            except Exception as e:
                self.logger.error(f"Error in queue monitor: {str(e)}")

    def start(self):
        """Start all components and the WebSocket server"""
        try:
            self.running = True
            self.logger.info("Starting components")
            print("Starting components")

            loop = asyncio.new_event_loop()
            print("Get asyncio event loop")

            # Start the processors
            self.stt_processor.start()
            self.translator.start()
            # self.tts_processor.start()

            print("Starting queue monitor thread")
            self.queue_monitor_thread.start()

            # Start the WebSocket server in a separate thread
            print("Starting WebSocket server thread")
            self.websocket_thread = threading.Thread(
                target=self._run_websocket_server_in_thread,
                args=(loop,),
                daemon=True
            )
            self.websocket_thread.start()


        except Exception as e:
            self.logger.error(f"Error starting session: {str(e)}")
            self.stop()
            raise

    def _run_websocket_server_in_thread(self, loop):
        """Run the WebSocket server in a separate thread"""
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._run_websocket_server())
        except Exception as e:
            self.logger.error(f"Error in WebSocket server thread: {str(e)}")

    def stop(self):
        """Stop all components and the WebSocket server"""
        print("Stopping session")
        if not self.running:
            print("Session is already stopped")
            return

        self.running = False

        # Stop each processor
        try:
            self.stt_processor.stop()
        except:
            pass

        try:
            self.translator.stop()
        except:
            pass

        try:
            self.tts_processor.stop()
        except:
            pass

        # Stop the WebSocket server
        if self.websocket_server:
            try:
                self.websocket_server.close()
            except:
                pass

        print("Stopping queue monitor thread")
        if self.queue_monitor_thread.is_alive():
            self.queue_monitor_thread.join(timeout=1)

        print("WebSocket session stopped")

    async def _shutdown_after_disconnect(self):
        """Safely shut down the session after clients disconnect"""
        print("Shutting down session after client disconnect")

        # Stop in a separate thread to avoid blocking the event loop
        shutdown_thread = threading.Thread(target=self.stop)
        shutdown_thread.daemon = True
        shutdown_thread.start()

