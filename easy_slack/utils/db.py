import sqlite3
from typing import Optional, Dict, List
import json
from pathlib import Path
import logging
import threading

class Database:
    """Database management for EasySlack"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.logger = logging.getLogger("Database")
        self._connection = None
        self._lock = threading.Lock()
        self._init_db()

    def _get_connection(self):
        """Get database connection with thread safety"""
        with self._lock:
            if self._connection is None:
                self._connection = sqlite3.connect(self.db_path, check_same_thread=False)
            return self._connection

    def _init_db(self):
        """Initialize database schema"""
        try:
            conn = self._get_connection()
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
            conn.commit()

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

        conn = self._get_connection()
        conn.execute('''
            INSERT OR REPLACE INTO config (key, value)
            VALUES (?, ?)
        ''', ('tokens', tokens))
        conn.commit()

    def get_tokens(self) -> Optional[Dict[str, str]]:
        """Get Slack tokens"""
        conn = self._get_connection()
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

        conn = self._get_connection()
        conn.execute('''
            INSERT OR REPLACE INTO users (id, name, email, slack_id, role)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, name, email, slack_id, role))
        conn.commit()

        return user_id

    def get_user_by_email(self, email: str) -> Optional[Dict]:
        """Get user by email"""
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        result = conn.execute('''
            SELECT * FROM users WHERE email = ?
        ''', (email,)).fetchone()

        if result:
            return dict(result)
        return None

    def get_user_by_slack_id(self, slack_id: str) -> Optional[Dict]:
        """Get user by Slack ID"""
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        result = conn.execute('''
            SELECT * FROM users WHERE slack_id = ?
        ''', (slack_id,)).fetchone()

        if result:
            return dict(result)
        return None

    def add_tag(self, type: str, entity_id: str, tag: str):
        """Add tag to entity"""
        conn = self._get_connection()
        conn.execute('''
            INSERT OR REPLACE INTO tags (type, entity_id, tag)
            VALUES (?, ?, ?)
        ''', (type, entity_id, tag))
        conn.commit()

    def get_tags(self, type: str, entity_id: str) -> List[str]:
        """Get tags for entity"""
        conn = self._get_connection()
        cursor = conn.execute('''
            SELECT tag FROM tags
            WHERE type = ? AND entity_id = ?
        ''', (type, entity_id))
        return [row[0] for row in cursor.fetchall()]

    def save_rule(self, rule_id: str, name: str, conditions: Dict,
                 actions: List[Dict], priority: str, enabled: bool = True):
        """Save notification rule"""
        conn = self._get_connection()
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
        conn.commit()

    def get_rules(self) -> List[Dict]:
        """Get all notification rules"""
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        rows = conn.execute('SELECT * FROM rules').fetchall()

        return [
            {
                **dict(row),
                'conditions': json.loads(row['conditions']),
                'actions': json.loads(row['actions']),
                'enabled': bool(row['enabled'])
            }
            for row in rows
        ]

    def save_sound_profile(self, profile_id: str, name: str,
                         sound_file: str, volume: float = 1.0,
                         pitch: float = 1.0, enabled: bool = True):
        """Save sound profile"""
        conn = self._get_connection()
        conn.execute('''
            INSERT OR REPLACE INTO sound_profiles
            (id, name, sound_file, volume, pitch, enabled)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (profile_id, name, sound_file, volume, pitch,
             1 if enabled else 0))
        conn.commit()

    def get_sound_profiles(self) -> List[Dict]:
        """Get all sound profiles"""
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        rows = conn.execute('SELECT * FROM sound_profiles').fetchall()

        return [
            {
                **dict(row),
                'enabled': bool(row['enabled'])
            }
            for row in rows
        ]