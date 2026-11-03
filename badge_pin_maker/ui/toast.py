"""Little pop-up notes in the bottom-right corner, each with the hamster.

They tell the person what just happened ("Saved!", "Canvas deleted", ...) and fade away by
themselves. A note can carry a small link such as "Undo", and a "busy" note stays up (with a
bobbing hamster and a progress bar) until the work it talks about is done.

    app.toasts.show("saved", name="My pins")
    note = app.toasts.busy("exporting"); ...; note.close()

The wording lives in MESSAGES; each event has a few variants and one is picked at random.
"""

import math
import random
import tkinter as tk
from tkinter import ttk

from . import theme as T
from .icons import load_logo


# event -> list of (title, body). {name}, {n}, {s} (an "s" for plurals) are filled in.
MESSAGES = {
    "saved": [
        ("Saved!", "“{name}” is tucked in safe and sound."),
        ("All saved!", "I put “{name}” somewhere cosy."),
        ("Squeak, saved!", "“{name}” won't get lost now."),
    ],
    "created": [
        ("A fresh canvas!", "“{name}” is ready. Go make something lovely."),
        ("Blank sheet, big ideas", "“{name}” is all yours."),
    ],
    "opened": [
        ("Welcome back!", "“{name}” is open and waiting for you."),
        ("There it is!", "I found “{name}” right where you left it."),
    ],
    "deleted": [
        ("Canvas deleted", "Poof! “{name}” is gone. Your images are safe, I promise."),
        ("Bye bye, canvas", "“{name}” has left the building. Your pictures are fine."),
    ],
    "exported": [
        ("Your PDF is ready!", "{name} is all set for printing."),
        ("Fresh off the press!", "{name} is done and waiting for you."),
    ],
    "printing": [
        ("Sent to the printer", "Fingers crossed for a smooth print!"),
        ("Printing…", "Your pins are on their way to the printer."),
    ],
    "cleared_all": [
        ("Sheet cleared", "All clean! Changed your mind? Undo brings them back."),
        ("Whoosh, all gone", "Didn't mean to? Undo will fetch them."),
    ],
    "cleared_one": [
        ("Pin removed", "One less pin. Undo if that was a slip."),
        ("Pin cleared", "That circle is empty again. Undo brings it back."),
    ],
    "added": [
        ("{n} new pin{s}!", "They look great on the sheet."),
        ("{n} pin{s} added!", "Lovely choice. Your sheet is filling up."),
    ],
    "swapped": [
        ("Switcheroo!", "Those two pins traded places."),
        ("Swapped!", "Two pins, new spots."),
    ],
    "moved": [
        ("Moved!", "That pin found a new home."),
        ("Pin moved", "Right where you wanted it."),
    ],
    "recovered": [
        ("Welcome back!", "I found your unsaved work and put it all back."),
        ("Phew, found it!", "Your unsaved changes are back where they belong."),
    ],
    "defaults": [
        ("Back to normal", "Your options are restored to their defaults."),
        ("All reset!", "Everything is back to how it started."),
    ],
    "folder": [
        ("New home for your canvases", "I'll keep them in {name} from now on."),
        ("Folder changed", "Your canvases will live in {name} now."),
    ],
    # busy notes (stay until the work is finished)
    "loading_image": [
        ("Loading your picture…", "Big pictures need a moment."),
        ("Fetching your picture…", "Nearly there, hold tight."),
    ],
    "opening_canvas": [
        ("Opening “{name}”…", "Fetching all your pictures."),
        ("Unpacking “{name}”…", "Just a moment while I find your pictures."),
    ],
    "exporting": [
        ("Building your PDF…", "Print-quality pictures take a little while."),
        ("Making your PDF…", "Getting every pin ready for print."),
    ],
}
_last_variant = {}


def pick(event, **fmt):
    """The (title, body) for an event, with a variant chosen at random (never the same one
    twice in a row) and the placeholders filled in.
    """
    variants = MESSAGES[event]
    i = random.randrange(len(variants))
    if len(variants) > 1 and _last_variant.get(event) == i:
        i = (i + 1) % len(variants)
    _last_variant[event] = i
    fmt.setdefault("s", "")
    title, body = variants[i]
    return title.format(**fmt), body.format(**fmt)


