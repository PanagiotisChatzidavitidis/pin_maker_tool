"""The app's version, build date and credits: the one place to change them."""

__version__ = "1.0.0"
ART_CREDIT = "Netherduck"            # who drew Ozzie

try:                                 # written by scripts/build_exe.py when the app is built
    from ._build import BUILD_DATE
except ImportError:                  # running from the source files
    BUILD_DATE = None


def version_text():
    """"Version 1.0.0" with the build date after it when this is a built app."""
    return f"Version {__version__}" + (f"  ·  build {BUILD_DATE}" if BUILD_DATE else "")
