#!/usr/bin/env python3
"""
Make the app icon from Ozzie, the mascot.

    python scripts/make_icon.py

It reads Ozzie's picture from the assets/ folder (ozzie.png, Ozzie.png ... any capital
letters), cuts out a flat background if it has one, and writes
    assets/icon.ico    (Windows: the icon of the .exe and of the windows)
    assets/icon.icns   (macOS: the icon of the .app)
    assets/icon.png    (a 512 px copy)
scripts/build_exe.py runs this for you before it builds.
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from badge_pin_maker.ui import mascot  # noqa: E402

SIZES = [16, 24, 32, 48, 64, 128, 256]


def main():
    """Write the icon files. Returns True if Ozzie's picture was found."""
    big = mascot.square("ozzie", 1024, pad=0.03)
    if big is None:
        print("No Ozzie picture in assets/ (ozzie.png): the icon was not made.")
        return False
    assets = os.path.join(ROOT, "assets")
    big.resize((512, 512)).save(os.path.join(assets, "icon.png"))
    big.save(os.path.join(assets, "icon.ico"), sizes=[(s, s) for s in SIZES])
    try:
        big.save(os.path.join(assets, "icon.icns"))
    except Exception as exc:  # noqa: BLE001 - the .icns is only needed on a Mac
        print("Could not write icon.icns:", exc)
    print("Wrote assets/icon.ico, icon.icns and icon.png from", mascot.find_file("ozzie"))
    return True


if __name__ == "__main__":
    main()
