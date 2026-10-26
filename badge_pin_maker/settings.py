"""Small preferences that are remembered between sessions.

The theme, the last paper and pin size, the window size and the folders you used last are
kept in a JSON file in your home folder. Losing or breaking that file is harmless: the app
simply starts with its defaults.
"""

import json
import os


SETTINGS_PATH = os.path.join(os.path.expanduser("~"), ".badge_pin_maker.json")


def load_settings():
    """Read the saved preferences. A missing or broken file just gives an empty dict."""
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_settings(data):
    """Write the preferences. Failing quietly is fine (for example a read-only home folder).
    """
    try:
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except OSError:
        pass


def default_projects_dir():
    """Where projects are kept unless the user picks another folder."""
    return os.path.join(os.path.expanduser("~"), "Badge Pin Maker Projects")