class Toast(tk.Frame):
    """One note. Create it through Toasts.show() / Toasts.busy(), not directly."""
    WRAP = 232                 # text width in pixels

    def __init__(self, mgr, title, body="", kind="success", action=None, busy=False):
        """Build the card: a coloured edge, the hamster, the text and, depending on the kind
        of note, a close mark, an action link or a progress bar.
        """
        super().__init__(mgr.app, bg=T.BORDER)
        self.mgr, self.busy = mgr, busy
        self._timer = self._bob_job = None
        self._closing = False
        self._width = 0
        edge = {"warn": T.WARN, "error": T.ERR}.get(kind, T.TEAL)
        fam = mgr.app.base_font[0]

        card = tk.Frame(self, bg=T.CARD)
        card.pack(padx=1, pady=1)
        tk.Frame(card, bg=edge, width=5).pack(side="left", fill="y")
        self.icon = tk.Canvas(card, width=54, height=62, bg=T.CARD, highlightthickness=0)
        self.icon.pack(side="left", padx=(8, 0), pady=8)
        self._icon_item = self.icon.create_image(27, 33, image=mgr.logo())

        right = tk.Frame(card, bg=T.CARD)
        right.pack(side="right", fill="y", padx=(0, 10), pady=8)
        text = tk.Frame(card, bg=T.CARD)
        text.pack(side="left", padx=(6, 8), pady=10)
        tk.Label(text, text=title, bg=T.CARD, fg=T.PETROL, font=("Georgia", 11, "bold"),
                 anchor="w", justify="left", wraplength=self.WRAP).pack(anchor="w")
        if body:
            tk.Label(text, text=body, bg=T.CARD, fg=T.TEXT, font=(fam, 9), anchor="w",
                     justify="left", wraplength=self.WRAP).pack(anchor="w", pady=(2, 0))
        self.bar = None
        if busy:
            self.bar = ttk.Progressbar(text, style="Teal.Horizontal.TProgressbar",
                                       mode="indeterminate", length=self.WRAP)
            self.bar.pack(anchor="w", pady=(8, 0))
            self.bar.start(14)
        else:
            close = tk.Label(right, text="×", bg=T.CARD, fg=T.MUTED, font=(fam, 13),
                             cursor="hand2")
            close.pack(anchor="ne")
        if action:
            label, fn = action
            link = tk.Label(right, text=label, bg=T.CARD, fg=T.TEAL, cursor="hand2",
                            font=(fam, 9, "underline"))
            link.pack(side="bottom", anchor="se")
            link.bind("<Button-1>", lambda e: (self.dismiss(), fn()))
        if not busy:                       # a click anywhere on the note closes it
            stack = [self]
            while stack:
                w = stack.pop()
                w.bind("<Button-1>", lambda e: self.dismiss(), add="+")
                stack.extend(w.winfo_children())

    # ---- showing and hiding
    def start(self, duration):
        """Slide in, hop, and (unless it is a busy note) close itself after ``duration`` ms."""
        self.update_idletasks()
        self._width = self.winfo_reqwidth()
        self.place(relx=1.0, rely=1.0, x=self._width + 20, y=-self.mgr.bottom(),
                   anchor="se")
        self.lift()
        self._slide(0, 9, out=False)
        if self.busy:
            self._bob(0)
        else:
            self._hop(0)
            if duration:
                self._timer = self.after(duration, self.dismiss)

    def _slide(self, i, n, out):
        """One frame of the slide in (or out): the note eases to / from the screen edge."""
        try:
            t = i / n
            ease = 1 - (1 - t) ** 3
            away = ease if out else 1 - ease
            self.place_configure(x=-self.mgr.MARGIN + away * (self._width + self.mgr.MARGIN + 20))
            if i < n:
                self.after(16, self._slide, i + 1, n, out)
            elif out:
                self._gone()
        except tk.TclError:
            pass

    def _hop(self, step):
        """The hamster's little hop when the note appears."""
        hops = (0, -9, 0, -5, 0, -2, 0)
        if step >= len(hops):
            return
        try:
            self.icon.coords(self._icon_item, 27, 33 + hops[step])
            self.after(70, self._hop, step + 1)
        except tk.TclError:
            pass

    def _bob(self, k):
        """A busy note's hamster keeps bobbing gently until the work is done."""
        if self._closing:
            return
        try:
            self.icon.coords(self._icon_item, 27, 33 - 3 * abs(math.sin(k / 3)))
            self._bob_job = self.after(60, self._bob, k + 1)
        except tk.TclError:
            pass

    def set_progress(self, done, total):
        """Switch a busy note's bar to "done of total" (a total of 0 keeps it sliding)."""
        if self.bar is None or total <= 0:
            return
        try:
            if str(self.bar.cget("mode")) != "determinate":
                self.bar.stop()
                self.bar.config(mode="determinate")
            self.bar.config(maximum=total, value=min(done, total))
        except tk.TclError:
            pass

    def dismiss(self):
        """Slide out and disappear."""
        if self._closing:
            return
        self._closing = True
        try:
            if self._timer is not None:
                self.after_cancel(self._timer)
            if self._bob_job is not None:
                self.after_cancel(self._bob_job)
            if self.bar is not None:
                self.bar.stop()
            if self._width:
                self._slide(0, 7, out=True)
            else:
                self._gone()
        except tk.TclError:
            pass

    close = dismiss              # what a busy note's owner calls when the work is done

    def _gone(self):
        """Remove the finished note and let the others settle."""
        self.mgr.forget(self)
        try:
            self.destroy()
        except tk.TclError:
            pass


