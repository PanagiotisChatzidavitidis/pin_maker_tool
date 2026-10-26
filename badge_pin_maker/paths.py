"""Finding the files that ship with the app (the icon and the logo).

When you run from source they sit in the "assets" folder at the top of the project. When the
app has been packed into a single .exe with PyInstaller they are unpacked into a temporary
folder instead, which PyInstaller announces through sys._MEIPASS.
"""

import os
import sys


def resource_path(name):
    """Find a bundled file both when running from source and from the built exe."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, name)


def asset_path(name):
    """Find a file inside the assets/ folder (icon.ico, logo.png, ...)."""
    return resource_path(os.path.join("assets", name))
