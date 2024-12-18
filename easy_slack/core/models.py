from dataclasses import dataclass, field
from typing import Dict, List, Set, Any, Optional, Tuple
from datetime import datetime
from .enums import (
    MessageType, 
    UserStatus, 
    NotificationPriority, 
    NotifySound, 
    ScreenReader
)

@dataclass
class Message:
    id: str
    content: str
    sender_id: str
    sender_name: str
    channel_id: Optional[str]
    thread_id: Optional[str]
    timestamp: float
    message_type: MessageType
    mentions: List[str] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)

    @property
    def formatted_time(self) -> str:
        return datetime.fromtimestamp(self.timestamp).strftime("%Y-%m-%d %H:%M:%S")

    def format_content(self, max_length: int = 100) -> str:
        content = self.content
        if len(content) > max_length:
            content = content[:max_length-3] + "..."
        return content

@dataclass
class NotificationRule:
    id: str
    name: str
    conditions: Dict[str, str]
    actions: List[Dict]
    priority: NotificationPriority
    enabled: bool = True
    exceptions: Set[str] = field(default_factory=set)

    def matches(self, message: Message) -> bool:
        """Check if message matches rule conditions"""
        if not self.enabled:
            return False
            
        if message.sender_id in self.exceptions:
            return False
            
        for condition_type, value in self.conditions.items():
            if not self._check_condition(condition_type, value, message):
                return False
        return True

    def _check_condition(self, condition_type: str, value: str, message: Message) -> bool:
        """Check individual condition"""
        if condition_type == "sender":
            if value == "self":
                return (message.message_type == MessageType.DIRECT and 
                        message.sender_id == message.channel_id)
            return message.sender_id == value
        elif condition_type == "channel":
            return message.channel_id == value
        elif condition_type == "content":
            import re
            return bool(re.search(value, message.content, re.IGNORECASE))
        elif condition_type == "message_type":
            return message.message_type.value == value
        return False

@dataclass
class UserPreferences:
    user_id: str
    notification_sound: bool = True
    speech_enabled: bool = True
    speech_rate: int = 175
    speech_volume: float = 1.0
    buffer_notifications: bool = False
    buffer_exceptions: Set[str] = field(default_factory=set)
    status: UserStatus = UserStatus.ACTIVE

@dataclass
class NotificationBuffer:
    enabled: bool = False
    messages: List[Message] = field(default_factory=list)
    start_time: Optional[float] = None
    exceptions: Set[str] = field(default_factory=set)

    def add_message(self, message: Message) -> bool:
        """Add message to buffer if appropriate"""
        if not self.enabled:
            return False
        if message.sender_id in self.exceptions:
            return False
        
        self.messages.append(message)
        return True

    def get_summary(self) -> str:
        """Get summary of buffered messages"""
        if not self.messages:
            return "No buffered messages"

        counts: Dict[str, int] = {}
        for msg in self.messages:
            counts[msg.sender_name] = counts.get(msg.sender_name, 0) + 1

        summary = []
        for sender, count in counts.items():
            summary.append(f"{count} message{'s' if count > 1 else ''} from {sender}")

        return ", ".join(summary)

    def clear(self) -> List[Message]:
        """Clear buffer and return messages"""
        messages = self.messages.copy()
        self.messages.clear()
        self.start_time = None
        self.enabled = False
        return messages

@dataclass
class NotificationProfile:
    name: str
    sound_type: NotifySound
    title_template: str
    message_template: str
    volume: float = 1.0
    enabled: bool = True
    priority: NotificationPriority = NotificationPriority.MEDIUM
    screen_reader_settings: Dict[str, Any] = field(default_factory=lambda: {
        'voiceover': {
            'voice': 'Alex',
            'rate': 250,
            'pitch': 50,
            'sound': 'Glass'
        },
        'nvda': {
            'voice': 'Microsoft David',
            'rate': 50,
            'pitch': 50,
            'sound': True
        },
        'jaws': {
            'voice': 'Microsoft David',
            'rate': 50,
            'pitch': 50,
            'sound': 'MessageBeep'
        },
        'orca': {
            'voice': 'default',
            'rate': 50,
            'pitch': 50,
            'sound': 'message-new-instant'
        }
    })

    def format_message(self, message: Message) -> tuple[str, str]:
        """Format title and message using templates"""
        context = {
            'sender': message.sender_name,
            'content': message.content,
            'channel': message.channel_id or 'DM',
            'time': message.formatted_time
        }
        
        title = self.title_template.format(**context)
        msg = self.message_template.format(**context)
        return title, msg

    def validate_settings(self, screen_reader: ScreenReader) -> bool:
        """Validate settings for given screen reader"""
        sr_type = screen_reader.value
        if sr_type not in self.screen_reader_settings:
            return False
            
        settings = self.screen_reader_settings[sr_type]
        # Basic validation rules per screen reader
        if sr_type == 'voiceover':
            return all(key in settings for key in ['voice', 'rate', 'pitch', 'sound'])
        elif sr_type in ['nvda', 'jaws', 'orca']:
            return all(key in settings for key in ['voice', 'rate', 'pitch', 'sound'])
        return False