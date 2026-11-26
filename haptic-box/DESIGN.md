# ComLang Haptic Palm-Writing Box: Design Specification v0.3

| | |
|---|---|
| **Status** | Concept agreed; thin prototype CAD complete, clearance- and hand-fit-checked; hardware not yet built |
| **Audience** | Anyone building, testing or extending the device from zero |
| **Source of truth** | `haptic_box_v2.FCMacro` (parametric CAD). Every dimension in this document comes from that file. If the two disagree, the CAD wins; then fix this document |
| **Supersedes** | v0.2 (80 mm tall box, sync-shaft drive layer, handprint well, Pause/Speed buttons). See Appendix A |
| **What changed in v0.3** | Box **54 mm tall instead of 80** (§4.3). **Cover** between pen and palm (§4.5). **Glove-shaped** well (§4.1). **Thumb scroll wheel** for speed and pause (§4.5). **Mode** button: palm, Braille or both. **Tactile symbols** on every control. **Speaker display + Reset** (§4.9). App: speaker view, reset, mode, cover-material test (§7) |

![product](renders/v2_product.png)

## 0. What it is

**ComLang** is a compact desktop device that turns speech into touch, completely offline. It is for people who cannot hear speech and cannot rely on sight, for example adults who became deafblind and never learned tactile sign language or Braille.

1. The user lays one hand **palm down** in a **10 mm deep, glove-shaped well** on top of a 54 mm tall box. The well is open to the front, so the wrist and forearm lie level with the palm.
2. Someone speaks into the microphone or types into the companion app. Offline speech recognition (Vosk) turns the speech into text.
3. A **single pointed pen** inside the box presses up through a thin **protective cover** under the palm. It **traces block capitals on the palm**, one letter on top of the next. This is *print-on-palm*: people read it with no training.
4. Two refreshable **Braille cells** under the index and middle fingertips show **the same letter at the same moment**. Users can communicate on day one and learn Braille along the way.
5. The resting hand reaches its controls **without moving**:
   - **Thumb scroll wheel:** roll away = faster, roll in = slower, press = pause.
   - **Repeat:** the little finger swings out onto a cap with a raised circular arrow.
6. The **free hand** has a **Mode** button: palm + Braille, palm only, or Braille only.
7. The **speaker** sees on a **display** at the back of the box exactly what the user is receiving. If it is wrong, the speaker presses **Reset**: the device stops and gives the user a "correction" cue.

The pen moves **in one plane on two axes**, on a crossed-bar XY gantry. A flat solenoid with a wedge lifts it 7 mm to touch and leave the palm.

![writing](renders/v2_writing.gif)

---

## 1. Decision record

Use this section to reach and record the common conclusion. Each row names its source. "Review 2" is the second design review (thin box, cover, controls, glove, display). "Pitch" is the ComLang pitch text.

### 1.1 Agreed

