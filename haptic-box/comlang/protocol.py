"""ComLang link between the host (laptop / Raspberry Pi) and the box's controller (RP2040 running
firmware/mcu). USB CDC serial, one ASCII line per message. ONE definition: the firmware's
tables are generated from this file (tools/gen_firmware_tables.py) and tests/test_sync.py checks
both ends.

Host -> box, QUEUED (executed in order, in step with the pen; x, y in 0.01 mm from the palm centre):
    m <x> <y> <v>       move in a straight line at v mm/s (trapezoidal, firmware acceleration)
    p <0|1>             pen solenoid off / on (pull-in, then hold current)
    d <ms>              dwell (scaled by the speed override)
    b <mask> <mask>     the two Braille cells, 6-bit masks (bit 0 = dot 1)
Host -> box, IMMEDIATE:
    !                   stop now: drop the queue, pen off
    H / R               hold (decelerate, lift the pen) / resume (pen back down, continue)
    V <percent>         speed override for moves and dwells
    G                   home both axes (switches at X-/Y-)
    O <x> <y>           palm centre in machine coordinates (0.01 mm), from calibration
    C <key> <value>     config: hand_sensor 0|1
    ?                   status request -> A ...
    W/T/P/S ...         speaker display content (see display_lines)
Box -> host:
    E <action>          a control (ACTIONS); pause, reset and hand_off already acted on locally
    X <n>               total queued commands finished (or dropped); host busy while n < sent
    A <x> <y> <pen> <hold> <armed> <hand> <homed> <depth> <b1> <b2>   status (x, y in 0.01 mm,
                        measured by the motor encoders)
    err stall           the carriage was blocked: the controller stopped, lifted the pen, released
                        the motors and holds; the wheel resumes (FAULTS)
    err <text> / # <text>   other error / log

Speaker display content, host -> box:
    W <letters> <k>             word being written, index of the current letter (-1 = none)
    T <transcript>              recent words; prefix * current, + waiting, ~ cancelled (struck)
    P <partial>                 speech not yet final (greyed); empty = none
    S <mode>|<waiting>|<paused>|<hand>     mode in MODES, waiting words, 0/1, hand present 0/1
"""

# controls on the box -> what the session does (Session.handle)
ACTIONS = ("faster", "slower", "pause", "repeat", "mode", "reset", "hand_on", "hand_off")

# keysym -> action for the demo app (keypad and '=' too, for '+' without shift)
DEMO_KEYS = {"plus": "faster", "equal": "faster", "KP_Add": "faster", "minus": "slower",
             "KP_Subtract": "slower", "space": "pause", "r": "repeat", "m": "mode", "Escape": "reset"}

FAULTS = ("stall",)                                 # 'err <fault>' the session must react to

MODES = ("both", "palm", "braille")                 # the Mode button cycles through these
MODE_NAME = {"both": "palm + Braille", "palm": "palm only", "braille": "Braille only"}

TRANSCRIPT_WORDS = 60                               # words of history sent to the display
_PREFIX = {"current": "*", "queued": "+", "cancelled": "~", "done": ""}
_STATE = {v: k for k, v in _PREFIX.items() if v}


def event_line(action):
    if action not in ACTIONS:
        raise ValueError(action)
    return "E %s" % action


def parse_event(line):
    """'E faster' -> 'faster'; anything else -> None."""
    p = line.strip().split(" ", 1)
    return p[1] if len(p) == 2 and p[0] == "E" and p[1] in ACTIONS else None


def cell_mask(dots):
    return sum(1 << (d - 1) for d in dots)


def mask_dots(mask):
    return tuple(d for d in range(1, 7) if mask >> (d - 1) & 1)


def braille_cmd(cells):
    """Two cells (lists of dot numbers; missing = blank) -> queued 'b m1 m2'."""
    m = [cell_mask(cells[k]) if k < len(cells) else 0 for k in range(2)]
    return "b %d %d" % tuple(m)


STATUS_FIELDS = ("x", "y", "pen", "hold", "armed", "hand", "homed", "depth", "b1", "b2")


def parse_status(line):
    """'A ...' -> dict (x, y in mm), or None."""
    p = line.split()
    if len(p) != 1 + len(STATUS_FIELDS) or p[0] != "A":
        return None
    d = dict(zip(STATUS_FIELDS, (int(v) for v in p[1:])))
    d["x"], d["y"] = d["x"] / 100.0, d["y"] / 100.0
    return d


def display_lines(st):
    """Session.display_state() -> the display messages (W, T, P, S)."""
    words = " ".join(_PREFIX[s] + w.upper() for w, s in st["transcript"][-TRANSCRIPT_WORDS:])
    return ["W %s %d" % (st["letters"] or "-", st["k"]),
            "T %s" % words,
            "P %s" % st["partial"],
            "S %s|%d|%d|%d" % (st["mode"], st["waiting"], st["paused"], st["hand"])]


def parse_display(lines, st=None):
    """Display messages -> display state (inverse of display_lines). Unknown lines are ignored,
    so the Pico firmware and the demo's speaker window can share this logic."""
    st = dict(st or {"letters": "", "k": -1, "transcript": [], "partial": "", "mode": "both",
                     "waiting": 0, "paused": 0, "hand": 1})
    for ln in lines:
        tag, _, body = ln.rstrip("\n").partition(" ")
        if tag == "W":
            letters, _, k = body.rpartition(" ")
            st["letters"], st["k"] = ("" if letters == "-" else letters), int(k)
        elif tag == "T":
            st["transcript"] = [(w[1:], _STATE[w[0]]) if w[0] in _STATE else (w, "done")
                                for w in body.split()]
        elif tag == "P":
            st["partial"] = body
        elif tag == "S":
            m, w, p, h = body.split("|")
            st.update(mode=m, waiting=int(w), paused=int(p), hand=int(h))
    return st
