# Real photo backdrops

Drop a real photograph here and the preview uses it instead of the drawn scene.

Name the file after the scene: `studio`, `desk`, `school`, `backpack`, `fridge`, `coffee`, `party`
(`.jpg` or `.png`). Use a landscape photo, shot straight down (or straight on for `fridge` and
`backpack`), with an empty area where the pins will sit. It is cropped to 3:2.

Optionally add `<scene>.json` with the pin area in millimetres on a 420 x 280 mm picture:

    {"stage": [left, top, right, bottom]}

Close-ups use the middle of the same photo, so keep the centre of the photo clear.
You can also put photos in `~/.cache/ozzies-pin-studio/backdrops/` (Windows: `%LOCALAPPDATA%`).
