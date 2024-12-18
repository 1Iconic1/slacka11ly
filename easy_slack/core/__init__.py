from .models import (
    Message,
    MessageType,
    UserStatus,
    NotificationPriority,
    NotifySound,
    NotificationProfile,
    NotificationRule,
    UserPreferences,
    NotificationBuffer
)

from .easy_slack import EasySlack
from .rules import RuleEngine, RuleBuilder
from .sound_management import NotificationManager
from .status import StatusManager
from .accessibility import AccessibilityManager, ScreenReader

# Version info
__version__ = "0.1.0"

__all__ = [
    # Core class
    "EasySlack",
    
    # Managers
    "RuleEngine",
    "RuleBuilder",
    "NotificationManager",
    "StatusManager",
    "AccessibilityManager",
    
    # Models
    "Message",
    "MessageType",
    "UserStatus",
    "NotificationPriority",
    "NotifySound",
    "NotificationProfile",
    "NotificationRule",
    "UserPreferences",
    "NotificationBuffer",
    
    # Enums
    "ScreenReader",
]