"""Peeking into saved project (.pinproj) files for the start screen's list.

This is deliberately cheap: it reads names, sizes and where the first photo sits, but never
loads a full-size photo, so listing many projects stays fast.
"""

import json
import os


def _resolve_photo(ph, base):
    """Find a photo referenced by a project (absolute path, relative path, same folder)."""
    orig = ph.get("path") or ""
    rel = ph.get("rel") or ""
    for cand in (orig, os.path.join(base, rel) if rel else "",
                 os.path.join(base, os.path.basename(orig)) if orig else ""):
        if cand and os.path.isfile(cand):
            return cand
    return None


def read_project_info(path):
    """Cheap summary of a .pinproj for the list (no full-res photo loading)."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        mtime = os.path.getmtime(path)
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or data.get("app") != "badge-pin-maker":
        return None
    paper = str(data.get("paper", ""))
    pin = str(data.get("pin", ""))
    paper = "Custom paper" if paper.startswith("Custom") else paper.split(" (")[0]
    pin = f"{data.get('diameter', '?')} mm pin" if pin.startswith("Custom") else pin
    info = dict(path=path, name=os.path.splitext(os.path.basename(path))[0],
                mtime=mtime, paper=paper, pin=pin, pins=0, art=None)
    slots = [s for s in data.get("slots", []) if isinstance(s, dict)]
    info["pins"] = len(slots)
    base = os.path.dirname(os.path.abspath(path))
    photos = data.get("photos", [])
    for sl in sorted(slots, key=lambda s: s.get("slot", 0)):
        try:
            photo = _resolve_photo(photos[int(sl["photo"])], base)
            if photo:
                info["art"] = (photo, float(sl.get("zoom", 1.0)), float(sl.get("cx", 0.5)),
                               float(sl.get("cy", 0.5)), float(sl.get("angle", 0.0)))
                break
        except (KeyError, ValueError, TypeError, IndexError, AttributeError):
            continue
    return info
