# Haptic palm-writing box: concept design v0.1

A box you put one hand into, palm up. A microphone picks up someone speaking, speech recognition turns it into text, and a soft-tipped stylus (the "haptic pen") writes the text onto your palm as block capitals, one letter on top of the next. This is the **print-on-palm** (block alphabet) method that many deafblind people already use with a human partner.

![assembly](assembly_preview.png)

> **Assumption to confirm:** here the pen writes on a still palm. The other way to read the brief is that the user *holds* the pen and the box moves their hand through the letters. The same XY mechanism and pen lift would serve both: you would only swap the stylus tip for a grip knob, and the guard window would need to be larger. See "Open questions".

## 1. System overview

```
voice ──► mic array ──► speech-to-text ──► text normaliser ──► letter queue ──► stroke planner ──► 5-bar IK ──► servos
          (lid)         (Vosk / whisper.cpp,  ("2" → "TWO" or "2",   (user controls:    (palm_writer.py)                   │
                         offline on Pi 5)      drop punctuation)      pause/repeat/speed)                                    ▼
                                                                                                    stylus on palm  ◄── lift servo + spring
```

| Stage | Choice | Why |
|---|---|---|
| Speech-to-text | Vosk (streaming) or whisper.cpp `small.en` on a Raspberry Pi 5 | Works offline (private, no network lag). Only **finalised** phrases are written: you cannot un-write a letter. |
| Letter planning | Single-stroke block capitals (`FONT` in `palm_writer.py`), 45 mm tall, all centred on the same spot | Matches print-on-palm. The stroke order follows normal handwriting. |
| Word / sentence cues | Word gap = one tap at the centre + 0.6 s pause. `.` = two taps | The palm can't "see" spacing, so it needs explicit cues. |
| Motion | 120 mm/s writing, 250 mm/s pen-up travel, 3 m/s² accel, 50 Hz setpoints | ≈ 29 letters/min with the current settings (see §5). |

## 2. Mechanical design (`haptic_box.FCMacro`)

**Outside size:** 208 W × 288 L × 193 H mm, plus the port surround and buttons. It fits on a table, and the user sits facing the port.

| Zone | Contents | Key dimensions |
|---|---|---|
| Front port | Rounded opening with a U-shaped brush/foam surround (top and sides only, so the forearm slides on a bare sill) | 130 × 85 mm, sill 15 mm above the floor |
| Forearm rest | Concave pad | 110 wide, 75 deep |
| Hand cradle | The back of the hand rests in a shallow dish | Top at z = 26. The palm surface ends up at about z = 58 |
| Thumb post | Soft peg in the thumb–index web, which places the palm under the window every time. Mirrored by `HAND = "left"` | Ø12 × 44 |
| Guard plate | Rigid sheet 50 mm above the palm. Fingers can never reach the linkage. Only the stylus passes through the 84 × 84 window | z = 108–111 |
| Linkage deck | Hinged at the rear. It carries the two XY servos (shafts point down) and the 5-bar links between the deck and the guard | Hinge at y = 272 |
| Pen lift | A lift spring holds the deck up (pen off the palm). A third servo on a side-wall bracket presses the deck down | 6 mm lift at the stylus |
| Electronics bay | Above the wrist, on top of the guard plate: SBC, servo controller | — |
| Lid | Mic array grille, status LED, and three domed buttons for the free hand (Repeat / Pause / Speed) | Buttons on the opposite side from the writing hand |

**5-bar parallel linkage.** The motors sit 40 mm apart, 80 mm behind the palm centre. The proximal links are 55 mm and the distal links 80 mm, with elbows out. `palm_writer.py --check` confirms it reaches the full 70 × 70 mm workspace, and the worst transmission-angle margin is 32.8° (it stays away from singular poses). A 5-bar was chosen over a gantry because:
- the moving mass is very small (two thin links plus the stylus), so it is quiet and fast
- both motors are fixed, so there is no cable chain
- it is compact enough to sit above the hand.

**Stylus.** Ø6 rod with a Ø8 silicone ball tip on a short compression spring (about 5 mm travel). The spring gives passive compliance, so palm height can vary. A coin LRA vibration motor on the carrier gives non-letter cues: new speech is waiting, end of message, error.

**Contact force: three layers.**
1. The lift-servo current limit sets the nominal force, about 0.5–1 N. That is a firm fingertip; tune it per user.
2. The tip spring caps the force even if the servo is commanded wrongly.
3. **Fail-safe:** if power is lost, the spring lifts the pen off the palm.

