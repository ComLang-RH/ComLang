"""Keeps the demos, the device software and the firmware in sync. Run from haptic-box/:

    python3 tests/test_sync.py          (or: python3 -m pytest tests)

Fails when the demo app, the device runtime, the controller firmware (firmware/mcu) and
DESIGN.md stop describing the same box. The full-stack test runs the real firmware (built for the
PC) against the simulated hardware and checks what the actuators did.
"""
import ast
import contextlib
import io
import math
import os
import queue
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from comlang import engine, protocol                               # noqa: E402
from comlang.session import Session                                # noqa: E402


def src(rel):
    return open(os.path.join(ROOT, rel), encoding="utf-8").read()


class Recorder:
    """Session sink that records everything the controller would receive."""

    def __init__(self):
        self.log = []

    def on_event(self, kind, data, s):
        self.log += [("cmd", ln) for ln in engine.event_commands(kind, data, True)]

    def on_braille(self, cells):
        self.log.append(("cmd", protocol.braille_cmd(cells)))

    def on_abort(self):
        self.log.append(("abort",))

    def on_pause(self, p):
        self.log.append(("pause", p))

    def on_speed(self, v):
        self.log.append(("speed", v))

    def on_changed(self, s):
        for ln in protocol.display_lines(s.display_state()):
            if not self.log or self.log[-1] != ("display", ln):
                self.log.append(("display", ln))


SCRIPT = [("text", "hello there"), ("tick", 400), ("action", "faster"), ("tick", 300),
          ("action", "repeat"), ("tick", 200), ("action", "mode"), ("tick", 900),
          ("action", "reset"), ("tick", 300), ("text", "ok 2"), ("action", "hand_off"), ("tick", 100),
          ("action", "hand_on"), ("action", "pause"), ("tick", 1500), ("action", "mode"), ("tick", 800)]


def run_script(s, tick):
    for op, arg in SCRIPT:
        if op == "text":
            s.add_text(arg)
        elif op == "action":
            s.handle(arg)
        else:
            for _ in range(arg):
                tick()


# ---------------------------------------------------------------- one behaviour
def test_demo_and_runtime_use_the_session_and_the_firmware():
    demo, rt = src("demos/haptic_app.py"), src("comlang/runtime.py")
    assert "Session(" in demo and "Session(" in rt
    assert "Mcu(" in demo and "Mcu(" in rt, "both must talk to the controller over the protocol"
    assert "SimBoard(" in demo, "the demo must run against the simulated firmware"
    for name in ("word_events", "braille_cells(", "Planner(", "event_commands(", ".cues", ".words.append",
                 "on_pen"):
        assert name not in demo, "demo re-implements device behaviour (%s): move it to comlang/" % name
    assert 'command=lambda: self.box("reset")' in demo, "box controls must go through the (simulated) box"


def test_demo_app_behaves_like_the_runtime():
    """Drive the real demo App (Tk, without a board) and a bare runtime Session with the same script
    and compare every command, Braille and display message the controller would receive."""
    try:
        import tkinter as tk
        root = tk.Tk()
    except Exception as e:                # no display: covered by the structural test above
        print("  (skipped: no display: %s)" % e)
        return
    root.withdraw()
    os.environ["COMLANG_BOARD"] = "none"
    sys.path.insert(0, os.path.join(ROOT, "demos"))
    import haptic_app
    haptic_app.cad_render = None          # no 3D needed
    app = haptic_app.App(root)
    a = Recorder()
    app.s.sinks.append(a)
    run_script(app.s, app.s.tick)
    root.destroy()

    b = Recorder()
    s = Session([b])
    run_script(s, s.tick)
    assert a.log == b.log, "demo and runtime diverge at %d" % next(
        i for i, (x, y) in enumerate(zip(a.log + [None], b.log + [None])) if x != y)
    assert any(x[0] == "cmd" and x[1].startswith("m ") for x in b.log)


def test_runtime_dry_run_matches_session():
    from comlang import runtime
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        runtime.main(["--dry-run", "--fast", "--text", "hi 2."])
    got = [ln[9:].split("   (")[0] for ln in out.getvalue().splitlines() if ln.startswith("box      ")]
    r = Recorder()
    s = Session([r])
    s.add_text("hi 2.")
    while not s.idle():
        s.tick()
    assert got == [x[1] for x in r.log if x[0] == "cmd"]


# ---------------------------------------------------------------- behaviour the docs promise
def test_cues_and_interlock():
    r = Recorder()
    s = Session([r])
    s.add_text("abc")
    for _ in range(100):
        s.tick()
    s.handle("reset")
    n = len(r.log)
    while not s.idle():
        s.tick()
    cue = r.log[n:]
    assert cue.count(("cmd", "p 1")) == 3, "reset = 3 pen taps"
    assert cue.count(("cmd", "b 63 63")) == 2, "reset = 2 Braille flashes"
    s.add_text("xyz")
    for _ in range(50):
        s.tick()
    s.handle("hand_off")
    assert s.paused and ("abort",) in r.log and s.words, "hand off stops and keeps the word"
    s.handle("pause")
    assert s.paused, "no restart without the hand"
    s.handle("hand_on")
    assert s.paused, "hand back alone does not restart"
    s.handle("pause")
    assert not s.paused


