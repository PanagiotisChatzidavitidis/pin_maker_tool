#!/usr/bin/env python3
"""
Build a standalone app (no Python needed to run it) with PyInstaller.

    pip install pyinstaller pillow reportlab tkinterdnd2
    python build_exe.py

Run it on the system you are building for (build on Windows for a Windows .exe,
on macOS for a .app). The result is in the "dist" folder.

Put your images in an "assets" folder next to this file:
    assets/icon.ico   (Windows)  or  assets/icon.icns  (macOS)
    assets/logo.png   (optional: replaces the in-app logo)
"""

import importlib.util
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
NAME = "Badge Pin Maker"


def main():
    if importlib.util.find_spec("PyInstaller") is None:
        sys.exit("PyInstaller is not installed. Run:  pip install pyinstaller")

    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
           "--windowed", "--name", NAME]
    if sys.platform != "darwin":
        cmd.append("--onefile")          # macOS builds a .app bundle instead
    if importlib.util.find_spec("tkinterdnd2") is not None:
        cmd += ["--collect-all", "tkinterdnd2"]

    icon = os.path.join(ASSETS, "icon.icns" if sys.platform == "darwin" else "icon.ico")
    print("Icon path:", icon, "| exists:", os.path.isfile(icon))
    if os.path.isfile(icon):
        cmd += ["--icon", icon]          # the icon of the .exe / .app file itself

    # Bundle the whole assets folder. The destination name "assets" must match
    # asset_path() in badge_maker.py, so the running app finds icon.ico and logo.png.
    print("Assets folder:", ASSETS, "| exists:", os.path.isdir(ASSETS))
    if os.path.isdir(ASSETS):
        cmd += ["--add-data", f"{ASSETS}{os.pathsep}assets"]

    cmd.append(os.path.join(HERE, "badge_maker.py"))

    print("Running:", " ".join(cmd))
    subprocess.run(cmd, check=True, cwd=HERE)
    print(f"\nDone. Look in: {os.path.join(HERE, 'dist')}")


if __name__ == "__main__":
    main()