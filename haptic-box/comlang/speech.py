"""Offline speech-to-text: microphone -> Vosk -> final phrases (partials shown, never written)."""
import os
import queue
import threading


class Listener(threading.Thread):
    """Mic -> Vosk. Posts ('status'|'error'|'partial'|'final', text) to `out` (a queue)."""

    def __init__(self, model, out):
        super().__init__(daemon=True)
        self.model, self.out, self.stop_evt = model, out, threading.Event()

    def run(self):
        try:
            import json
            import sounddevice as sd
            from vosk import Model, KaldiRecognizer, SetLogLevel
        except ImportError:
            self.out.put(("error", "Listening needs:  pip install vosk sounddevice"))
            return
        try:
            SetLogLevel(-1)
            self.out.put(("status", "Loading speech model (first time downloads ~40 MB)..."))
            if os.path.isdir(self.model):
                if not os.path.isdir(os.path.join(self.model, "am")):
                    raise RuntimeError("%r is not a Vosk model folder" % self.model)
                m = Model(model_path=self.model)
            else:
                m = Model(lang=self.model)
            rate = int(sd.query_devices(kind="input")["default_samplerate"])
            rec = KaldiRecognizer(m, rate)
            audio = queue.Queue()
            with sd.RawInputStream(samplerate=rate, blocksize=rate // 4, dtype="int16",
                                   channels=1, callback=lambda d, *_: audio.put(bytes(d))):
                self.out.put(("status", "Listening (%d Hz)" % rate))
                while not self.stop_evt.is_set():
                    try:
                        data = audio.get(timeout=0.2)
                    except queue.Empty:
                        continue
                    if rec.AcceptWaveform(data):
                        text = json.loads(rec.Result()).get("text", "")
                        if text:
                            self.out.put(("final", text))
                    else:
                        self.out.put(("partial", json.loads(rec.PartialResult()).get("partial", "")))
            self.out.put(("status", "Stopped listening"))
        except Exception as e:      # model download, no microphone, ...
            self.out.put(("error", "Speech: %s" % e))

    def stop(self):
        self.stop_evt.set()
