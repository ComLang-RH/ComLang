# ComLang Haptic Palm-Writing Box: Design Specification v0.3

| | |
|---|---|
| **Status** | Concept agreed; **20 mm** prototype CAD complete, clearance- and hand-fit-checked. Device software and controller firmware written and tested end to end on the **simulated board**; RP2040 build not yet compiled; hardware not yet built |
| **Audience** | Anyone building, testing or extending the device from zero |
| **Source of truth** | Dimensions: `haptic_box_v2.FCMacro` (parametric CAD). Behaviour: `comlang/` (host) and `firmware/mcu` (controller). If this document disagrees with them, the code wins; then fix this document |
| **Software** | Two sections, kept in sync by `tests/test_sync.py`: **A. device software**, the host program (`comlang/`) and the box controller firmware in C (`firmware/mcu`), and **B. demos** (`demos/`) built on top of it. The demo's simulation **runs the real firmware** against a model of the hardware (§6, §7) |
| **Supersedes** | v0.3 first build (54 mm, shaft-driven gantry, steppers, 10 mm well) and v0.2 (80 mm). See Appendix A |
| **What changed in v0.3** | Box **20 mm tall** (was 80, then 54): flat **CoreXY** gantry with two **flat BLDC motors** and encoders, 2.5 mm glove recess, thin scroll roller, **pop-out latching Braille pins** (§4.3–4.5). **Matte black** finish. **Cover** between pen and palm (§4.5). **Glove-shaped** well (§4.1). **Thumb scroll wheel** for speed and pause (§4.5). **Mode** button: palm, Braille or both. **Tactile symbols** on every control. **Speaker display + Reset** (§4.9). App: speaker view, reset, mode, cover-material test (§7). Software: **custom controller firmware in C** on one RP2040 (replaces off-the-shelf motion firmware on a second board); the demo simulates the box by **running that firmware** (§6, §7) |

![product](renders/v2_product.png)

## 0. What it is

**ComLang** is a compact desktop device that turns speech into touch, completely offline. It is for people who cannot hear speech and cannot rely on sight, for example adults who became deafblind and never learned tactile sign language or Braille.

1. The user lays one hand **palm down** in a **shallow (2.5 mm) glove-shaped recess** on top of a **20 mm** flat box. The recess is open to the front, so the wrist and forearm lie level with the palm.
2. Someone speaks into the microphone or types into the companion app. Offline speech recognition (Vosk) turns the speech into text.
3. A **single pointed pen** inside the box presses up through a thin **protective cover** under the palm. It **traces block capitals on the palm**, one letter on top of the next. This is *print-on-palm*: people read it with no training.
4. Two refreshable **Braille cells**, pins that pop out of the surface under the index and middle fingertips, show **the same letter at the same moment**. Users can communicate on day one and learn Braille along the way.
5. The resting hand reaches its controls **without moving**:
   - **Thumb scroll roller:** roll away = faster, roll in = slower, press = pause.
   - **Repeat:** the little finger swings out onto a cap with a raised circular arrow.
6. The **free hand** has a **Mode** button: palm + Braille, palm only, or Braille only.
7. The **speaker** sees on a **display** at the back of the box exactly what the user is receiving. If it is wrong, the speaker presses **Reset**: the device stops and gives the user a "correction" cue.

The pen moves **in one plane on two axes**, on a flat CoreXY gantry driven by two flat, closed-loop BLDC motors. A mini solenoid with a wedge lifts it 5 mm to touch and leave the palm.

![writing](renders/v2_writing.gif)

---

## 1. Decision record

Use this section to reach and record the common conclusion. Each row names its source. "Review 2" is the second design review (thin box, cover, controls, glove, display). "Pitch" is the ComLang pitch text.

### 1.1 Agreed

