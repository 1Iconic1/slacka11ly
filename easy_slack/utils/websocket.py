import asyncio
from typing import Dict, Optional, Callable, Any, List
import logging
from slack_sdk.socket_mode import SocketModeClient
from slack_sdk.socket_mode.response import SocketModeResponse
from slack_sdk.socket_mode.request import SocketModeRequest
from slack_sdk.web import WebClient
from ..core.models import Message
from ..core.enums import MessageType  # Add this import

# In websocket.py

class SlackEventHandler:
    """Handles real-time Slack events via WebSocket"""
    
    def __init__(self, app_token: str, bot_token: str):
        self.logger = logging.getLogger("SlackEvents")
        self.web_client = WebClient(token=bot_token)
        self.socket_client = SocketModeClient(
            app_token=app_token,
            web_client=self.web_client
        )
        
        self._message_handler: Optional[Callable] = None
        self._presence_handler: Optional[Callable] = None
        self._status_handler: Optional[Callable] = None
        
        self._connected = False
        self._running = False
        self._loop = None

    async def start(self):
        if self._running:
            return

        self._running = True
        self._loop = asyncio.get_event_loop()

        def handle_events(client, req):
            if not self._running:
                return

            if req.type == "events_api":
                event = req.payload["event"]
                event_type = event["type"]
                
                try:
                    if event_type == "message" and self._message_handler:
                        asyncio.run_coroutine_threadsafe(
                            self._message_handler(event),  # Pass the raw event
                            self._loop
                        )
                    elif event_type == "presence_change" and self._presence_handler:
                        asyncio.run_coroutine_threadsafe(
                            self._presence_handler(event),
                            self._loop
                        )
                    elif event_type == "user_status_changed" and self._status_handler:
                        asyncio.run_coroutine_threadsafe(
                            self._status_handler(event),
                            self._loop
                        )
                except Exception as e:
                    self.logger.error(f"Error handling event: {e}")

        try:
            self.socket_client.socket_mode_request_listeners.clear()
            self.socket_client.socket_mode_request_listeners.append(handle_events)
            
            self.socket_client.connect()
            self._connected = True
            self.logger.info("Connected to Slack WebSocket")
            
            while self._running:
                await asyncio.sleep(1)
                
        except Exception as e:
            self.logger.error(f"WebSocket error: {e}")
            self._running = False
    
    def _convert_slack_message(self, event: dict) -> Message:
        """Convert Slack event to internal message format"""
        msg_type = MessageType.CHANNEL  # Now using MessageType enum
        
        if event.get('channel_type') == 'im':
            if event.get('user') == event.get('channel'):  # Message to self
                msg_type = MessageType.DIRECT
        elif event.get('thread_ts'):
            msg_type = MessageType.THREAD
        elif f'<@{event.get("user")}>' in event.get('text', ''):
            msg_type = MessageType.MENTION

        return Message(
            id=event.get('client_msg_id', ''),
            content=event.get('text', ''),
            sender_id=event.get('user', ''),
            sender_name=self._get_user_name(event.get('user', '')),
            channel_id=event.get('channel', ''),
            thread_id=event.get('thread_ts'),
            timestamp=float(event.get('ts', 0)),
            message_type=msg_type,
            mentions=self._extract_mentions(event.get('text', ''))
        )

    def _get_user_name(self, user_id: str) -> str:
        """Get user name from Slack API"""
        try:
            if not user_id:
                return "Unknown User"
            response = self.web_client.users_info(user=user_id)
            if response['ok']:
                return response['user']['real_name']
            return "Unknown User"
        except Exception as e:
            self.logger.error(f"Error getting user name: {e}")
            return "Unknown User"

    def _extract_mentions(self, text: str) -> List[str]:
        """Extract user mentions from message text"""
        import re
        return re.findall(r'<@([A-Z0-9]+)>', text or '')

    async def _handle_disconnect(self):
        """Handle disconnection and attempt reconnection"""
        if not self._connected:
            return
            
        self._connected = False
        
        if self._running and self._reconnect_attempt < self.MAX_RECONNECT_ATTEMPTS:
            self._reconnect_attempt += 1
            delay = min(2 ** self._reconnect_attempt, 30)
            self.logger.info(f"Attempting reconnection {self._reconnect_attempt}/{self.MAX_RECONNECT_ATTEMPTS} in {delay}s")
            
            await asyncio.sleep(delay)
            try:
                self.socket_client.connect()
                self._connected = True
                self.logger.info("Reconnected to Slack WebSocket")
            except Exception as e:
                self.logger.error(f"Reconnection failed: {str(e)}")
        else:
            self.logger.error("Max reconnection attempts reached")
            self._running = False

    def on_message(self, handler: Callable[[Dict], Any]):
        """Register message event handler"""
        self._message_handler = handler

    def on_presence_change(self, handler: Callable[[Dict], Any]):
        """Register presence change handler"""
        self._presence_handler = handler

    def on_status_change(self, handler: Callable[[Dict], Any]):
        """Register status change handler"""
        self._status_handler = handler

    async def stop(self):
        """Stop listening for events"""
        self._running = False
        if self.socket_client:
            self.socket_client.disconnect()
            self._connected = False
            self.logger.info("Disconnected from Slack WebSocket")