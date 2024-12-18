from dataclasses import dataclass
from typing import Dict, Optional, List, Any
import logging
from pathlib import Path
import json
from notifypy import Notify
import threading
import queue
from .models import (
    NotifySound, 
    NotificationPriority, 
    UserStatus, 
    Message,
    NotificationProfile
)
from .accessibility import AccessibilityManager
import platform
import subprocess  # Add this line
import time

class NotificationManager:
    """Manages system notifications with priority and status handling"""
    
    def __init__(self, config_dir: Optional[Path] = None):
        self.logger = logging.getLogger("NotificationManager")
        self.config_dir = config_dir or Path.home() / '.easy_slack'
        self.config_dir.mkdir(exist_ok=True)

        self._processed_notifications = set()
        self._notification_start_time = time.time()
        
        self.os_type = platform.system()
        
        # Initialize notification components
        self.profiles: Dict[str, NotificationProfile] = {}
        self.user_profiles: Dict[str, str] = {}  # user_id -> profile_name
        self.current_status = UserStatus.ACTIVE
        
        # Queue for thread-safe notification handling
        self.notification_queue = queue.PriorityQueue()
        self.running = True
        
        # Load configuration
        self._load_config()
        self._init_default_profiles()
        
        # Start notification worker
        self._start_worker()

        self.accessibility = AccessibilityManager()
        self.accessibility.check_voiceover_status()



    
    def _init_default_profiles(self):
        """Initialize default notification profiles"""
        defaults = {
            "default": (
                NotifySound.MESSAGE,
                "Slack Message",
                "New message from {sender}",
                NotificationPriority.MEDIUM
            ),
            "mention": (
                NotifySound.MENTION,
                "Slack Mention",
                "{sender} mentioned you",
                NotificationPriority.HIGH
            ),
            "dm": (
                NotifySound.DM,
                "Direct Message",
                "DM from {sender}",
                NotificationPriority.HIGH
            ),
            "urgent": (
                NotifySound.URGENT,
                "Urgent Message",
                "URGENT: {content}",
                NotificationPriority.CRITICAL
            ),
            "team": (
                NotifySound.MESSAGE,
                "Team Message",
                "Team update in {channel}",
                NotificationPriority.MEDIUM
            )
        }
        
        for name, (sound, title, msg, priority) in defaults.items():
            if name not in self.profiles:
                self.profiles[name] = NotificationProfile(
                    name=name,
                    sound_type=sound,
                    title_template=title,
                    message_template=msg,
                    priority=priority
                )
    
    # In sound_management.py, update the create_profile method:

    def create_profile(
        self,
        name: str,
        sound_type: NotifySound,
        title_template: str,
        message_template: str,
        priority: NotificationPriority = NotificationPriority.MEDIUM,
        volume: float = 1.0,
        screen_reader_settings: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Create a custom notification profile with screen reader support"""
        try:
            # Create default screen reader settings if none provided
            if screen_reader_settings is None:
                screen_reader_settings = {
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
                }
                
            self.profiles[name] = NotificationProfile(
                name=name,
                sound_type=sound_type,
                title_template=title_template,
                message_template=message_template,
                volume=volume,
                priority=priority,
                screen_reader_settings=screen_reader_settings
            )
            self._save_config()
            return True
        except Exception as e:
            self.logger.error(f"Error creating profile: {e}")
            return False

    def set_user_profile(self, user_id: str, profile_name: str) -> bool:
        """Assign notification profile to user"""
        if profile_name not in self.profiles:
            return False
        
        self.user_profiles[user_id] = profile_name
        self._save_config()
        return True

    def notify(self, message: Message, profile_name: Optional[str] = None):
        """Queue notification for message with screen reader support"""
        try:
            if message.timestamp < self._notification_start_time:
                return
                
            notification_key = f"{message.id}:{profile_name}"
            if notification_key in self._processed_notifications:
                return
                
            self._processed_notifications.add(notification_key)
            
            # Trim cache if it gets too large
            if len(self._processed_notifications) > 1000:
                self._processed_notifications.clear()

            # Get profile (user-specific, specified, or default)
            profile = self.profiles.get(
                self.user_profiles.get(message.sender_id) or 
                profile_name or 
                "default"
            )
            
            if not profile or not profile.enabled:
                return
                
            # Check if notification should break through current status
            if not profile.priority.can_break_through(self.current_status):
                return
                
            # Format notification
            title, msg = profile.format_message(message)
            
            # Add to queue with priority
            priority_value = {
                NotificationPriority.LOW: 1,
                NotificationPriority.MEDIUM: 2,
                NotificationPriority.HIGH: 3,
                NotificationPriority.CRITICAL: 4
            }.get(profile.priority, 2)  # Default to MEDIUM if unknown
            
            # Get screen reader settings based on detected screen reader
            reader_type = self.accessibility.screen_reader.value
            sr_settings = profile.screen_reader_settings.get(reader_type, {})
            
            # Create notification tuple with screen reader settings
            notification_data = (
                title, 
                msg, 
                profile,
                sr_settings  # Add screen reader settings to the tuple
            )
            
            # Add to priority queue
            priority_tuple = (
                -priority_value,  # Negative so higher priorities come first
                -int(message.timestamp),  # Convert timestamp to int
                notification_data
            )
            
            self.notification_queue.put(priority_tuple)
            self.logger.debug(f"Queued notification with priority {priority_value}")
            
        except Exception as e:
            self.logger.error(f"Error queuing notification: {e}")

    def set_status(self, status: UserStatus):
        """Update current status"""
        self.current_status = status
        self.logger.info(f"Status set to: {status.name}")

    def _send_notification(self, title: str, message: str, profile: NotificationProfile, sr_settings: Dict[str, Any] = None):
        """Send notification with screen reader support"""
        try:
            reader_type = self.accessibility.screen_reader.value
            
            # For VoiceOver/system speech
            if self.os_type == "Darwin":
                try:
                    # Map NotifySound types to system sounds
                    sound_mapping = {
                        NotifySound.MESSAGE: "/System/Library/Sounds/Morse.aiff",    # Basic notification
                        NotifySound.MENTION: "/System/Library/Sounds/Ping.aiff",     # When mentioned
                        NotifySound.DM: "/System/Library/Sounds/Purr.aiff",          # Direct messages
                        NotifySound.URGENT: "/System/Library/Sounds/Glass.aiff",     # Urgent/important
                        NotifySound.SUCCESS: "/System/Library/Sounds/Bottle.aiff",   # Success events
                        NotifySound.WARNING: "/System/Library/Sounds/Basso.aiff"     # Warning events
                    }
                    
                    # Get appropriate sound file or use default
                    sound_file = sound_mapping.get(profile.sound_type, "/System/Library/Sounds/Morse.aiff")
                    subprocess.run(['afplay', sound_file])
                    
                except Exception as e:
                    self.logger.error(f"Error playing sound: {e}")
                
                if reader_type != "none" and profile.message_template.strip():
                    notification_text = f"{title}: {message}"
                    apple_script = f'''
                    tell application "VoiceOver"
                        output "{notification_text}"
                    end tell
                    '''
                    subprocess.run(['osascript', '-e', apple_script])

                notification_text = f"{title}: {message}"
                if reader_type == "voiceover":
                    # Use VoiceOver if running
                    apple_script = f'''
                    tell application "VoiceOver"
                        output "{notification_text}"
                    end tell
                    '''
                    subprocess.run(['osascript', '-e', apple_script])
                    # Play system sound if specified
                    if sr_settings and sr_settings.get('sound'):
                        subprocess.run(['afplay', f'/System/Library/Sounds/{sr_settings["sound"]}.aiff'])
                else:
                    # Use system speech if no screen reader
                    subprocess.run(['say', notification_text])
                    
            # For Windows screen readers
            elif self.os_type == "Windows":
                notification_text = f"{title}: {message}"
                if reader_type == "nvda":
                    import nvda_controller_client as nvda
                    nvda.nvdaController.speakText(notification_text)
                elif reader_type == "jaws":
                    import win32com.client
                    jaws = win32com.client.Dispatch("FreedomSci.JawsApi")
                    jaws.SayString(notification_text)
                else:
                    # Use Windows speech
                    import win32com.client
                    speaker = win32com.client.Dispatch("SAPI.SpVoice")
                    speaker.Speak(notification_text)
                    
            # For Linux/Orca
            elif self.os_type == "Linux":
                notification_text = f"{title}: {message}"
                if reader_type == "orca":
                    subprocess.run(['spd-say', notification_text])
                else:
                    # Use system speech
                    subprocess.run(['espeak', notification_text])
                    
        except Exception as e:
            self.logger.error(f"Error sending notification: {e}")
    def _start_worker(self):
        """Start notification worker thread"""
        def notification_worker():
            while self.running:
                try:
                    # Get next notification from queue
                    _, _, (title, msg, profile, sr_settings) = self.notification_queue.get(timeout=0.1)
                    
                    # Send notification with screen reader settings
                    self._send_notification(
                        title=title,
                        message=msg,
                        profile=profile,
                        sr_settings=sr_settings
                    )
                    
                    self.notification_queue.task_done()
                except queue.Empty:
                    continue
                except Exception as e:
                    self.logger.error(f"Notification worker error: {e}")

        self.worker_thread = threading.Thread(
            target=notification_worker,
            daemon=True
        )
        self.worker_thread.start()

    def _load_config(self):
        """Load configuration from file"""
        config_file = self.config_dir / 'notifications.json'
        try:
            if config_file.exists():
                with open(config_file) as f:
                    config = json.load(f)
                    
                # Load profiles
                for name, profile_data in config.get('profiles', {}).items():
                    self.profiles[name] = NotificationProfile(
                        name=name,
                        sound_type=NotifySound[profile_data['sound_type']],
                        title_template=profile_data['title_template'],
                        message_template=profile_data['message_template'],
                        volume=profile_data.get('volume', 1.0),
                        enabled=profile_data.get('enabled', True),
                        priority=NotificationPriority[profile_data.get(
                            'priority', 'MEDIUM')]
                    )
                    
                # Load user profile assignments
                self.user_profiles = config.get('user_profiles', {})
                
        except Exception as e:
            self.logger.error(f"Error loading config: {e}")

    def _save_config(self):
        """Save configuration to file"""
        try:
            config = {
                'profiles': {
                    name: {
                        'sound_type': profile.sound_type.name,
                        'title_template': profile.title_template,
                        'message_template': profile.message_template,
                        'volume': profile.volume,
                        'enabled': profile.enabled,
                        'priority': profile.priority.name
                    }
                    for name, profile in self.profiles.items()
                },
                'user_profiles': self.user_profiles
            }
            
            config_file = self.config_dir / 'notifications.json'
            with open(config_file, 'w') as f:
                json.dump(config, f, indent=2)
                
        except Exception as e:
            self.logger.error(f"Error saving config: {e}")

    def cleanup(self):
        """Clean up resources"""
        self.running = False
        if hasattr(self, 'worker_thread'):
            # Wait for queue to empty
            self.notification_queue.join()
            # Clear any remaining items
            while not self.notification_queue.empty():
                try:
                    self.notification_queue.get_nowait()
                    self.notification_queue.task_done()
                except queue.Empty:
                    break
        self._save_config()