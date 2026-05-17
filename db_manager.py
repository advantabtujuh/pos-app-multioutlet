"""
db_manager.py
Dual Database Manager: SQLite (local) + MariaDB (remote, lazy connect)
Supports UUID generation, lazy MariaDB connection, and cross-compatible queries.
"""

import sqlite3
import uuid
import json
from datetime import datetime

# Lazy import for MariaDB - only load when needed
try:
    import pymysql
    MARIADB_AVAILABLE = True
except ImportError:
    MARIADB_AVAILABLE = False

DB_NAME = "pos_inventory.db"


class DBManager:
    """Manages dual database connections: SQLite (local) and MariaDB (remote)."""

    def __init__(self):
        self._mariadb_conn = None
        self._mariadb_config = None
        self._online = False

    # ==========================================================================
    # UUID HELPERS
    # ==========================================================================
    @staticmethod
    def generate_uuid():
        """Generate UUID bytes (16 bytes) for primary keys."""
        return uuid.uuid4().bytes

    @staticmethod
    def uuid_to_hex(uuid_bytes):
        """Convert UUID bytes to hex string for display."""
        return uuid_bytes.hex() if uuid_bytes else None

    @staticmethod
    def hex_to_uuid(hex_str):
        """Convert hex string back to UUID bytes."""
        return bytes.fromhex(hex_str) if hex_str else None

    # ==========================================================================
    # SQLITE (LOCAL) - Always available
    # ==========================================================================
    def sqlite_conn(self):
        """Get SQLite connection with row factory."""
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        return conn

    def execute_local(self, query, params=(), fetch_one=False, fetch_all=False):
        """Execute query on SQLite. Returns result or None."""
        conn = self.sqlite_conn()
        cursor = conn.cursor()
        try:
            cursor.execute(query, params)
            if fetch_one:
                result = cursor.fetchone()
            elif fetch_all:
                result = cursor.fetchall()
            else:
                result = None
            conn.commit()
            return result
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def execute_local_many(self, query, params_list):
        """Execute many queries on SQLite."""
        conn = self.sqlite_conn()
        cursor = conn.cursor()
        try:
            cursor.executemany(query, params_list)
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    # ==========================================================================
    # MARIADB (REMOTE) - Lazy connection
    # ==========================================================================
    def set_mariadb_config(self, host, port, user, password, database):
        """Set MariaDB connection configuration."""
        self._mariadb_config = {
            'host': host,
            'port': int(port),
            'user': user,
            'password': password,
            'database': database,
            'charset': 'utf8mb4',
            'connect_timeout': 5,
            'read_timeout': 10,
            'write_timeout': 10
        }

    def mariadb_connect(self):
        """Lazy connect to MariaDB. Returns connection or None if failed."""
        if not MARIADB_AVAILABLE:
            return None
        if self._mariadb_conn is not None:
            try:
                self._mariadb_conn.ping(reconnect=True)
                return self._mariadb_conn
            except:
                self._mariadb_conn = None

        if self._mariadb_config is None:
            return None

        try:
            self._mariadb_conn = pymysql.connect(**self._mariadb_config)
            self._online = True
            return self._mariadb_conn
        except Exception as e:
            self._online = False
            self._mariadb_conn = None
            return None

    def is_online(self):
        """Check if MariaDB connection is available."""
        if self._mariadb_conn is None:
            return self.mariadb_connect() is not None
        try:
            self._mariadb_conn.ping(reconnect=True)
            self._online = True
            return True
        except:
            self._online = False
            return False

    def execute_remote(self, query, params=(), fetch_one=False, fetch_all=False):
        """Execute query on MariaDB. Returns result or None. Falls back to None if offline."""
        conn = self.mariadb_connect()
        if conn is None:
            return None
        cursor = conn.cursor()
        try:
            cursor.execute(query, params)
            if fetch_one:
                result = cursor.fetchone()
            elif fetch_all:
                result = cursor.fetchall()
            else:
                result = None
            conn.commit()
            return result
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()

    def close_remote(self):
        """Close MariaDB connection."""
        if self._mariadb_conn:
            try:
                self._mariadb_conn.close()
            except:
                pass
            self._mariadb_conn = None
            self._online = False

    # ==========================================================================
    # DATABASE INITIALIZATION & MIGRATION
    # ==========================================================================
    def _ensure_table(self, cursor, table_name, create_sql):
        """Create table if not exists."""
        cursor.execute(create_sql)

    def _ensure_column(self, cursor, table_name, column_name, column_def):
        """Add column if not exists (SQLite compatible migration)."""
        cursor.execute(f"PRAGMA table_info({table_name})")
        existing = [info[1] for info in cursor.fetchall()]
        if column_name not in existing:
            cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def}")

    def init_all_databases(self):
        """Initialize all SQLite tables with migration support. Called on app startup."""
        conn = self.sqlite_conn()
        cursor = conn.cursor()

        # --- app_settings ---
        self._ensure_table(cursor, "app_settings", """
            CREATE TABLE IF NOT EXISTS app_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                setting_key TEXT UNIQUE NOT NULL,
                setting_value TEXT DEFAULT '',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # --- master_user ---
        self._ensure_table(cursor, "master_user", """
            CREATE TABLE IF NOT EXISTS master_user (
                id BLOB PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL DEFAULT '',
                nama_lengkap TEXT NOT NULL DEFAULT '',
                role TEXT NOT NULL DEFAULT 'KASIR',
                outlet_id BLOB,
                is_active INTEGER NOT NULL DEFAULT 1,
                last_login TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Migrate: ensure all columns exist for older DB versions
        self._ensure_column(cursor, "master_user", "nama_lengkap", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column(cursor, "master_user", "role", "TEXT NOT NULL DEFAULT 'KASIR'")
        self._ensure_column(cursor, "master_user", "outlet_id", "BLOB")
        self._ensure_column(cursor, "master_user", "is_active", "INTEGER NOT NULL DEFAULT 1")
        self._ensure_column(cursor, "master_user", "last_login", "TEXT")
        self._ensure_column(cursor, "master_user", "created_at", "TEXT DEFAULT CURRENT_TIMESTAMP")

        # --- master_outlet ---
        self._ensure_table(cursor, "master_outlet", """
            CREATE TABLE IF NOT EXISTS master_outlet (
                id BLOB PRIMARY KEY,
                kode_outlet TEXT UNIQUE NOT NULL,
                nama_outlet TEXT NOT NULL DEFAULT '',
                alamat TEXT NOT NULL DEFAULT '',
                tailscale_ip TEXT DEFAULT '',
                db_mariadb_port INTEGER DEFAULT 3306,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self._ensure_column(cursor, "master_outlet", "tailscale_ip", "TEXT DEFAULT ''")
        self._ensure_column(cursor, "master_outlet", "db_mariadb_port", "INTEGER DEFAULT 3306")
        self._ensure_column(cursor, "master_outlet", "is_active", "INTEGER NOT NULL DEFAULT 1")
        self._ensure_column(cursor, "master_outlet", "created_at", "TEXT DEFAULT CURRENT_TIMESTAMP")

        # --- activity_log ---
        self._ensure_table(cursor, "activity_log", """
            CREATE TABLE IF NOT EXISTS activity_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id BLOB,
                username TEXT,
                action TEXT NOT NULL,
                detail TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Insert default settings if not exists
        defaults = [
            ('app_mode', 'PUSAT'),
            ('outlet_id', ''),
            ('outlet_kode', ''),
            ('mariadb_host', ''),
            ('mariadb_port', '3306'),
            ('mariadb_user', ''),
            ('mariadb_pass', ''),
            ('printer_name', ''),
            ('paper_width', '58'),
            ('theme', 'light'),
        ]
        for key, val in defaults:
            cursor.execute("INSERT OR IGNORE INTO app_settings (setting_key, setting_value) VALUES (?, ?)", (key, val))

        conn.commit()
        conn.close()

    # ==========================================================================
    # UTILITY
    # ==========================================================================
    def log_activity(self, user_id, username, action, detail=""):
        """Log user activity to SQLite."""
        self.execute_local(
            "INSERT INTO activity_log (user_id, username, action, detail) VALUES (?, ?, ?, ?)",
            (user_id, username, action, detail)
        )

    def has_users(self):
        """Check if any user exists in database."""
        result = self.execute_local("SELECT COUNT(*) as count FROM master_user", fetch_one=True)
        return result['count'] > 0 if result else False


# Singleton instance
db = DBManager()
