"""Small helpers that talk to the operating system: printing a PDF and opening a folder, each
done the right way for Windows, macOS and Linux.
"""

import os
import platform
import subprocess


def print_pdf(path):
    """Send a PDF to the printer. Windows uses the default PDF app's "print" action (or just
    opens the file if that fails). macOS and Linux use ``lp`` with scaling=100 so the pins
    print at their true size; without ``lp`` the file is opened in a viewer instead.
    """
    system = platform.system()
    if system == "Windows":
        try:
            os.startfile(path, "print")  # type: ignore[attr-defined]
        except OSError:
            os.startfile(path)  # type: ignore[attr-defined]
    elif system == "Darwin":
        subprocess.run(["lp", "-o", "scaling=100", path], check=False)
    else:
        if subprocess.run(["which", "lp"], capture_output=True).returncode == 0:
            subprocess.run(["lp", "-o", "scaling=100", path], check=False)
        else:
            subprocess.run(["xdg-open", path], check=False)


def reveal_folder(path):
    """Open a folder in the system file manager."""
    try:
        if platform.system() == "Windows":
            os.startfile(path)  # type: ignore[attr-defined]
        elif platform.system() == "Darwin":
            subprocess.run(["open", path], check=False)
        else:
            subprocess.run(["xdg-open", path], check=False)
    except OSError:
        pass
