"""ComLang device runtime: the program that runs the box (laptop for MVP-1, Raspberry Pi 5 later).
No GUI. Speech (or typed lines) -> Session -> box controller (firmware/mcu: gantry, pen, controls,
speaker display, Braille cells), on USB or simulated.

    python -m comlang --list-ports
    python -m comlang --board auto --listen                 # the real box, speech in
    python -m comlang --board sim --text "hello there"      # the simulated box (same firmware)
    python -m comlang --dry-run --text "hello there"        # no controller: print the commands

Typed lines on stdin are written like speech; lines starting with '/' are operator commands:
/pause /repeat /faster /slower /mode /reset /skip /clear /hand_on /hand_off /quit
and for calibration (DESIGN.md §9):  /home  /goto X Y  /pen 0|1  /centre X Y  /where
"""
import argparse
import queue
import sys
import threading
import time

from . import engine, protocol
from .devices import serial_ports
from .session import Session

OPERATOR = {"skip", "clear", "quit"}
CALIBRATION = {"home", "goto", "pen", "centre", "where"}


def calibrate(mcu, words, log):
    """Calibration commands: /home, /goto X Y (mm from the palm centre), /pen 0|1,
    /centre X Y (palm centre in machine mm), /where (current position)."""
    cmd, args = words[0], [float(v) for v in words[1:]]
    if cmd == "home":
        mcu.home()
    elif cmd == "goto" and len(args) == 2:
        mcu.goto(*args)
    elif cmd == "pen" and len(args) == 1:
        mcu.pen(args[0])
    elif cmd == "centre" and len(args) == 2:
        mcu.set_centre(*args)
        log("Palm centre set to %.2f %.2f mm: start future runs with --palm-centre %.2f %.2f" % (args * 2))
    elif cmd == "where":
        mcu.status_evt.clear()
        mcu.request_status()
        if mcu.status_evt.wait(1) and mcu.status:
            log("pen at %(x).2f %(y).2f mm from the palm centre (pen %(pen)d, homed %(homed)d)" % mcu.status)
    else:
        log("usage: /home | /goto X Y | /pen 0|1 | /centre X Y | /where")


def _stdin(inbox):
    for ln in sys.stdin:
        ln = ln.strip()
        if ln.startswith("/"):
            inbox.put(("command", ln[1:].lower()))
        elif ln:
            inbox.put(("final", ln))
    inbox.put(("eof", ""))


def find_board():
    """The first port that looks like the box controller (RP2040 USB CDC)."""
    ports = serial_ports()
    for dev, desc in ports:
        if any(k in desc for k in ("Pico", "RP2040", "ComLang")):
            return dev
    acm = [d for d, _ in ports if "ACM" in d]
    return acm[0] if acm else None


def connect(args, inbox, log):
    """Open the controller. Returns (mcu or None, closers)."""
    if not args.board:
        return None, []
    from .devices.mcu import Mcu, SerialTransport
    closers = []
    if args.board == "sim":
        from .devices.sim import SimBoard
        board = SimBoard()
        transport = board.transport
        closers.append(board.close)
    else:
        port = find_board() if args.board == "auto" else args.board
        if not port:
            sys.exit("No box controller found (try --list-ports, or --board sim)")
        transport = SerialTransport(port)
    mcu = Mcu(transport, inbox, log, mirror=not args.no_mirror, hand_sensor=not args.no_hand_sensor,
              palm_centre=args.palm_centre)
    closers.insert(0, mcu.close)
    if not mcu.wait_homed():
        log("controller did not home (check the switches)")
    log("Box controller: %s" % transport.name)
    return mcu, closers


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m comlang", description=__doc__.split("\n")[0])
    ap.add_argument("--board", metavar="PORT", help="controller serial port, 'auto', or 'sim'")
    ap.add_argument("--listen", nargs="?", const="en-us", metavar="MODEL",
                    help="speech input: Vosk language code (default en-us) or model folder")
    ap.add_argument("--text", help="write this text, then exit when done (bench test)")
    ap.add_argument("--mode", choices=protocol.MODES, default="both")
    ap.add_argument("--speed", type=float, default=1.0)
    ap.add_argument("--letter-mm", type=float, default=engine.LETTER_H)
    ap.add_argument("--palm-centre", type=float, nargs=2, metavar=("X", "Y"),
                    help="calibrated palm centre in machine mm (default: firmware 37.5 37.5)")
    ap.add_argument("--no-mirror", action="store_true", help="do not flip x (only for a palm-up rig)")
    ap.add_argument("--no-hand-sensor", action="store_true", help="bench only: no hand-present pad")
    ap.add_argument("--dry-run", action="store_true", help="no controller: print the commands")
    ap.add_argument("--fast", action="store_true", help="with --dry-run: do not wait in real time")
    ap.add_argument("--list-ports", action="store_true")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)

    if args.list_ports:
        for dev, desc in serial_ports() or [("(none, or pyserial missing)", "")]:
            print("%-16s %s" % (dev, desc))
        return 0

    inbox = queue.Queue()

    def log(msg):
        print(time.strftime("%H:%M:%S"), msg, file=sys.stderr, flush=True)

    from .devices import console
    sinks = [console.ConsoleLog()] if args.verbose or args.dry_run else []
    if args.dry_run:
        sinks.append(console.ConsoleBox(not args.no_mirror))
    mcu, closers = connect(args, inbox, log)
    hand = True
    if mcu:
        sinks.append(mcu)
        if mcu.status and not args.no_hand_sensor:
            hand = bool(mcu.status["hand"])
    s = Session(sinks, mode=args.mode, letter_h=args.letter_mm, hand_present=hand)
    if args.speed != 1.0:
        s.set_speed(args.speed)
    listener = None
    if args.listen:
        from .speech import Listener
        listener = Listener(args.listen, inbox)
        listener.start()
    if args.text:
        s.add_text(args.text)
    else:
        threading.Thread(target=_stdin, args=(inbox,), daemon=True).start()
    s.say("ComLang ready (%s%s)" % (protocol.MODE_NAME[s.mode],
                                    "" if hand else ", put the hand on the box and press the wheel"))

    t_next, eof = time.monotonic(), False
    try:
        while True:
            while True:
                try:
                    kind, val = inbox.get_nowait()
                except queue.Empty:
                    break
                if kind == "final":
                    s.set_partial("")
                    s.add_text(val)
                elif kind == "partial":
                    s.set_partial(val)
                elif kind in ("action", "command"):
                    if val == "quit":
                        return 0
                    if val.split() and val.split()[0] in CALIBRATION:
                        if mcu:
                            calibrate(mcu, val.split(), log)
                        else:
                            log("calibration needs a controller (--board)")
                    elif val in protocol.ACTIONS:
                        s.handle(val)
                    elif val in OPERATOR:
                        getattr(s, val)()
                    else:
                        log("unknown command /%s" % val)
                elif kind == "fault":
                    s.fault(val)
                elif kind in ("status", "error"):
                    log(val)
                elif kind == "eof":
                    eof = True
            s.tick()
            if (args.text or (eof and not listener)) and s.idle() and not s._busy():
                return 0
            if not (args.dry_run and args.fast and not mcu):
                t_next += engine.DT
                time.sleep(max(0.0, t_next - time.monotonic()))
    except KeyboardInterrupt:
        return 0
    finally:
        if listener:
            listener.stop()
        for c in closers:
            c()
