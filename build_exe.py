#!/usr/bin/env python3
"""
Build a standalone app (no Python needed to run it) with PyInstaller.

    pip install pyinstaller pillow reportlab tkinterdnd2
    python build_exe.py

Run it on the system you are building for (build on Windows for a Windows .exe,
on macOS for a .app). The result is in the "dist" folder.
Optional: put an icon.ico (Windows) or icon.icns (macOS) next to this file.
Optional: put a logo.png next to this file to replace the in-app logo.
"""

import importlib.util
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
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

    icon = os.path.join(HERE, "icon.icns" if sys.platform == "darwin" else "icon.ico")
    print("Icon path:", icon, "| exists:", os.path.isfile(icon))
    if os.path.isfile(icon):
        cmd += ["--icon", icon]
        if sys.platform == "win32":
            # bundle it so the running window can use it too (iconbitmap)
            cmd += ["--add-data", f"{icon}{os.pathsep}."]

    logo = os.path.join(HERE, "logo.png")
    print("Logo path:", logo, "| exists:", os.path.isfile(logo))
    if os.path.isfile(logo):
        cmd += ["--add-data", f"{logo}{os.pathsep}."]

    cmd.append(os.path.join(HERE, "badge_maker.py"))

    print("Running:", " ".join(cmd))
    subprocess.run(cmd, check=True, cwd=HERE)
    print(f"\nDone. Look in: {os.path.join(HERE, 'dist')}")


if __name__ == "__main__":
    main()