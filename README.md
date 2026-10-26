# Badge Pin Maker

A small desktop app for making printable sheets of round badge-pin artwork. Pick a paper
size and a pin size, drop in your photos, position each one under the pin circle, then
export a PDF (or print straight away) ready to cut out.

## What it does

- **Automatic layout.** Choose a paper size (A3 to A6, Letter, Legal, Tabloid, photo sizes
  or your own) and a pin size (25 to 75 mm or your own). The app tries a plain grid and a
  staggered "honeycomb" packing, in portrait and landscape, and keeps whichever fits the
  most pins.
- **Crop under the pin.** Drag to move, scroll to zoom, rotate in 90° steps or freely. The
  part that folds behind the pin is shaded, so you can see what will actually show.
- **Quality warnings.** Photos that would print below 200 dpi get a small "!" on the sheet
  and a warning before export.
- **Fill many circles at once.** Select several photos, or drop image files onto the sheet
  (drag and drop needs the optional `tkinterdnd2` package). One photo can be copied onto
  several circles.
- **PDF export and printing.** Photos are embedded at 600 dpi, with a thin cut line, crop
  ticks and an optional safe-area ring. Empty circles print blank.
- **Projects.** Everything is saved as a `.pinproj` file so you can come back and edit it.
  Undo / redo, a light and a dark theme, and your last settings are remembered.

## Getting started

You need Python 3 with tkinter (it ships with Python; on Linux install it with
`sudo apt install python3-tk`).

```bash
pip install -r requirements.txt
python badge_maker.py
```

`python -m badge_pin_maker` does the same thing.

### Keyboard shortcuts

On macOS use Cmd instead of Ctrl.

| Shortcut | Action |
| --- | --- |
| Ctrl+N | New project |
| Ctrl+O | Browse for a project |
| Ctrl+S / Ctrl+Shift+S | Save / Save as |
| Ctrl+H | Back to the projects screen |
| Ctrl+E | Export PDF |
| Ctrl+P | Print |
| Ctrl+Z / Ctrl+Y | Undo / Redo |
| Delete | Clear the circle under the mouse |

## Building a standalone app

To get an app that runs without Python installed:

```bash
pip install pyinstaller
python scripts/build_exe.py
```

Build on the system you are building for (Windows for a `.exe`, macOS for a `.app`). The
result appears in `dist/`. Put `icon.ico` / `icon.icns` and `logo.png` in
[`assets/`](assets/README.md) first if you want your own artwork.

## Project layout

```
badge_maker.py            Start the app (a tiny launcher)
requirements.txt          Python packages the app needs
assets/                   Icon and logo images (see assets/README.md)
scripts/
  build_exe.py            Packs the app into a single executable with PyInstaller
badge_pin_maker/          The program itself
  constants.py            Fixed numbers: margins, print quality, paper and pin size menus
  paths.py                Finding bundled files, from source or from the built exe
  settings.py             Remembered preferences (a small JSON file in your home folder)
  layout.py               Where the circles go on the sheet (pure arithmetic)
  imaging.py              Photos, zoom / rotation maths, rendering one pin's picture
  pdf_export.py           Writing the PDF
  project_files.py        Reading .pinproj files for the projects list
  system_actions.py       Printing and opening folders on Windows / macOS / Linux
  ui/                     Everything you see on screen
    app.py                The main window (editor, projects, export)
    home_screen.py        The start screen with the project list
    crop_dialog.py        The window for positioning a photo under the pin
    dialogs.py            Message boxes in the app's own style
    widgets.py            Cards, stat tiles, the on / off switch
    icons.py              Project thumbnails and the logo
    theme.py              Light and dark colours and ttk styling
    dnd.py                Optional drag and drop support
```

The first group of modules (everything outside `ui/`) never opens a window, so the maths
and the PDF output can be read, run and tested on their own.

## Where things are saved

| What | Where |
| --- | --- |
| Projects | `~/Badge Pin Maker Projects/` (changeable from the start screen) |
| Preferences | `~/.badge_pin_maker.json` |
| Photos | Stay where they are. A project stores only their location, so moving a photo means the project has to find it again (it also looks next to the project file). |
