"""Stand-ins for a missing controller: print what the box would get (bench tests, CI)."""
from .. import engine, protocol


class ConsoleBox:
    """Prints the controller commands (with --dry-run)."""

    def __init__(self, mirror=True):
        self.mirror = mirror

    def on_event(self, kind, data, session):
        for ln in engine.event_commands(kind, data, self.mirror):
            print("box      " + ln)

    def on_braille(self, cells):
        print("box      %s   (%s)" % (protocol.braille_cmd(cells),
                                      "".join(chr(0x2800 + protocol.cell_mask(c)) for c in cells) or "--"))

    def on_abort(self):
        print("box      !")

    def on_pause(self, paused):
        print("box      %s" % ("H" if paused else "R"))

    def on_speed(self, speed):
        print("box      V %d" % round(speed * 100))


class ConsoleLog:
    def on_letter(self, ch, word):
        if ch:
            print("letter   %s  (%s)" % (ch, word))

    def on_message(self, text):
        print("status   " + text)
