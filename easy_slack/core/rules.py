from typing import Dict, List, Optional, Callable
import re
import logging
from .models import (
    Message, 
    NotificationPriority, 
    NotificationRule,
    UserStatus
)
import time

class RuleEngine:
    """Handles notification rules and message processing"""
    
    def __init__(self):
        self.logger = logging.getLogger("RuleEngine")
        self.rules: Dict[str, NotificationRule] = {}
        self.current_status = UserStatus.ACTIVE
        self.slack = None  # Will be set later
        self._processed_messages = set()  # Cache for processed message IDs
        self._start_time = time.time()    # Store engine start tim
        
    def set_slack_client(self, slack_instance):
        """Set the Slack client after initialization"""
        self.slack = slack_instance
        
    def add_rule(self, rule: NotificationRule):
        """Add or update a notification rule"""
        self.rules[rule.id] = rule
        self.logger.info(f"Added rule: {rule.name}")
        
    def remove_rule(self, rule_id: str):
        """Remove a rule"""
        if rule_id in self.rules:
            del self.rules[rule_id]
            self.logger.info(f"Removed rule: {rule_id}")
            
    def get_rule(self, rule_id: str) -> Optional[NotificationRule]:
        """Get rule by ID"""
        return self.rules.get(rule_id)
            
    def process_message(self, message: Message) -> List[Dict]:
        """Process message and return prioritized actions"""
        actions = []

        if message.timestamp < self._start_time:
            return []
        
        if message.id in self._processed_messages:
            return []
            
        # Add to processed cache
        self._processed_messages.add(message.id)
        
        # Trim cache if it gets too large
        if len(self._processed_messages) > 1000:
            self._processed_messages.clear()
        
        try:
            # Process each rule
            for rule in self.rules.values():
                if rule.matches(message):
                    # Check if rule priority can break through current status
                    if rule.priority.can_break_through(self.current_status):
                        processed_actions = self._process_actions(rule.actions, message)
                        actions.extend(processed_actions)
            
            # Sort by priority - handle both string and enum priorities
            def get_priority_value(action):
                priority = action.get('priority', 'MEDIUM')
                if isinstance(priority, str):
                    # Convert string priority to enum
                    return NotificationPriority[priority.upper()].value
                return priority.value
            
            # Sort actions
            sorted_actions = sorted(
                actions,
                key=get_priority_value,
                reverse=True
            )
            
            return sorted_actions
            
        except Exception as e:
            self.logger.error(f"Error processing message: {str(e)}")
            return []
            
    def _process_actions(self, actions: List[Dict], message: Message) -> List[Dict]:
        """Process rule actions with message context"""
        processed = []
        
        for action in actions:
            try:
                # Deep copy action to avoid modifying original
                processed_action = action.copy()
                self.logger.debug(f"Processing action for message: {message.content}")
                
                # Process message templates in action parameters
                params = processed_action.get('params', {})
                if params and 'message' in params:
                    template = params['message']
                    if template is not None:  # Check if template exists
                        params['message'] = template.format(
                            sender=message.sender_name,
                            content=message.content,
                            channel=message.channel_id or 'DM',
                            time=message.formatted_time
                        )
                    else:
                        # If no template, use content directly
                        params['message'] = message.content
                else:
                    # If no message parameter exists, add one with content
                    processed_action['params'] = params
                    processed_action['params']['message'] = message.content
                    
                processed.append(processed_action)
                
            except Exception as e:
                self.logger.error(f"Error processing action: {e}")
                
        return processed    
    def set_status(self, status: UserStatus):
        """Update current status"""
        self.current_status = status
        self.logger.info(f"Rule engine status set to: {status.name}")

class RuleBuilder:
    """Fluent interface for building notification rules"""
    
    def __init__(self, rule_engine: RuleEngine):
        self.engine = rule_engine
        self._conditions = {}
        self._actions = []
        self._name = None
        self._priority = NotificationPriority.MEDIUM
        self._exceptions = set()
        
    def from_person(self, identifier: str) -> 'RuleBuilder':
            """Add sender condition"""
            if identifier.lower() == "self":
                # Get the user ID from EasySlack instance
                if self.engine.slack and self.engine.slack._user_id:
                    self._conditions['sender'] = self.engine.slack._user_id
                else:
                    raise ValueError("Cannot create self-message rule: User ID not available")
            else:
                # Handle email or direct user ID
                if '@' in identifier and self.engine.slack:
                    user_id = self.engine.slack._convert_email_to_user_id(identifier)
                    if user_id:
                        self._conditions['sender'] = user_id
                    else:
                        self._conditions['sender'] = identifier
                else:
                    self._conditions['sender'] = identifier
            return self
        
    def when(self, name: str) -> 'RuleBuilder':
        """Start building a rule"""
        self._name = name
        return self
        
    def in_channel(self, channel_id: str) -> 'RuleBuilder':
        """Add channel condition"""
        self._conditions['channel'] = channel_id
        return self
        
    def containing(self, pattern: str) -> 'RuleBuilder':
        """Add content pattern condition"""
        self._conditions['content'] = pattern
        return self
        
    def of_type(self, message_type: str) -> 'RuleBuilder':
        """Add message type condition"""
        self._conditions['message_type'] = message_type
        return self
        
    def with_priority(self, priority: NotificationPriority) -> 'RuleBuilder':
        """Set rule priority"""
        self._priority = priority
        # Update priority in existing actions
        for action in self._actions:
            action['priority'] = priority.name  # Use name instead of enum
        return self
        
    def add_exception(self, entity_id: str) -> 'RuleBuilder':
        """Add exception"""
        self._exceptions.add(entity_id)
        return self
        
    def play_sound(self, profile_name: str, 
                title: Optional[str] = None,
                message: Optional[str] = None) -> 'RuleBuilder':
        """Add notification action"""
        self._actions.append({
            'type': 'notify',
            'profile': profile_name,
            'params': {
                'title': title,
                'message': message or '{content}'
            },
            'priority': self._priority.name  # Use name instead of enum
        })
        return self
        
    def speak(self, message: str) -> 'RuleBuilder':
        """Add speech action"""
        self._actions.append({
            'type': 'speak',
            'params': {
                'message': message
            },
            'priority': self._priority.value
        })
        return self
        
    def done(self) -> NotificationRule:
        """Finish building and register the rule"""
        if not self._name:
            raise ValueError("Rule must have a name")
            
        rule = NotificationRule(
            id=f"rule_{self._name.lower().replace(' ', '_')}",
            name=self._name,
            conditions=self._conditions,
            actions=self._actions,
            priority=self._priority,
            exceptions=self._exceptions
        )
        
        self.engine.add_rule(rule)
        return rule

class RuleSerializer:
    """Handles rule serialization and deserialization"""
    
    @staticmethod
    def to_dict(rule: NotificationRule) -> Dict:
        """Convert rule to dictionary"""
        return {
            'id': rule.id,
            'name': rule.name,
            'conditions': rule.conditions,
            'actions': rule.actions,
            'priority': rule.priority.value,
            'enabled': rule.enabled,
            'exceptions': list(rule.exceptions)
        }
    
    @staticmethod
    def from_dict(data: Dict) -> NotificationRule:
        """Create rule from dictionary"""
        return NotificationRule(
            id=data['id'],
            name=data['name'],
            conditions=data['conditions'],
            actions=data['actions'],
            priority=NotificationPriority[data['priority']],
            enabled=data.get('enabled', True),
            exceptions=set(data.get('exceptions', []))
        )