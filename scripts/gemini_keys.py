"""Read local Gemini credentials without persisting or exposing their values."""

import os
import re
import sys


def user_setting(name):
    value = os.environ.get(name)
    if value:
        return value
    if sys.platform == 'win32':
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, 'Environment') as registry:
                return winreg.QueryValueEx(registry, name)[0]
        except (FileNotFoundError, OSError):
            pass
    return ''


def api_keys():
    """Return unique keys from legacy, list, and numbered user settings."""
    values = [user_setting('GEMINI_API_KEY')]
    values.extend(re.split(r'[,;\s]+', user_setting('GEMINI_API_KEYS').strip()))
    values.extend(user_setting(f'GEMINI_API_KEY_{index}') for index in range(2, 21))
    values.append(user_setting('GOOGLE_API_KEY'))
    return tuple(dict.fromkeys(value.strip() for value in values if value and value.strip()))