def test_braille_only_moves_nothing():
    r = Recorder()
    s = Session([r], mode="braille")
    s.add_text("abc")
    while not s.idle():
        s.tick()
    cmds = [x[1] for x in r.log if x[0] == "cmd"]
    assert cmds and all(c.startswith("b ") for c in cmds)


# ---------------------------------------------------------------- protocol
def test_display_protocol_roundtrip():
    s = Session()
    s.add_text("hello brave new world")
    for _ in range(700):
        s.tick()
    s.handle("reset")
    s.add_text("again")
    s.set_partial("still talk")
    for _ in range(300):
        s.tick()
    st = s.display_state()
    back = protocol.parse_display(protocol.display_lines(st))
    want = dict(st, transcript=[(w.upper(), x) for w, x in st["transcript"][-protocol.TRANSCRIPT_WORDS:]])
    assert back == want
    for a in protocol.ACTIONS:
        assert protocol.parse_event(protocol.event_line(a)) == a
    assert protocol.braille_cmd([(1, 2), (3, 4, 5, 6)]) == "b 3 60"
    st = protocol.parse_status("A 150 -2250 1 0 1 1 1 4 3 0")
    assert st["x"] == 1.5 and st["y"] == -22.5 and st["pen"] == 1 and st["b1"] == 3


# ---------------------------------------------------------------- firmware
def test_firmware_tables_generated_from_python():
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "gen_firmware_tables.py"), "--check"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_firmware_handles_every_action_and_command():
    controls = src("firmware/mcu/src/controls.c")
    for a in protocol.ACTIONS:
        assert "ACT_%s" % a.upper() in controls, "firmware never reports %r" % a
    link = src("firmware/mcu/src/link.c")
    doc = src("comlang/protocol.py").split('"""')[1].split("Box -> host:")[0]
    host_cmds = set(re.findall(r"^    ([a-zA-Z!?])[ /\n]", doc, re.M)) | {"R", "T", "P", "S"}
    for c in host_cmds:
        assert "'%s'" % c in link, "firmware link does not handle %r" % c
    cfg = src("firmware/mcu/src/config.h")
    travel = float(re.search(r"TRAVEL_MM\s+([\d.]+)", cfg).group(1))
    centre = float(re.search(r"PALM_CENTRE_MM\s+([\d.]+)", cfg).group(1))
    assert centre - engine.WORKSPACE / 2 >= 0 and centre + engine.WORKSPACE / 2 <= travel, \
        "the writing area does not fit the machine travel"


def test_full_stack_on_simulated_firmware():
    """Session -> protocol -> C firmware -> simulated hardware, and the box's controls back."""
    from comlang.devices.mcu import Mcu
    from comlang.devices.sim import SimBoard, build
    try:
        build()
    except Exception as e:
        raise AssertionError("simulated firmware does not build: %s" % e)
    board = SimBoard()
    inbox = queue.Queue()
    errors = []
    mcu = Mcu(board.transport, inbox, log=errors.append)
    sent = Recorder()
    s = Session([mcu, sent])

    def run(seconds, until=None):
        t_end = time.monotonic() + seconds
        while time.monotonic() < t_end:
            while not inbox.empty():
                kind, val = inbox.get()
                s.fault(val) if kind == "fault" else s.handle(val)
            s.tick()
            time.sleep(engine.DT)
            if until and until():
                return True
        return False

    try:
        assert mcu.wait_homed(), "firmware did not home"
        s.add_text("hi")
        assert run(20, lambda: s.idle() and not mcu.busy()), "did not finish writing"
        cmds = [x[1] for x in sent.log if x[0] == "cmd"]
        pulls = [e for e in board.events if e[1] == "pen" and e[2] == 1000]
        assert len(pulls) == cmds.count("p 1"), "solenoid pull-ins %d != pen commands %d" % (
            len(pulls), cmds.count("p 1"))
        hw_br = [list(e[2]) for e in board.events if e[1] == "br"]
        want_br = [[int(v) for v in c.split()[1:]] for c in cmds if c.startswith("b ")]
        assert hw_br == [b for i, b in enumerate(want_br) if i == 0 or b != want_br[i - 1]], (hw_br, want_br)
        mcu.status_evt.clear()
        mcu.request_status()
        mcu.status_evt.wait(1)
        last = [c for c in cmds if c.startswith("m ")][-1].split()
        assert abs(mcu.status["x"] - int(last[1]) / 100) < 0.02 and abs(mcu.status["y"] - int(last[2]) / 100) < 0.02
        frame = board.frame()
        assert frame and any(frame[i:i + 2] != b"\0\0" for i in range(0, len(frame), 997)), "LCD never drawn"

        # controls on the box -> firmware -> session
        board.roll(+1)
        assert run(1, lambda: s.speed > 1.0), "wheel roll not reported"
        n = len(board.events)
        board.press("reset")
        run(4)
        cue = board.events[n:]
        assert sum(1 for e in cue if e[1] == "pen" and e[2] == 1000) == 3, "reset cue: 3 taps on the hardware"
        assert sum(1 for e in cue if e[1] == "br" and e[2] == (63, 63)) == 2, "reset cue: 2 flashes"

        # hand removed mid-word: firmware stops the pen itself; only hand + wheel restarts
        s.add_text("mmm")
        run(1.5)
        board.set_hand(False)
        run(0.6)
        assert board.pen == 0 and s.paused and s.words, "hand off must stop and keep the word"
        k = len(board.events)
        board.press("wheel")
        run(0.8)
        assert s.paused and not [e for e in board.events[k:] if e[1] == "pen" and e[2]], "moved without a hand"
        board.set_hand(True)
        run(0.6)
        board.press("wheel")
        assert run(20, lambda: s.idle() and not mcu.busy()), "did not resume after hand + wheel"

        # carriage blocked mid-word -> firmware stall -> session pauses and keeps the word
        s.add_text("www")
        run(1.2)
        board.jam(True)
        run(0.6)
        assert s.paused and s.words and board.pen == 0, "stall must pause the session and keep the word"
        board.jam(False)
        board.press("wheel")
        assert run(25, lambda: s.idle() and not mcu.busy()), "did not resume after a stall"
        assert all("ready" in e or "stall" in e for e in errors), errors
    finally:
        mcu.close()
        board.close()


