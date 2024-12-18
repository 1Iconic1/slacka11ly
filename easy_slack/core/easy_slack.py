import asyncio
from typing import Optional, Dict, List, Set
import logging
from pathlib import Path
from slack_sdk import WebClient

from .models import (
    Message, 
    UserStatus, 
    NotificationPriority, 
    MessageType,
    NotifySound
)
from .rules import RuleEngine, RuleBuilder
from .sound_management import NotificationManager
from .status import StatusManager
from ..utils.websocket import SlackEventHandler
from ..utils.db import Database

class EasySlack:
    """Main class for accessible Slack interactions"""
    
    def __init__(self, config_dir: Optional[Path] = None):
        # Initialize basic components
        self.logger = logging.getLogger("EasySlack")
        self.config_dir = config_dir or Path.home() / '.easy_slack'
        self.config_dir.mkdir(exist_ok=True)
        
        # Initialize storage and managers
        self.db = Database(self.config_dir / 'workspace.db')
        self.notify_manager = NotificationManager(self.config_dir)
        self.status_manager = StatusManager()
        self.rule_engine = RuleEngine()  # Initialize without self
        
        # These will be set up during login
        self._web_client: Optional[WebClient] = None
        self._event_handler: Optional[SlackEventHandler] = None
        self._user_id: Optional[str] = None
        self._user_email: Optional[str] = None
        
        # Connect status manager
        self.status_manager.add_status_listener(self._handle_status_change)
    

    def get_user_by_email(self, email: str) -> Optional[Dict]:
        """Get user information from Slack API using email"""
        if not self._web_client:
            self.logger.error("Slack client not initialized. Please login first.")
            return None
            
        try:
            response = self._web_client.users_lookupByEmail(email=email)
            if response['ok']:
                return response['user']
            return None
        except Exception as e:
            self.logger.error(f"Error looking up user by email: {e}")
            return None

    def _convert_email_to_user_id(self, email: str) -> Optional[str]:
        """Convert email to Slack user ID using API"""
        user_info = self.get_user_by_email(email)
        if user_info:
            return user_info['id']
        return None

    async def login(self, email: str) -> bool:
        """Login to Slack workspace and set up components"""
        try:
            # Get tokens from database
            tokens = self.db.get_tokens()
            if not tokens:
                self.notify_manager.notify(
                    Message(
                        id="system",
                        content="Workspace not set up. Please run setup first.",
                        sender_id="system",
                        sender_name="System",
                        channel_id=None,
                        thread_id=None,
                        timestamp=0,
                        message_type=MessageType.DIRECT
                    ),
                    "urgent"
                )
                return False

            # Set up clients
            self._web_client = WebClient(token=tokens['bot_token'])
            self._event_handler = SlackEventHandler(
                app_token=tokens['app_token'],
                bot_token=tokens['bot_token']
            )

            # Look up the user's Slack ID
            user_info = self.get_user_by_email(email)
            if not user_info:
                self.logger.error(f"Could not find Slack user with email: {email}")
                return False

            # Set user information
            self._user_id = user_info['id']
            self._user_email = email
            
            self.logger.info(f"Logged in as user: {user_info['name']} (ID: {self._user_id})")

            # Now that we have web_client and user info, attach to RuleEngine
            self.rule_engine.set_slack_client(self)

            # Register event handlers
            self._event_handler.on_message(self._handle_message)
            self._event_handler.on_presence_change(self._handle_presence_change)
            self._event_handler.on_status_change(self._handle_status_change)

            return True

        except Exception as e:
            self.logger.error(f"Login failed: {str(e)}")
            return False
        
    def when(self, trigger: str) -> RuleBuilder:
        """Start building a notification rule"""
        return RuleBuilder(self.rule_engine).when(trigger)

    async def start(self):
        """Start listening for events"""
        if not self._event_handler:
            self.logger.error("Not logged in")
            return

        try:
            self.logger.info("Starting EasySlack")
            await self._event_handler.start()
        except Exception as e:
            self.logger.error(f"Error starting: {str(e)}")

    def set_status(self, status: UserStatus):
        """Set user status"""
        try:
            self.status_manager.set_status(status)
            self.rule_engine.set_status(status)
            self.notify_manager.set_status(status)
            
            # Update Slack status
            if self._web_client:
                status_emoji = {
                    UserStatus.ACTIVE: ":green_circle:",
                    UserStatus.FOCUSED: ":headphones:",
                    UserStatus.DND: ":no_entry:",
                    UserStatus.AWAY: ":clock1:"
                }.get(status, ":speech_balloon:")
                
                asyncio.create_task(
                    self._event_handler.update_status(
                        status.value,
                        status_emoji
                    )
                )
        except Exception as e:
            self.logger.error(f"Error setting status: {str(e)}")

    def add_exception(self, email: str):
        """Add notification exception"""
        user = self.db.get_user_by_email(email)
        if user:
            self.status_manager.add_exception(user['id'])
            self.notify_manager.notify(
                Message(
                    id="system",
                    content=f"Added exception for {user['name']}",
                    sender_id="system",
                    sender_name="System",
                    channel_id=None,
                    thread_id=None,
                    timestamp=0,
                    message_type=MessageType.DIRECT
                ),
                "success"
            )
        else:
            self.notify_manager.notify(
                Message(
                    id="system",
                    content=f"User {email} not found",
                    sender_id="system",
                    sender_name="System",
                    channel_id=None,
                    thread_id=None,
                    timestamp=0,
                    message_type=MessageType.DIRECT
                ),
                "warning"
            )

    async def _handle_message(self, event: dict):
        """Handle incoming Slack message"""
        try:
            # Convert to internal message format
            message = self._convert_slack_message(event)
            self.logger.info(f"Processing message from: {message.sender_id}")  # Add logging

            # Check if message should be buffered
            if self.status_manager.should_buffer(message):
                return
                    
            # Process through rule engine and notify
            actions = self.rule_engine.process_message(message)
            self.logger.info(f"Rule engine returned actions: {actions}")  # Add logging
            
            # Execute actions
            for action in actions:
                if action['type'] == 'notify':
                    self.notify_manager.notify(
                        message=message,
                        profile_name=action.get('profile', 'default')
                    )
                        
        except Exception as e:
            self.logger.error(f"Error handling message: {str(e)}")

    def _convert_slack_message(self, event: dict) -> Message:
        """Convert Slack event to internal message format"""
        msg_type = MessageType.CHANNEL
        if event.get('channel_type') == 'im':
            msg_type = MessageType.DIRECT
        elif event.get('thread_ts'):
            msg_type = MessageType.THREAD
        elif f'<@{self._user_id}>' in event.get('text', ''):
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

    async def _execute_action(self, action: Dict, message: Message):
        """Execute notification action"""
        try:
            action_type = action['type']
            params = action.get('params', {})

            if action_type == 'notify':
                self.notify_manager.notify(
                    message,
                    action.get('profile', 'default')
                )
            elif action_type == 'speak':
                print("speak the message = "+str(message.content))
                msg_text = params.get('message', '').format(
                    sender=message.sender_name,
                    content=message.content,
                    channel=message.channel_id or 'DM',
                    time=message.formatted_time
                )
                self.notify_manager.notify(
                    message,
                    'default',
                    msg_text
                )
        except Exception as e:
            self.logger.error(f"Error executing action: {str(e)}")

    def _handle_status_change(self, old_status: UserStatus, new_status: UserStatus):
        """Handle user status changes"""
        if old_status.should_buffer():
            # Get buffered messages summary
            summary = self.status_manager.get_buffer_summary()
            if summary != "No buffered messages":
                self.notify_manager.notify(
                    Message(
                        id="system",
                        content=f"While you were {old_status.value}: {summary}",
                        sender_id="system",
                        sender_name="System",
                        channel_id=None,
                        thread_id=None,
                        timestamp=0,
                        message_type=MessageType.DIRECT
                    ),
                    "default"
                )

    def _handle_presence_change(self, event: dict):
        """Handle presence change events"""
        if event.get('user') == self._user_id:
            presence = event.get('presence')
            if presence == 'away':
                self.set_status(UserStatus.AWAY)
            elif presence == 'active':
                self.set_status(UserStatus.ACTIVE)

    def _get_user_name(self, user_id: str) -> str:
        """Get user name from Slack API"""
        try:
            if not user_id or not self._web_client:  # Check for web_client
                return "Unknown User"
            response = self._web_client.users_info(user=user_id)  # Use _web_client
            if response['ok']:
                user = response['user']
                # Try real name first, then display name, then username
                return (user.get('real_name') or 
                    user.get('profile', {}).get('display_name') or 
                    user.get('name') or 
                    "Unknown User")
        except Exception as e:
            self.logger.error(f"Error getting user name: {e}")
        return "Unknown User"

    def _extract_mentions(self, text: str) -> List[str]:
        """Extract user mentions from message text"""
        import re
        return re.findall(r'<@([A-Z0-9]+)>', text)

    def _load_rules(self):
        """Load saved rules from database"""
        try:
            rules = self.db.get_rules()
            for rule in rules:
                self.rule_engine.add_rule(rule)
        except Exception as e:
            self.logger.error(f"Error loading rules: {str(e)}")

    async def stop(self):
        """Stop listening for events"""
        if self._event_handler:
            await self._event_handler.stop()
            self.logger.info("Stopped EasySlack")