**Clearance checks run by the macro (all pass):**
- The hand and forearm envelopes clear the shell, port brush, guard, electronics and thumb post.
- 98 linkage poses: full workspace, pen up and down, 154 part pairs, zero overlap.
- The palm sits 50 mm below the guard.
- The tip reaches exactly 0.0 mm above the palm with the pen down, and at least 6.0 mm with the pen up.

## 3. Electronics (indicative BOM)

| Part | Qty | Note |
|---|---|---|
| Raspberry Pi 5 (4–8 GB) | 1 | Runs speech-to-text and the planner |
| USB 4-mic array (e.g. ReSpeaker-class) | 1 | Under the lid grille, facing the speaker. Beamforming and noise suppression help |
| Dynamixel XL330-M288 (or similar smart servo with current-based position control) | 3 | Two for XY, one for lift. The current mode is what gives force limiting |
| Servo controller (U2D2 or OpenRB-150) | 1 | |
| VL53L1X ToF sensor | 1 | Under the guard, looking down: detects the hand and measures palm height |
| Coin LRA + driver (DRV2605L) | 1 | Cues |
| Lift spring, Ø6 carbon rod, silicone ball tip, 3 × domed buttons, 5 V 5 A PSU | — | |

## 4. Safety and usability rules (design requirements)

- **No restraint, ever.** No straps or clamps. The hand can always be pulled straight out, and the port is wider than a fist.
- **Hand interlock:** the mechanism moves only while the ToF sensor sees a palm at the expected height. If the hand is removed, the motors stop and the pen lifts.
- **Pinch-free:** every moving link is above the guard plate. Only the round, spring-loaded tip goes through the window.
- **Hygiene:** the silicone tip cover is replaceable, and the cradle and forearm pad are wipeable.
- **Touch-first controls:** large domed buttons with Braille and tactile marks. The status LED is for sighted helpers only and is never the only signal.
- **Calibration at start:** the tip touches down at the centre and corners (the servo current rises at contact), which measures the palm plane. Letter size and position can be set per user.

## 5. The big design problem: throughput

| | Rate |
|---|---|
| Conversational speech | ~150 words/min ≈ 750 letters/min |
| This box (current settings) | ~29 letters/min ≈ 6 words/min |
| Skilled human print-on-palm | roughly the same order (a letter every 1–2 s) |

The palm is about 25× slower than speech, so the box **cannot keep up with live conversation verbatim**. Options, which can be combined:
1. **Turn-taking:** the speaker sees a "still writing… N words queued" indicator (LED or small screen on the speaker's side) and waits.
2. **User controls:** Pause, Repeat last word, Skip to newest, and a speed setting that rises as the user gets fluent.
3. **Compression mode (optional):** keep only key words, or shorten the text with an on-device or LLM summariser before writing. This must be opt-in and clearly signalled, because it changes the speaker's words.
4. **Hybrid output:** add a refreshable Braille cell or vibrotactile codes for Braille users, and keep print-on-palm for people who don't read Braille.

## 6. Files

| File | What it is |
|---|---|
| `haptic_box.FCMacro` | Parametric FreeCAD assembly. GUI: animates the linkage writing `TEXT`. Headless (`freecadcmd haptic_box.FCMacro`): clearance checks, then saves `haptic_box.FCStd` |
| `palm_writer.py` | Stroke font, path planner, 5-bar IK, preview (`palm_writer.gif`), `--csv` joint trajectories, `--check`, `--live` (mic → Vosk) |
| `palm_writer.gif` | Simulated linkage writing "HELLO WORLD." on a palm |
| `stroke_font.png` | All 37 glyphs. The dot marks where each stroke starts; colours show stroke order |

## 7. Open questions / next steps

1. **Pen writes on the palm, or pen guides the held hand?** This decides the end effector and the window size. The kinematics and planner stay the same.
2. **Co-design with deafblind users and their organisations:** check the letter forms, size and speed, the word-gap and sentence cues, and the contact force. Is a 45 mm letter right for small palms and children?
3. Prototype order:
   1. 3D-print the 5-bar and drive it from `--csv` output on paper.
   2. Add the lift and force control.
   3. Add the guard and cradle, and do first palm trials.
   4. Add live speech-to-text.
4. Hardware driver: stream the `palm_writer.joint_trajectory()` output to the servos. This is not written yet.
5. Disambiguation: `0`/`O` and `1`/`I` look alike. Prefix numbers with a cue, as the Braille number sign does.
