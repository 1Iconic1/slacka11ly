import platform
import subprocess
import logging
from typing import Optional, Dict, Any
from .models import ScreenReader  # If you moved ScreenReader to models.py
# OR from .enums import ScreenReader  # If you created enums.py
from ..core.models import NotifySound
class AccessibilityManager:
    """Manages screen reader detection and notifications"""
    
    def __init__(self):
        self.logger = logging.getLogger("AccessibilityManager")
        self.os_type = platform.system()
        self.screen_reader = self._detect_screen_reader()
        
        # Define supported settings for each screen reader
        self.supported_settings = {
            'voiceover': {
                'voice': ['Alex', 'Victoria', 'Daniel'],  # Common VoiceOver voices
                'rate': range(100, 401),  # 100-400 WPM
                'pitch': range(0, 101),   # 0-100
                'sound': ['Glass', 'Pop', 'Ping']  # Common macOS sounds
            },
            'nvda': {
                'voice': ['Microsoft David', 'Microsoft Zira'],  # Common NVDA voices
                'rate': range(0, 101),    # 0-100
                'pitch': range(0, 101),   # 0-100
                'sound': [True, False]     # Enable/disable sounds
            },
            'jaws': {
                'voice': ['Microsoft David', 'Microsoft Zira'],  # Common JAWS voices
                'rate': range(0, 101),    # 0-100
                'pitch': range(0, 101),   # 0-100
                'sound': ['MessageBeep', 'SystemAsterisk', 'SystemExclamation']
            },
            'orca': {
                'voice': ['default', 'english', 'spanish'],
                'rate': range(0, 101),    # 0-100
                'pitch': range(0, 101),   # 0-100
                'sound': ['message-new-instant', 'message-new-email']
            }
        }

    def _detect_screen_reader(self) -> ScreenReader:
        """Detect active screen reader"""
        if self.os_type == "Darwin":  # macOS
            try:
                # Check if VoiceOver is running using different AppleScript
                cmd = '''
                tell application "System Events"
                    tell application process "VoiceOver"
                        return running
                    end tell
                end tell
                '''
                result = subprocess.run(['osascript', '-e', cmd], 
                                      capture_output=True,
                                      text=True)
                
                # Check stdout
                if "true" in result.stdout.lower():
                    return ScreenReader.VOICEOVER
            except subprocess.CalledProcessError:
                # VoiceOver process might not exist, try alternative check
                try:
                    cmd = 'tell application "System Events" to return (exists process "VoiceOver")'
                    result = subprocess.run(['osascript', '-e', cmd],
                                          capture_output=True,
                                          text=True)
                    if "true" in result.stdout.lower():
                        return ScreenReader.VOICEOVER
                except Exception as e:
                    self.logger.error(f"Error checking VoiceOver alternative: {e}")
                    
        elif self.os_type == "Windows":
            # Check for NVDA or JAWS
            try:
                result = subprocess.run(['tasklist'], capture_output=True, text=True)
                if "nvda.exe" in result.stdout.lower():
                    return ScreenReader.NVDA
                elif "jfw.exe" in result.stdout.lower():
                    return ScreenReader.JAWS
            except Exception as e:
                self.logger.error(f"Error checking Windows screen readers: {e}")
                
        elif self.os_type == "Linux":
            # Check for Orca
            try:
                result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
                if "orca" in result.stdout.lower():
                    return ScreenReader.ORCA
            except Exception as e:
                self.logger.error(f"Error checking Orca: {e}")
                
        return ScreenReader.NONE

    def validate_settings(self, screen_reader: ScreenReader, settings: Dict[str, Any]) -> bool:
        """Validate settings for specific screen reader"""
        sr_type = screen_reader.value
        if sr_type not in self.supported_settings:
            return False
            
        supported = self.supported_settings[sr_type]
        try:
            # Check each setting against supported values
            for key, value in settings.items():
                if key not in supported:
                    return False
                    
                if key in ['rate', 'pitch']:
                    if not isinstance(value, int) or value not in supported[key]:
                        return False
                elif key in ['voice', 'sound']:
                    if value not in supported[key]:
                        return False
                        
            return True
        except Exception as e:
            self.logger.error(f"Error validating settings: {e}")
            return False

    def notify(self, message: str, sound: bool = True, **settings):
        """Send notification to active screen reader with validation"""
        try:
            # Validate settings before proceeding
            if settings and not self.validate_settings(self.screen_reader, settings):
                self.logger.error("Invalid screen reader settings provided")
                settings = {}  # Use defaults if invalid

            if self.screen_reader == ScreenReader.VOICEOVER:
                self._voiceover_notify(message, sound, **settings)
            elif self.screen_reader == ScreenReader.NVDA:
                self._nvda_notify(message, sound, **settings)
            elif self.screen_reader == ScreenReader.JAWS:
                self._jaws_notify(message, sound, **settings)
            elif self.screen_reader == ScreenReader.ORCA:
                self._orca_notify(message, sound, **settings)
            else:
                self.logger.warning("No screen reader detected")
                
        except Exception as e:
            self.logger.error(f"Error sending notification: {e}")

    def _voiceover_notify(self, message: str, sound: bool = True, **settings):
        """Send notification via VoiceOver with enhanced error handling"""
        try:
            if sound:
                # Map NotifySound types to system sounds
                sound_mapping = {
                    NotifySound.MESSAGE: "Morse.aiff",    # Basic notification
                    NotifySound.MENTION: "Ping.aiff",     # When mentioned
                    NotifySound.DM: "Purr.aiff",         # Direct messages
                    NotifySound.URGENT: "Glass.aiff",     # Urgent/important
                    NotifySound.SUCCESS: "Bottle.aiff",   # Success events
                    NotifySound.WARNING: "Basso.aiff"     # Warning events
                }
                # Get sound type from profile settings
                sound_type = settings.get('sound_type', NotifySound.MESSAGE)
                sound_file = sound_mapping.get(sound_type, "Morse.aiff")
                
                # Use AppleScript to play sound to avoid audio queue issues
                sound_script = f'''
                tell application "System Events"
                    play sound file "/System/Library/Sounds/{sound_file}"
                end tell
                '''
                subprocess.run(['osascript', '-e', sound_script])
            
            # Queue message using current VoiceOver settings
                apple_script = f'''
                tell application "System Events"
                    add "{message}" in queue
                    say "{message}" without interrupting
                end tell
                '''
            
            subprocess.run(['osascript', '-e', apple_script])
                
        except Exception as e:
            self.logger.error(f"VoiceOver notification error: {e}")
            
    def _nvda_notify(self, message: str, sound: bool = True, **settings):
        """Send notification via NVDA with settings"""
        try:
            import nvda_controller_client as nvda
            if sound and settings.get('sound', True):
                nvda.nvdaController.speakText("notification")
            
            # Apply settings if available
            if 'rate' in settings:
                nvda.nvdaController.setRate(settings['rate'])
            if 'pitch' in settings:
                nvda.nvdaController.setPitch(settings['pitch'])
                
            nvda.nvdaController.speakText(message)
        except Exception as e:
            self.logger.error(f"NVDA notification error: {e}")

    def _jaws_notify(self, message: str, sound: bool = True, **settings):
        """Send notification via JAWS with settings"""
        try:
            import win32com.client
            jaws = win32com.client.Dispatch("FreedomSci.JawsApi")
            
            if sound:
                sound_type = settings.get('sound', 'MessageBeep')
                jaws.RunFunction(sound_type)
                
            # Apply settings if available
            if 'voice' in settings:
                jaws.SayString(f'Select voice {settings["voice"]}')
            if 'rate' in settings:
                jaws.Rate = settings['rate']
                
            jaws.SayString(message, False)
        except Exception as e:
            self.logger.error(f"JAWS notification error: {e}")

    def _orca_notify(self, message: str, sound: bool = True, **settings):
        """Send notification via Orca with settings"""
        try:
            if sound:
                sound_file = settings.get('sound', 'message-new-instant')
                subprocess.run(['paplay', f'/usr/share/sounds/freedesktop/stereo/{sound_file}.oga'])
            
            # Build speech-dispatcher command with settings
            rate = settings.get('rate', 50)
            pitch = settings.get('pitch', 50)
            voice = settings.get('voice', 'default')
            
            cmd = [
                'spd-say',
                '-r', str(rate),
                '-p', str(pitch),
                '-t', voice,
                message
            ]
            
            subprocess.run(cmd)
        except Exception as e:
            self.logger.error(f"Orca notification error: {e}")

    def check_voiceover_status(self) -> bool:
        """Check if VoiceOver is running"""
        if self.os_type == "Darwin":
            try:
                # Use system_profiler to check accessibility
                result = subprocess.run(
                    ['defaults', 'read', 'com.apple.universalaccess', 'voiceOverOnOffKey'],
                    capture_output=True,
                    text=True
                )
                is_running = result.stdout.strip() == '1'
                
                if not is_running:
                    print("\nVoiceOver is not running. To hear notifications:")
                    print("1. Press Command + F5 to turn on VoiceOver")
                    print("   OR")
                    print("2. Go to System Preferences > Accessibility > VoiceOver")
                    print("3. Check 'Enable VoiceOver'\n")
                    return False
                return True
            except Exception as e:
                self.logger.error(f"Error checking VoiceOver: {e}")
                return False
        return True