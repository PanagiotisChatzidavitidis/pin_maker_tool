# Badge Pin Maker

A small desktop app for making printable sheets of round badge-pin artwork. Pick a paper
size and a pin size, drop in your images, position each one under the pin circle, then
export a PDF (or print straight away) ready to cut out.

## What it does

- **Automatic layout.** Choose a paper size (A3 to A6, Letter, Legal, Tabloid, photo-paper sizes
  or your own) and a pin size (25 to 75 mm or your own). The app tries a plain grid and a
  staggered "honeycomb" packing, in portrait and landscape, and keeps whichever fits the
  most pins.
- **Crop under the pin.** Drag to move, scroll to zoom (it zooms toward the cursor), rotate in
  90° steps or freely. *Fill* covers the pin, *Fit* shows the whole picture, double-click
  toggles between them, and the arrow keys nudge. The crop window can be resized, and the
  part that folds behind the pin is shaded, so you can see what will actually show.
- **Quality warnings.** Images that would print below 200 dpi get a small "!" on the sheet
  and a warning before export.
- **Fill many circles at once.** Select several images, or drop image files onto the sheet
  (drag and drop needs the optional `tkinterdnd2` package). One image can be copied onto
  several circles.
- **PDF export and printing.** Images are embedded at 600 dpi, with a thin cut line, crop
  ticks and an optional safe-area ring. Empty circles print blank.
- **Canvases.** Everything is saved as a `.pinproj` file so you can come back and edit it.
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
| Ctrl+N | New canvas |
| Ctrl+O | Browse for a canvas |
| Ctrl+S / Ctrl+Shift+S | Save / Save as |
| Ctrl+H | Back to the canvases screen |
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
  imaging.py              Images, zoom / rotation maths, rendering one pin's picture
  pdf_export.py           Writing the PDF
  canvas_files.py         Reading .pinproj files for the canvases list
  system_actions.py       Printing and opening folders on Windows / macOS / Linux
  ui/                     Everything you see on screen
    app.py                The main window (editor, canvases, export)
    home_screen.py        The start screen with the canvas list
    crop_dialog.py        The window for positioning an image under the pin
    dialogs.py            Message boxes in the app's own style
    widgets.py            Cards, stat tiles, the on / off switch
    icons.py              Canvas thumbnails and the logo
    theme.py              Light and dark colours and ttk styling
    dnd.py                Optional drag and drop support
```

The first group of modules (everything outside `ui/`) never opens a window, so the maths
and the PDF output can be read, run and tested on their own.

## Where things are saved

| What | Where |
| --- | --- |
| Canvases | `~/Badge Pin Maker Canvases/` (changeable from the start screen) |
| Preferences | `~/.badge_pin_maker.json` |
| Images | Stay where they are. A canvas stores only their location, so moving an image means the canvas has to find it again (it also looks next to the canvas file). |
