import asyncio
from typing import Optional, List, Set
from .models import UserStatus, Message, NotificationBuffer
from datetime import datetime

class StatusManager:
    """Manages user status and notification buffering"""
    
    def __init__(self):
        self.current_status = UserStatus.ACTIVE
        self.buffer = NotificationBuffer()
        self.status_listeners = []
        self._status_history = []
        self._cleanup_handlers = []

    
    def add_cleanup_handler(self, handler):
        """Add handler to be called during cleanup"""
        self._cleanup_handlers.append(handler)

    async def cleanup(self):
        """Clean up resources"""
        for handler in self._cleanup_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler()
                else:
                    handler()
            except Exception as e:
                self.logger.error(f"Error in cleanup handler: {e}")

        self.buffer.clear()
        self.status_listeners.clear()
        self._status_history.clear()

    def set_status(self, status: UserStatus, auto_buffer: bool = True):
        """Set user status and optionally start buffering"""
        old_status = self.current_status
        self.current_status = status
        self._status_history.append((status, datetime.now().timestamp()))
        
        # Handle buffering
        if auto_buffer:
            if status == UserStatus.FOCUSED or status == UserStatus.DND:
                self.buffer.start_buffering()
            elif old_status in (UserStatus.FOCUSED, UserStatus.DND):
                self._flush_buffer()
                
        # Notify listeners
        for listener in self.status_listeners:
            listener(old_status, status)

    def add_buffer_exception(self, entity_id: str):
        """Add exception to notification buffering"""
        self.buffer.exceptions.add(entity_id)

    def remove_buffer_exception(self, entity_id: str):
        """Remove exception from notification buffering"""
        self.buffer.exceptions.discard(entity_id)

    def should_buffer(self, message: Message) -> bool:
        """Check if message should be buffered"""
        return self.buffer.add_message(message)

    def _flush_buffer(self) -> List[Message]:
        """Stop buffering and return buffered messages"""
        return self.buffer.stop_buffering()

    def get_buffer_summary(self) -> str:
        """Get summary of buffered messages"""
        return self.buffer.get_summary()

    def get_status_duration(self) -> float:
        """Get duration of current status in seconds"""
        if not self._status_history:
            return 0.0
        return datetime.now().timestamp() - self._status_history[-1][1]

    def add_status_listener(self, listener):
        """Add listener for status changes"""
        self.status_listeners.append(listener)

    def remove_status_listener(self, listener):
        """Remove status change listener"""
        self.status_listeners.remove(listener)