class Toasts:
    """Keeps the notes in the corner of the main window, newest at the bottom."""
    MARGIN, GAP, MAX = 18, 10, 3

    def __init__(self, app):
        """``app`` is the main window; the notes are placed on top of it."""
        self.app = app
        self.live = []
        self._logo = None

    def logo(self):
        """The hamster picture (assets/logo.png, or the default pin icon), loaded once."""
        if self._logo is None:
            self._logo = load_logo(44)
        return self._logo

    def bottom(self):
        """How far above the window's bottom edge the lowest note sits (it clears the
        editor's status bar).
        """
        return self.MARGIN + (34 if getattr(self.app, "screen", "") == "editor" else 0)

    def show(self, event, kind="success", action=None, duration=4600, **fmt):
        """Show a note. ``event`` is a key of MESSAGES (or a plain title; then ``body`` can be
        given). ``action`` is an optional ("Label", function) link. Returns the note.
        """
        if event in MESSAGES:
            title, body = pick(event, **fmt)
        else:
            title, body = event, fmt.get("body", "")
        note = self._add(Toast(self, title, body, kind=kind, action=action))
        note.start(max(duration, 7000) if action else duration)
        return note

    def busy(self, event, **fmt):
        """Show a note that stays until you call its close(). Use set_progress() on it to
        turn its bar into "done of total".
        """
        title, body = pick(event, **fmt) if event in MESSAGES else (event, fmt.get("body", ""))
        note = self._add(Toast(self, title, body, busy=True))
        note.start(None)
        return note

    def _add(self, note):
        """Keep track of a new note; if there are too many, the oldest one leaves."""
        note.update_idletasks()               # measure it, so the others make room right
        self.live.append(note)
        shown = [t for t in self.live if not t.busy and not t._closing]
        while len(shown) > self.MAX:
            shown.pop(0).dismiss()
        self.reflow()
        return note

    def forget(self, note):
        """A note has gone away."""
        if note in self.live:
            self.live.remove(note)
        self.reflow()

    def reflow(self):
        """Stack the notes upwards from the corner."""
        y = self.bottom()
        for note in reversed(self.live):
            try:
                if note.winfo_ismapped() or note._width:
                    note.place_configure(y=-y)
                y += note.winfo_reqheight() + self.GAP
            except tk.TclError:
                pass

    def raise_all(self):
        """Bring the notes in front of anything created after them (after a screen change)."""
        self.reflow()
        for note in self.live:
            try:
                note.lift()
            except tk.TclError:
                pass

    def clear(self):
        """Remove every note at once (the colours are about to change)."""
        for note in list(self.live):
            try:
                note.destroy()
            except tk.TclError:
                pass
        self.live.clear()

    def reset(self):
        """Clear the notes and forget the loaded hamster picture, for a theme change."""
        self.clear()
        self._logo = None
