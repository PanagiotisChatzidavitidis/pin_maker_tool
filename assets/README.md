# Assets

Pictures the app uses for itself. Everything here is optional: without them the app
still runs and falls back to a simple built-in pin icon.

## Ozzie, the mascot

Put three pictures of Ozzie in this folder:

| File | Who |
| --- | --- |
| `ozzie.png` | Ozzie, the default |
| `mr_ozzie.png` | Mr Ozzie |
| `ms_ozzie.png` | Ms Ozzie |

The names do not have to be exact: capital letters, spaces and underscores are ignored, so
`Ozzie.png`, `MrOzzie.png` and `ms ozzie.png` all work (`.png`, `.webp` and `.jpg` are fine).
Square pictures about 512 px or larger look best. If a picture has a flat background (a cream
square, say), the app cuts it out by itself, so Ozzie sits cleanly on every theme.

The one picked in **Options → Mascot** is the logo (start screen, Options, corner notes) and
the window icon.

## The app icon

`python scripts/make_icon.py` makes `icon.ico` (Windows), `icon.icns` (macOS) and `icon.png`
from `ozzie.png`; `python scripts/build_exe.py` does it for you before building the `.exe` /
`.app`. If there is no Ozzie picture, put your own `icon.ico` / `icon.icns` here instead, and
`logo.png` still works as a plain logo.

## Git

Ozzie's pictures and `icon.ico` / `icon.png` are allowed through `.gitignore`, so they are
committed with the project. Other image files here are not.
