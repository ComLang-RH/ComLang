"""ComLang session: everything the box *does*, independent of how it is shown or driven.

Words queue -> touch events -> pen samples + Braille cells, the controls (wheel, Repeat, Mode,
Reset, hand-present interlock), the touch cues and the speaker-display state. The device
runtime (comlang.runtime) and the demos run this same class, so behaviour cannot drift apart.

Outputs go to *sinks*: any objects with some of these methods (all optional):
    on_event(kind, data, session)   an event starts with the pen on (controller commands go out here)
    on_pen(x, y, z)                 every planner sample (DT) - simulations only
    on_braille(cells)               the two cells changed (list of dot tuples, [] = all down)
    on_letter(ch, word)             a letter starts (ch) or the output goes quiet (None, None)
    on_abort()                      stop the pen now and forget queued motion
    on_pause(paused)                pause / resume (controller hold / resume)
    on_speed(speed)                 speed changed (controller speed override)
    busy()                          True while a device is still executing what it was sent:
                                    the next event waits, so the host never runs ahead of the pen
    on_control(action)              a box control was used (demo: animate the hand)
    on_changed(session)             transcript / status changed (displays re-render)
    on_message(text)                a status message for the operator / log
"""
import collections

from . import engine as pw
from .protocol import ACTIONS, MODES, MODE_NAME

BRAILLE_ONLY_LETTER_S = 0.8     # how long a letter stays on the cells in Braille-only mode
FLASH_S = 0.5                   # Braille cue: all six dots up on both cells for this long
SPEED_MIN, SPEED_MAX, SPEED_STEP = 0.5, 2.0, 0.1
PALM_S_PER_LETTER = 2.1         # rough palm-writing time per letter at 1x (status estimate)
ALL_DOTS = (1, 2, 3, 4, 5, 6)


