"""The box controller (firmware/mcu): one link for the gantry, pen, controls, speaker display and
Braille cells. Works the same with the real board (USB serial) and the simulated board (the
firmware built for the PC, comlang.devices.sim): only the transport differs.

As a Session sink it turns events into queued controller commands (engine.event_commands),
Braille into queued 'b' commands (so the cells change exactly when the pen reaches the letter),
pause / speed / abort into immediate commands, and mirrors the display. Its reader thread posts
('action', name) to `inbox` for every control on the box, and keeps the latest status ('A').
"""
import threading

from .. import engine, protocol


class SerialTransport:
    def __init__(self, port):
        import serial                    # pyserial
        self.ser = serial.Serial(port, 115200, timeout=0.2)
        self.name = port

    def write(self, data):
        self.ser.write(data)

    def readline(self):
        return self.ser.readline().decode(errors="replace")

    def close(self):
        self.ser.close()


class Mcu:
    def __init__(self, transport, inbox, log=print, mirror=True, hand_sensor=True, palm_centre=None,
                 home=True):
        self.t, self.inbox, self.log, self.mirror = transport, inbox, log, mirror
        self.sent = 0                    # queued commands sent
        self.executed = 0                # ... reported finished by the controller ('X')
        self.status = None               # latest 'A' report as a dict
        self.status_evt = threading.Event()
        self.lines = {}                  # last display line per tag (only changes go out)
        self.lock = threading.Lock()
        self.alive = True
        threading.Thread(target=self._read, daemon=True).start()
        self._send(["C hand_sensor %d" % int(hand_sensor)])
        if palm_centre:
            self._send(["O %d %d" % (round(palm_centre[0] * 100), round(palm_centre[1] * 100))])
        if home:
            self._send(["G"])

    # ---- Session sink
    def on_event(self, kind, data, session):
        self._queue(engine.event_commands(kind, data, self.mirror))

    def on_braille(self, cells):
        self._queue([protocol.braille_cmd(cells)])

    def on_abort(self):
        self._send(["!"])

    def on_pause(self, paused):
        self._send(["H" if paused else "R"])

    def on_speed(self, speed):
        self._send(["V %d" % round(speed * 100)])

    def on_changed(self, session):
        out = [ln for ln in protocol.display_lines(session.display_state()) if self.lines.get(ln[0]) != ln]
        for ln in out:
            self.lines[ln[0]] = ln
        self._send(out)

    def busy(self):
        return self.executed < self.sent

    # ---- link
    def _queue(self, cmds):
        with self.lock:
            self.sent += len(cmds)
        self._send(cmds)

    def _send(self, lines):
        if not lines:
            return
        with self.lock:
            try:
                self.t.write("".join(ln + "\n" for ln in lines).encode())
            except Exception as e:
                self.log("controller: %s" % e)

    # ---- calibration (DESIGN.md §9)
    def home(self):
        self._send(["G"])

    def goto(self, x, y, v=50):
        """Pen-up move to (x, y) mm from the palm centre (palm coordinates, mirrored like writing)."""
        sx = -1 if self.mirror else 1
        self._queue(["m %d %d %d" % (round(sx * x * 100), round(y * 100), v)])

    def pen(self, on):
        self._queue(["p %d" % int(bool(on))])

    def set_centre(self, x, y):
        """Palm centre in machine mm (from the switches), i.e. the work zero."""
        self._send(["O %d %d" % (round(x * 100), round(y * 100))])

    def request_status(self):
        self._send(["?"])

    def _read(self):
        while self.alive:
            try:
                ln = self.t.readline()
            except Exception as e:
                if self.alive:
                    self.log("controller: %s" % e)
                return
            if not ln:
                continue
            ln = ln.strip()
            if ln.startswith("X "):
                self.executed = int(ln[2:])
            elif ln.startswith("A "):
                self.status = protocol.parse_status(ln)
                self.status_evt.set()
            elif ln.startswith("E "):
                a = protocol.parse_event(ln)
                if a:
                    self.inbox.put(("action", a))
            elif ln.startswith("err"):
                fault = ln[4:].strip()
                if fault in protocol.FAULTS:
                    self.inbox.put(("fault", fault))
                self.log("controller %s" % ln)
            elif ln.startswith("#"):
                self.log("controller: %s" % ln[1:].strip())

    def wait_homed(self, timeout=10.0):
        """Block until the controller reports it is homed (status polling)."""
        import time
        t_end = time.monotonic() + timeout
        while time.monotonic() < t_end:
            self.status_evt.clear()
            self.request_status()
            self.status_evt.wait(0.3)
            if self.status and self.status["homed"]:
                return True
            time.sleep(0.1)
        return False

    def close(self):
        self._send(["!"])
        self.alive = False
        try:
            self.t.close()
        except Exception:
            pass
