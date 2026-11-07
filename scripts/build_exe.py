#!/usr/bin/env python3
"""
Build a standalone app (no Python needed to run it) with PyInstaller.

    pip install pyinstaller pillow reportlab tkinterdnd2
    python scripts/build_exe.py

Run it on the system you are building for (build on Windows for a Windows .exe,
on macOS for a .app). The result is in the "dist" folder at the top of the project.

Put your images in an "assets" folder at the top of the project:
    assets/ozzie.png, mr_ozzie.png, ms_ozzie.png   (the mascot; the app icon is made from Ozzie)
    assets/icon.ico (Windows) or icon.icns (macOS) are made from Ozzie when you build, or put
    your own there if there is no Ozzie picture
"""

import datetime
import importlib.util
import os
import subprocess
import sys

# The top folder of the project. This file lives one level down, in scripts/.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "assets")
NAME = "Ozzie's Pin Studio"          # the name of the finished .exe / .app


def main():
    if importlib.util.find_spec("PyInstaller") is None:
        sys.exit("PyInstaller is not installed. Run:  pip install pyinstaller")

    # --windowed = no console window behind the app, --clean = ignore old build caches
    # The spec file and the work files go into build/, so the top folder stays tidy; the
    # finished app is in dist/.
    build = os.path.join(ROOT, "build")
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
           "--windowed", "--name", NAME,
           "--specpath", build, "--workpath", os.path.join(build, "work"),
           "--distpath", os.path.join(ROOT, "dist")]
    if sys.platform != "darwin":
        cmd.append("--onefile")          # macOS builds a .app bundle instead
    if importlib.util.find_spec("tkinterdnd2") is not None:
        # drag and drop is optional, but when it is installed it must be packed in too
        cmd += ["--collect-all", "tkinterdnd2"]

    # The icon comes from Ozzie's picture (assets/ozzie.png), made fresh for each build.
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    try:
        import make_icon
        make_icon.main()
    except Exception as exc:  # noqa: BLE001 - fall back to whatever icon file exists
        print("Could not make the icon from Ozzie:", exc)

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

    # Stamp the build date so the About box can show it (the file is removed again afterwards).
    stamp = os.path.join(ROOT, "badge_pin_maker", "_build.py")
    with open(stamp, "w", encoding="utf-8") as f:
        f.write(f'BUILD_DATE = "{datetime.date.today().isoformat()}"\n')
    print("Running:", " ".join(cmd))
    try:
        subprocess.run(cmd, check=True, cwd=ROOT)
    finally:
        os.remove(stamp)
    print(f"\nDone. Look in: {os.path.join(ROOT, 'dist')}")


if __name__ == "__main__":
    main()
