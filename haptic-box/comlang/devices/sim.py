"""Simulated box: the controller firmware (firmware/mcu, the same C code as the real board)
built for the PC and run as a process, with a model of the box's hardware.

    board = SimBoard()                     # builds build/mcu-sim/comlang_sim if needed
    mcu = Mcu(board.transport, inbox)      # exactly as with a real board on USB
    board.press("wheel"); board.roll(+1); board.set_hand(False)   # the hardware inputs
    board.pen, board.braille, board.frame()   # the hardware outputs (solenoid, cells, LCD pixels)
"""
import os
import subprocess
import tempfile
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, "firmware", "mcu")
BUILD = os.path.join(ROOT, "build", "mcu-sim")
EXE = os.path.join(BUILD, "comlang_sim")
LCD_W, LCD_H = 480, 320


def build(force=False):
    """(Re)build the simulated firmware when any firmware source is newer than the binary."""
    srcs = [os.path.join(d, f) for d, _, fs in os.walk(SRC) for f in fs]
    if not force and os.path.exists(EXE) and all(os.path.getmtime(s) <= os.path.getmtime(EXE) for s in srcs):
        return EXE
    subprocess.run(["cmake", "-S", SRC, "-B", BUILD, "-DCMAKE_BUILD_TYPE=Release"], check=True,
                   stdout=subprocess.DEVNULL)
    subprocess.run(["cmake", "--build", BUILD], check=True, stdout=subprocess.DEVNULL)
    return EXE


class _PipeTransport:
    def __init__(self, proc):
        self.p, self.name = proc, "simulated board"

    def write(self, data):
        self.p.stdin.write(data)
        self.p.stdin.flush()

    def readline(self):
        return self.p.stdout.readline().decode(errors="replace")

    def close(self):
        try:
            self.p.stdin.close()
        except Exception:
            pass


class SimBoard:
    BUTTONS = ("wheel", "repeat", "mode", "reset")
    COUNTS_PER_DETENT = 4

    def __init__(self, on_output=None):
        exe = build()
        self.on_output = on_output       # callback(kind) for 'pen' / 'br' / 'fb' (any thread)
        self.pen, self.braille, self.hand = 0, (0, 0), True
        self.events = []                 # (time, kind, value) of every actuator change
        self.fb_path = os.path.join(tempfile.mkdtemp(prefix="comlang_sim_"), "lcd.raw")
        self.fb_version = 0
        hw_in_r, self.hw_in = os.pipe()
        self.hw_out, hw_out_w = os.pipe()
        self.proc = subprocess.Popen([exe, "--hw-in", str(hw_in_r), "--hw-out", str(hw_out_w),
                                      "--fb", self.fb_path], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     pass_fds=(hw_in_r, hw_out_w))
        os.close(hw_in_r)
        os.close(hw_out_w)
        self.transport = _PipeTransport(self.proc)
        threading.Thread(target=self._outputs, daemon=True).start()

    # ---- hardware inputs
    def _hw(self, line):
        try:
            os.write(self.hw_in, (line + "\n").encode())
        except OSError:
            pass

    def press(self, button, hold_s=0.05):
        """Press and release a button (held long enough for the firmware's debounce)."""
        self._hw("btn %s 1" % button)
        threading.Timer(hold_s, self._hw, args=("btn %s 0" % button,)).start()

    def roll(self, detents):
        """Roll the thumb wheel: + = away from the palm."""
        self._hw("enc %d" % (detents * self.COUNTS_PER_DETENT))

    def set_hand(self, present):
        self.hand = bool(present)
        self._hw("hand %d" % int(present))

    def jam(self, blocked=True):
        """Something (a finger, an object) blocks the carriage."""
        self._hw("jam %d" % int(blocked))

    # ---- hardware outputs
    def _outputs(self):
        buf = b""
        while True:
            try:
                chunk = os.read(self.hw_out, 4096)
            except OSError:
                return
            if not chunk:
                return
            buf += chunk
            *lines, buf = buf.split(b"\n")
            for ln in lines:
                p = ln.decode().split()
                if not p:
                    continue
                t = time.monotonic()
                if p[0] == "pen":
                    self.pen = int(p[1])
                    self.events.append((t, "pen", self.pen))
                elif p[0] == "br":
                    self.braille = (int(p[1]), int(p[2]))
                    self.events.append((t, "br", self.braille))
                elif p[0] == "fb":
                    self.fb_version += 1
                if self.on_output:
                    self.on_output(p[0])

    def frame(self):
        """The LCD as the firmware drew it: bytes, RGB565 little-endian, 480 x 320 (or None)."""
        try:
            with open(self.fb_path, "rb") as f:
                data = f.read()
            return data if len(data) == LCD_W * LCD_H * 2 else None
        except OSError:
            return None

    def close(self):
        self._hw("quit")
        self.transport.close()
        try:
            self.proc.wait(timeout=2)
        except Exception:
            self.proc.kill()
