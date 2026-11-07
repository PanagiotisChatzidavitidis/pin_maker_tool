"""Small preferences that are remembered between sessions.

The theme, the last paper and pin size, the window size and the folders you used last are
kept in a JSON file in your home folder. Losing or breaking that file is harmless: the app
simply starts with its defaults.
"""

import json
import os
import shutil
import sys

APP_NAME = "Ozzie's Pin Studio"


def _data_dir():
    """The folder for the app's own files (preferences and the crash-recovery copy), in the
    place each system keeps such things, so your Documents stay for your own work.
    """
    home = os.path.expanduser("~")
    if sys.platform == "win32":
        return os.path.join(os.environ.get("APPDATA") or os.path.join(home, "AppData", "Roaming"),
                            APP_NAME)
    if sys.platform == "darwin":
        return os.path.join(home, "Library", "Application Support", APP_NAME)
    return os.path.join(os.environ.get("XDG_CONFIG_HOME") or os.path.join(home, ".config"),
                        "ozzies-pin-studio")


DATA_DIR = _data_dir()
SETTINGS_PATH = os.path.join(DATA_DIR, "settings.json")
# Unsaved work is copied here every few seconds. It is removed again on a normal save or exit,
# so if it is still there at the next start, the app closed unexpectedly.
RECOVERY_PATH = os.path.join(DATA_DIR, "recovery.pinproj")

# where older versions kept these files (straight in the home folder)
_OLD_SETTINGS = os.path.join(os.path.expanduser("~"), ".badge_pin_maker.json")
_OLD_RECOVERY = os.path.join(os.path.expanduser("~"), ".badge_pin_maker_recovery.pinproj")


def _move_old_files():
    """Bring the preferences and a leftover recovery copy from the old place to DATA_DIR
    (only if the new ones don't exist yet). Failing is harmless.
    """
    for old, new in ((_OLD_SETTINGS, SETTINGS_PATH), (_OLD_RECOVERY, RECOVERY_PATH)):
        try:
            if os.path.isfile(old) and not os.path.exists(new):
                os.makedirs(DATA_DIR, exist_ok=True)
                shutil.move(old, new)
        except OSError:
            pass


def load_settings():
    """Read the saved preferences. A missing or broken file just gives an empty dict."""
    _move_old_files()
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
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except OSError:
        pass


# ---- your own files: one tidy folder in Documents ------------------------------------
#   Documents/Ozzie's Pin Studio/Canvases   the canvas files
#   Documents/Ozzie's Pin Studio/PDFs       the PDFs you export

def library_dir():
    """The app's folder in Documents (the home folder if there is no Documents folder)."""
    home = os.path.expanduser("~")
    docs = os.path.join(home, "Documents")
    return os.path.join(docs if os.path.isdir(docs) else home, APP_NAME)


def legacy_canvases_dir():
    """The folder older versions kept canvases in, if it exists (else None)."""
    home = os.path.expanduser("~")
    for name in ("Badge Pin Maker Canvases", "Badge Pin Maker Projects"):
        d = os.path.join(home, name)
        if os.path.isdir(d):
            return d
    return None


def default_canvases_dir():
    """Where canvases are kept unless the person picked another folder. Someone who already
    has an old canvases folder (and no new one yet) keeps using it until they tidy up.
    """
    new = os.path.join(library_dir(), "Canvases")
    old = legacy_canvases_dir()
    return old if old and not os.path.isdir(new) else new


def default_pdf_dir():
    """Where exported PDFs are offered, unless the person went somewhere else last time."""
    return os.path.join(library_dir(), "PDFs")


def tidy_candidates():
    """The canvas files in the old folder that could be moved to the new one, or []. Only
    when the person didn't choose a folder themselves and the new one doesn't exist yet.
    """
    old = legacy_canvases_dir()
    if not old or os.path.isdir(os.path.join(library_dir(), "Canvases")):
        return []
    try:
        return sorted(n for n in os.listdir(old) if n.lower().endswith(".pinproj"))
    except OSError:
        return []


def tidy_legacy(settings):
    """Move the canvases from the old folder into Documents/Ozzie's Pin Studio/Canvases and
    point the recent list at them. Returns how many were moved. The old folder is removed if
    it ends up empty; anything else in it stays where it is.
    """
    old, names = legacy_canvases_dir(), tidy_candidates()
    new = os.path.join(library_dir(), "Canvases")
    if not old or not names:
        return 0
    os.makedirs(new, exist_ok=True)
    moved = {}
    for name in names:
        src, dst = os.path.join(old, name), os.path.join(new, name)
        if os.path.exists(dst):
            continue
        try:
            shutil.move(src, dst)
            moved[src] = dst
        except OSError:
            pass
    recent = settings.get("recent")
    if isinstance(recent, list):
        settings["recent"] = [moved.get(p, p) if isinstance(p, str) else p for p in recent]
    settings.pop("canvases_dir", None)
    settings.pop("projects_dir", None)
    try:
        os.rmdir(old)                      # only works when it is empty
    except OSError:
        pass
    return len(moved)
