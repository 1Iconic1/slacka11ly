import sqlite3
from typing import Optional, Dict, List
import json
from pathlib import Path
import logging

class Database:
    """Database management for EasySlack"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.logger = logging.getLogger("Database")
        self._init_db()

    def _init_db(self):
        """Initialize database schema"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.executescript('''
                    -- Users table
                    CREATE TABLE IF NOT EXISTS users (
                        id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        email TEXT UNIQUE NOT NULL,
                        slack_id TEXT UNIQUE,
                        role TEXT
                    );

                    -- Sound profiles
                    CREATE TABLE IF NOT EXISTS sound_profiles (
                        id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        sound_file TEXT NOT NULL,
                        volume REAL DEFAULT 1.0,
                        pitch REAL DEFAULT 1.0,
                        enabled INTEGER DEFAULT 1
                    );

                    -- Entity profiles (users/roles -> sound profiles)
                    CREATE TABLE IF NOT EXISTS entity_profiles (
                        entity_type TEXT,
                        entity_id TEXT,
                        profile_id TEXT,
                        PRIMARY KEY (entity_type, entity_id),
                        FOREIGN KEY (profile_id) REFERENCES sound_profiles(id)
                    );

                    -- Tags
                    CREATE TABLE IF NOT EXISTS tags (
                        type TEXT,
                        entity_id TEXT,
                        tag TEXT,
                        PRIMARY KEY (type, entity_id, tag)
                    );

                    -- Notification rules
                    CREATE TABLE IF NOT EXISTS rules (
                        id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        conditions TEXT NOT NULL,  -- JSON
                        actions TEXT NOT NULL,     -- JSON
                        priority TEXT NOT NULL,
                        enabled INTEGER DEFAULT 1
                    );

                    -- Configuration
                    CREATE TABLE IF NOT EXISTS config (
                        key TEXT PRIMARY KEY,
                        value TEXT
                    );
                ''')
                
        except sqlite3.Error as e:
            self.logger.error(f"Database initialization error: {str(e)}")
            raise

    def save_tokens(self, bot_token: str, app_token: str, user_token: str = None):
        """Save Slack tokens"""
        tokens = json.dumps({
            'bot_token': bot_token,
            'app_token': app_token,
            'user_token': user_token  # New: user token
        })
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT OR REPLACE INTO config (key, value)
                VALUES (?, ?)
            ''', ('tokens', tokens))

    def get_tokens(self) -> Optional[Dict[str, str]]:
        """Get Slack tokens"""
        with sqlite3.connect(self.db_path) as conn:
            result = conn.execute('''
                SELECT value FROM config WHERE key = ?
            ''', ('tokens',)).fetchone()
            
            if result:
                return json.loads(result[0])
        return None

    def add_user(self, name: str, email: str, slack_id: Optional[str] = None,
                 role: Optional[str] = None) -> str:
        """Add or update user"""
        user_id = f"U{email.split('@')[0]}"
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT OR REPLACE INTO users (id, name, email, slack_id, role)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, name, email, slack_id, role))
            
        return user_id

    def get_user_by_email(self, email: str) -> Optional[Dict]:
        """Get user by email"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            result = conn.execute('''
                SELECT * FROM users WHERE email = ?
            ''', (email,)).fetchone()
            
            if result:
                return dict(result)
        return None

    def get_user_by_slack_id(self, slack_id: str) -> Optional[Dict]:
        """Get user by Slack ID"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            result = conn.execute('''
                SELECT * FROM users WHERE slack_id = ?
            ''', (slack_id,)).fetchone()
            
            if result:
                return dict(result)
        return None

    def add_tag(self, type: str, entity_id: str, tag: str):
        """Add tag to entity"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT OR REPLACE INTO tags (type, entity_id, tag)
                VALUES (?, ?, ?)
            ''', (type, entity_id, tag))

    def get_tags(self, type: str, entity_id: str) -> List[str]:
        """Get tags for entity"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT tag FROM tags 
                WHERE type = ? AND entity_id = ?
            ''', (type, entity_id))
            return [row[0] for row in cursor.fetchall()]

    def save_rule(self, rule_id: str, name: str, conditions: Dict,
                 actions: List[Dict], priority: str, enabled: bool = True):
        """Save notification rule"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT OR REPLACE INTO rules 
                (id, name, conditions, actions, priority, enabled)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                rule_id, name, 
                json.dumps(conditions),
                json.dumps(actions),
                priority,
                1 if enabled else 0
            ))

    def get_rules(self) -> List[Dict]:
        """Get all notification rules"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute('SELECT * FROM rules')
            rules = []
            
            for row in cursor:
                rule = dict(row)
                rule['conditions'] = json.loads(rule['conditions'])
                rule['actions'] = json.loads(rule['actions'])
                rule['enabled'] = bool(rule['enabled'])
                rules.append(rule)
                
            return rules

    def save_sound_profile(self, profile_id: str, name: str, 
                         sound_file: str, volume: float = 1.0,
                         pitch: float = 1.0, enabled: bool = True):
        """Save sound profile"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT OR REPLACE INTO sound_profiles 
                (id, name, sound_file, volume, pitch, enabled)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (profile_id, name, sound_file, volume, pitch, 
                 1 if enabled else 0))

    def get_sound_profiles(self) -> List[Dict]:
        """Get all sound profiles"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute('SELECT * FROM sound_profiles')
            profiles = []
            
            for row in cursor:
                profile = dict(row)
                profile['enabled'] = bool(profile['enabled'])
                profiles.append(profile)
                
            return profiles