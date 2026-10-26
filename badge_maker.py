"""Start Badge Pin Maker:  python badge_maker.py

The program itself lives in the "badge_pin_maker" package. This small file just starts it,
so the familiar command (and the PyInstaller build) keep working.
"""

from badge_pin_maker.ui.app import main

if __name__ == "__main__":
    main()