| # | Decision | Source |
|---|---|---|
| D1 | The base is a **box**. The hand rests **on top, palm down**. There is no tunnel or enclosure around the hand | Sketch + review |
| D2 | **One pointed pen reaches up from below** through a window under the palm and traces the letters | Review: "one pointy pen below palm" |
| D3 | The pen moves **in one plane on two axes** on a crossed-bar (Cartesian) gantry. Pen up/down is a short local stroke at the carriage, not a third gantry axis. *v0.3 (20 mm):* flat CoreXY with belts in two flat layers, two flat BLDC motors with encoders (§4.3) | Review; Review 2 (thin) |
| D4 | Controls by the thumb and little finger | Sketch circles |
| D5 | **Refreshable Braille cells** under the fingertips | "+ Braille" on the sketch; Pitch |
| D6 | Primary output is print-on-palm **block capitals, one letter on top of the next**, with word and sentence cues (§7.3) | v0.1, kept; Pitch |
| D7 | The person uses it through an **app**. The device software (`comlang/`) runs the box; the demo app (`demos/haptic_app.py`) is built on the same code (§7) | Review: "must be an app for me to use"; Pitch: "companion app" |
| D8 | The prototype is defined by a **parametric CAD model** (FreeCAD) | Review |
| D9 | A **hand recess** cut through a separate upper layer, open to the front for the wrist. *20 mm box:* 2.5 mm deep; the plate between the glove fingers guides them | Review: "deeper cut-out for the hand"; owner: ~2 cm box |
| D11 | The app includes a **live 3D simulation of the CAD model** with an anatomical hand and forearm in three sizes | Review |
| D13 | **The box is flat: 20 mm tall** (was 80, then 54). Palm surface at 17.5 mm, forearm pad 17.5 mm. Achieved with flat CoreXY, flat BLDC motors, a 2.5 mm recess, a thin roller and pop-out latching Braille | Review 2: "more thin in the Z dimension"; owner: "about 2 cm" |
| D14 | **A cover sits between the pen and the hand.** It is a membrane on a drop-in cassette, flush with the recess floor. Hands and fingers never touch the mechanism. *Replaces v0.2 P4 (open window)* | Review 2: "otherwise deafblind people will likely harm themselves" |
| D15 | **The cover material is chosen by experiment.** Letters are written through each candidate material and recognition is measured (test T13). The app has a built-in test mode for this (§7.5) | Review 2 (reviewer's suggestion) |
| D16 | **Glove-shaped print instead of a handprint.** Each digit and the palm is the convex hull over the small, medium and large hand models + 5 mm: smooth "glove fingers" that fit many hand sizes | Review 2 |
| D17 | **Speed up/down + pause on a thumb scroll roller.** Roll away from the palm = faster, roll in = slower (one detent = ±0.1×), press = pause/resume. It replaces the v0.2 Pause cap and the ring-finger Speed bar (§4.6 explains why). *20 mm box:* a thin Ø6 roller (the gantry runs under it) instead of the Ø22 wheel | Review 2: "slider or a pair of buttons"; Pitch: "thumb scroll wheel (buttons)" |
| D18 | **Every control carries a tactile symbol of its meaning:** Repeat = circular arrow, roller = **+** (far end) / **−** (near end) / **‖** (beside it, press = pause; incised, under the thumb), Mode = Braille cell + pen stroke, Reset = **×**. Lines 1.4 mm wide, 0.8 mm relief | Review 2; Pitch: "repeat button shaped like a circular arrow" |
| D19 | **The user switches modes**: palm + Braille (default), palm only, Braille only. Mode button for the free hand + app. Each change is confirmed by touch (§7.3) | Review 2 |
| D20 | **Speaker display:** the box shows the speaker the text being written (current letter highlighted, what was dropped struck through), so the speaker can **Reset** wrong output. Reset button next to it. The app also has a full-screen speaker view | Review 2: "so the speaker can see what the output is so it can be reset" |
| D21 | **The Braille cells show the current letter, synchronised with the pen** (answers v0.2 open question 2) | Pitch: "simultaneously display that exact character" |

### 1.2 Proposed: confirm or change

| # | Proposal (current CAD/app default) | Why | Alternatives |
|---|---|---|---|
| P1 | **Mirror the letters in x** for the palm-down box, so a letter feels the same relative to the hand as print-on-palm on an upturned hand | Keeps the convention users already know | Unmirrored. Settled by test T7 |
| P2 | **Pen tip: 0.5 mm radius point** (CAD default), force **0.3–1.0 N** set by a spring. Also 1.0 mm and 2.0 mm radius tips. *With a cover, a fine point concentrates wear on the membrane. Run T13 with T05 and T10 tips* | "Pointy" gives a crisp line | Rolling Ø3 ball tip (no drag on the membrane). Choose after T6 + T13 |
| P3 | **Mini frame solenoid + wedge** lying flat for pen up/down: 5 mm lift. The return spring retracts the pen when unpowered | Fits the 7 mm carriage of the 20 mm box | Voice coil (faster, quieter, costlier) |
| P5 | Letter height **45 mm**, writing speed **120 mm/s**, ~29 letters/min | Fits an adult palm. Speed is adjustable on the roller | 35 / 55 mm. Test T8 |
| P6 | **Right hand by default.** `HAND="left"` mirrors the recess, controls and Braille | Most users | A reversible top plate |
| P7 | **Hand-present pad** (capacitive disc at the wrist) as the motion interlock | Sketch shows a circle at the wrist | IR/ToF sensor looking up through the window |
| P8 | **Separate forearm pad** in front of the box, 17.5 mm tall | The palm is 17.5 mm above the table | Box sunk into a table cut-out |
| P9 | **Pop-out latching Braille pins are phase 2.** The plate already has their holes and the firmware drives them. MVP-1 shows Braille on screen only. *The pitch presents Braille as a core feature: decide whether MVP-1 must have them* | Supplier and cost of thin latching actuators open (R12) | Include them in MVP-1 |
| P10 | **Braille cells on a ±25 mm slider** along the finger direction, set once per user | Fixed cells fit medium fingertips only (§4.6) | Separate cell sets per size |
| P11 | **Symbols raised (embossed)**, 0.8 mm. `SYMBOL_RELIEF = "etched"` switches every symbol to incised grooves 0.8 mm deep | Review 2 asked for etched symbols; the pitch says "raised, embossed". Raised lines are generally easier to read by touch, and stay readable after the parts get dirty. Settled by T15 | Etched |
| P12 | **Roller direction: away from the palm = faster.** Matches "roll up to speed up" in the pitch if "up" means away | For a palm-down hand, "up" and "down" are ambiguous | Reverse with `WHEEL_AWAY_POSITIVE` in `firmware/mcu/src/config.h` |
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
| R-F1 | Write recognised or typed text on the palm as block capitals | All A–Z, 0–9, `?` (37 glyphs, `FONT` in `comlang/engine.py`) |
| R-F2 | Word and sentence cues | Word gap = 1 tap + 0.6 s; `.`/`!` = 2 taps |
| R-F3 | Braille output for the same text, **synchronised with the pen** | English Grade 1 (uncontracted); a run of digits gets one number sign |
| R-F4 | User controls without lifting the hand | Pause/resume and speed (thumb roller), Repeat (little finger). Mode with the free hand. Duplicated as app keys |
| R-F5 | Offline speech recognition | Vosk small en-us model, runs on a laptop or a Raspberry Pi 5 |
| R-F6 | **Speaker sees the output and can reset it** | Box display + app speaker view show the current word with the current letter highlighted. Reset drops current and queued words and sends the correction cue within 0.5 s |
| R-F7 | **Mode switching** | Palm + Braille / palm / Braille, from the Mode button or the app, confirmed by touch |
| R-P1 | Writing area on the palm | 70 × 70 mm reachable; glyphs fit in 45 mm height |
| R-P2 | Pen speed and acceleration | 120 mm/s writing, 250 mm/s travel, 3000 mm/s² |
| R-P3 | Pen up/down | Lift 5.0 mm; switch time ≤ 50 ms |
| R-P4 | Contact force | Adjustable 0.3–1.0 N, set mechanically (spring), never by motor torque. Gantry push force limited to ≤ 4 N by the motor torque limit; a blocked carriage stops within 100 ms |
| R-P5 | Positioning | Repeatability ≤ ±0.3 mm |
| R-E1 | Ergonomics | **Box ≤ 20 mm tall.** Palm surface 17.5 mm above the table, in a 2.5 mm glove recess. Forearm supported level |
| R-E2 | Control reach | Every resting-hand control used by one digit **without moving the hand**, for small, medium and large hands (§4.6): swing ≤ 25° (thumb) / ≤ 46° (little finger). ≥ 2 mm clearance to resting digits. Switch force 2.5–3.5 N so resting digits never trigger |
| R-E3 | **Fit** | The glove recess accepts every hand from the small to the large model with ≥ 5 mm room around each digit |
| R-E4 | **Tactile identification** | Every control identifiable by touch alone (T15) |
| R-S1 | Safety | No restraints. The hand can be lifted at any time. Motion only while a hand is present. Pen retracts on power loss. Max 12 V outside the box |
| R-S2 | Hygiene | Wipeable top. Cover cassette removable for cleaning or replacement. Pen tip replaceable |
| R-S3 | **Cover** | No opening between the user and the mechanism wider than 2 mm while the cover is fitted. The membrane survives ≥ 10 000 letters without puncture (T13) |
| R-N1 | Noise and vibration | Sinusoidal (FOC) BLDC drive at 25 kHz PWM: no step noise |

---

## 3. System architecture

```
 speaker's voice                                          speaker's eyes
      │                                                         ▲
  [USB mic] ──► HOST: python -m comlang (laptop for MVP-1, Raspberry Pi 5 inside the box later)
                  │  speech    Vosk speech-to-text (offline) → final phrases only
                  │  session   word queue, touch cues, modes, Reset, interlock, speaker-display content
                  │  engine    text → strokes → controller commands (mirrored x); text → Braille cells
                  ▼
        USB CDC serial, one ASCII line per message (comlang/protocol.py)
                  │
  [BOX CONTROLLER: Raspberry Pi Pico (RP2040) running firmware/mcu, C]
     motion queue + CoreXY + 10 kHz motor control · pen PWM · controls + safety · LCD · Braille
     │3-phase PWM ×2  │SSI        │PWM        │GPIO in                 │SPI            │shift-out
 [2 × DRV8313]   [3 × MT6701  [MOSFET]   [roller press, Repeat,  [3.5" IPS LCD]  [12 latching
     │            encoders]      │        Mode, Reset, hand pad,                  Braille pins]
 2 × flat BLDC ◄─────┘   mini solenoid    2 home switches]
 (CoreXY belts) ──► gantry ──► carriage ──► wedge ──► pen ──► cover ──► palm
```

**Who does what, and why.**

| Layer | Runs | Does | Why there |
|---|---|---|---|
| **Firmware** (`firmware/mcu`, C) | RP2040 in the box | CoreXY kinematics and closed-loop control of the two BLDC motors (FOC, torque-limited), acceleration, pen solenoid (pull-in, then hold current), homing and soft limits, debouncing every control, **the safety rules** (hand pad, Reset, wheel pause act locally, within one loop), Braille cell output **in step with the pen**, drawing the speaker display, watchdog | Hard real time (a 10 kHz motor control loop) and safety must not depend on a laptop or a Linux scheduler. A hung host can never leave the pen moving: the controller only executes what is queued, and the watchdog resets it (pen off) if its own loop stalls |
| **Device software** (`comlang/`, Python) | Laptop / Pi 5 | Speech recognition, language (words, letters, Braille Grade 1), the stroke font and path planning, the word queue, cues, modes, what the speaker display shows | Speech models, text handling and the companion app are host jobs; none of it needs microsecond timing |
| **Demos** (`demos/`) | Any PC | The companion app, with the box **simulated by running the real firmware** on the PC (§7.2) | Show and test the product without hardware |

**Signal conventions**
- Positions in controller commands are in 0.01 mm **relative to the palm centre** (work zero). The controller homes against its switches and holds the palm centre in machine coordinates (`O`, from calibration, §9). Machine x is **mirrored**: `x = −palm_x` (P1).
- Pen: the controller drives the solenoid MOSFET with PWM: full current for 30 ms (pull-in), then 40 % (hold).

---

## 4. Mechanical design

### 4.1 Coordinate system and key dimensions

The origin is at the centre of the box front edge, on the table. +x is the user's right, +y points away from the user, +z is up. Units are mm. For the right hand, the thumb is on −x.

![top layout](renders/v2_top.png)

| Feature | Value |
|---|---|
| Box outside | **260 (W) × 380 (L) × 20 (H)**, vertical corners R12. The rear 70 mm is the speaker strip |
| Base / walls / top plate | 1.5 aluminium sheet / 2 / 5 (top plate = 2.5 mm aluminium floor layer + 2.5 mm recess layer, §4.2) |
| Plate underside / palm surface / top | z = 15 / **17.5** / 20. **Recess depth 2.5** |
| Wrist crease line | y = 100 |
| **Writing centre** (palm centre) | **(0, 155)** |
| **Window** | **84 × 84**, R8, centred on (0, 155) |
| **Cover cassette** | 100 × 100, R10, in a 1.5 mm pocket in the floor layer (1.0 mm ledge); fingernail notch at (0, 104) |
| **Thumb scroll roller** | Ø6 × 10 knurled roller, crown 2.5 mm above the recess floor (flush with the top), centre (−91.2, 157.3), rolls along (−0.84, 0.55), i.e. the thumb's axis when it rests on it |
| **Repeat** (little finger) | Ø26 cap, top flush with the top surface, (60.9, 225.4) |
| **Mode** (free hand) | Ø24 cap in a 3 mm pocket, (−93, 42) |
| **Reset** (speaker) | Ø20 cap in a 3 mm pocket, (45, 340) |
| **Speaker display** | 3.5" IPS module 85 × 55 × 6 in a pocket, centre (−25, 340), glass 1 mm below the top |
| Braille cell, index / middle fingertip (medium hand) | (−35.4, 259.7) / (−10.0, 269.4), slider ±25 mm (P10) |
| Hand-present pad (wrist channel floor) | (0, 75), Ø24 |
| Mic grille / status LED | 4 × 4 holes Ø2.4 at x 80…95, y 328…343 (faces the speaker) / Ø4 at (108, 345) |
| Forearm pad | 120 × 140 × 17.5, in front of the box (y −142…−2) |

**Glove-shaped recess** (cut through the 2.5 mm upper layer; floor at z 17.5). It is generated from the hand model (§4.6), not drawn by hand:
- **Palm of the glove:** convex hull of the palm sections and digit roots of the small, medium and large hands, + 5 mm.
- **Glove fingers:** for each digit, the convex hull of its joints over all three hands, grown by the largest joint radius + 5 mm. One smooth channel per digit; the plate left standing between the channels guides the fingers.
- Wrist channel: 80 wide, from the front edge (y 0) to y 100.
- The cover cassette footprint (+2 mm), so the cassette can always be lifted out.
- Control access: the path from each resting fingertip to its control and the pressed pose (+3.5 mm), plus bays of cap radius + 5 mm (Repeat) and + 17 mm (roller, which also holds the incised + / − / ‖ marks).
- Top edge rounded R1.2 (modelled).
- Export the outline from the CAD (`TopPlate` → top face → DXF) rather than redrawing it.

![section](renders/v2_section.png)

### 4.2 Enclosure

![exploded](renders/v2_exploded.png)

| Part | Material and process (MVP) | Notes |
|---|---|---|
| **F01 Base** 260 × 380 × 1.5 + **walls** 2 mm, 15 tall | **Base:** 1.5 mm aluminium sheet, CNC/laser-cut, tapped for the rod supports, motors and idler posts; it is also the motor heat sink. **Walls:** 3D-printed or aluminium extrusion frame | The base is the gantry datum: flat to ±0.2 mm. Rear wall: 9 vent slots 10 × 4, USB-C (12 V PD + data) at (90, rear, z 6) |
| **F02 Top plate, floor layer** 260 × 380 × **2.5** aluminium | CNC-machined (pockets), anodised black | Window 84 × 84 R8. **Cover pocket** 100.4 × 100.4 × 1.5 + notch. Roller slot + underside pocket for its cradle and sensor, switch plunger holes, Braille pin holes Ø1.6 (12×), display cable slot, mic holes, LED, pad pocket. Stiff enough at 2.5 mm to carry a resting hand |
| **F03 Top plate, recess layer** 260 × 380 × **2.5** | Black soft-touch PC/ABS, laser- or water-jet-cut, bonded to F02 | **Glove recess cut through**, R1.2 edge. Pockets: Mode and Reset (Ø29 × 3 deep), display (86 × 56 × 7 deep, through into F02). **+ − ‖** marks incised around the roller |
| **F05 Cover cassette** | Frame: 1.2 mm stainless, laser-cut, 100 × 100, opening 84 × 84. Membrane: 0.3 mm (T13 material) stretched and bonded on top | Drops into the pocket, top flush with the recess floor. One cassette per test material |
| **F04 Forearm pad** 120 × 140 × 17.5 | Printed or plywood + 8 mm EVA foam + vinyl cover | Separate part, level with the recess floor |
| Feet | 4 × Ø12 × 1.5 silicone pads | |

**Colour and finish:** matte black body and top plate, light-grey control caps (visible to sighted helpers) with raised symbols, red Reset, one warm accent (the hand-present pad).

### 4.3 XY gantry: flat CoreXY with two flat BLDC motors (the 20 mm design)

![cut-away](renders/v2_cutaway.png)

**Why v0.3 (first build) was 54 mm tall.** It used four rotating Ø8 perimeter shafts as rails *and* drive shafts, with GT2 belts looping vertically round pulleys on them (two layers 16 mm apart), and two NEMA14 steppers lying on the floor (35 mm). The motors set the height.

**What the 20 mm design does.**
- **CoreXY kinematics.** Two belts, both lying **flat** (GT2 3 mm, width vertical) in two layers: belt A at z 2–5, belt B at z 5.5–8.5. Motor A moves the pen along x + y, motor B along x − y; the firmware converts (§6). No belt loops stand up, so the drive needs only 7 mm of height.
- **Two flat gimbal BLDC motors** (2804 class, Ø28 × 10.5) stand on the base with their shafts vertical. A GT2 50T ring pulley (pitch Ø31.8) on each rotor carries the belt directly, so 250 mm/s needs only 150 rpm, where gimbal motors are strong. **Magnetic encoders** (14-bit) close the position loop in the firmware: no lost steps, quiet, and the torque is limited so the carriage can push with **at most ~3.5 N** (pinch-safe; a blocked carriage is detected and released, §6).
- **Gantry:** two Y-blocks slide on **Ø5 Y-rods** (iglidur bushings) at x ±108; a bridge over the belt runs holds the **twin Ø5 X-rods** (y ±7 about the gantry centre) and, hanging below it, the gantry idlers of both belts. The **carriage** slides on the twin X-rods and clamps belt A (front lug) and belt B (rear lug). The pen sits at the carriage centre, between the rods.
- **Belt routing:** belt A runs from the carriage to the gantry idlers, along both sides (x ±98) to the rear, round motor A (rear left, (−82, 238)) and the rear-right idler (93, 249). Belt B runs from the carriage to the gantry idlers, along both sides to the front, round motor B (front right, (82, 72)) and the front-left idler (−93, 61). Each belt ~0.6 m, both ends clamped on the carriage.
- The pen lifter lies **flat** on the carriage (§4.4).

![section detail, pen down](renders/v2_section_detail.png)

**Z stack** (from the table):

| Item | z (mm) |
|---|---|
| Base (aluminium) | 0–1.5 |
| **Belt A** (lower layer) + its idlers and motor-A ring | **2.0–5.0** |
| **Belt B** (upper layer) + its idlers and motor-B ring | **5.5–8.5** |
| **Y-rods** Ø5 (sides) | **7.0** (4.5–9.5) |
| **X-rods** Ø5 (twin) | **10.5** (8–13) |
| Y-blocks / gantry bridge | 2–12.5 / 9.5–13.5 |
| Carriage | 7–14, lugs down to the belts |
| Flat BLDC motors | 1.5–12 |
| Pen tip, retracted / pressed | 14.0 / 19.0 |
| Top plate | 15–20: floor layer 15–17.5 (palm rests at **17.5**, on the cover over the window), recess layer 17.5–20 |

Everything moving clears the plate underside by ≥ 1 mm (checked over the whole workspace).

**Travel.** Pen: ±35 mm about (0, 155). Gantry centre y 120…190; carriage x ±35.
**Resolution.** 14-bit encoder on a 31.8 mm ring: 0.006 mm of belt per count. On the simulated board the pen follows the commanded path within 0.05 mm (median) / 0.16 mm (95 %) while writing.
**Belts.** GT2 3 mm (low-stretch, glass or aramid cord). Tension so a run deflects ~1 mm under a light finger; the position loop takes up the rest.

### 4.4 Pen actuator and tip

![section detail, pen up](renders/v2_section_detail_up.png)

| Item | Spec |
|---|---|
| Lifter | 12 V **mini push frame solenoid** (~16 × 7 × 6 mm, 6 mm stroke) lying flat on the carriage. Its plunger pushes a wedge under a roller on the pen: 5 mm lift. Return spring retracts the pen when unpowered. Flyback diode |
| Stroke | 5.0 mm: tip at z 14.0 (1 mm below the plate underside, 3.5 mm below the cover) → z 19.0 (1.5 mm above the floor, pressing the membrane into the skin) |
| Pen | Ø3 stainless rod, 11 mm, with interchangeable tips, in a Ø6 sleeve at the carriage centre |
| **Force limiter** | Compression spring between the wedge roller and the pen: ~0.3 N/mm, preload 0.2 N → 0.8 N max. Shims set 0.3–1.0 N. Force never depends on solenoid strength. *Calibrate with the cover fitted* |
| Tips (P2) | T05: 0.5 mm radius point. T10: 1.0 mm radius. T20: Ø4 ball. Option: rolling Ø3 ball |
| Hold current | Full current for 30 ms (pull-in), then 40 % PWM (`firmware/mcu/src/config.h`) |

### 4.5 Hand interface

| Element | Implementation |
|---|---|
| Glove recess | 2.5 mm deep cut-out in F03 (§4.1), edge R1.2. The plate between the glove fingers guides the fingers |
| **Cover** | Drop-in cassette (F05) over the window, membrane top flush with the recess floor. The pen presses it 1.5 mm into the palm. The membrane must sag **< 2.5 mm** under a resting palm so it never touches the retracted pen (3.5 mm below). Swap cassettes to run T13. Clean with 70 % isopropyl alcohol |
| **Thumb scroll roller** (D17) | Ø6 × 10 knurled roller (12 ribs = 12 detents/rev) in a slot, crown 2.5 mm above the recess floor (flush with the top). A diametric magnet in the roller end and a **magnetic angle sensor** (MT6701) read the roll; the roller cradle pivots onto a side tact switch for **press = pause**. Roll away = faster (+0.1× per detent), roll in = slower. **+** (far end), **−** (near end) and **‖** (beside it) are **incised** in the recess floor: the thumb lies over them, so raised marks would press into it. The thumb swings out 22° to reach it (all sizes) |
| **Repeat** | Ø26 cap, top flush with the top surface (2.5 mm above the recess floor), **raised circular arrow** (1.4 mm line, arrowhead). Ø10 stem onto a 6 × 6 mm low-profile tactile switch (2.5–3.5 N) under the plate |
| **Mode** (free hand) | Flat Ø24 cap in a 3 mm pocket at the front corner on the thumb side, top 1 mm below the surface. Raised **6-dot Braille cell + pen stroke**. 6 × 6 switch |
| Symbols (D18, P11) | Caps: lines 1.4 mm wide, raised 0.8 mm (or etched), 12–17 mm. Print the caps with the symbol on top (resin), so the edges are crisp |
| Control reach | From the hand-model study (§4.6). Validate with real users in T11 |
| Hand-present pad | Ø24 brass disc inlaid 0.4 mm into the wrist-channel floor, capacitive touch module (TTP223 type) |
| **Pop-out Braille** | 2 cells × 6 pins, 2.5 mm pitch, pins Ø1.4 rising **0.7 mm** out of the recess floor under the index and middle fingertips. Each cell is a block of six **latching (bistable) pin actuators**, 9 × 12 × 7 mm, under the plate: a 4 ms current pulse pushes a pin up or pulls it flush, and it stays without power. Dots 1–3 on the reader's left (−x), dot 1 furthest away |

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

| Size | Rest fit | Thumb roller | Repeat (little finger) | Palm centre vs writing centre | Fingertips vs Braille cells |
|---|---|---|---|---|---|
| small | no clash | swing 22°, presses | swing 32°, presses | −9.6 mm | 23 mm short |
| medium | no clash | swing 22°, presses | swing 39°, presses | −2.8 mm | on the cells |
| large | no clash | swing 22°, presses | swing 46°, presses | +1.4 mm | 14 mm beyond |

![control use](renders/v2_button_press.png)

**Why speed went on the thumb roller, and Mode to the free hand.** The study searched every digit and swing direction for positions that all three hand sizes reach and that clear the resting hand by 2 mm:
- **Thumb:** outward swing ~20°. This is the only comfortable spot, and it is the best one, so the roller combines speed and pause there.
- **Little finger:** outward swing 32–46°, used by Repeat.
- **Index and middle:** only reachable at 33° and 55° swings, above the comfort limits in R-E2. They also rest on the Braille cells.
- **Ring:** only press-down under the fingertip. This was the v0.2 Speed bar. A single press can't give up *and* down, so it was dropped.

So the resting hand has two good control positions. The thumb roller puts three functions on one of them. Mode is rare, so it went to the free hand (P13).

**Known limits.** Joint angles are estimates. Real hands vary in proportion. The 46° little-finger swing for large hands is near the limit. Test T11 with real users is what counts.

### 4.7 Fabricated parts list

| ID | Part | Qty | Material / process | Key dimensions |
|---|---|---|---|---|
| F01 | Base + walls | 1 + 1 | 1.5 mm aluminium (CNC/laser) + printed or extruded walls | 260 × 380, walls 2 × 15, R12 |
| F02 | Top plate, floor layer | 1 | 2.5 mm aluminium, CNC, black anodised | 260 × 380, §4.2 |
| F03 | Top plate, recess layer | 1 | 2.5 mm black PC/ABS, laser / water-jet | Glove recess, pockets |
| F04 | Forearm pad | 1 | Printed / plywood + EVA | 120 × 140 × 17.5 |
| F05 | Cover cassettes | 1 per material | Stainless frame + membrane | 100 × 100 × 1.5 |
| F20 | Caps: Repeat, Mode, Reset; scroll roller | 3 + 1 | Resin print | Ø26 / Ø24 / Ø20 with raised symbols; roller Ø6 × 10, 12 ribs, magnet pocket |
| F21 | Switch / sensor flex PCBs | 4 | Flex or 0.8 mm FR4 | Under F02 |
| F10 | Y-rod supports | 4 | Aluminium or PETG | 10 × 8 × 8.5, rod axis z 7 |
| F12 | Y-blocks + bridge (idler axles, X-rod clamps) | 2 | PETG/nylon (or machined), iglidur J Ø5 bushings | 15 × 28 × 10.5 + bridge 12 × 40 × 4 |
| F14 | Carriage + pen head (sleeve, solenoid seat, wedge guide, belt lugs) | 1 | Nylon print, 2 × iglidur J Ø5 bushings | 24 × 20 × 7 + lugs |
| F15 | Motor and idler posts | 4 | Aluminium, tapped into the base | |
| F16 | Wedge + roller | 1 | POM / steel pin | 5 mm lift |
| F18 | Pen + tips | 1 + 3 | Stainless | Ø3 × 11 |

### 4.8 Purchased parts (BOM)

| # | Item | Qty | Spec / note |
|---|---|---|---|
| 1 | Rod Ø5 h6, hardened | 4 | 2 × 128 (Y-rods), 2 × 190 (X-rods) |
| 2 | iglidur J bushing Ø5 × 7 | 6 | Y-blocks (2 each), carriage (2) |
| 3 | GT2 3 mm belt, low-stretch | 1.5 m | Two open belts, ~0.6 m each |
| 4 | GT2 idler, 16T, 3 mm, Ø3 bore | 6 | 4 on the gantry, 2 at the corners |
| 5 | GT2 50T ring pulley, 3 mm (pitch Ø31.8), for the motor rotor | 2 | Bonded / screwed to the rotor can |
| 6 | **Flat gimbal BLDC motor, 2804 class, hollow shaft**, Ø28 × ≤ 10.5 | 2 | 7 pole pairs, ~10 Ω, ≥ 0.06 N m peak at 12 V |
| 7 | **MT6701 magnetic encoder** (SSI) + diametric magnet | 3 | 2 motors + scroll roller |
| 8 | **DRV8313** 3-phase driver (8–60 V) | 2 | Voltage-mode FOC from the Pico |
| 9 | **Raspberry Pi Pico (RP2040)** | 1 | The box controller, runs `firmware/mcu` |
| 10 | 12 V mini push frame solenoid, 6 mm stroke | 1 | §4.4 |
| 11 | Logic-level MOSFET + flyback diode | 1 | SOT-23 class, 1 A |
| 12 | Micro limit switch | 2 | X-min, Y-min |
| 13 | **Latching Braille pin actuators** | 12 | Bistable, ≤ 7 mm tall, 2.5 mm pitch (or 2 ready-made 6-pin latching modules); supplier to select (R12) |
| 14 | H-bridge pin drivers + 3 × 74HC595 | set | 24 outputs for the 12 pins (up / down) |
| 15 | 6 × 6 mm tactile switch, low profile (≤ 2.5 mm), 2.5–3.5 N | 4 | Repeat, Mode, Reset, roller press |
| 16 | **Controller board** 70 × 46 × 6 | 1 | Pico, 2 × DRV8313, MOSFET, Braille drivers, USB-C PD trigger (12 V), 12 → 5 V (CAD part "Controller", §5.2) |
| 17 | **3.5" IPS SPI display 480 × 320, ST7796S** | 1 | Speaker display, drawn by the controller |
| 18 | TTP223 module + Ø24 brass disc | 1 | Hand-present |
| 19 | MEMS microphone module (USB) | 1 | Under the grille, or external |
| 20 | 12 V USB-C PD supply (≥ 36 W) | 1 | |
| 21 | Cover membrane samples | set | T13 list (§10) |
| 22 | M2 screws, inserts, compression springs for the Ø3 pen | set | |
| 23 | **Phase 2:** Raspberry Pi CM5 + flat carrier (a Pi 5 board is too tall) | 1 | Standalone |

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
| 2 × flat BLDC via DRV8313 (6 V phase limit, ~10 Ω) | 12 V | 2 × 0.6 A |
| Pen solenoid | 12 V | ≤ 1 A pull-in (30 ms), ~0.4 A hold (40 % PWM) |
| Braille latching pins | 12 V | ~0.3 A per pin, 4 ms pulses only |
| Controller (Pico) + encoders + TTP223 + display | 5 V (from 12 V on the board) | < 0.35 A |
| CM5 (phase 2) | 5 V / 3 A buck | ≤ 2.5 A |
| **Total** | **12 V (USB-C PD)** | ≈ 2.5 A (MVP), ≈ 3.5 A with the CM5 |

### 5.2 Wiring (MVP): one controller board

The **controller board** (CAD part "Controller", 70 × 46 × 6 mm, front of the base) holds the Pico, two DRV8313 three-phase drivers, the pen MOSFET, the Braille pin drivers and the USB-C PD input. All 26 Pico GPIO are used; pin numbers are `firmware/mcu/rp2040/hal_rp2040.c`.

| From | To (Pico GPIO) | Note |
|---|---|---|
| USB-C PD (12 V) | Board V+ → DRV8313 VM, solenoid, Braille drivers; 12 → 5 V buck | 3 A polyfuse. The same USB-C can carry the host link |
| X-min / Y-min switches | GP0 / GP1 | Normally open to GND, internal pull-up |
| Motor A phases U / V / W | GP2 / GP3 / GP4 (PWM slices 1A, 1B, 2A) | DRV8313 #1, 25 kHz centre-aligned |
| Motor B phases U / V / W | GP5 / GP6 / GP7 (PWM slices 2B, 3A, 3B) | DRV8313 #2 |
| Pen MOSFET gate | GP8 (PWM 20 kHz) | Flyback diode across the coil |
| TTP223 hand pad | GP9 | High = hand present |
| Encoders (MT6701 ×3, SSI) | SCK GP10, MISO GP12, CS GP13 (motor A), GP14 (motor B), GP15 (roller) | SPI1, read only from the control interrupt |
| Braille pin drivers (3 × 74HC595 → 12 H-bridges) | Data GP11 (SPI1 MOSI), clock GP10 (shared), latch GP21 | Also driven only from the control interrupt; outputs change on latch |
| LCD (ST7796S) | SPI0: SCK GP18, MOSI GP19, CS GP17, DC GP16; reset on the RUN line; backlight tied on | ~30 cm ribbon to the rear: 20 MHz |
| DRV8313 enable (both) | GP20 | High = drivers on; off = motors free-wheel |
| Roller press, Repeat, Mode, Reset | GP22, GP26, GP27, GP28 | To GND, pull-ups |
| Pico USB, mic USB | Laptop (MVP) / CM5 (phase 2) | The controller's only link to the host |

### 5.3 Electrical safety
- Only 12 V DC enters the box (USB-C PD).
- The motor torque is limited in firmware (phase voltage ≤ 6 V, `TORQUE_LIMIT`), so the gantry can push with at most ~3.5 N, and a blocked carriage releases within ~60 ms (§6).
- The cover keeps fingers away from the moving parts; the hand pad, Reset, stall detection and the watchdog stop the pen in the controller itself (§6).

---

## 6. Firmware (box controller, `firmware/mcu`)

C11, one source tree for two targets: the **real board** (RP2040, Pico SDK) and the **simulated board** (the same code built for the PC with a model of the hardware; the demo app and the tests run it, §7.2). Only the hardware layer differs.

| File | Role |
|---|---|
| `firmware/mcu/src/hal.h` | Everything the firmware needs from the board: motor angle and torque, switches, pen PWM, buttons, roller counts, hand pad, Braille pulses, LCD fill, USB link, time, critical sections |
| `firmware/mcu/src/motion.c` | Command queue (256), executed by the 10 kHz tick: trapezoidal moves (3000 mm/s², ≤ 250 mm/s) as position targets with feed-forward acceleration, settle at each end point, dwells, pen, Braille; homing; soft limits; speed override; smooth hold / resume; stall → stop |
| `firmware/mcu/src/servo.c` | CoreXY (a = x + y, b = x − y) and per-motor PID + feed-forward on the encoder positions, torque-limited; following error > 1.5 mm for 60 ms = **stall**: motors released |
| `firmware/mcu/src/braille.c` | Latching pins: energises only the pins that change, 4 ms pulses, then no power |
| `firmware/mcu/src/controls.c` | Debouncing, the scroll roller, the **safety rules** (below), control reports |
| `firmware/mcu/src/display.c` | Draws the speaker display from the host's `W/T/P/S` messages (current letter highlighted, transcript, struck-through words, status) |
| `firmware/mcu/src/link.c`, `fw.c` | Line protocol, main loop, status and progress reports |
| `firmware/mcu/src/generated.h` | **Generated** from the host code by `tools/gen_firmware_tables.py`: control actions, modes, speeds, acceleration, pen timing, display font |
| `firmware/mcu/rp2040/` | Real board: pins, 2 × three-phase PWM with voltage-mode **FOC** and rotor alignment at power-up, MT6701 encoders, SPI LCD (ST7796S), Braille drivers, watchdog, 10 kHz timer |
| `firmware/mcu/sim/hal_sim.c` | Simulated board: stdin/stdout as the USB link; a **physics model** of the two motors (torque limit, rotor inertia), the CoreXY belts, carriage and gantry masses, friction, home switches and hard stops, 14-bit encoders; solenoid, buttons, roller, hand pad, latching Braille pins (move only on a long enough pulse), an obstruction input (`jam`) and a 480 × 320 LCD framebuffer |

**Safety rules (in the firmware, not the host).**
1. A queued command starts only while **(hand present and armed)**, or when the hand sensor is configured off (bench only).
2. **Hand removed:** stop at once (queue dropped, pen off), hold, disarm. Report `hand_off`.
3. **Re-arm** only by pressing the roller **with the hand on the pad**. No hand at power-up = held and disarmed.
4. **Reset button:** stop at once, pen off, report `reset` (the host then sends the correction cue).
5. **Roller press:** hold / resume immediately (smooth 50 ms stop; the pen lifts while held and goes back down before continuing), report `pause`.
6. **Stall / obstruction:** if the carriage cannot follow (something blocks it), the motors are released within ~60 ms, the queue is dropped, the pen lifts and the box holds; report `err stall`. The roller press resumes. The torque limit caps the push force at ~3.5 N before that.
7. **Watchdog** 200 ms: a stalled loop resets the controller; the pen and motors are off at reset.

The host follows the controller: every control is reported (`E <action>`) and the session reacts the same way, so the two never disagree (tested, §7.6).

**Commands** (full list in `comlang/protocol.py`): queued `m x y v`, `p 0|1`, `d ms`, `b m1 m2`; immediate `!`, `H`, `R`, `V %`, `G`, `O x y`, `C hand_sensor 0|1`, `?`, and the display messages. One letter "I" at 45 mm, as sent by the device software (`event_commands` in `comlang/engine.py`):

```
b 10 0           ; Braille cell for I (dots 2 4), shown as the pen starts the letter
m 0 2250 250     ; travel to the top of the stroke
p 1              ; pen up into the palm
d 80             ; settle
m 0 -2250 120    ; draw at 120 mm/s
p 0              ; retract
d 80
```

**Build and flash.**

```
cmake -S firmware/mcu -B build/mcu-sim && cmake --build build/mcu-sim          # simulated board
cmake -S firmware/mcu -B build/mcu-rp2040 -DCOMLANG_TARGET=rp2040 -DPICO_SDK_PATH=~/pico-sdk
cmake --build build/mcu-rp2040        # → comlang_mcu.uf2: hold BOOTSEL, plug in, copy to RPI-RP2
```

**State.** The simulated build compiles warning-free (`-Werror`) and passes the full-stack and firmware-safety tests (homing, writing within 0.16 mm, hand, Reset, stall). The RP2040 sources type-check against the Pico SDK API, but **the RP2040 build has not been compiled or run yet** (no ARM toolchain where it was written). Bring-up order on the bench: USB link and `?` → buttons, roller, hand pad (`E` reports) → pen PWM → encoders (turn the motors by hand, `?`) → one motor at low `TORQUE_LIMIT`, alignment, then position loop gains → CoreXY, homing → LCD → Braille. Tune `KP/KD/KI` on the real motors.

---

## 7. Software

The software has **two sections**, plus the firmware they both talk to:

| Section | Folder | What it is | Runs on |
|---|---|---|---|
| **A. Device software** | `comlang/` + `firmware/mcu` | The product: the host program (speech → session → controller protocol) and the box controller firmware (§6) | Host: laptop (MVP-1), Raspberry Pi 5 (phase 2). Controller: RP2040 |
| **B. Demos** | `demos/` (+ the CAD tools) | The companion app with the live 3D simulation, the palm-writing preview, the cover-material test, the renders | Any PC, with or without the box |

**Rule: the demos are built on the device software, never beside it.** Everything the box *does* lives once: language, queue, cues, modes and display content in `comlang/`; motion, pen, controls, safety and display drawing in `firmware/mcu`. A demo may only *show* it or *feed* it. **The demo's simulation is the real firmware**, built for the PC (§7.2), so the demo cannot show behaviour the product does not have. `tests/test_sync.py` enforces all of this (§7.6).

```
                ┌────────────────── A. comlang/ (host) ─────────────────┐      ┌── firmware/mcu (C) ──┐
 mic ─► speech ►│ session.Session ── engine (font, Braille, planner)    │      │ motion · controls ·  │
 typed / stdin ►│   ▲ handle(action)        │ sinks                     │ USB  │ safety · LCD ·       │
                │   │                       └─► devices.mcu.Mcu ────────┼─────►│ Braille              │
                │   └──── E <action> ◄──────────────────────────────────┼──────│                      │
                └───────────────────────────────────────────────────────┘      └──────────┬───────────┘
                                                                     real board: RP2040 + box hardware
                                                                     demo/tests: comlang_sim + hardware model
 B. demos/haptic_app.py = the same Session + Mcu, talking to comlang_sim; draws the 3D view, palm view,
    Braille cells and speaker display from what the simulated hardware does
```

### 7.1 A. Device software (host)

| File | Role |
|---|---|
| `comlang/engine.py` | Text → touch: stroke font (37 glyphs), cues (tap, long tap), `Planner` (timed path), Braille Grade 1, controller commands (`event_commands`) |
| `comlang/session.py` | `Session`: word queue, transcript, the controls (`handle(action)`), touch cues, modes, Reset, hand interlock, speed, display state. Outputs go to *sinks*; it waits while the controller is `busy()` so the host never runs ahead of the pen |
| `comlang/protocol.py` | **The link definition**: control actions (`faster slower pause repeat mode reset hand_on hand_off`), modes, every host ↔ controller message. The firmware's tables are generated from it |
| `comlang/speech.py` | Offline speech-to-text (Vosk), final phrases only |
| `comlang/devices/mcu.py` | The controller driver: events → queued commands, Braille → queued `b` (so the cells change exactly when the pen reaches the letter), pause / speed / stop → immediate commands, display mirroring, progress (`X`) and status (`A`); calibration helpers |
| `comlang/devices/sim.py` | Builds and runs the simulated board (`build/mcu-sim/comlang_sim`) and exposes its hardware: press buttons, roll the roller, lift the hand, block the carriage; read the solenoid, the Braille pins, the LCD pixels |
| `comlang/devices/console.py` | Prints the commands instead (`--dry-run`) |
| `comlang/runtime.py` | The headless program: `python -m comlang` |
| `tools/gen_firmware_tables.py` | Writes `firmware/mcu/src/generated.h` from `engine.py` and `protocol.py` |

**Running the box.**

```
cd haptic-box
python3 -m comlang --list-ports
python3 -m comlang --board auto --listen                 # the real box, speech in
python3 -m comlang --board sim --text "hello there"      # the same, on the simulated firmware
python3 -m comlang --dry-run --text "hello there"        # no controller: print the commands
```

Typed lines on stdin are written like speech. Lines starting with `/` are operator commands: `/pause /repeat /faster /slower /mode /reset /skip /clear /hand_on /hand_off /quit`, and for calibration `/home /goto X Y /pen 0|1 /centre X Y /where` (§9).

**Link** (`comlang/protocol.py`, USB CDC, one ASCII line per message):

| Direction | Message | Meaning |
|---|---|---|
| host → box, queued | `m x y v` · `p 0\|1` · `d ms` · `b m1 m2` | Move (0.01 mm from the palm centre, mm/s) · pen · dwell · the two Braille cells (6-bit masks) |
| host → box, immediate | `!` · `H` / `R` · `V %` · `G` · `O x y` · `C hand_sensor 0\|1` · `?` | Stop now · hold / resume · speed override · home · palm centre · config · status |
| host → box, display | `W <letters> <k>` · `T <words>` · `P <text>` · `S <mode>\|<waiting>\|<paused>\|<hand>` | Word + current letter · transcript (`*` current, `+` waiting, `~` cancelled) · speech not yet final · status line |
| box → host | `E <action>` | A control: roller away = `faster`, roller in = `slower`, roller press = `pause`, Repeat = `repeat`, Mode = `mode`, Reset = `reset`, hand pad = `hand_on` / `hand_off` |
| box → host | `X n` · `A …` · `err stall` · `err …` | Commands finished so far · status (position from the encoders, pen, hold, armed, hand, homed, queue, cells) · the carriage was blocked (the session pauses and keeps the word) · other error |

**Timing and synchronisation.** The session sends each event's commands when the controller has finished the previous one (`X` caught up), so at most one letter is queued. The Braille cell command is queued just before the letter's strokes, so the controller changes the cells at the instant the pen starts that letter. Speed changes go to the controller as an override (`V`); pause, Reset and the hand pad act in the controller first and are mirrored by the session.

### 7.2 B. Demos

| File | Role |
|---|---|
| `demos/haptic_app.py` | The ComLang companion app (Tkinter): the device software's `Session` + `Mcu`, talking to the **simulated board** (or a real one). Live 3D CAD view, palm view, Braille view, speaker display, cover-material test (§7.5) |
| `demos/palm_writer.py` | Palm-writing preview GIF, command export and the v0.1 5-bar linkage maths, on top of `comlang/engine.py` |
| `haptic_box_v2.FCMacro` | Prototype CAD + clearance checks + STEP + mesh export (hardware source of truth) |
| `hand_model.py` | Hand + forearm model (3 sizes), control placement and reach maths, **glove outline** |
| `cad_render.py` | Numpy renderer, also the app's live 3D view |
| `render_views.py` | All the images in this document |
| `start.sh` | One-command launcher for the demo app |

**Running the demo.**

```
cd haptic-box
./start.sh
```

This creates `.venv`, installs `numpy vosk sounddevice pyserial`, rebuilds `build/v2_mesh.json` with FreeCAD when the CAD changed, and starts the demo app. The app builds the simulated firmware with CMake and a C compiler on first start (a few seconds). The first **Listen** downloads the small en-us model (~40 MB).

**How the simulation works.** The app does not simulate the box itself. It starts the controller firmware built for the PC (`comlang_sim`) and talks to it over the same protocol as a real board:
- **Pen and gantry** are drawn from the position the firmware measures with its motor encoders (status polled every 30 ms), i.e. the result of the simulated motors, belts and masses; ink appears where the firmware's solenoid output is on.
- **Block the pen (J)** puts a simulated obstruction on the carriage: the firmware detects the stall, lifts the pen and holds; the roller press resumes.
- **Braille cells** show the firmware's cell output.
- **Speaker display** shows the firmware's own LCD pixels (480 × 320, drawn by `display.c`).
- **Box controls** in the app (Pause, Repeat, Faster/Slower, Mode, Reset, the hand checkbox, and their keys) **press the simulated hardware**: the firmware debounces them, applies the safety rules and reports them back, exactly as on the box.
- The carriage starts at an unknown position, so every start shows the firmware **homing** first.
- **Use real board** swaps the simulated board for a real controller on USB; nothing else changes.

**Controls.**

| Action | Demo key / button | On the box (action) |
|---|---|---|
| Pause / resume | Space | Press the thumb roller (`pause`) |
| Faster / slower | `+` / `−` | Roll the roller away / in (`faster` / `slower`) |
| Block the pen (simulated obstruction) | J, or "block the pen" | Stall detection (`err stall`) |
| Repeat word | R | Repeat, little finger (`repeat`) |
| Mode: palm + Braille → palm → Braille | M | Mode, free hand (`mode`) |
| **Reset** (speaker: output is wrong) | Esc, or the red button on the speaker display | Reset, speaker (`reset`) |
| Hand on / off the box | H, or "on the box" | Hand-present pad (`hand_on` / `hand_off`) |
| Skip to the newest phrase / clear all | S / C | runtime `/skip`, `/clear` |
| Listen on/off | L | runtime `--listen` |
| **Speaker display** window | D | Built-in display |
| **Cover-material test** (T13) | T | — |

![app](renders/app_screenshot.png)

**Speaker display window**: the box's display exactly as the firmware draws it (shown 2×), with big **Reset** and **Pause** buttons that press the simulated box's Reset and roller. With a real board, the app draws the same `W/T/P/S` messages itself.

![speaker display](renders/app_speaker_display.png)

### 7.3 Text → touch rules (`comlang/session.py`, `comlang/engine.py`)
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

- **Reset** stops the pen at once (in the controller: queue dropped, pen off), drops the current and queued words, shows them struck through on the speaker display, and sends the correction cue.
- **Hand-present interlock.** The hand leaving the pad (`hand_off`) stops the pen at once (the controller drops its queue, pen off) and the session puts the current word back at the front of the queue. Writing resumes only when the hand is back **and** the user presses the roller. With no hand at power-up the box starts in this stopped state.

### 7.4 To do before user trials (MVP-1 gate)

| # | Item | State |
|---|---|---|
| 1 | Hand-present interlock | Done in the firmware (§6, safety rules) and mirrored in the session; tested on the simulated board. Verify T5 on hardware |
| 2 | Calibration (home, jog, set the palm centre, test letter, §9) | Done as runtime commands; a demo panel on top of them is open |
| 3 | Speaker display | Done (`firmware/mcu/src/display.c`). ST7796S init and orientation unverified on hardware |
| 4 | Controller firmware on the RP2040 | Written; **compile and bring up** on the bench (§6) |
| 5 | Braille driver (phase 2) | Host and firmware done (`b` commands, shift-out); bit order to check against the chosen cells |
| 6 | Hold current after pull-in | Done (30 ms full, then 40 % PWM); tune on the bench |

### 7.5 Cover-material test (demo app; supports D15 / T13)

**Cover test** (key T) runs the recognition experiment:
1. Enter the participant, cover material (list of candidates, editable), pen tip, force and letters per block.
2. **Start block.** The app switches to palm-only mode and writes random letters one at a time. Letter size and speed come from the main window.
3. After each letter, the operator types what the participant reports (`?` = don't know) and presses Enter. **Repeat letter** writes it again.

Every answer is appended to `trials/cover_trials.csv`: time, participant, cover, tip, force, letter size, speed, target, response, correct, response time. The window shows accuracy per material so far.

### 7.6 Keeping the sections in sync

`python3 tests/test_sync.py` (or `pytest tests`) must print `SYNC OK` before every commit (about 20 s). It checks:

| Check | Fails when |
|---|---|
| The demo app and the runtime both use `Session` and `Mcu`; the demo runs the simulated firmware and contains no device logic of its own; its box controls go through the (simulated) box | Behaviour is added to a demo instead of the device software |
| **The real demo app and a bare runtime session, given the same script of text and controls, send identical commands, Braille and display messages** | The demo and the device would behave differently |
| `python -m comlang --dry-run` sends the same commands as the session | The runtime adds or loses behaviour |
| Reset cue (3 taps, 2 flashes), interlock, Braille-only mode | The documented behaviour (§7.3) changes |
| Display and status messages round-trip | The link format breaks |
| `firmware/mcu/src/generated.h` matches `engine.py` / `protocol.py`; the firmware reports every action and handles every host command; the writing area fits the machine travel | The firmware and the host drift |
| **Full stack: session → protocol → firmware → simulated hardware.** Homes; writes "hi" with one solenoid pull-in per pen command and the exact Braille sequence; ends where the last move ends; draws the LCD; a wheel roll on the hardware changes the speed; the hardware Reset button gives 3 taps and 2 flashes; lifting the hand mid-word stops the pen, the roller alone does not restart, hand + roller does; blocking the carriage mid-word stalls, the session pauses and keeps the word, the roller resumes | The product does not do what the demo shows |
| **Firmware safety with the host silent**: a hung host keeps queueing; lifting the hand still stops the pen and drops the queue, the roller alone does not restart, hand + roller does, the roller holds locally, a blocked carriage stops by itself, Reset stops locally | A safety rule depends on the host |
| Every code path named in this document exists; every action is documented; no superseded hardware is described | The doc goes stale |

When changing the box's behaviour: change `comlang/` and/or `firmware/mcu` (re-run `tools/gen_firmware_tables.py` if `engine.py` or `protocol.py` changed), then the demo UI if it shows something new, then this document, then run the test.

---

## 8. Build guide (MVP-1)

1. **Cut the base and plates.** F01 base (1.5 mm aluminium), F02 (2.5 mm aluminium, CNC pockets), F03 (2.5 mm PC/ABS) from DXF exported from the CAD. Check the window, cover pocket, roller slot, holes and pockets against §4.1.
2. **Print / machine** the Y-blocks with bridge, carriage, rod supports, caps and the roller. Press in the bushings; they must slide freely on the Ø5 rods.
3. **Base.** Flat to ±0.2 mm. Fit the walls, the rod supports, the motor and idler posts, the feet.
4. **Gantry.** Fit the Y-rods (z 7) through the Y-blocks, clamp the twin X-rods (z 10.5) in the bridges with the carriage on them. The carriage must move freely over the 70 × 70 mm range, and the gantry must be **square** (diagonals within 0.3 mm).
5. **Motors.** Fit the two flat motors with their ring pulleys (A rear left, B front right) and the encoders under them (magnet on the rotor axis, 1 mm gap).
6. **Belts.** Belt A on the lower layer, belt B on the upper layer, routed as in §4.3; clamp both ends on the carriage lugs with equal tension.
7. **Pen head.** Fit the mini solenoid, wedge, roller, pen and force spring (start with tip T10). Check the 5 mm lift.
8. **Electronics.** Controller board at the front, encoder and switch flex PCBs under F02, Braille actuators in their pockets, display in its pocket on a ribbon. Wire per §5.2.
9. **Flash the controller** (§6): build `comlang_mcu.uf2`, hold BOOTSEL, plug in, copy it to RPI-RP2. Bring up in the order in §6. Home (`/home`), jog (`/goto`), confirm directions.
10. **Top plate.** Bond F03 on F02, fit the caps and roller (each returns freely), inlay the pad, screw down. The pen must clear the window by ≥ 2 mm at every corner, and every moving part the plate underside by ≥ 1 mm.
11. **Cover.** Make one cassette per test material. Drop one in: flush with the floor, < 2.5 mm sag under a resting palm.
12. **Software.** Calibrate (§9), then `python3 -m comlang --board auto --palm-centre X Y --text "hello"`. The demo app can use the same box ("Use real board") for the 3D view and the cover test.

---

## 9. Calibration

Run `python3 -m comlang --board auto --no-hand-sensor` on the bench and type the commands (§7.1).

1. **Home:** `/home` (the controller also homes when the host connects).
2. **Palm centre:** `/goto 0 0`, then jog with `/goto X Y` until the retracted pen sits under the window centre (cross on masking tape). `/where` prints the position. Set it with `/centre X Y` in machine mm (default 37.5 37.5 + the offset you found), and start later runs with `--palm-centre X Y`.
0. **Motors:** at power-up the controller aligns each motor (the carriage nudges < 1 mm). `/where` must change smoothly when you push the carriage by hand with the motors off.
3. **Height and force, with the cover fitted:**
   1. With `/pen 1`, the tip must lift the membrane **1.5 ± 0.3 mm** above the floor (5 mm stroke). `/pen 0` to retract.
   2. Measure the force with a pocket scale over the cover. Target **40–80 g**.
   3. Shim the spring.
4. **Orientation (P1):** write `L`, `F`, `R` on a person's palm. Keep the mirror on (default) or run with `--no-mirror` (demo: "mirror (palm-down)") to match.
5. **Workspace:** `/goto` the four corners (±35, ±35). No contact with the window edge or the cassette frame.

---

## 10. Test plan

| ID | Test | Pass criterion |
|---|---|---|
| T0 | Software and firmware on the simulated board: `python3 tests/test_sync.py` | Prints `SYNC OK` |
| T1 | CAD checks: `freecadcmd haptic_box_v2.FCMacro` | Prints `CLEARANCES OK` and `HAND FIT OK`. Pen tip +1.5 down / −5.5 up |
| T2 | Repeatability: 40 mm square 20× on paper over the window | Line width spread ≤ 0.6 mm |
| T3 | Speed: write the pangram | ≥ 25 letters/min; following error < 0.3 mm while writing (status log) |
| T4 | Pen timing: high-speed video of 20 taps | Up and down ≤ 50 ms each |
| T5 | Interlock: lift the hand mid-letter; then press the roller without the hand; then hand back + roller | Pen retracts and motion stops within 250 ms of lifting (200 ms pad debounce); no motion on the wheel alone; resumes with hand + wheel. Repeat with the USB cable pulled mid-letter: the queue runs out and the pen stays off |
| T6 | Tip/force comfort (P2): 3 tips × 3 forces, 5 participants | Best clarity, no discomfort |
| T7 | Orientation (P1): 10 asymmetric letters, mirrored vs not | Higher recognition wins |
| T8 | Recognition: 26 letters, sizes 35/45/55 mm | ≥ 80 % after 10 min familiarisation |
| T9 | Session comfort: 20 min | No wrist or forearm discomfort |
| T10 | End-to-end: 5 spoken sentences | Every final phrase written; queue, repeat, skip, reset behave as specified |
| T11 | Control reach: ≥ 6 participants, small to large hands, eyes closed | Roller roll, roller press (the Ø6 roller, R13) and Repeat each done within 3 s without lifting the palm. Mode found with the free hand within 5 s. No accidental presses in a 5 min writing session |
| T12 | Braille slider: small and large hands | Cells under both pads |
| **T13** | **Cover material experiment** (D15). See below | Choose the material |
| T14 | Speaker display: read from the speaker's seat (1–1.5 m, across the table) | Current word readable at a glance; Reset understood without instruction |
| T15 | Tactile symbols (P11): blindfolded participants identify each control by touch, raised vs etched versions | ≥ 95 % correct; choose raised or etched |
| T16 | Glove fit: ≥ 10 participants of varied hand size and shape place the hand without guidance | Hand settles in the 2.5 mm recess within 5 s; no pressure points at the edges |
| T17 | **Pinch / obstruction:** block the carriage with a force gauge (and a gloved finger) at full speed | Push force ≤ 4 N; motors released within 100 ms (`err stall`); resumes on the roller |
| T18 | Height and flatness: measure the box | ≤ 20.5 mm everywhere; top plate deflection < 0.3 mm under a 20 N resting hand |

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
| **MVP-0: bench rig** | Gantry + pen on an open baseboard. Controller board + `python -m comlang`. Writes on paper and through cover samples | T2, T3, T4 pass. First T13 pass (bench) |
| **MVP-1: first box** *(the CAD)* | 20 mm box: aluminium base and plate, glove recess, flat CoreXY with two BLDC motors, cover cassettes, forearm pad, thumb roller / Repeat / Mode / Reset on the controller, hand-present pad, speaker display, laptop app, USB mic. Braille on screen only (P9) | T1–T16 with ≥ 5 participants. Decide P1, P2, P5, P11, cover material |
| **Phase 2: standalone** | Raspberry Pi 5 inside, piezo Braille cells, power button, enclosure finish, left-hand plate | Usable without a laptop. Braille synchronised with the pen |

## 12. Risks

| ID | Risk | Mitigation |
|---|---|---|
| R1 | **Throughput:** speech ~150 words/min vs palm ~6 words/min | Speaker display shows how far behind it is. Skip, Reset, Braille-only mode, optional summarising (open question 2) |
| R2 | A pointed tip feels sharp | Spring-limited force, interchangeable tips, the cover spreads the point. T6, T13 |
| R3 | **The cover dulls the letters** | T13 picks the thinnest material that still protects. Larger letters (P5). Fallback: open window + interlock (v0.2) for trained users only |
| R4 | The membrane wears through or sags onto the pen | Replaceable cassette, durability test, sag < 3 mm check at every cassette change |
| R5 | CoreXY gantry racks (the single-sided drive of each Y-block) | Twin X-rods and wide Y-blocks; belt tension equal on both belts; the position loop corrects the belt coordinates, not the racking: check squareness at assembly (§8) |
| R6 | Ø5 rods deflect or bushings bind | Short Y-rod spans (128 mm), twin X-rods (≤ 0.02 mm at 1 N); iglidur J bushings, dry |
| R7 | Flat solenoid too weak at full stroke | The wedge puts the high-force (closed) end at pen-down. Choose the solenoid by its force at 1–2 mm from closed. Fallback: two solenoids or a steeper wedge |
| R8 | Speech errors write wrong words | Final-only results. Speaker display + Reset + correction cue. Larger Vosk model on the Pi |
| R9 | Accidental Mode or Reset presses | Pocket buttons, top 1 mm below the surface. Reset is on the speaker side |
| R10 | **Controller firmware unproven on hardware** (written, tested only on the simulated board; motor control gains tuned on the model) | Full-stack tests on the simulated physics model; bench bring-up in a fixed order (§6); watchdog, torque limit and local safety rules; update the model (masses, friction, motor constant) from bench measurements |
| R11 | Braille cell cost | Phase 2. Screen-Braille fallback |
| R12 | **Thin latching Braille actuators** (≤ 7 mm) are less established than piezo cells; supply and cost open | Candidates: electromagnetic bistable pins (as in Braille watches / tablets), SMA latches. The firmware and plate already support 12 latching pins; screen Braille until a supplier is chosen |
| R13 | **The Ø6 scroll roller** is small for some thumbs | Knurl ribs + detents; T11 decides. Fallback: two flush buttons for faster / slower on the same spot |
| R14 | Flat gimbal motors: torque margin and heating at 12 V | 2× margin on the needed belt force; 0.6 A per motor; the base is the heat sink; tune `TORQUE_LIMIT` on the bench |

---

## Appendix A: earlier versions (superseded)

**v0.3 first build** (Nov 2026) was **54 mm** tall: an Ultimaker-style crossed-bar gantry on four rotating Ø8 perimeter shafts (rails and drive shafts), GT2 belts looping vertically round pulleys on them in two layers 16 mm apart, two NEMA14 steppers (35 mm, the height limit) on an Arduino-class step generator, a 10 mm deep glove well, a Ø22 thumb wheel on an EC11 encoder, 7 mm pen lift, and 64 mm tall piezo Braille cells planned for phase 2. The owner asked for **about 2 cm**, which led to the flat CoreXY / BLDC design above.

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
cmake -S firmware/mcu -B build/mcu-sim && cmake --build build/mcu-sim   # simulated controller
python3 tests/test_sync.py                                        # demos == device software == firmware
python3 tools/gen_firmware_tables.py                              # after changing engine.py / protocol.py
freecad haptic_box_v2.FCMacro                                     # interactive 3D, animates TEXT
```

All dimensions are parameters at the top of `haptic_box_v2.FCMacro`. For example:
- `BOX_W/L`, `PLATE_UNDER`, `BASE_T`, `RECESS`
- `GLOVE_MARGIN`, `COVER`, `COVER_T`
- `WHEEL_R/W/UP` (scroll roller), `STRIP`, `SPEAKER`, `DISPLAY`
- `SYMBOL_RELIEF`, `Z_YROD/Z_XROD`, `BELT_A_Z/BELT_B_Z`, `RAIL_X`, `BELT_X`, `MOTOR_R/H`, `HAND`

The box height follows from them: `BOX_H = PLATE_UNDER + BASE_T + RECESS` = 15 + 2.5 + 2.5 = 20. After changing any of them, re-run both commands and update §4.1 and §4.3.