class Session:
    def __init__(self, sinks=(), mode="both", speed=1.0, letter_h=pw.LETTER_H, hand_present=True):
        self.sinks = list(sinks)
        self.mode, self.speed, self.letter_h = mode, speed, letter_h
        self.hand_present = hand_present      # False until the hand sensor reports a hand
        self.interlocked = not hand_present   # stopped because the hand left; wheel press resumes
        self.words = collections.deque()      # (transcript index, phrase id) waiting
        self.transcript = []                  # [word, phrase id, state]: queued/current/done/cancelled
        self.phrase_id = 0
        self.partial = ""
        self.events, self.rows, self.row_i = [], [], 0.0
        self.cur_word = None
        self.planner = pw.Planner()
        self.pen = (0.0, 0.0, pw.PEN_LIFT)
        self.paused = not hand_present
        self.wrote_any = False
        self.cues = collections.deque()       # touch cues (mode change, reset) before the next word
        self.letters, self.letter_k = [], 0
        self.letter = None
        self.braille = []
        self.flashing = False
        self.message = ""

    # ---------------- sinks
    def _emit(self, name, *args):
        for s in self.sinks:
            fn = getattr(s, name, None)
            if fn:
                fn(*args)

    def _changed(self):
        self._emit("on_changed", self)

    def say(self, msg):
        self.message = msg
        self._emit("on_message", msg)
        self._changed()

    def _set_braille(self, cells):
        cells = [tuple(c) for c in cells]
        if cells != self.braille:
            self.braille = cells
            self._emit("on_braille", cells)

    def _set_letter(self, ch, word=None):
        self.letter = ch
        self._emit("on_letter", ch, word)

    # ---------------- input
    def add_text(self, text):
        words = [w for w in text.split() if any(c in pw.FONT or c in ".!" for c in w.upper())]
        if not words:
            return
        self.phrase_id += 1
        for w in words:
            self.transcript.append([w, self.phrase_id, "queued"])
            self.words.append((len(self.transcript) - 1, self.phrase_id))
        self._changed()

    def set_partial(self, text):
        if text != self.partial:
            self.partial = text
            self._changed()

    def handle(self, action):
        """A control on the box (see protocol.ACTIONS)."""
        if action not in ACTIONS:
            raise ValueError(action)
        {"faster": lambda: self.nudge_speed(+SPEED_STEP), "slower": lambda: self.nudge_speed(-SPEED_STEP),
         "pause": self.toggle_pause, "repeat": self.repeat, "mode": self.cycle_mode, "reset": self.reset,
         "hand_on": lambda: self.set_hand(True), "hand_off": lambda: self.set_hand(False)}[action]()

    # ---------------- writing engine
    def _start_next_word(self):
        if not self.words:
            return False
        idx, _ = self.words.popleft()
        self.cur_word = idx
        self.transcript[idx][2] = "current"
        word = self.transcript[idx][0]
        ev = pw.word_events(word, last=True, height=self.letter_h)
        if self.wrote_any:                        # word-space cue before every word but the first
            ev = [("tap", " ", 1), ("pause", " ", pw.T_WORD_GAP)] + ev
        self.events = ev
        self.letters = [c for c in word.upper() if c in pw.FONT]
        self.letter_k = 0
        self.wrote_any = True
        self._changed()
        return True

    def _start_next_event(self):
        while not self.events:
            if self.cur_word is not None:
                self.transcript[self.cur_word][2] = "done"
                self.cur_word = None
                self._changed()
            if self.cues:                         # touch cues go before the next word
                self.events.append(self.cues.popleft())
                continue
            if not self._start_next_word():
                return False
        kind, ch, data = self.events.pop(0)
        self.flashing = False
        if kind == "flash":                       # Braille cue: all dots up, `data` times
            self.flashing = True
            n = max(1, int(FLASH_S / pw.DT))
            self.rows = ([self.pen] * n + [None] * (n // 2)) * data
            self.row_i = 0.0
            return True
        if kind == "glyph":
            word = self.transcript[self.cur_word][0].upper()
            prev = self.letters[self.letter_k - 1] if self.letter_k else ""
            self.letter_k += 1
            self._set_letter(ch, word)
            self._set_braille(pw.braille_cells(ch, prev) if self.mode in ("braille", "both") else [])
            self._changed()
        if self.mode in ("palm", "both"):
            self.rows = self.planner.rows(kind, data)
            self._emit("on_event", kind, data, self)
        else:                                     # Braille only: just hold the letter
            dur = {"glyph": BRAILLE_ONLY_LETTER_S, "tap": 0.3}.get(kind, data if kind == "pause" else 0)
            self.rows = [self.pen] * max(1, int(dur / pw.DT))
        self.row_i = 0.0
        return True

    def _busy(self):
        return any(s.busy() for s in self.sinks if hasattr(s, "busy"))

    def tick(self):
        """Advance by one planner sample (DT of real time, scaled by the speed)."""
        if self.paused:
            return
        if self.row_i >= len(self.rows) and self._busy():
            return
        if self.row_i >= len(self.rows) and not self._start_next_event():
            if self.letter is not None and not self.words:
                self._set_letter(None)
                self._set_braille([])
                self._changed()
            return
        row = self.rows[int(self.row_i)]
        self.row_i += self.speed
        if row is None:                           # gap inside a Braille flash cue
            self._set_braille([])
            return
        if self.flashing:
            self._set_braille([ALL_DOTS, ALL_DOTS])
        self.pen = tuple(row)
        self._emit("on_pen", *self.pen)

    def idle(self):
        return not self.words and not self.events and self.cur_word is None and not self.cues and \
            self.row_i >= len(self.rows)

    def _abort_current(self):
        self.events, self.rows, self.row_i = [], [], 0.0
        self.flashing = False
        self.planner = pw.Planner()
        self.pen = (0.0, 0.0, pw.PEN_LIFT)
        self._emit("on_abort")
        self._emit("on_pen", *self.pen)

    def _requeue_current(self):
        """Put the word being written (or the last finished one) back at the front of the queue."""
        if self.cur_word is not None:
            idx = self.cur_word
        else:
            done = [i for i, w in enumerate(self.transcript) if w[2] == "done"]
            if not done:
                return None
            idx = done[-1]
        self._abort_current()
        self.cur_word = None
        self.transcript[idx][2] = "queued"
        self.words.appendleft((idx, self.transcript[idx][1]))
        return idx

    # ---------------- controls
    def toggle_pause(self):
        """Wheel press: pause / resume. After the hand left the box, this is also how writing
        resumes once the hand is back."""
        self._emit("on_control", "pause")
        if not self.hand_present:
            self.say("Hand not on the box: writing stays stopped")
            return
        self.paused = not self.paused
        self.interlocked = False
        self._emit("on_pause", self.paused)
        self.say("Paused" if self.paused else "Resumed")

    def repeat(self):
        """Repeat: write the current word again from the start (or the last finished word)."""
        self._emit("on_control", "repeat")
        idx = self._requeue_current()
        if idx is not None:
            self.say("Repeating %s" % self.transcript[idx][0].upper())

    def nudge_speed(self, d):
        """Thumb wheel roll: away from the palm = faster (+), in = slower (-)."""
        self._emit("on_control", "faster" if d > 0 else "slower")
        self.set_speed(self.speed + d)

    def set_speed(self, v):
        v = round(min(SPEED_MAX, max(SPEED_MIN, v)), 1)
        changed = v != self.speed
        self.speed = v
        if changed:
            self._emit("on_speed", v)
        self.say("Speed %.1fx" % v)

    def _cue(self, palm_taps, flashes, long_press=False):
        """Queue a touch cue the user feels in the current mode: pen taps (or one long press)
        and/or Braille flashes (all dots up)."""
        palm, cells = self.mode in ("palm", "both"), self.mode in ("braille", "both")
        if palm and long_press:
            self.cues.append(("longtap", " ", 0.6))
        elif palm and palm_taps:
            self.cues.append(("tap", " ", palm_taps))
        if cells and flashes:
            self.cues.append(("flash", None, flashes))

    def set_mode(self, mode):
        self.mode = mode
        self._changed()

    def cycle_mode(self):
        """Mode: palm + Braille -> palm only -> Braille only. Confirmed by touch: a 0.6 s pen press
        when the pen is now on, one Braille flash when the cells are on. (One short tap is already
        the word gap, three taps the correction cue.)"""
        self._emit("on_control", "mode")
        self.mode = MODES[(MODES.index(self.mode) + 1) % len(MODES)]
        self._cue(0, 1, long_press=True)
        self.say("Mode: %s" % MODE_NAME[self.mode])

    def reset(self):
        """Speaker's Reset: the output is wrong. Stop, drop the current and queued words (shown
        struck through) and send the correction cue (3 pen taps and/or 2 Braille flashes) so the
        user knows to discard what they just felt."""
        self._emit("on_control", "reset")
        dropped = ([self.cur_word] if self.cur_word is not None else []) + [i for i, _ in self.words]
        self._abort_current()
        for i in dropped:
            self.transcript[i][2] = "cancelled"
        self.words.clear()
        self.cur_word, self.wrote_any, self.letters = None, False, []
        self.cues.clear()
        if self.paused and self.hand_present:
            self.paused = self.interlocked = False
            self._emit("on_pause", False)
        self._cue(3, 2)
        self._set_letter(None)
        self._set_braille([])
        self.say("Reset: %d word(s) dropped, correction cue sent" % len(dropped))

    def set_hand(self, present):
        """Hand-present sensor. The hand leaving stops the pen at once (the current word is put
        back to be written again); writing resumes only when the hand is back AND the user presses
        the wheel, so the pen never starts on a hand that is still settling."""
        if present == self.hand_present:
            return
        self.hand_present = present
        if not present:
            if not self.idle():
                self._requeue_current()
                self.cues.clear()
            if not self.paused:
                self._emit("on_pause", True)
            self.paused = self.interlocked = True
            self._set_letter(None)
            self._set_braille([])
            self.say("Hand removed: stopped")
        else:
            self.say("Hand on the box: press the wheel to start" if self.paused else "Hand on the box")

    def fault(self, what):
        """The controller stopped by itself (e.g. 'stall': the carriage was blocked). It has
        already lifted the pen and holds; the word being written goes back to the front of the
        queue and the session pauses, so the wheel resumes both together."""
        if not self.idle():
            self._requeue_current()
            self.cues.clear()
        self.paused = True
        self._set_letter(None)
        self._set_braille([])
        self.say("Stopped: %s (check nothing blocks the pen, then press the wheel)" % what)

    def skip(self):
        """Operator: drop everything except the newest phrase."""
        if not self.words and self.cur_word is None:
            return
        newest = self.phrase_id
        self._abort_current()
        if self.cur_word is not None:
            self.transcript[self.cur_word][2] = "done"
            self.cur_word = None
        for i, p in self.words:
            if p != newest:
                self.transcript[i][2] = "done"
        self.words = collections.deque((i, p) for i, p in self.words if p == newest)
        self.say("Skipped to the newest phrase")

    def clear(self):
        """Operator: forget everything."""
        self._abort_current()
        self.cues.clear()
        self.words.clear()
        self.transcript.clear()
        self.cur_word, self.wrote_any, self.partial, self.letters = None, False, "", []
        self._set_letter(None)
        self._set_braille([])
        self.say("Cleared")

    # ---------------- state for displays
    def behind_s(self):
        letters = sum(len([c for c in self.transcript[i][0] if c.isalnum()]) for i, _ in self.words)
        per = PALM_S_PER_LETTER if self.mode != "braille" else BRAILLE_ONLY_LETTER_S
        return letters * per / self.speed

    def display_state(self):
        """What the speaker display shows (encoded by protocol.display_lines)."""
        cur = self.cur_word is not None and self.letters
        return {"letters": "".join(self.letters) if cur else "", "k": self.letter_k - 1 if cur else -1,
                "transcript": [(w, s) for w, _, s in self.transcript[-200:]], "partial": self.partial,
                "mode": self.mode, "waiting": len(self.words), "paused": int(self.paused),
                "hand": int(self.hand_present)}