| # | Decision | Source |
|---|---|---|
| D1 | The base is a **box**. The hand rests **on top, palm down**. There is no tunnel or enclosure around the hand | Sketch + review |
| D2 | **One pointed pen reaches up from below** through a window under the palm and traces the letters | Review: "one pointy pen below palm" |
| D3 | The pen moves **in one plane on two axes** on a crossed-bar (Cartesian) gantry. Pen up/down is a short local stroke at the carriage, not a third gantry axis. *v0.3:* the bars now run on four perimeter shafts that are both rails and drive shafts (§4.3) | Review; Review 2 (thin) |
| D4 | Controls by the thumb and little finger | Sketch circles |
| D5 | **Refreshable Braille cells** under the fingertips | "+ Braille" on the sketch; Pitch |
| D6 | Primary output is print-on-palm **block capitals, one letter on top of the next**, with word and sentence cues (§7.3) | v0.1, kept; Pitch |
| D7 | The person uses it through an **app** (`haptic_app.py`) | Review: "must be an app for me to use"; Pitch: "companion app" |
| D8 | The prototype is defined by a **parametric CAD model** (FreeCAD) | Review |
| D9 | A **10 mm deep hand well**, cut through a separate upper layer, open to the front for the wrist | Review: "deeper cut-out for the hand" |
| D11 | The app includes a **live 3D simulation of the CAD model** with an anatomical hand and forearm in three sizes | Review |
| D13 | **The box is thin: 54 mm tall** (was 80). Palm surface at 44 mm, forearm pad 44 mm | Review 2: "more thin in the Z dimension" |
| D14 | **A cover sits between the pen and the hand.** It is a membrane on a drop-in cassette, flush with the well floor. Hands and fingers never touch the mechanism. *Replaces v0.2 P4 (open window)* | Review 2: "otherwise deafblind people will likely harm themselves" |
| D15 | **The cover material is chosen by experiment.** Letters are written through each candidate material and recognition is measured (test T13). The app has a built-in test mode for this (§7.5) | Review 2 (reviewer's suggestion) |
| D16 | **Glove-shaped print instead of a handprint.** Each digit and the palm is the convex hull over the small, medium and large hand models + 5 mm: smooth "glove fingers" that fit many hand sizes | Review 2 |
| D17 | **Speed up/down + pause on a thumb scroll wheel.** Roll away from the palm = faster, roll in = slower (one detent = ±0.1×), press = pause/resume. It replaces the v0.2 Pause cap and the ring-finger Speed bar (§4.6 explains why) | Review 2: "slider or a pair of buttons"; Pitch: "thumb scroll wheel (buttons)" |
| D18 | **Every control carries a tactile symbol of its meaning:** Repeat = circular arrow, wheel = **+** (far end) / **−** (near end) / **‖** (beside it, press = pause), Mode = Braille cell + pen stroke, Reset = **×**. Lines 1.4 mm wide, 0.8 mm relief | Review 2; Pitch: "repeat button shaped like a circular arrow" |
| D19 | **The user switches modes**: palm + Braille (default), palm only, Braille only. Mode button for the free hand + app. Each change is confirmed by touch (§7.3) | Review 2 |
| D20 | **Speaker display:** the box shows the speaker the text being written (current letter highlighted, what was dropped struck through), so the speaker can **Reset** wrong output. Reset button next to it. The app also has a full-screen speaker view | Review 2: "so the speaker can see what the output is so it can be reset" |
| D21 | **The Braille cells show the current letter, synchronised with the pen** (answers v0.2 open question 2) | Pitch: "simultaneously display that exact character" |

### 1.2 Proposed: confirm or change

| # | Proposal (current CAD/app default) | Why | Alternatives |
|---|---|---|---|
| P1 | **Mirror the letters in x** for the palm-down box, so a letter feels the same relative to the hand as print-on-palm on an upturned hand | Keeps the convention users already know | Unmirrored. Settled by test T7 |
| P2 | **Pen tip: 0.5 mm radius point** (CAD default), force **0.3–1.0 N** set by a spring. Also 1.0 mm and 2.0 mm radius tips. *With a cover, a fine point concentrates wear on the membrane. Run T13 with T05 and T10 tips* | "Pointy" gives a crisp line | Rolling Ø3 ball tip (no drag on the membrane). Choose after T6 + T13 |
| P3 | **Flat frame solenoid + 35° wedge** for pen up/down: 10 mm plunger travel gives 7 mm lift. The return spring retracts the pen when unpowered | A tubular solenoid standing upright (v0.2) needs 45 mm of height | Micro servo + cam (too slow: ~100 ms) |
| P5 | Letter height **45 mm**, writing speed **120 mm/s**, ~29 letters/min | Fits an adult palm. Speed is adjustable on the wheel | 35 / 55 mm. Test T8 |
| P6 | **Right hand by default.** `HAND="left"` mirrors the well, controls and Braille | Most users | A reversible top plate |
| P7 | **Hand-present pad** (capacitive disc at the wrist) as the motion interlock | Sketch shows a circle at the wrist | IR/ToF sensor looking up through the window |
| P8 | **Separate forearm pad** in front of the box, 44 mm tall | The palm is 44 mm above the table | Box sunk into a table cut-out |
| P9 | **Braille cells are phase 2.** The plate already has their holes. MVP-1 shows Braille on screen only. *The pitch presents Braille as a core feature: decide whether MVP-1 must have them* | Most expensive part (§4.8) | Include them in MVP-1 |
| P10 | **Braille cells on a ±25 mm slider** along the finger direction, set once per user | Fixed cells fit medium fingertips only (§4.6) | Separate cell sets per size |
| P11 | **Symbols raised (embossed)**, 0.8 mm. `SYMBOL_RELIEF = "etched"` switches every symbol to incised grooves 0.8 mm deep | Review 2 asked for etched symbols; the pitch says "raised, embossed". Raised lines are generally easier to read by touch, and stay readable after the parts get dirty. Settled by T15 | Etched |
| P12 | **Wheel direction: away from the palm = faster.** Matches "roll up to speed up" in the pitch if "up" means away | For a palm-down hand, "up" and "down" are ambiguous | Reverse in the Pico firmware |
| P13 | **Mode on a free-hand pocket button** at the front corner on the thumb side | Mode changes are rare. No comfortable resting-digit position is left (§4.6). A pocket stops the forearm pressing it | On the wheel (long press). Settled by T11 |
| P14 | **Display flush in the top plate** (3.5" IPS, wide viewing angle), text rotated 180° to face the speaker across the table | Keeps the box flat | A hinged tilting display. A display on the user's side for sighted helpers |
| P15 | **Touch cues:** correction (Reset) = 3 quick taps and/or 2 Braille flashes. Mode change = a 0.6 s long pen press and/or 1 flash. Word gap = 1 tap. `.` `!` = 2 taps | Every cue must feel different from the others | Taught signs, e.g. writing "X" for a correction |

### 1.3 Open questions (owner: product)

1. Who operates the app day to day: the deafblind user, a companion, or both? This decides whether the Pi runs standalone with physical controls only (phase 2), or a laptop/tablet screen is always present.
2. Is a sentence-level "compression mode" acceptable (§12, risk R1)?
3. Should speed changes be confirmed by touch, e.g. a short Braille digit for the new speed? Today they are silent except for the writing tempo.

---

## 2. Requirements

| ID | Requirement | Target / acceptance |
|---|---|---|
| R-F1 | Write recognised or typed text on the palm as block capitals | All A–Z, 0–9, `?` (37 glyphs, `palm_writer.FONT`) |
| R-F2 | Word and sentence cues | Word gap = 1 tap + 0.6 s; `.`/`!` = 2 taps |
| R-F3 | Braille output for the same text, **synchronised with the pen** | English Grade 1 (uncontracted); a run of digits gets one number sign |
| R-F4 | User controls without lifting the hand | Pause/resume and speed (thumb wheel), Repeat (little finger). Mode with the free hand. Duplicated as app keys |
| R-F5 | Offline speech recognition | Vosk small en-us model, runs on a laptop or a Raspberry Pi 5 |
| R-F6 | **Speaker sees the output and can reset it** | Box display + app speaker view show the current word with the current letter highlighted. Reset drops current and queued words and sends the correction cue within 0.5 s |
| R-F7 | **Mode switching** | Palm + Braille / palm / Braille, from the Mode button or the app, confirmed by touch |
| R-P1 | Writing area on the palm | 70 × 70 mm reachable; glyphs fit in 45 mm height |
| R-P2 | Pen speed and acceleration | 120 mm/s writing, 250 mm/s travel, 3000 mm/s² |
| R-P3 | Pen up/down | Lift 7.0 mm; switch time ≤ 50 ms |
| R-P4 | Contact force | Adjustable 0.3–1.0 N, set mechanically (spring), never by motor torque |
| R-P5 | Positioning | Repeatability ≤ ±0.3 mm |
| R-E1 | Ergonomics | Box ≤ 55 mm tall. Palm surface 44 mm above the table, in a 10 mm deep well. Forearm supported level |
| R-E2 | Control reach | Every resting-hand control used by one digit **without moving the hand**, for small, medium and large hands (§4.6): swing ≤ 25° (thumb) / ≤ 46° (little finger). ≥ 2 mm clearance to resting digits. Switch force 2.5–3.5 N so resting digits never trigger |
| R-E3 | **Fit** | The glove well accepts every hand from the small to the large model with ≥ 5 mm room around each digit |
| R-E4 | **Tactile identification** | Every control identifiable by touch alone (T15) |
| R-S1 | Safety | No restraints. The hand can be lifted at any time. Motion only while a hand is present. Pen retracts on power loss. Max 12 V outside the box |
| R-S2 | Hygiene | Wipeable top. Cover cassette removable for cleaning or replacement. Pen tip replaceable |
| R-S3 | **Cover** | No opening between the user and the mechanism wider than 2 mm while the cover is fitted. The membrane survives ≥ 10 000 letters without puncture (T13) |
| R-N1 | Noise and vibration | Steppers in silent mode (TMC2209 stealthChop) |

---

## 3. System architecture

```
 speaker's voice                                    speaker's eyes
      │                                                   ▲
  [USB mic] ──► haptic_app.py (laptop for MVP, Raspberry Pi 5 later)
                  │  Vosk speech-to-text (offline) → final phrases only
                  │  queue of words  ← thumb wheel / Repeat / Mode / Reset (USB HID keys) / app keys
                  │  palm_writer: text → strokes → G-code (mirrored x)
                  │  palm_writer: text → Braille cells
                  ▼                                        │
        USB serial (115200)            USB CDC (Pico)      │  SPI/GPIO (phase 2)
                  │                        │               │        │
     [Arduino Uno + CNC Shield, GRBL]  [Pico: keys + display link]  [Braille HV driver]
       │X step/dir │Y step/dir │spindle      │SPI                     │
   [TMC2209]   [TMC2209]   [MOSFET]   [3.5" IPS display]   [2 × piezo Braille cells]
       │           │           │
   NEMA14 X    NEMA14 Y    12 V frame solenoid ──► wedge ──► pen ──► cover ──► palm
```

**Signal conventions**
- G-code coordinates are **relative to the palm centre** (work zero, set during calibration §9). Machine x is **mirrored**: `X = −palm_x` (P1).
- Pen up/down uses GRBL's spindle output: `M3 S1000` lifts the pen into the palm, `M5` retracts it. Laser mode is off (`$32=0`).

---

## 4. Mechanical design

### 4.1 Coordinate system and key dimensions

The origin is at the centre of the box front edge, on the table. +x is the user's right, +y points away from the user, +z is up. Units are mm. For the right hand, the thumb is on −x.

![top layout](renders/v2_top.png)

| Feature | Value |
|---|---|
| Box outside | **260 (W) × 380 (L) × 54 (H)**, vertical corners R12. The rear 70 mm is the speaker strip |
| Walls / floor / top plate | 3 / 3 / 14 (top plate = 4 mm floor layer + 10 mm well layer, §4.2) |
| Plate underside / palm surface / top | z = 40 / **44** / 54. **Well depth 10** |
| Wrist crease line | y = 100 |
| **Writing centre** (palm centre) | **(0, 155)** |
| **Window** | **84 × 84**, R8, centred on (0, 155) |
| **Cover cassette** | 100 × 100, R10, in a 2.0 mm pocket in the floor layer; fingernail notch at (0, 104) |
| **Thumb wheel** | Ø22 × 8, crown 4 mm above the floor, centre (−91.2, 157.3), rolls along (−0.84, 0.55), i.e. the thumb's axis when it rests on the wheel |
| **Repeat** (little finger) | Ø26 domed cap, (60.9, 225.4) |
| **Mode** (free hand) | Ø24 cap in a 4 mm pocket, (−93, 42) |
| **Reset** (speaker) | Ø20 cap in a 4 mm pocket, (45, 340) |
| **Speaker display** | 3.5" IPS module 85 × 55 × 6 in a pocket, centre (−25, 340), glass 1 mm below the top |
| Braille cell, index / middle fingertip (medium hand) | (−35.4, 259.7) / (−10.0, 269.4), slider ±25 mm (P10) |
| Hand-present pad (wrist channel floor) | (0, 75), Ø24 |
| Mic grille / status LED | 4 × 4 holes Ø2.4 at x 80…95, y 328…343 (faces the speaker) / Ø4 at (108, 345) |
| Forearm pad | 120 × 140 × 44, in front of the box (y −142…−2) |

**Glove-shaped well** (cut through the 10 mm upper layer; floor at z 44). It is generated from the hand model (§4.6), not drawn by hand:
- **Palm of the glove:** convex hull of the palm sections and digit roots of the small, medium and large hands, + 5 mm.
- **Glove fingers:** for each digit, the convex hull of its joints over all three hands, grown by the largest joint radius + 5 mm. The result is one smooth, rounded channel per digit, like the fingers of a glove, instead of the scalloped union of three handprints in v0.2. Hands between and slightly outside the modelled sizes, and of different proportions, fit with room to spare.
- Wrist channel: 80 wide, from the front edge (y 0) to y 100.
- The cover cassette footprint (+2 mm), so the cassette can always be lifted out.
- Control access: the path from each resting fingertip to its control and the pressed pose (+3.5 mm), plus bays of cap radius + 5 mm (Repeat) and + 14 mm (wheel, which also holds the + / − / ‖ marks).
- Top edge: round over by hand or router (R3). The CAD does not model this round-over.
- Export the outline from the CAD (`TopPlate` → top face → DXF) rather than redrawing it.

![section](renders/v2_section.png)

### 4.2 Enclosure

![exploded](renders/v2_exploded.png)

| Part | Material and process (MVP) | Notes |
|---|---|---|
| **F01 Base tray** 260 × 380 × 40, walls 3, floor 3 | **MVP:** 3 mm plywood or acrylic, laser-cut with finger joints. **Later:** 3D-printed in quadrants or vacuum-formed | The floor is the gantry datum: flat to ±0.3 mm. Rear wall: 7 vent slots 6 × 18, DC jack Ø10 at (95, rear, z 22) |
| **F02 Top plate, floor layer** 260 × 380 × **4** acrylic (PMMA) | Laser-cut, pocket engraved | Window 84 × 84 R8. **Cover pocket** 100.4 × 100.4 × 2.0 + notch. Wheel slot, axle slot, plunger holes Ø13, Braille pin holes Ø1.6 (12×), display cable slot 30 × 4, mic holes, LED, pad pocket |
| **F03 Top plate, well layer** 260 × 380 × **10** | **MVP:** 2 × 5 mm laser-cut layers. **Better:** 10 mm HDPE, CNC-routed with a 3 mm round-over bit | **Glove well cut through.** Pockets: Mode and Reset (Ø29 × 4 deep), display (86 × 56 × 7 deep). Raised **+ − ‖** marks around the wheel: print and bond, or engrave the well layer away around them |
| **F05 Cover cassette** | Frame: 1.7 mm PETG print or laser-cut acrylic, 100 × 100, opening 84 × 84. Membrane: 0.3 mm (T13 material) stretched and bonded on top | Drops into the pocket, top flush with the well floor. Make one cassette per test material |
| **F04 Forearm pad** 120 × 140 × 44 | 3D-printed or plywood box + 10 mm EVA foam + vinyl cover | Separate part, level with the well floor |
| Feet | 4 × Ø15 × 3 rubber bumpers | Decouple vibration from the table |

### 4.3 XY gantry: crossed bars on four drive shafts (the thin design)

![cut-away](renders/v2_cutaway.png)

**Why v0.2 was 80 mm tall.** v0.2 drove each bar from a separate sync shaft in a layer *under* the rails: drive axis at z 21, rails at 34 and 48, then a 32 mm upright solenoid on top. Three layers stacked.

**What v0.3 does.** It uses the Ultimaker-style crossed-bar gantry: **the four perimeter shafts are the rails and the drive shafts at the same time.** The drive layer disappears.
- The **Y-bar** (Ø6) runs along x and moves in y. Its end blocks slide on the two **y-shafts** (left/right, Ø8, rotating).
- The **X-bar** (Ø6) runs along y and moves in x. Its end blocks slide on the two **x-shafts** (front/back, Ø8, rotating).
- The **y-belts** (one per side) loop around pulleys on the front and back **x-shafts**. Turning the back x-shaft moves both y-belts equally, so the Y-bar cannot rack.
- The **x-belts** (front and back) loop around pulleys on the left and right **y-shafts**. Turning one y-shaft moves both x-belts equally, so the X-bar cannot rack.
- The bushings slide on rotating shafts. This is normal in this design; use self-aligning sintered-bronze bushings.
- The pen lifter lies **flat** (P3).

![section detail, pen down](renders/v2_section_detail.png)

**Z stack** (from the table):

| Item | z (mm) |
|---|---|
| Floor top | 3 |
| x-belts (runs) | 6.6 and 19.4 |
| **y-shafts** (Ø8) + x-belt pulleys (GT2 20T, flange Ø18) | **13** |
| **Y-bar** (Ø6) | **16** |
| **X-bar** (Ø6) | **24** |
| y-belts (runs) | 22.6 and 35.4 |
| **x-shafts** (Ø8) + y-belt pulleys | **29** |
| Carriage block | 10–30 (24 × 24 × 20) |
| Pen lifter (flat solenoid 30 × 14 × 16 + wedge) | 10–26 |
| NEMA14 motors (lying, 35 mm) | 3–38 |
| Pen tip, retracted / pressed | 38.5 / 45.5 |
| Top plate | 40–54: floor layer 40–44 (palm rests at **44**, on the cover over the window), well layer 44–54 |

The height is now set by the **NEMA14 motors** (3 + 35 + 2 mm clearance = plate underside at 40). NEMA11 motors (28 mm) would allow about 47 mm, at the cost of torque margin. The x-shafts sit 16 mm above the y-shafts so the x-belts and y-belts cross with clearance.

**Layout** (all from the CAD, right hand):

| Element | Position |
|---|---|
| y-shafts | Ø8 at x = ±110, z 13, y 55…253 (the X-motor side extended to 285). 688ZZ bearing blocks at y 59 and 249 |
| x-shafts | Ø8 at y = 67 and 243, z 29, wall to wall (252 long). 688ZZ bearing posts at x ±120 |
| y-belts | x = −70 (thumb side) and +80 (little-finger side). They avoid the wheel and the Repeat switch above them. Pulleys on the x-shafts. Clamped by tabs on the Y-bar end blocks |
| x-belts | y = 81 and 229. Pulleys on the y-shafts at x ±110. Clamped by tabs reaching down from the X-bar end blocks |
| X motor | NEMA14 at the rear on the thumb side (x −88, y 280…314), shaft along y. Short GT2 loop to the thumb-side y-shaft at y 275 |
| Y motor | NEMA14 at the rear on the little-finger side (x 80, y 272), shaft along x. Short GT2 loop to the back x-shaft at x 58 |
| **Pen offset** | The pen sits **+16, +16 mm** (diagonal) from the carriage centre, clear of both bars. The calibration zero handles this (§9) |

**Travel.** Pen: ±35 mm about (0, 155). Carriage centre: x −51…19, y 104…174.
**Steps.** GT2 (2 mm pitch) on 20T pulleys gives 40 mm per rev. With 1:1 short belts, 200 steps × 1/16 = **80 steps/mm**, as before.
**Belts.** GT2 6 mm. y-belts 2 × ~392 mm, x-belts 2 × ~480 mm, open, both ends clamped. Short motor belts: closed GT2 loops of ~90–100 mm on slotted motor mounts. Tension so the belt deflects ~2 mm under a light finger.

### 4.4 Pen actuator and tip

![section detail, pen up](renders/v2_section_detail_up.png)

| Item | Spec |
|---|---|
| Lifter | 12 V **push-pull frame solenoid** (JF-0530B class, ~30 × 14 × 16 mm, 10 mm stroke) lying flat on the carriage. Its plunger pushes a **35° wedge** under a roller on the pen: 10 mm plunger → 7 mm lift. The solenoid is strongest when closed, which is when the pen presses. Return spring retracts the pen when unpowered. Flyback diode |
| Stroke | 7.0 mm: tip at z 38.5 (1.5 mm below the plate underside, 5.5 mm below the cover) → z 45.5 (1.5 mm above the floor, pressing the membrane into the skin) |
| Pen | Ø3 stainless or POM rod with an M3 thread for interchangeable tips, in a Ø9 printed sleeve on the carriage |
| **Force limiter** | Compression spring between the wedge roller and the pen: ~0.3 N/mm, preload 0.2 N → 0.8 N max. Shims set 0.3–1.0 N. Force never depends on solenoid strength. *Calibrate with the cover fitted: the membrane takes part of the force* |
| Tips (P2) | T05: 0.5 mm radius point. T10: 1.0 mm radius. T20: Ø4 ball. Option: rolling Ø3 ball |
| Hold current | After pull-in, reduce with GRBL `S400` to limit heating |

### 4.5 Hand interface

| Element | Implementation |
|---|---|
| Glove well | 10 mm deep cut-out in F03 (§4.1), top edge R3 |
| **Cover** | Drop-in cassette (F05) over the window, membrane top flush with the well floor. The pen presses it 1.5 mm into the palm. The palm rests on the membrane over the 84 mm opening; the membrane must sag **< 3 mm** under a resting palm so it never touches the retracted pen (5.5 mm below). Swap cassettes to run T13. Clean with 70 % isopropyl alcohol |
| **Thumb wheel** (D17) | Ø22 × 8 knurled wheel (20 ribs) on a **detented rotary encoder with push switch** (EC11 class, 20 detents, ~3 N push). The axle goes to the encoder under the floor layer. The crown stands 4 mm above the floor in a 10 × 22 slot. Roll away = faster (+0.1× per detent), roll in = slower, press = pause/resume. Raised **+** at the far end, **−** at the near end, **‖** beside it on the floor (Ø7 symbols, 0.8 mm). The thumb swings out 22° to reach it (all sizes) |
| **Repeat** | 3D-printed domed cap Ø26, 4.5 mm tall, 0.5 mm above the floor, with a **raised circular arrow** (Ø12, 1.4 mm line, arrowhead). Ø12 stem through a Ø13 hole onto a low-profile 12 × 12 tactile switch (2.5–3.5 N) under the plate |
| **Mode** (free hand) | Flat Ø24 cap in a 4 mm pocket at the front corner on the thumb side, top 1 mm below the surface. Raised **6-dot Braille cell + pen stroke** symbol. 12 × 12 switch |
| Symbols (D18, P11) | Lines 1.4 mm wide, raised 0.8 mm (or etched 0.8 mm deep), sized 12–17 mm. Print the caps with the symbol on top (resin or 0.1 mm layers), so the edges are crisp |
| Control reach | From the hand-model study (§4.6). Validate with real users in T11 |
| Hand-present pad | Ø24 brass disc inlaid 0.4 mm into the wrist-channel floor, wired to a capacitive touch module (TTP223 type) |
| Braille cells (phase 2) | 2 cells, 6 dots, 2.5 mm pitch. Module 12 × 44 × 16 under the plate; pins through Ø1.6 holes. Dots 1–3 on the reader's left (−x), dot 1 furthest away |

![tactile symbols](renders/v2_symbols.png)

### 4.6 Hand model, fit and reach study

The CAD contains a parametric **anatomical hand and forearm** (`hand_model.py`) in three sizes:

| Size | Hand length × breadth | Represents |
|---|---|---|
| small | 165 × 70 mm | ~5th percentile woman |
| medium | 190 × 87 mm | ~50th percentile man |
| large | 205 × 97 mm | ~95th percentile man |

Forearm and palm are lofted elliptical sections, flattened 2 mm where they rest. Fingers have three phalanges; the thumb has a metacarpal + two phalanges. Every hand is placed with its wrist crease at y = 100.

![hand sizes](renders/v2_hand_sizes.png)

Running the macro (`freecadcmd haptic_box_v2.FCMacro`) prints this study:

| Size | Rest fit | Thumb wheel | Repeat (little finger) | Palm centre vs writing centre | Fingertips vs Braille cells |
|---|---|---|---|---|---|
| small | no clash | swing 22°, presses | swing 32°, presses | −9.6 mm | 23 mm short |
| medium | no clash | swing 22°, presses | swing 39°, presses | −2.8 mm | on the cells |
| large | no clash | swing 22°, presses | swing 46°, presses | +1.4 mm | 14 mm beyond |

![control use](renders/v2_button_press.png)

**Why speed went on the thumb wheel, and Mode to the free hand.** The study searched every digit and swing direction for positions that all three hand sizes reach and that clear the resting hand by 2 mm:
- **Thumb:** outward swing ~20°. This is the only comfortable spot, and it is the best one, so the wheel combines speed and pause there.
- **Little finger:** outward swing 32–46°, used by Repeat.
- **Index and middle:** only reachable at 33° and 55° swings, above the comfort limits in R-E2. They also rest on the Braille cells.
- **Ring:** only press-down under the fingertip. This was the v0.2 Speed bar. A single press can't give up *and* down, so it was dropped.

So the resting hand has two good control positions. The thumb wheel puts three functions on one of them. Mode is rare, so it went to the free hand (P13).

**Known limits.** Joint angles are estimates. Real hands vary in proportion. The 46° little-finger swing for large hands is near the limit. Test T11 with real users is what counts.

### 4.7 Fabricated parts list

| ID | Part | Qty | Material / process | Key dimensions |
|---|---|---|---|---|
| F01 | Base tray | 1 | 3 mm plywood/acrylic, laser | 260 × 380 × 40, R12 |
| F02 | Top plate, floor layer | 1 | 4 mm PMMA, laser | 260 × 380, §4.2 |
| F03 | Top plate, well layer | 1 (or 2 × 5 mm) | 10 mm HDPE or 2 × 5 mm laser | Glove well, pockets |
| F04 | Forearm pad | 1 | PLA/plywood + EVA | 120 × 140 × 44 |
| F05 | Cover cassettes | 1 per material | PETG frame + membrane | 100 × 100 × 2.0 |
| F20 | Caps: Repeat, Mode, Reset; thumb wheel | 3 + 1 | Resin or fine PETG print | Ø26 / Ø24 / Ø20 with raised symbols; wheel Ø22 × 8, 20 ribs, D-bore for the encoder |
| F21 | Switch / encoder PCBs | 4 | Perfboard | Under F02 |
| F10 | y-shaft bearing blocks | 4 | PETG, 688ZZ | Shaft axis z 13 |
| F11 | x-shaft bearing posts | 4 | PETG, 688ZZ | Shaft axis z 29 |
| F12 | Y-bar end block + belt tab | 2 | PETG, Ø8 bronze bushing | 18 × 22 × 16, tab to the y-belt |
| F13 | X-bar end block + belt tab | 2 | PETG, Ø8 bronze bushing | 18 × 14 × 16, tab down to the x-belt |
| F14 | Carriage + pen head (sleeve, solenoid seat, wedge guide) | 1 | PETG, 2 × Ø6 bushings | 24 × 24 × 20 |
| F15 | Motor mounts, slotted | 2 | PETG | NEMA14, 31 mm pattern |
| F16 | Wedge + roller | 1 | POM / steel pin | 35° |
| F18 | Pen + tips | 1 + 3 | Stainless/brass | Ø3, M3 |

### 4.8 Purchased parts (BOM)

| # | Item | Qty | Spec / note |
|---|---|---|---|
| 1 | Shaft Ø8 h6, hardened | 4 | 198, 230, 252, 252 |
| 2 | Rod Ø6 h6 | 2 | 206 (Y-bar), 166 (X-bar) |
| 3 | Self-aligning bronze bushing Ø8 / Ø6 | 4 / 2 | End blocks / carriage |
| 4 | Bearing 688ZZ (8 × 16 × 5) | 8 | Shaft ends |
| 5 | GT2 6 mm belt | 2 m | Open belt |
| 6 | GT2 20T pulley, 8 mm bore / 5 mm bore | 10 / 2 | 8 belt pulleys + 2 short-belt pulleys on shafts / motors |
| 7 | GT2 closed loop ~100 mm | 2 | Motor short belts |
| 8 | NEMA14 stepper 35 × 35 × 34 | 2 | ~0.6–1.0 A |
| 9 | Arduino Uno R3 + CNC Shield V3 | 1 | GRBL 1.1 |
| 10 | TMC2209 step-stick | 2 | stealthChop, 1/16 |
| 11 | 12 V push-pull frame solenoid, 10 mm stroke | 1 | §4.4 |
| 12 | Logic-level MOSFET + flyback diode | 1 | IRLZ44N, 1N5819 |
| 13 | Microswitch (limit) | 2 | X-min, Y-min |
| 14 | **Rotary encoder with push switch, detented** | 1 | EC11 class, 20 detents |
| 15 | 12 × 12 mm tactile switch, low profile, 2.5–3.5 N | 3 | Repeat, Mode, Reset |
| 16 | Raspberry Pi Pico (RP2040) | 1 | Encoder + switches + pad → USB HID keys; display link (USB CDC) |
| 17 | **3.5" IPS SPI display 480 × 320** (ILI9488 / ST7796 class) | 1 | Speaker display, driven by the Pico |
| 18 | TTP223 module + Ø24 brass disc | 1 | Hand-present |
| 19 | USB microphone | 1 | Under the grille, or external |
| 20 | 12 V 5 A DC supply + jack | 1 | |
| 21 | Cover membrane samples | set | T13 list (§10) |
| 22 | M3 screws, heat-set inserts, compression springs for Ø3 pen | set | |
| 23 | **Phase 2:** Raspberry Pi 5 + 12→5 V 5 A buck | 1 | Standalone |
| 24 | **Phase 2:** piezo Braille cells + HV driver | 2 | Most expensive item (P9) |

### 4.9 Speaker strip

The rear 70 mm of the box faces the speaker, who usually sits across the table.
- **Display:** 3.5" IPS, flush, text rotated 180°. It shows the word being written in large letters, with done letters grey and the current letter highlighted. Underneath are the last few phrases, with dropped words struck through, plus the mode, words waiting, and a paused flag.
- **Reset:** pocket button (×) next to it.
- **Microphone grille** and status LED.

The app's **speaker display** window (§7.2) shows the same thing on a laptop or tablet.

---

## 5. Electrical design

### 5.1 Power budget

| Consumer | Supply | Current (peak) |
|---|---|---|
| 2 × NEMA14 via TMC2209 | 12 V | 2 × 0.6 A |
| Pen solenoid | 12 V | ≤ 1 A pull-in, ~0.4 A hold |
| Uno + Pico + TTP223 + display | 5 V via USB | < 0.3 A |
| Pi 5 (phase 2) | 5 V / 5 A buck | ≤ 3 A |
| **Total** | **12 V** | ≈ 3 A (MVP), ≈ 5 A with the Pi |

### 5.2 Wiring (MVP)

| From | To | Note |
|---|---|---|
| 12 V jack | CNC Shield V+ / GND | 3 A inline fuse |
| X / Y drivers | X / Y steppers | 1/16 microsteps |
| X-min / Y-min | Shield X−/Y− | Normally-open to GND |
| GRBL spindle output | MOSFET gate | **Pin check:** GRBL 1.1 with variable spindle puts spindle PWM/enable on **D11** (the shield silk label says Z+). Wire by pin number; confirm against `cpu_map.h` |
| MOSFET drain | Solenoid −; solenoid + to 12 V | Flyback diode across the coil |
| Wheel push switch | **also** to GRBL feed-hold (A1) | Pause works in hardware even if the app hangs |
| Encoder A/B, wheel switch, Repeat, Mode, Reset, TTP223 | Pico GPIO (pull-ups) | Pico sends keys: wheel away = `+`, wheel in = `−`, wheel press = Space, Repeat = R, Mode = M, Reset = Esc, hand present = F9 (down/up) |
| Display (SPI) | Pico SPI0 | Pico shows lines received over USB CDC (§7.4) |
| Uno, Pico, mic USB | Laptop (MVP) / Pi 5 (phase 2) | |

### 5.3 Electrical safety
- Only 12 V DC enters the box.
- The Braille HV (phase 2) stays inside a closed driver module.
- Keep the motor current low (0.5 A). The interlock (§7.4) and the cover keep fingers away from the moving parts.

---

## 6. Firmware (GRBL 1.1 on the Uno)

| Setting | Value | Meaning |
|---|---|---|
| `$100` / `$101` | 80 | steps/mm X / Y |
| `$110` / `$111` | 15000 | max rate mm/min (250 mm/s) |
| `$120` / `$121` | 3000 | accel mm/s² |
| `$130` / `$131` | 75 | max travel |
| `$20` / `$21` | 1 / 1 | soft and hard limits |
| `$22` / `$23` / `$27` | 1 / 3 / 2 | homing on, towards X−/Y−, pull-off 2 mm |
| `$30` / `$31` / `$32` | 1000 / 0 / 0 | spindle range, laser mode off |
| `$1` | 255 | keep motors energised |
| `$3` | on test | invert X if the wiring differs (P1) |

**G-code produced by the app** (`palm_writer.event_gcode`), work zero = palm centre:

```
G0 X15.75 Y22.50        ; travel to the start of a stroke
M3 S1000                ; pen up into the palm
G4 P0.08                ; settle
G1 X15.75 Y-22.50 F7200 ; draw at 120 mm/s
M5                      ; retract
G4 P0.08
```

The mode-change cue is a `longtap`: `G0 X0 Y0`, `M3 S1000`, `G4 P0.68`, `M5`.

---

## 7. Software

### 7.1 Components

| File | Role |
|---|---|
| `haptic_app.py` | The ComLang companion app (Tkinter): listen/type → queue → simulation + Braille → GRBL. Speaker display, reset, mode, cover-material test |
| `palm_writer.py` | Engine: stroke font, cues (tap, long tap), `Planner`, Braille Grade 1, G-code |
| `haptic_box_v2.FCMacro` | Prototype CAD + clearance checks + STEP + mesh export |
| `hand_model.py` | Hand + forearm model (3 sizes), control placement and reach maths, **glove outline** |
| `cad_render.py` | Numpy renderer, also the app's live 3D view |
| `render_views.py` | All the images in this document |
| `start.sh` | One-command launcher |

### 7.2 Running

```
cd haptic-box
./start.sh
```

This creates `.venv`, installs `numpy vosk sounddevice pyserial`, rebuilds `build/v2_mesh.json` with FreeCAD when the CAD changed, and starts the app. The first **Listen** downloads the small en-us model (~40 MB).

**App controls.**

| Action | App key / button | On the box |
|---|---|---|
| Pause / resume | Space | Press the thumb wheel |
| Faster / slower | `+` / `−` | Roll the wheel away / in |
| Repeat word | R | Repeat (little finger) |
| Mode: palm + Braille → palm → Braille | M | Mode (free hand) |
| **Reset** (speaker: output is wrong) | Esc, or the red button on the speaker display | Reset (speaker) |
| Skip to the newest phrase / clear all | S / C | — |
| Listen on/off | L | — |
| **Speaker display** window | D | Built-in display |
| **Cover-material test** (T13) | T | — |

**Speaker display window.** Black, large type, for a second screen or a tablet turned to the speaker. It shows the word being written with the current letter highlighted, the recent transcript (dropped words struck through in red), mode / queue / paused, and big **Reset** and **Pause** buttons.

**Live simulation.** The 3D tab renders the CAD model with the anatomical hand (small / medium / large). The gantry and pen move in real time, ink appears on the palm, and the thumb or little finger visibly presses the wheel or Repeat when those are used. Because the 3D view is built from the CAD meshes, CAD changes appear the next time `./start.sh` runs.

### 7.3 Text → touch rules
- Only **finalised** recognition results are queued. Partial results are shown greyed and never written.
- Letters are written at the same spot, 45 mm tall, 0.25 s apart. Word gap: 1 tap + 0.6 s. `.` and `!`: 2 taps.
- Braille: one cell per letter, shown **while the pen writes that letter** (D21). Digits: number sign at the start of a run.
- **Touch cues (P15):**

  | Event | Palm (pen) | Braille cells |
  |---|---|---|
  | Word gap | 1 tap | — |
  | Sentence end (typed `.` `!`) | 2 taps | — |
  | **Reset / correction** | 3 quick taps | 2 flashes (all dots up 0.5 s) |
  | **Mode changed** | 0.6 s long press (if the pen is now on) | 1 flash (if the cells are now on) |

- **Reset** stops the pen at once (GRBL soft reset + `M5`), drops the current and queued words, shows them struck through on the speaker display, and sends the correction cue.

### 7.4 To implement before user trials (MVP-1 gate)

1. **Hand-present interlock.** Pico sends F9 down/up. With no hand: feed hold (`!`) + `M5`; resume only after the hand returns and the user presses the wheel.
2. **Calibration screen.** Jog, set zero, test letter (§9).
3. **Box display link.** The app sends the speaker-display content to the Pico over USB CDC, one line per message, UTF-8:
   - `W <word> <index of current letter>`
   - `T <recent transcript, cancelled words prefixed with ~>`
   - `S <mode>|<waiting>|<paused 0/1>`

   The Pico firmware (CircuitPython, `usb_cdc` + `usb_hid` + `displayio`) draws them rotated 180°. The app's speaker window already renders the same content (`App._render_speaker`); the link only needs the serial sender.
4. **Pico firmware** for the encoder (`+`/`−` per detent, Space on press) and the switches.
5. **Braille driver output** (phase 2).
6. **Hold-current change** after pull-in (`S400`).

### 7.5 Cover-material test (supports D15 / T13)

**Cover test** (key T) runs the recognition experiment:
1. Enter the participant, cover material (list of candidates, editable), pen tip, force and letters per block.
2. **Start block.** The app switches to palm-only mode and writes random letters one at a time. Letter size and speed come from the main window.
3. After each letter, the operator types what the participant reports (`?` = don't know) and presses Enter. **Repeat letter** writes it again.

Every answer is appended to `trials/cover_trials.csv`: time, participant, cover, tip, force, letter size, speed, target, response, correct, response time. The window shows accuracy per material so far.

---

## 8. Build guide (MVP-1)

1. **Cut the plates.** F01, F02, F03 from DXF exported from the CAD. Check the window, cover pocket, wheel slot, holes and pockets against §4.1.
2. **Print** bearing blocks, end blocks, carriage, motor mounts, caps and the wheel. Press in the bushings and ream them to slide freely.
3. **Assemble the base tray.** Flat and square (diagonals within 0.5 mm). Feet.
4. **Shafts.** Mount the bearing blocks and posts. Fit the y-shafts (z 13) and x-shafts (z 29) with their belt pulleys (loose grub screws). Each shaft must turn freely.
5. **Bars.** Slide the end blocks onto the shafts, fit the Y-bar and X-bar through the carriage. The carriage must move freely over the 70 × 70 mm range.
6. **Belts.** Clamp each belt into its tab with **both ends of each bar at the same position** (square the bar first), then tighten the pulley grub screws. Tension.
7. **Motors.** Mount on slotted mounts, fit the short belts, tension.
8. **Pen head.** Fit the solenoid, wedge, roller, pen and force spring (start with tip T10). Check the 7 mm lift.
9. **Electronics.** Uno + shield, MOSFET, Pi (later), Pico at the rear, encoder and switch boards under F02, display in its pocket. Wire per §5.2. Set the TMC2209 Vref.
10. **Flash and configure** GRBL (§6). Home, jog, confirm directions.
11. **Top plate.** Laminate F03 on F02, round the well edge, fit the caps and wheel (each returns freely), inlay the pad, screw down. The pen must clear the window by ≥ 2 mm at every corner.
12. **Cover.** Make one cassette per test material. Drop one in: flush with the floor, < 3 mm sag under a resting palm.
13. **App.** Connect, calibrate (§9), write test letters.

---

## 9. Calibration

1. **Home** with `$H`.
2. **Zero:** jog the pen (retracted) under the window centre (cross on masking tape), then `G10 L20 P1 X0 Y0`.
3. **Height and force, with the cover fitted:**
   1. With `M3 S1000`, the tip must lift the membrane **1.5 ± 0.3 mm** above the floor.
   2. Measure the force with a pocket scale over the cover. Target **40–80 g**.
   3. Shim the spring.
4. **Orientation (P1):** write `L`, `F`, `R` on a person's palm. Set "palm-down box (mirror)" to match.
5. **Workspace:** `G0` to the four corners (±35, ±35). No contact with the window edge or the cassette frame.

---

## 10. Test plan

| ID | Test | Pass criterion |
|---|---|---|
| T1 | CAD checks: `freecadcmd haptic_box_v2.FCMacro` | Prints `CLEARANCES OK` and `HAND FIT OK`. Pen tip +1.5 down / −5.5 up |
| T2 | Repeatability: 40 mm square 20× on paper over the window | Line width spread ≤ 0.6 mm |
| T3 | Speed: write the pangram | ≥ 25 letters/min, no lost steps |
| T4 | Pen timing: high-speed video of 20 taps | Up and down ≤ 50 ms each |
| T5 | Interlock: lift the hand mid-letter | Pen retracts, motion stops within 100 ms |
| T6 | Tip/force comfort (P2): 3 tips × 3 forces, 5 participants | Best clarity, no discomfort |
| T7 | Orientation (P1): 10 asymmetric letters, mirrored vs not | Higher recognition wins |
| T8 | Recognition: 26 letters, sizes 35/45/55 mm | ≥ 80 % after 10 min familiarisation |
| T9 | Session comfort: 20 min | No wrist or forearm discomfort |
| T10 | End-to-end: 5 spoken sentences | Every final phrase written; queue, repeat, skip, reset behave as specified |
| T11 | Control reach: ≥ 6 participants, small to large hands, eyes closed | Wheel roll, wheel press and Repeat each done within 3 s without lifting the palm. Mode found with the free hand within 5 s. No accidental presses in a 5 min writing session |
| T12 | Braille slider: small and large hands | Cells under both pads |
| **T13** | **Cover material experiment** (D15). See below | Choose the material |
| T14 | Speaker display: read from the speaker's seat (1–1.5 m, across the table) | Current word readable at a glance; Reset understood without instruction |
| T15 | Tactile symbols (P11): blindfolded participants identify each control by touch, raised vs etched versions | ≥ 95 % correct; choose raised or etched |
| T16 | Glove fit: ≥ 10 participants of varied hand size and shape place the hand without guidance | Hand settles in the well within 5 s; no pressure points at the edges |

**T13 Cover material experiment.**
- **Candidates:**
  - no cover (baseline only, without people at risk: the operator's own hand)
  - nitrile glove film ~0.1 mm
  - latex sheet 0.2 mm
  - silicone sheet 0.5 mm
  - TPU film 0.1 mm
  - PET film 0.05 mm
  - Lycra/elastane fabric
  - PTFE film 0.1 mm

  Make one cassette per material, with equal pre-tension.
- **Design:** within-subject. Each participant does one block of 20 random letters per material (app: Cover test), in a counterbalanced (Latin-square) order. Pen tips T05 and T10 at 0.6 N. 45 mm letters, 1.0× speed. ≥ 5 participants (sighted-hearing blindfolded first, then deafblind users with their organisation).
- **Measures:**
  - recognition % (from the CSV) and response time
  - confusion pairs
  - comfort and "sharpness" ratings (1–5)
  - after the block: membrane sag under a resting palm (< 3 mm), visible wear
  - bench durability: 10 000 letters, no puncture.
- **Choose** the material whose recognition is within 10 percentage points of the open window, with no discomfort and no puncture. If two qualify, choose the easier to clean.

Run trials with deafblind people **together with their organisations or interpreters**. Get informed consent in an accessible format.

---

## 11. Phases and MVP

| Phase | Scope | Exit criteria |
|---|---|---|
| **MVP-0: bench rig** | Gantry + pen on an open baseboard. App + GRBL. Writes on paper and through cover samples | T2, T3, T4 pass. First T13 pass (bench) |
| **MVP-1: first box** *(the CAD)* | Thin base, 2-layer top plate with glove well, cover cassettes, forearm pad, thumb wheel / Repeat / Mode / Reset via Pico, hand-present pad, speaker display, laptop app, USB mic. Braille on screen only (P9) | T1–T16 with ≥ 5 participants. Decide P1, P2, P5, P11, cover material |
| **Phase 2: standalone** | Raspberry Pi 5 inside, piezo Braille cells, power button, enclosure finish, left-hand plate | Usable without a laptop. Braille synchronised with the pen |

## 12. Risks

| ID | Risk | Mitigation |
|---|---|---|
| R1 | **Throughput:** speech ~150 words/min vs palm ~6 words/min | Speaker display shows how far behind it is. Skip, Reset, Braille-only mode, optional summarising (open question 2) |
| R2 | A pointed tip feels sharp | Spring-limited force, interchangeable tips, the cover spreads the point. T6, T13 |
| R3 | **The cover dulls the letters** | T13 picks the thinnest material that still protects. Larger letters (P5). Fallback: open window + interlock (v0.2) for trained users only |
| R4 | The membrane wears through or sags onto the pen | Replaceable cassette, durability test, sag < 3 mm check at every cassette change |
| R5 | A bar racks if the belt ends are clamped unevenly | Both ends driven from one shaft. Square at assembly (§8.6) |
| R6 | Bushings sliding on rotating shafts wear or squeak | Self-aligning sintered bronze, light oil; the gantry is lightly loaded |
| R7 | Flat solenoid too weak at full stroke | The wedge puts the high-force (closed) end at pen-down. Choose the solenoid by its force at 1–2 mm from closed. Fallback: two solenoids or a steeper wedge |
| R8 | Speech errors write wrong words | Final-only results. Speaker display + Reset + correction cue. Larger Vosk model on the Pi |
| R9 | Accidental Mode or Reset presses | Pocket buttons, top 1 mm below the surface. Reset is on the speaker side |
| R10 | GRBL spindle pin mix-up | Wire by pin number (§5.2) |
| R11 | Braille cell cost | Phase 2. Screen-Braille fallback |

---

## Appendix A: earlier versions (superseded)

**v0.2** (Nov 2026) was 80 mm tall:
- crossed rails at z 34 / 48, driven by sync shafts in a separate layer at z 21
- an upright Ø16 × 32 solenoid
- an open window (no cover)
- a well made from the union of three handprints
- Braille-labelled Pause (thumb) and Repeat (little finger) caps, plus a flush Speed bar under the ring fingertip.

Review 2 asked for a thinner box, a cover, a glove print, speed up/down controls, symbols, mode switching and a speaker display. The pitch added the thumb wheel and synchronised Braille. That led to v0.3.

**v0.1** had the hand inserted palm up into an enclosed box, written on from above by a 5-bar linkage (`haptic_box.FCMacro`). It stays in the repo for reference.

## Appendix B: Regenerating the CAD and images

```
cd haptic-box
HAPTIC_DUMP=build/v2_mesh.json freecadcmd haptic_box_v2.FCMacro   # checks, .FCStd, .step, meshes (~30 s)
python3 render_views.py                                           # all renders → renders/
python3 render_views.py top section symbols                       # selected views
freecad haptic_box_v2.FCMacro                                     # interactive 3D, animates TEXT
```

All dimensions are parameters at the top of `haptic_box_v2.FCMacro`. For example:
- `BOX_W/L`, `PLATE_UNDER`, `BASE_T`, `RECESS`
- `GLOVE_MARGIN`, `COVER`, `COVER_T`
- `WHEEL_R/W/UP`, `STRIP`, `SPEAKER`, `DISPLAY`
- `SYMBOL_RELIEF`, `Z_YRAIL/Z_XRAIL/Z_YBAR/Z_XBAR`, `BELT_X_THUMB/LITTLE`, `HAND`

The box height follows from them: `BOX_H = PLATE_UNDER + BASE_T + RECESS`. After changing any of them, re-run both commands and update §4.1 and §4.3.
