from .core.easy_slack import EasySlack
from .core.models import NotificationPriority, MessageType, UserStatus, NotifySound

__version__ = "0.1.0"

__all__ = [
    'EasySlack',
    'NotificationPriority',
    'MessageType',
    'UserStatus',
    'NotifySound'
]