def test_firmware_safety_without_the_host():
    """The safety rules must hold in the firmware ALONE: the host queues a long word and then
    goes silent (hung), so only the controller can react to the hand, the wheel and Reset."""
    from comlang.devices.mcu import Mcu
    from comlang.devices.sim import SimBoard
    board = SimBoard()
    mcu = Mcu(board.transport, queue.Queue(), log=lambda m: None)   # nobody reads the events

    def status():
        mcu.status_evt.clear()
        mcu.request_status()
        assert mcu.status_evt.wait(1)
        return dict(mcu.status)

    def word():
        for ch in "MMMMMMMM":
            mcu._queue(engine.event_commands("glyph", engine.glyph_mm(ch)))

    try:
        assert mcu.wait_homed()
        # hand removed while writing -> stop, pen off, queue dropped, no restart by the wheel alone
        word()
        time.sleep(1.0)
        board.set_hand(False)
        time.sleep(0.5)
        a = status()
        assert board.pen == 0 and a["depth"] == 0 and not a["armed"], "hand off: firmware must stop by itself"
        word()                                     # host keeps sending (it is hung)
        board.press("wheel")
        time.sleep(0.6)
        b = status()
        assert math.dist((b["x"], b["y"]), (a["x"], a["y"])) < 0.1 and board.pen == 0, "moved without a hand"
        # hand back + wheel -> runs again
        board.set_hand(True)
        time.sleep(0.4)
        board.press("wheel")
        time.sleep(0.6)
        assert math.dist((status()["x"], status()["y"]), (b["x"], b["y"])) > 0.5, "hand + wheel must resume"
        # something blocks the carriage -> stall: stop, pen off, motors released, held
        word()
        time.sleep(0.5)
        board.jam(True)
        time.sleep(0.4)
        j = status()
        assert j["hold"] and j["depth"] == 0 and board.pen == 0, "a blocked carriage must stop by itself"
        board.jam(False)
        board.press("wheel")                       # resumes after a stall
        time.sleep(0.3)
        assert not status()["hold"], "wheel must resume after a stall"
        # wheel press -> local hold: the carriage stops and the pen lifts
        board.press("wheel")
        time.sleep(0.3)
        c = status()
        time.sleep(0.3)
        d = status()
        assert c["hold"] and math.dist((c["x"], c["y"]), (d["x"], d["y"])) < 0.1 and board.pen == 0, \
            "wheel must hold locally"
        board.press("wheel")
        time.sleep(0.3)
        # Reset button -> stop now, queue dropped
        board.press("reset")
        time.sleep(0.3)
        e = status()
        assert e["depth"] == 0 and board.pen == 0, "Reset must stop the pen locally"
    finally:
        mcu.close()
        board.close()


# ---------------------------------------------------------------- docs
def test_design_doc_paths_exist():
    doc = src("DESIGN.md")
    paths = set(re.findall(r"`((?:comlang|demos|firmware|tests|tools)/[\w./-]+)`", doc))
    assert paths, "DESIGN.md should name the code it describes"
    missing = [p for p in paths if not os.path.exists(os.path.join(ROOT, p))]
    assert not missing, "DESIGN.md names missing files: %s" % missing
    for a in protocol.ACTIONS:
        assert a in doc, "DESIGN.md does not mention action %r" % a
    for stale in ("GRBL", "CircuitPython", "grbl_settings", "Arduino"):
        assert stale not in doc.split("## Appendix A")[0], "DESIGN.md still describes %s" % stale


if __name__ == "__main__":
    fails = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            try:
                fn()
                print("ok    ", name)
            except Exception as e:
                fails += 1
                print("FAIL  ", name, "-", type(e).__name__, e)
    print("SYNC OK" if not fails else "%d FAILED" % fails)
    sys.exit(1 if fails else 0)
