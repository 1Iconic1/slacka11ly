from enum import Enum

class ScreenReader(Enum):
    VOICEOVER = "voiceover"
    NVDA = "nvda"
    JAWS = "jaws"
    ORCA = "orca"
    NONE = "none"

class MessageType(Enum):
    DIRECT = "direct"
    CHANNEL = "channel"
    THREAD = "thread"
    MENTION = "mention"

class UserStatus(Enum):
    ACTIVE = "active"
    FOCUSED = "focused"
    DND = "do_not_disturb"
    AWAY = "away"

    def should_buffer(self) -> bool:
        return self in (UserStatus.FOCUSED, UserStatus.DND)

class NotificationPriority(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    def can_break_through(self, status: UserStatus) -> bool:
        if status == UserStatus.ACTIVE:
            return True
        elif status == UserStatus.FOCUSED:
            return self in (NotificationPriority.HIGH, NotificationPriority.CRITICAL)
        elif status == UserStatus.DND:
            return self == NotificationPriority.CRITICAL
        return False

class NotifySound(Enum):
    """Notify-py default sounds"""
    MESSAGE = "base"      # Regular message
    MENTION = "ping"      # User mention
    DM = "hello"         # Direct message
    URGENT = "error"     # Urgent/important
    SUCCESS = "success"  # Success events
    WARNING = "warning"  # Warning events