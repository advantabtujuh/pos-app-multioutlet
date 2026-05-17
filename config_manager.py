"""
config_manager.py
Simple wrapper to read/write application settings from SQLite app_settings table.
"""

from db_manager import db


class ConfigManager:
    """Manages application configuration stored in SQLite app_settings table."""

    @staticmethod
    def get(key, default=""):
        """Get setting value by key. Returns default if not found."""
        result = db.execute_local(
            "SELECT setting_value FROM app_settings WHERE setting_key = ?",
            (key,), fetch_one=True
        )
        return result['setting_value'] if result else default

    @staticmethod
    def set(key, value):
        """Set or update setting value by key."""
        db.execute_local(
            "UPDATE app_settings SET setting_value = ?, updated_at = datetime('now') WHERE setting_key = ?",
            (str(value), key)
        )

    @staticmethod
    def get_all():
        """Get all settings as dictionary."""
        rows = db.execute_local("SELECT setting_key, setting_value FROM app_settings", fetch_all=True)
        return {row['setting_key']: row['setting_value'] for row in rows} if rows else {}

    @staticmethod
    def get_int(key, default=0):
        """Get setting as integer."""
        try:
            return int(ConfigManager.get(key, default))
        except (ValueError, TypeError):
            return default

    @staticmethod
    def get_bool(key, default=False):
        """Get setting as boolean."""
        val = ConfigManager.get(key, str(default)).lower()
        return val in ('1', 'true', 'yes', 'on')

    @staticmethod
    def is_pusat():
        """Check if app is running in PUSAT mode."""
        return ConfigManager.get('app_mode', 'PUSAT').upper() == 'PUSAT'

    @staticmethod
    def is_outlet():
        """Check if app is running in OUTLET mode."""
        return ConfigManager.get('app_mode', 'PUSAT').upper() == 'OUTLET'

    @staticmethod
    def get_outlet_id():
        """Get outlet UUID bytes from config."""
        val = ConfigManager.get('outlet_id', '')
        return db.hex_to_uuid(val) if val else None

    @staticmethod
    def set_outlet_id(uuid_bytes):
        """Set outlet UUID in config."""
        ConfigManager.set('outlet_id', db.uuid_to_hex(uuid_bytes) if uuid_bytes else '')


# Singleton
config = ConfigManager()
