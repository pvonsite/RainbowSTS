from typing import Dict, List, Callable, Any

from component.stt import STTProcessor


class CommandHandler:
    """
    Handles command messages and distributes them to registered listeners.
    Listeners can register to receive specific message types.
    """

    def __init__(self):
        # Dictionary to store listeners by message type
        self.listeners: Dict[str, List[Callable[[Any], None]]] = {}

    def register_listener(self, message_type: str, listener: Callable[[Any], None]) -> None:
        """
        Register a listener for a specific message type.

        Args:
            message_type: The type of message to listen for
            listener: The callback function to be called when a message of this type is received
        """
        if message_type not in self.listeners:
            self.listeners[message_type] = []

        if listener not in self.listeners[message_type]:
            self.listeners[message_type].append(listener)
            print(f"Listener registered for message type: {message_type}")

    def unregister_listener(self, message_type: str, listener: Callable[[Any], None]) -> bool:
        """
        Unregister a listener for a specific message type.

        Args:
            message_type: The type of message
            listener: The callback function to be removed

        Returns:
            bool: True if the listener was removed, False otherwise
        """
        if message_type in self.listeners and listener in self.listeners[message_type]:
            self.listeners[message_type].remove(listener)
            print(f"Listener unregistered for message type: {message_type}")

            # Clean up empty listener lists
            if not self.listeners[message_type]:
                del self.listeners[message_type]

            return True
        return False

    def handle_message(self, message_type: str, message_data: Any) -> int:
        """
        Handle an incoming message by distributing it to all registered listeners.

        Args:
            message_type: The type of the message
            message_data: The data payload of the message

        Returns:
            int: The number of listeners that received the message
        """
        if message_type not in self.listeners:
            return 0

        listener_count = 0
        for listener in self.listeners[message_type]:
            try:
                listener(message_data)
                listener_count += 1
            except Exception as e:
                print(f"Error in listener for message type {message_type}: {str(e)}")

        return listener_count

    def get_listener_count(self, message_type: str = None) -> int:
        """
        Get the count of registered listeners.

        Args:
            message_type: Optional message type to count listeners for.
                          If None, returns the total count across all types.

        Returns:
            int: The number of listeners
        """
        if message_type:
            return len(self.listeners.get(message_type, []))

        # Count all listeners across all message types
        return sum(len(listeners) for listeners in self.listeners.values())
