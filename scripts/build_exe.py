#!/usr/bin/env python3
"""
Build a standalone app (no Python needed to run it) with PyInstaller.

    pip install pyinstaller pillow reportlab tkinterdnd2
    python scripts/build_exe.py

Run it on the system you are building for (build on Windows for a Windows .exe,
on macOS for a .app). The result is in the "dist" folder at the top of the project.

Put your images in an "assets" folder at the top of the project:
    assets/icon.ico   (Windows)  or  assets/icon.icns  (macOS)
    assets/logo.png   (optional: replaces the in-app logo)
"""

import importlib.util
import os
import subprocess
import sys

# The top folder of the project. This file lives one level down, in scripts/.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "assets")
NAME = "Badge Pin Maker"          # the name of the finished .exe / .app


def main():
    if importlib.util.find_spec("PyInstaller") is None:
        sys.exit("PyInstaller is not installed. Run:  pip install pyinstaller")

    # --windowed = no console window behind the app, --clean = ignore old build caches
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
           "--windowed", "--name", NAME]
    if sys.platform != "darwin":
        cmd.append("--onefile")          # macOS builds a .app bundle instead
    if importlib.util.find_spec("tkinterdnd2") is not None:
        # drag and drop is optional, but when it is installed it must be packed in too
        cmd += ["--collect-all", "tkinterdnd2"]

    icon = os.path.join(ASSETS, "icon.icns" if sys.platform == "darwin" else "icon.ico")
    print("Icon path:", icon, "| exists:", os.path.isfile(icon))
    if os.path.isfile(icon):
        cmd += ["--icon", icon]          # the icon of the .exe / .app file itself

    # Bundle the whole assets folder. The destination name "assets" must match
    # asset_path() in badge_pin_maker/paths.py, so the running app finds icon.ico and logo.png.
    print("Assets folder:", ASSETS, "| exists:", os.path.isdir(ASSETS))
    if os.path.isdir(ASSETS):
        cmd += ["--add-data", f"{ASSETS}{os.pathsep}assets"]

    # badge_maker.py is the small launcher; PyInstaller follows its imports and finds the
    # whole badge_pin_maker package from there.
    cmd.append(os.path.join(ROOT, "badge_maker.py"))

    print("Running:", " ".join(cmd))
    subprocess.run(cmd, check=True, cwd=ROOT)
    print(f"\nDone. Look in: {os.path.join(ROOT, 'dist')}")


if __name__ == "__main__":
    main()
