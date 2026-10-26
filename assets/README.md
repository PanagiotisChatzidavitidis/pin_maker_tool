# Assets

Pictures the app uses for itself. Everything here is optional: without them the app
still runs and falls back to a simple built-in pin icon.

| File | Used for |
| --- | --- |
| `icon.ico` | Window / title-bar icon on Windows, and the icon of the built `.exe` |
| `icon.icns` | Icon of the built `.app` on macOS |
| `logo.png` | The logo on the start screen and in dialogs (transparent PNG works best) |

`.ico` and `.png` files are listed in `.gitignore`, so they are **not** committed to the
repository. Copy them into this folder on each machine you build or run on. If you do want
them in the repository, remove those two lines from `.gitignore`.

When the app is packed into a single file with `python scripts/build_exe.py`, this whole
folder is bundled inside it.
