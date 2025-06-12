import asyncio
import json
import logging
import queue
import threading
import time
from asyncio import AbstractEventLoop

import websockets

from component import stt, translation
from handler.audio_socket_handler import AudioSocketHandler
from handler.command_handler import CommandHandler

logger = logging.getLogger("ws_audio")

class WebsocketManager:
    def __init__(self,
                 host="localhost",
                 stt_config = None,
                 translation_config = None,
                 tts_config = None):

        self.host = host
        self.port = 0  # Port will be set later
        self.clients = set()
        self.websocket = None
        self.ws_thread = None

        # Initialize queues for communication between components
        self.shared_queue = queue.Queue() # Shared queue for broadcast messages
        self.stt_to_translator_queue = queue.Queue()  # Queue for STT to Translation
        self.translator_to_tts_queue = queue.Queue()  # Queue for Translation to TTS

        print("Create STT processor")
        # Create component instances
        self.stt = stt.STTProcessor(
            stt_config,
            self.shared_queue
        )

        print("Create Translation processor")
        self.translator = translation.TranslationProcessor(
            translation_config,
            self.stt_to_translator_queue,
            self.translator_to_tts_queue
        )

        self.audio_socket_handler = AudioSocketHandler(self.stt)

        # Initialize command handler
        self.command_handler = CommandHandler()
        self.stt.register_commands(self.command_handler.register_listener)

    async def _handler(self, websocket : websockets.ServerConnection):
        logger.info(f"Audio client connected: {websocket}")
        self.clients.add(websocket)
        send_task = None
        try:
            # Set up a task to send messages to this client
            send_task = asyncio.create_task(self._send_messages_to_client(websocket))

            async for message in websocket:
                try:
                    if isinstance(message, bytes):
                        print(f"Received audio data. Sending to AudioSocketHandler")
                        self.audio_socket_handler.handle_audio_data(message)
                    else:
                        data = json.loads(message)
                        if not data or 'command' not in data:
                            print("Invalid message format received")
                            continue

                        cnt_listeners = self.command_handler.handle_message(data.get('command'), data)
                        print(f"Command '{data.get('command')}' processed, {cnt_listeners} listeners notified")

                except json.JSONDecodeError as e:
                    print(f"JSON decode error: {str(e)}")
                except Exception as e:
                    print(f"Audio WS error: {str(e)}")

        except Exception as e:
            logger.error(f"Audio WS error: {str(e)}")
        finally:
            self.clients.remove(websocket)
            logger.info(f"Audio client disconnected: {websocket}")
            if send_task:
                send_task.cancel()


    async def _send_messages_to_client(self, websocket : websockets.ServerConnection):
        """
        Sends messages to the websocket client and relevant services.
        """
        while True:
            try:
                while not self.shared_queue.empty():
                    message = self.shared_queue.get()
                    if not message or 'type' not in message:
                        print("Invalid message format in shared queue")

                    type = message['type']
                    await websocket.send(json.dumps(message))
                    print(f"Sent message to client: {type}, message: {message}")
                    as_command = message.get('as_command', False)
                    if as_command:
                        cnt_listeners = self.command_handler.handle_message(type, message)
                        print(f"Command '{type}' processed, {cnt_listeners} listeners notified")
            except queue.Empty:
                await asyncio.sleep(0.05)
            except Exception as e:
                logger.error(f"Error sending message to client: {str(e)}")
                await asyncio.sleep(0.1)


    def _run_server(self, loop : AbstractEventLoop):
        print("Starting Audio WebSocket server")
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._running_web_socket())
        finally:
            loop.close()
            print("Audio WebSocket server stopped")

    async def _running_web_socket(self):
        async with websockets.serve(
            handler=self._handler,
            host=self.host,
            port=self.port
        ) as websocket:
            for socket in websocket.sockets:
                if socket and socket.getsockname()[1]:
                    self.port = socket.getsockname()[1]
            self.websocket = websocket
            await asyncio.Future()

    def start(self) -> int:
        print("Creating thread for Audio WebSocket server")
        loop = asyncio.new_event_loop()
        self.ws_thread = threading.Thread(target=self._run_server, args=(loop,), daemon=True)
        self.ws_thread.start()

        # After starting the thread, wait for the server to start to get the port
        start_time = time.time()
        while not self.websocket:
            # Wait for max 2 seconds
            if time.time() - start_time > 2:
                print("Timeout waiting for WebSocket server to start")
                return -1
            start_time = time.time()

        print(f"Audio WebSocket server started on ws://{self.host}:{self.port}")
        return self.port

    def stop(self):
        if self.websocket:
            print("Stopping Audio WebSocket server")
            self.websocket.close()
            self.ws_thread.join(timeout=1)
            print("Audio WebSocket server stopped")
        else:
            print("Audio WebSocket server is not running")


