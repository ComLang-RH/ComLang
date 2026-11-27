"""ComLang host software: the code that runs the real box (and that every demo is built on).

    engine    text -> strokes, Braille cells, timed path, G-code
    session   queue, controls, cues, interlock, display state (one behaviour for device and demos)
    protocol  Pico <-> host messages, control actions, modes
    speech    offline speech-to-text (Vosk)
    devices   the box controller (real board on USB, or the simulated board), console stand-ins
    runtime   headless program for the box:  python -m comlang --help
"""
