# Ozzie's Pin Studio

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
- **Options in one place.** The **Options** button (start screen and editor) opens a window with
  full screen / windowed (full screen is the default), the mascot, the themes, a button to watch the
  tutorial again and where your files are kept. **Restore defaults** puts everything back,
  **Return** closes the window. Changing a theme blends every colour on screen into the new ones,
  with no flash and nothing covering the window.
- **Themes.** Creamy, warm colours throughout. Four light themes (Oat Milk, Vanilla Latte,
  Cream & Denim, Strawberry Cream), four dark themes that are coffee and cream rather than steel
  (Espresso Mint, Cocoa Cream, Cocoa Denim, Mocha Orchid) and the original teal pair (Lagoon Sand and Lagoon Night). Each
  tile previews its own colours. Oat Milk is the default light theme and Espresso Mint the
  default dark one; the app remembers your last light and your last dark theme. Themes
  chosen before the renaming carry over (Carbon Blue is now Cocoa Denim, Graphite Mint is
  Espresso Mint, Midnight Orchid is Mocha Orchid, Classic is Lagoon).
- **Drag to rearrange.** Drag a pin onto another circle to swap the two, or onto an empty
  circle to move it. A ghost follows the mouse and the target lights up; Esc cancels. A plain
  click still opens Modify / Clear, and every move can be undone.
- **Autosave and crash recovery.** Unsaved work is copied to a recovery file every 10 seconds
  (your canvas file is never touched). After a crash or power cut the app offers to put it all
  back at the next start; saving or closing normally clears it.
- **Gentle loading.** Big pictures, opening a canvas and PDF export run in the background, so the
  window never freezes. A little progress note appears if it takes a moment, and buttons that
  could clash with the running job are ignored until it finishes.
- **Canvas grid, search and sorting.** The start screen shows your canvases as a grid of cards
  that fills the window (more columns on a wide screen), with a "New canvas" tile first, a search box (name, paper or pin size) and a sort menu: recently
  edited, recently opened, name A–Z / Z–A, oldest first, most pins. Thumbnails appear as they
  are ready, and your sort choice is remembered.
- **A guided tour with the mascot.** The first time you see the start screen, and again the
  first time you open the editor, Ozzie (or Mr / Ms Ozzie) walks you through it: a soft glowing
  frame glides to each part of the screen and a card with the mascot says what it does. Use
  Next / Back or the arrow keys, Esc or "Skip tour" to leave. The rest of the window is locked
  while the tour runs, so nothing is clicked by accident. Switch on "Don't show tips again" in
  the card to stop it for good. "Watch the tutorial again" in Options plays it again. The steps
  are in `ui/tour.py`.
- **Zoom and pan the sheet.** Ctrl + scroll zooms in on the spot under the mouse (up to 8x), and
  so does the zoom bar under the sheet (slider, - / + and a Fit button). A small readout
  (the zoom HUD) pops up while you zoom and fades away. Zoomed in, scroll slides the sheet up
  and down (Shift + scroll sideways), and holding Ctrl or Space while dragging, or dragging with
  the middle button, moves it freely. Ctrl + / Ctrl - zoom and Ctrl 0, the Fit button or a click
  on the corner pill fits the whole sheet again.
- **Quiet animations.** Pins glide into their new circles when swapped or moved and fade away
  when cleared (always on).
- **Undo and redo arrows.** Two arrows next to the app name (greyed out when there is nothing to
  undo or redo) do the same as Ctrl+Z and Ctrl+Y.
- **Held keys count once.** Holding Ctrl+S (or any other shortcut) runs it only once instead of
  repeating. Zooming with Ctrl + and Ctrl - is the exception: holding it keeps zooming.
- **Ozzie, the mascot.** Ozzie the hamster is the app's logo, the picture in the corner notes
  and the window icon. In **Options → Mascot** you can pick **Ozzie**, **Mr Ozzie** (bow tie)
  or **Ms Ozzie** (hair bow); the choice is remembered and swaps everywhere straight away.
  Ozzie is the default.
- **Corner notes.** Small cheerful notes with the hamster appear in the bottom-right corner
  for saved, opened, deleted, exported, swapped and so on. Some carry a link (Undo, Show in
  folder). They fade by themselves, or click one to close it.

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
| Ctrl+H | Back to the menu |
| Ctrl+E | Export PDF |
| Ctrl+P | Print |
| Ctrl+Z / Ctrl+Y | Undo / Redo |
| Delete | Clear the circle under the mouse |
| F11 | Switch between full screen and windowed |
| Ctrl + scroll / Ctrl + / Ctrl - | Zoom the sheet |
| Ctrl 0 | Fit the whole sheet |
| Ctrl + drag / Space + drag | Move the zoomed sheet |
| Esc | Cancel a drag, close the popup, or leave full screen |

## Building a standalone app

To get an app that runs without Python installed:

```bash
pip install pyinstaller
python scripts/build_exe.py
```

Build on the system you are building for (Windows for a `.exe`, macOS for a `.app`). The
result appears in `dist/`; the spec file and the work files go into `build/`, so the top folder stays clean. Ozzie's pictures live in [`assets/`](assets/README.md); the build makes the app icon
from Ozzie's picture.

## Project layout

```
badge_maker.py            Start the app (a tiny launcher)
requirements.txt          Python packages the app needs
assets/                   Icon and logo images (see assets/README.md)
scripts/
  build_exe.py            Packs the app into a single executable with PyInstaller
  make_icon.py            Makes the app icon (.ico / .icns) from Ozzie's picture
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
    options_dialog.py     The Options window (display mode, mascot, themes, tutorial, your files)
    morph.py              The smooth blend from one theme to another
    crop_dialog.py        The window for positioning an image under the pin
    dialogs.py            Message boxes in the app's own style
    widgets.py            Cards, stat tiles, the on / off switch
    toast.py              The corner notes and their cute messages (one of each kind at a time)
    tour.py               The guided tour: the steps, the glowing frame and the mascot card
    icons.py              Canvas thumbnails and the logo
    mascot.py             Ozzie, Mr Ozzie and Ms Ozzie: finding, cutting out and sizing the pictures
    theme.py              The light and dark themes (colours) and ttk styling
    dnd.py                Optional drag and drop support
```

The first group of modules (everything outside `ui/`) never opens a window, so the maths
and the PDF output can be read, run and tested on their own.

## Where things are saved

| What | Where |
| --- | --- |
| Canvases | `Documents/Ozzie's Pin Studio/Canvases/` (changeable in Options) |
| Exported PDFs | `Documents/Ozzie's Pin Studio/PDFs/` (the save box starts there) |
| Preferences | `settings.json` in the app's own folder: `%APPDATA%\Ozzie's Pin Studio` on Windows, `~/Library/Application Support/Ozzie's Pin Studio` on macOS, `~/.config/ozzies-pin-studio` on Linux |
| Crash recovery | `recovery.pinproj` in that same folder (deleted on save or normal close) |
| Images | Stay where they are. A canvas stores only their location, so moving an image means the canvas has to find it again (it also looks next to the canvas file). |

Older versions kept the canvases in `~/Badge Pin Maker Canvases/` and the preferences straight in
the home folder. The preferences move to the new place by themselves, and the first start offers
to tidy the canvases into Documents (nothing is deleted; a canvas folder you chose yourself is
left alone).

## About and credits

The **About** button on the start screen shows the version (and, in a built app, the build date).
Ozzie, the hamster mascot, is drawn by **Netherduck**.

The version lives in `badge_pin_maker/version.py` (change `__version__` there). `scripts/build_exe.py`
stamps the build date into the app when you build it.
