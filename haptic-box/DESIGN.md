# Haptic Palm-Writing Box: Design Specification v0.2

| | |
|---|---|
| **Status** | Concept agreed; prototype CAD complete and clearance-checked; hardware not yet built |
| **Audience** | Anyone building, testing or extending the device from zero |
| **Source of truth** | `haptic_box_v2.FCMacro` (parametric CAD). Every dimension in this document comes from that file. If the two disagree, the CAD wins; then fix this document |
| **Supersedes** | v0.1 (hand inside an enclosed box, 5-bar linkage from above). See Appendix A |

![product](renders/v2_product.png)

## 0. What it is

The **haptic palm-writing box** is a desktop device for people who cannot hear speech and cannot rely on sight, for example deafblind users.

1. The user lays one hand **palm down** in a hand-shaped recess on top of the box.
2. A microphone picks up a speaker. Offline speech recognition turns the speech into text.
3. A **single pointed pen** inside the box comes up through a window under the palm. It **traces block capitals on the palm**, one letter on top of the next. This is the *print-on-palm* method that deafblind people already use with human partners.
4. Two refreshable **Braille cells** under the index and middle fingertips can show the same letters, which is faster for Braille readers.
5. **Buttons** by the thumb and little finger let the user pause, repeat a word and change the speed without lifting the hand.

The pen moves in **one plane on two axes**, on a crossed-rail XY gantry. A push solenoid moves it a short distance up and down to touch and leave the palm.

![writing](renders/v2_writing.gif)

---

## 1. Decision record

Use this section to reach and record the common conclusion. Each row names its source.

### 1.1 Agreed

| # | Decision | Source |
|---|---|---|
| D1 | The base is a **box**. The hand rests **on top, palm down**. There is no tunnel or enclosure around the hand | Sketch + review |
| D2 | **One pointed pen reaches up from below** through a window under the palm and traces the letters | Review: "one pointy pen below palm" |
| D3 | The pen moves **in one plane on two axes**: a crossed-rail (Cartesian) XY gantry. Pen up/down is a short local stroke at the carriage, not a third gantry axis | Review |
| D4 | **Buttons** at the thumb side and the little-finger side | Sketch circles |
| D5 | **Refreshable Braille cells** under the fingertips | "+ Braille" on the sketch |
| D6 | Primary output is print-on-palm **block capitals, one letter on top of the next**, with word and sentence cues (§7.3) | v0.1, kept |
| D7 | The person uses it through an **app** (`haptic_app.py`): listen/type, queue, pause/repeat/skip, speed, mode, hardware connection | Review: "must be an app for me to use" |
| D8 | The prototype is defined by a **parametric CAD model** (FreeCAD) | Review |

### 1.2 Proposed: confirm or change

| # | Proposal (current CAD/app default) | Why | Alternatives |
|---|---|---|---|
| P1 | **Mirror the letters in x** for the palm-down box, so a letter feels the same relative to the hand as print-on-palm on an upturned hand | Keeps the convention users already know | Unmirrored ("as seen through the back of the hand"). Settled by user test T7 |
| P2 | **Pen tip: 0.5 mm radius point** (the CAD default), force **0.3–1.0 N** set by a spring. The prototype also ships with 1.0 mm and 2.0 mm radius tips | "Pointy" gives a crisp line, but a fine point at 1 N can feel sharp | Choose after test T6 |
| P3 | **Push solenoid** for pen up/down (fast, ~20–30 ms, binary). The return spring retracts the pen when unpowered, so it fails safe | Simple, quiet enough, fail-safe | Micro servo + lever (slower, continuous force control) |
| P4 | **Open 84 × 84 mm window** plus a hand-present interlock | Nothing between pen and skin | Thin replaceable membrane over the window (more hygienic, dulls the sensation, risk of puncture with a sharp tip) |
| P5 | Letter height **45 mm**, writing speed **120 mm/s**, ~29 letters/min | Fits an adult palm. Speed is adjustable in the app | 35 / 55 mm. Test T8 |
| P6 | **Right hand by default.** `HAND="left"` mirrors the recess, buttons and Braille | Most users. Left is one parameter away | A reversible top plate |
| P7 | **Hand-present pad** (capacitive disc at the wrist) as the motion interlock | The sketch shows a circle at the wrist | IR/ToF sensor looking up through the window |
| P8 | **Separate forearm pad** in front of the box, 72 mm tall, so the forearm is level with the top | The box top is 72 mm above the table; without support the wrist would bend | Box sunk into a table cut-out |
| P9 | **Braille cells are phase 2.** The plate already has their holes. MVP-1 shows Braille on screen only | Braille cells are the most expensive part (§4.8) | Include them in MVP-1 |

### 1.3 Open questions (owner: product)

1. Who operates the app day to day: the deafblind user, a companion, or both? This decides whether the Pi runs standalone with physical buttons only, or a laptop/tablet screen is always present.
2. Should the Braille cells show the **current letter** (synchronised with the pen), or the **next letter** as a preview?
3. Is a sentence-level "compression mode" acceptable (§11, risk R1)?

---

## 2. Requirements

| ID | Requirement | Target / acceptance |
|---|---|---|
| R-F1 | Write recognised or typed text on the palm as block capitals | All A–Z, 0–9, `?` (37 glyphs, `palm_writer.FONT`) |
| R-F2 | Word and sentence cues | Word gap = 1 tap + 0.6 s; `.`/`!` = 2 taps |
| R-F3 | Braille output for the same text | English Grade 1 (uncontracted); a run of digits gets one number sign |
| R-F4 | User controls without lifting the hand | Pause/Resume, Repeat word, Speed (physical) + app keys |
| R-F5 | Offline speech recognition | Vosk small en-us model, runs on a laptop or a Raspberry Pi 5 |
| R-P1 | Writing area on the palm | 70 × 70 mm reachable; glyphs fit in 45 mm height |
| R-P2 | Pen speed and acceleration | 120 mm/s writing, 250 mm/s travel, 3000 mm/s² |
| R-P3 | Pen up/down | Stroke 7.5 mm; switch time ≤ 50 ms |
| R-P4 | Contact force | Adjustable 0.3–1.0 N, set mechanically (spring), never by motor torque |
| R-P5 | Positioning | Repeatability ≤ ±0.3 mm (the palm resolves ~10 mm, so this is generous) |
| R-E1 | Ergonomics | Palm surface 72 mm above the table. Forearm supported level. Hand position fixed by the recess |
| R-S1 | Safety | No restraints. The hand can be lifted off at any time. Motion only while a hand is present. The pen retracts on power loss. Max 12 V outside the box |
| R-S2 | Hygiene | Wipeable top. Pen tip replaceable or disinfectable (70 % isopropyl alcohol) |
| R-N1 | Noise and vibration | Steppers in silent mode (TMC2209 stealthChop). No vibration felt through the top except the pen |

---

## 3. System architecture

```
 speaker's voice
      │
  [USB mic] ──► haptic_app.py (laptop for MVP, Raspberry Pi 5 later)
                  │  Vosk speech-to-text (offline) → final phrases only
                  │  queue of words  ← buttons (USB HID keys) / app keys
                  │  palm_writer: text → strokes → G-code (mirrored x)
                  │  palm_writer: text → Braille cells
                  ▼
        USB serial (115200)                       SPI/GPIO (phase 2)
                  │                                        │
     [Arduino Uno + CNC Shield V3, GRBL 1.1]        [Braille HV driver]
       │X step/dir   │Y step/dir   │spindle out           │
   [TMC2209]     [TMC2209]     [MOSFET]           [2 × piezo Braille cells]
       │             │             │
   NEMA14 X      NEMA14 Y      12 V push solenoid ──► pen ──► palm
   (x-belts)     (y-belts)
```

**Signal conventions**
- G-code coordinates are **relative to the palm centre** (work zero, set during calibration §9). Machine x is **mirrored**: `X = −palm_x` (P1).
- Pen up/down uses GRBL's spindle output: `M3 S1000` pushes the pen up into the palm, `M5` retracts it. Laser mode is off (`$32=0`), so the pen does not depend on motion.

---

## 4. Mechanical design

### 4.1 Coordinate system and key dimensions

The origin is at the centre of the box front edge, on the table. +x is the user's right, +y points away from the user, +z is up. Units are mm. For the right hand, the thumb is on −x.

![top layout](renders/v2_top.png)

| Feature | Value |
|---|---|
| Box outside | **260 (W) × 330 (L) × 72 (H)**, vertical corners R12 |
| Walls / floor / top plate | 3 / 3 / 6 (top plate = 4 + 2 layers, §4.2) |
| Palm surface (recess floor) | z = **70**; recess depth 2 |
| Wrist crease line | y = 100 |
| **Writing centre** (palm centre) | **(0, 155)** |
| **Window** | **84 × 84**, R8, centred on (0, 155): x −42…42, y 113…197 |
| Pause button (thumb) | (−104, 160) |
| Repeat button (thumb) | (−96, 212) |
| Speed button (little finger) | (72, 220) |
| Braille cell, index fingertip | (−30, 265) |
| Braille cell, middle fingertip | (−10, 273) |
| Hand-present pad (wrist) | (0, 75), Ø24 |
| Mic grille / status LED | 4 × 4 holes Ø2.4 at x 80…95, y 290…305 / Ø4 at (105, 300) |
| Forearm pad | 120 × 140 × 72, in front of the box (y −142…−2) |

**Hand recess outline** (cut through the 2 mm upper plate layer):
- Palm: 100 × 120 rounded rectangle, R15, x −50…50, y 92…212.
- Fingers: slots 22 wide, R10, starting at y 195.
  - index: x = −30, to y 289
  - middle: x = −10, to y 297
  - ring: x = +10, to y 292
  - little: x = +30, to y 277
- Thumb: slot 26 wide, 80 long, starting at (−42, 135). It points along (−0.6, 0.8), i.e. 37° out from the y axis toward the thumb side.

### 4.2 Enclosure

![exploded](renders/v2_exploded.png)

| Part | Material and process (MVP) | Notes |
|---|---|---|
| **P01 Base tray** 260 × 330 × 66, walls 3, floor 3 | **MVP:** 3 mm plywood or acrylic, laser-cut with finger joints, glued. **Later:** 3D-printed in 4 quadrants, or vacuum-formed | The floor is the gantry datum: keep it flat to ±0.3 mm. A 3 mm aluminium floor plate is better if available. Rear wall: 7 vent slots 6 × 22, power jack Ø10 at (95, rear, z 30) |
| **P02 Top plate, lower layer** 260 × 330 × **4** acrylic (PMMA), R12 corners | Laser-cut | Window 84 × 84 R8; button holes Ø19; Braille pin holes Ø1.6 (12×); mic holes Ø2.4; LED Ø4. Screwed to the tray with 8 × M3 into heat-set inserts in corner/side posts |
| **P03 Top plate, upper layer** 260 × 330 × **2** | Laser-cut acrylic, HDPE or 2 mm EVA/neoprene laminated on 1 mm acrylic for a warmer feel | **The hand outline is cut through** this layer, which forms the 2 mm tactile recess without milling. Bond to P02 with transfer tape (3M 468MP-type) |
| **P04 Forearm pad** 120 × 140 × 72 | 3D-printed or plywood box + 10 mm EVA foam + vinyl/neoprene cover | Separate part. Non-slip feet |
| Feet | 4 × Ø15 rubber bumpers under the tray | Decouple vibration from the table |

### 4.3 XY gantry: crossed rails, one plane, two axes

![cut-away](renders/v2_cutaway.png)

**Principle.** Two bars cross at right angles, and the carriage slides on both.
- The **Y-bar** runs along x and moves in y on two **y-rails** at the sides.
- The **X-bar** runs along y and moves in x on two **x-rails** at the front and back.
- Each bar is pulled at **both ends** by belts on a common sync shaft, so it cannot rack (twist).
- The two bars sit at different heights (z 34 and z 48), so they never touch. The carriage holds a bushing for each.

![section](renders/v2_section.png)
![section detail, pen down](renders/v2_section_detail.png)

**Z stack** (from the table):

| Item | z (mm) |
|---|---|
| Floor top | 3 |
| Y-drive axis (Y-belts at z 15 and 27, pulleys Ø12.7) | 21 |
| **Y-rails + Y-bar** (Ø8) | **34** |
| **X-rails + X-bar + X-drive** (X-belts at 42 and 54) | **48** |
| Carriage block | 28–54 (26 × 26 × 26) |
| Solenoid (Ø16 × 32) | 26–58 |
| Pen tip, retracted / pressed | 64 / 71.5 |
| Top plate | 66–72; palm on the recess floor at 70 |

**Layout** (all from the CAD):

| Element | Position |
|---|---|
| y-rails | Ø8 × 158 at x = ±100, y 76…234; pillars at y 80 and 230 |
| x-rails | Ø8 × 160 at y = 70 and 240, x −80…80; pillars at x ±76 |
| Y-bar | Ø8 × 190 between two end blocks (18 × 22 × 18) that ride the y-rails. Belt-clamp tabs reach out to the y-belts at x = ±116 |
| X-bar | Ø8 × 160 between two end blocks (22 × 18 × 18) that ride the x-rails. Clamp tabs to the x-belts at y = 58 and 252 |
| Y-drive | Dual-shaft NEMA14 at (0, 262, 21), shaft along x. Ø5 × 240 sync shaft with GT2-20T pulleys at x = ±116. Idlers at y = 70 |
| X-drive | NEMA14 at the front-left (x −88, y 12…47, z 48), shaft along y. Ø5 × 209 sync shaft with GT2-20T pulleys at y = 58 and 252. Idlers at x = +88 |
| **Pen offset** | The pen and solenoid sit **+16, +16 mm** (diagonal) from the carriage centre, so they clear both bars. The calibration zero takes care of this offset (§9) |

**Travel.** Pen: ±35 mm about (0, 155). Carriage centre: x −51…19, y 104…174.
**Steps.** GT2 belt (2 mm pitch) on a 20T pulley gives 40 mm per rev. 200 steps × 1/16 microsteps = **80 steps/mm**. 250 mm/s needs 20 kHz, which is within GRBL-on-Uno limits.

**Bearings.** Use sintered-bronze (oilite) bushings 8 × 12 × 12 mm pressed into the printed blocks: 2 in the carriage, 1 in each of the 4 end blocks. LM8UU ball bushings (Ø15 × 24) are an option if the blocks grow to ≥ 24 mm. Sync shafts run in 625ZZ bearings (5 × 16 × 5) in printed bearing blocks.

**Belts.** GT2 6 mm, open belt, both ends clamped in the bar's tab.
- y-belts: 2 × ~430 mm.
- x-belts: 2 × ~392 mm.
- Tension with slotted idler mounts (2 × M3) to ~3–5 N; the belt should deflect ~2 mm under a light finger.

### 4.4 Pen actuator and tip

![section detail, pen up](renders/v2_section_detail_up.png)

| Item | Spec |
|---|---|
| Solenoid | 12 V **push** type, tubular, ≤ Ø16 × 32 mm body, **≥ 10 mm stroke**, ≥ 2 N at 7.5 mm, built-in return spring, ≤ 1 A. Flyback diode across the coil |
| Stroke used | 7.5 mm: tip at z 64 (2 mm below the plate underside) → z 71.5 (1.5 mm above the recess floor, i.e. pressing into the skin) |
| Pen | Ø3 stainless or POM rod with an M3 thread for interchangeable tips. It slides in a Ø3 PTFE/brass sleeve on the plunger |
| **Force limiter** | Compression spring between plunger and pen: rate ~0.3 N/mm, preload 0.2 N, 2 mm over-travel → 0.8 N max. Shims set 0.3–1.0 N. **Force never depends on solenoid strength** |
| Tips (P2) | T05: 0.5 mm radius point (default, "pointy"). T10: 1.0 mm radius. T20: Ø4 ball. Turned brass/stainless or printed resin. Smooth finish, no burrs |
| Hold current | After pull-in, reduce to ~40 % with GRBL `S400` to limit heating. Duty during writing ≈ 60 % |

### 4.5 Hand interface

| Element | Implementation |
|---|---|
| Recess | 2 mm cut-out in P03 (§4.1). Edges broken (0.5 mm chamfer or sanded). Users find the position by touch |
| Buttons (3) | 19 mm momentary panel push-buttons (hole Ø19), domed caps. **Braille letter on each cap:** P (Pause), R (Repeat), S (Speed). Switch body under the plate (≤ 14 × 14 × 12) |
| Hand-present pad | Ø24 brass disc inlaid 0.4 mm into the top, wired to a capacitive touch module (TTP223-type) |
| Braille cells (phase 2) | 2 cells, 6 dots, 2.5 mm dot pitch. Each cell module 12 × 44 × 16 under the plate; pins come up through Ø1.6 holes in the finger-slot floor. Dots 1–3 on the reader's left (−x), dot 1 furthest away (the fingertip reads as on paper) |

### 4.6 Fabricated parts list

| ID | Part | Qty | Material / process | Key dimensions |
|---|---|---|---|---|
| P01 | Base tray | 1 | 3 mm plywood/acrylic, laser | 260 × 330 × 66, R12 |
| P02 | Top plate, lower | 1 | 4 mm PMMA, laser | 260 × 330, holes per §4.1 |
| P03 | Top plate, upper (recess) | 1 | 2 mm PMMA/HDPE (or EVA on 1 mm PMMA), laser | Hand outline cut-out |
| P04 | Forearm pad | 1 | PLA/plywood + EVA | 120 × 140 × 72 |
| P10 | Rail pillar, y | 4 | PETG print | 12 × 8, rod centre z 34 |
| P11 | Rail pillar, x | 4 | PETG print | 8 × 12, rod centre z 48 |
| P12 | Y-bar end block + belt tab | 2 | PETG print, bronze bushing | 18 × 22 × 18, tab to x ±116 |
| P13 | X-bar end block + belt tab | 2 | PETG print, bronze bushing | 22 × 18 × 18 |
| P14 | Carriage (cross block + solenoid bracket) | 1 | PETG print, 2 bushings | 26 × 26 × 26 + bracket 25 × 25 × 4 |
| P15 | Motor mounts (X, Y) | 2 | PETG print | NEMA14 31 mm hole pattern, M3 |
| P16 | Sync-shaft bearing blocks | 4 | PETG print, 625ZZ | Shaft axis z 21 (Y) / z 48 (X) |
| P17 | Idler mounts, slotted | 4 | PETG print | ±4 mm tension slot |
| P18 | Pen + tips | 1 + 3 | Stainless/brass, turned | Ø3, M3 thread |
| P19 | Electronics standoffs | — | M3 nylon | 3 mm above the floor |

### 4.7 Purchased parts (BOM)

| # | Item | Qty | Spec / note |
|---|---|---|---|
| 1 | Linear rod Ø8 h6, hardened | 6 | Cut to 158 (2), 160 (3), 190 (1) |
| 2 | Steel shaft Ø5 | 2 | 240 and 209 |
| 3 | Bronze bushing 8 × 12 × 12 | 6 | Or LM8UU (needs bigger blocks) |
| 4 | Bearing 625ZZ | 4 | Sync shafts |
| 5 | GT2 6 mm belt | 2 m | Open belt |
| 6 | GT2 20T pulley, 5 mm bore | 4 | On the sync shafts |
| 7 | GT2 idler 20T, 5 mm bore (or 3 mm) | 4 | |
| 8 | NEMA14 stepper 35 × 35 × 34, 1.8° | 2 | One **dual-shaft** (Y). ~0.6–1.0 A |
| 9 | Flexible coupler 5–5 mm | 3 | |
| 10 | Arduino Uno R3 + CNC Shield V3 | 1 | GRBL 1.1 |
| 11 | TMC2209 step-stick | 2 | Standalone, stealthChop, 1/16 |
| 12 | 12 V push solenoid, ≥ 10 mm stroke | 1 | §4.4 |
| 13 | Logic-level MOSFET module + flyback diode | 1 | IRLZ44N-type, 1N5819 |
| 14 | Microswitch (limit) | 2 | X-min, Y-min homing |
| 15 | 19 mm momentary push-button | 3 | |
| 16 | Raspberry Pi Pico (RP2040) | 1 | Buttons + pad → USB keyboard (HID) |
| 17 | TTP223 capacitive module + Ø24 brass disc | 1 | Hand-present |
| 18 | USB microphone | 1 | Under the grille, or external |
| 19 | 12 V 5 A DC supply + 5.5/2.1 jack | 1 | |
| 20 | M3 screws, heat-set inserts, nuts | set | |
| 21 | Compression springs, 0.3 N/mm, for Ø3 pen | 3 | Shim to the target force |
| 22 | **Phase 2:** Raspberry Pi 5 (4 GB) + 12→5 V 5 A buck | 1 | Standalone operation |
| 23 | **Phase 2:** piezo Braille cells + HV driver (~200 V) | 2 | Most expensive item. Choose a module with an integrated driver (e.g. a Metec-type cell with a serial driver board). Follow the HV safety rules in the datasheet |

---

## 5. Electrical design

### 5.1 Power budget

| Consumer | Supply | Current (peak) |
|---|---|---|
| 2 × NEMA14 via TMC2209 | 12 V | 2 × 0.6 A (set Vref for ~0.5 A RMS, enough for this light gantry) |
| Solenoid | 12 V | ≤ 1 A pull-in, ~0.4 A hold |
| Uno + Pico + TTP223 | 5 V via USB | < 0.2 A |
| Pi 5 (phase 2) | 5 V / 5 A buck | ≤ 3 A typical |
| **Total** | **12 V** | **≈ 3 A (MVP), ≈ 5 A with the Pi** → 12 V 5 A supply |

### 5.2 Wiring (MVP)

| From | To | Note |
|---|---|---|
| 12 V jack | CNC Shield V+ / GND | Add a 3 A inline fuse |
| X driver (shield X socket) | X stepper | Set the TMC2209 microsteps to 1/16 with the MS1/MS2 jumpers (see the TMC2209 standalone table) |
| Y driver (shield Y socket) | Y stepper (dual-shaft) | |
| X-min / Y-min endstops | Shield X−/Y− | Normally-open to GND; `$5` sets the polarity |
| GRBL spindle output | MOSFET gate | **Pin check:** in GRBL 1.1 with variable spindle (the default), the spindle PWM, which also acts as enable, is on **D11**. Z-limit moves to D12, and D13 is spindle *direction*. The CNC Shield V3 silk labels follow GRBL 0.9 (SpnEn = D12, Z+ = D11). Wire the MOSFET gate to **D11** by pin number, not by the label, and confirm against `cpu_map.h` of the GRBL build you flash |
| MOSFET drain | Solenoid −. Solenoid + to 12 V | Flyback diode across the coil (cathode to +12 V) |
| Pause button | **also** to GRBL feed-hold (A1) | The pause works in hardware even if the app hangs |
| 3 buttons + TTP223 | Pico GPIO (pull-ups) | Pico firmware sends keys: Space = Pause, R = Repeat, S/+ = Speed, F9 = hand present (§7.4) |
| Uno USB, Pico USB, mic USB | Laptop (MVP) / Pi 5 (phase 2) | |

### 5.3 Electrical safety
- Only 12 V DC enters the box. The external supply carries the safety approval.
- The Braille HV (phase 2) stays inside a closed driver module. No exposed pins.
- Keep the steppers' motor current low (0.5 A). The belt drive can still exert several newtons, which is why the interlock (§7.4) exists.

---

## 6. Firmware (GRBL 1.1 on the Uno)

Flash GRBL 1.1h, then send these settings (`$$` lists them):

| Setting | Value | Meaning |
|---|---|---|
| `$100` / `$101` | 80 | steps/mm X / Y (GT2 + 20T, 1/16) |
| `$110` / `$111` | 15000 | max rate mm/min (250 mm/s) |
| `$120` / `$121` | 3000 | accel mm/s² |
| `$130` / `$131` | 75 | max travel X / Y (pen ±35 plus margin) |
| `$20` / `$21` | 1 / 1 | soft and hard limits on |
| `$22` | 1 | homing enabled |
| `$23` | 3 | home towards X−, Y− |
| `$27` | 2 | pull-off mm |
| `$30` / `$31` | 1000 / 0 | spindle S range (S1000 = pull-in, S400 = hold) |
| `$32` | 0 | laser mode off |
| `$1` | 255 | keep the motors energised (holds position) |
| `$3` | set on test | invert X so that `X+` = −palm-x if wiring differs (P1) |

**G-code produced by the app** (`palm_writer.event_gcode`), in work coordinates where **(0, 0) is the palm centre**:

```
G0 X15.75 Y22.50        ; travel to the start of a stroke (pen down)
M3 S1000                ; pen up into the palm
G4 P0.08                ; settle
G1 X15.75 Y-22.50 F7200 ; draw at 120 mm/s
M5                      ; retract
G4 P0.08
```

To try it without the app: `python3 palm_writer.py "HELLO" --gcode hello.nc --mirror`, then stream the file with any GRBL sender.

---

## 7. Software

### 7.1 Components

| File | Role |
|---|---|
| `haptic_app.py` | The app the person uses: Tkinter desktop GUI. Listen (Vosk) or type → queue → simulation + Braille display → GRBL over USB |
| `palm_writer.py` | Engine: stroke font (37 glyphs), word/sentence cues, `Planner` (trapezoidal motion at 50 Hz), Braille Grade 1, G-code, CLI tools |
| `haptic_box_v2.FCMacro` | Prototype CAD + clearance checks + STEP export + mesh export |
| `render_views.py` | All the images in this document, rendered from the CAD meshes |

### 7.2 Running

```
python3 -m venv .venv && .venv/bin/pip install numpy vosk sounddevice pyserial
.venv/bin/python haptic_app.py               # the app
# first "Listen" downloads the small en-us model (~40 MB) to ~/.cache/vosk
```

![app](renders/app_screenshot.png)

**App controls.**
- Keys: **Space** pause, **R** repeat word, **S** skip to the newest phrase, **C** clear, **L** listen, **+/−** speed.
- Settings: speed 0.5–2×, letter height 30–60 mm, output (palm / Braille / both), speech model, box port with **Connect**, and "palm-down box (mirror)".

### 7.3 Text → touch rules
- Only **finalised** recognition results are queued. Partial results are shown greyed and never written, because a letter on the palm can't be taken back.
- Letters are written at the same spot, 45 mm tall. A 0.25 s pause separates letters. Between words: 1 tap at the centre + 0.6 s. `.` and `!` give 2 taps. Vosk outputs no punctuation, so these cues come from typed text only.
- Braille: one cell per letter. A digit gets the number sign (⠼) only at the start of a run of digits.

### 7.4 To implement before user trials (MVP-1 gate)

1. **Hand-present interlock in the app.** The Pico sends F9 down/up. With no hand: feed hold (`!`) + `M5`; resume (`~`) only after the hand returns and the user presses Pause/Resume.
2. **Calibration screen.** Jog, set zero (`G10 L20 P1 X0 Y0`), and a test letter (§9).
3. **Braille driver output** (phase 2): send the cell dot patterns to the driver board.
4. **Hold-current change** after pull-in (`S400`) in `event_gcode`.

---

## 8. Build guide (MVP-1)

1. **Cut the plates.** P01 (tray parts), P02 and P03 from the DXF exported from the CAD (FreeCAD: select the face → Draft → Shape2DView → export DXF). Check the window, button and pin hole positions against §4.1.
2. **Print** P10–P17 in PETG (0.2 mm layers, 4 walls, 40 % infill). Press in the bushings, then ream them to slide freely on the rods.
3. **Assemble the base tray.** Glue the walls to the floor and check it is flat and square (diagonals within 0.5 mm). Fit the rubber feet.
4. **Mount the rails.** Screw the pillars to the floor at the §4.3 positions. Insert the y-rails at z 34 and the x-rails at z 48, and check they are parallel (±0.2 mm along the length).
5. **Fit the bars.** Slide the end blocks onto the rails. Fit the Y-bar and X-bar through the carriage, and check that the carriage moves freely over the whole 70 × 70 mm range.
6. **Drives.** Mount the steppers, sync shafts (625ZZ blocks), pulleys and idlers. Clamp the belts into the tabs **with both ends of each bar at the same position** (square the bar against the pillars first). Then tension the belts.
7. **Pen.** Mount the solenoid on the carriage bracket. Fit the pen, sleeve and force spring, starting with tip T10.
8. **Electronics.** Mount the Uno + shield, MOSFET, Pico and TTP223 on standoffs in the front bay. Wire per §5.2. Set the TMC2209 Vref.
9. **Flash and configure** GRBL (§6). Home it (`$H`), then jog to confirm the directions.
10. **Top plate.** Laminate P03 on P02. Fit the buttons and the brass pad. Screw the plate down. The pen must pass through the window with ≥ 2 mm clearance at every corner of the workspace.
11. **App.** Connect, run calibration (§9), then write test letters.

---

## 9. Calibration

1. **Home** with `$H`.
2. **Zero:** jog the pen (retracted) under the window centre; a cross on masking tape over the window helps. Then send `G10 L20 P1 X0 Y0`.
3. **Height and force:**
   1. With `M3 S1000`, the tip must stand **1.5 ± 0.3 mm above the recess floor**. Adjust with the sleeve or shims.
   2. Measure the force: put a pocket scale, upside down, on spacers over the window. Target **40–80 g (0.4–0.8 N)**.
   3. Adjust the spring preload with shims.
4. **Orientation (P1):** with a person's hand on the box, write `L`, `F` and `R`. The person reports which way each letter faces. Set "palm-down box (mirror)" to match, or set `$3`.
5. **Workspace:** run `G0` to the four corners (±35, ±35). There must be no contact with the window edge.

---

## 10. Test plan

| ID | Test | Pass criterion |
|---|---|---|
| T1 | CAD clearance: `freecadcmd haptic_box_v2.FCMacro` | Prints `CLEARANCES OK`. Pen tip +1.5 down / −6.0 up |
| T2 | Repeatability: draw a 40 mm square 20× on paper taped over the window (pencil tip) | Line width spread ≤ 0.6 mm |
| T3 | Speed: write the pangram (`palm_writer.py --check`) | ≥ 25 letters/min with no lost steps (square still closes afterwards) |
| T4 | Pen timing: high-speed phone video of 20 taps | Up and down ≤ 50 ms each |
| T5 | Interlock: lift the hand mid-letter | Pen retracts and motion stops within 100 ms |
| T6 | Tip/force comfort (P2): 3 tips × 3 forces, 5 participants, 5 min each | Choose the combination with the best clarity and no discomfort |
| T7 | Orientation (P1): 10 asymmetric letters, mirrored vs not | Choose the version with the higher recognition rate |
| T8 | Recognition: 26 letters in random order, sizes 35/45/55 mm | ≥ 80 % recognition after a 10 min familiarisation (first target) |
| T9 | Session comfort: 20 min continuous use | No wrist or forearm discomfort with the forearm pad |
| T10 | End-to-end: a person speaks 5 sentences | Every finalised phrase is written. Queue, repeat and skip behave as specified |

Run trials with deafblind people **together with their organisations or interpreters**. Get informed consent in an accessible format.

---

## 11. Phases and MVP

| Phase | Scope | Exit criteria |
|---|---|---|
| **MVP-0: bench rig** | Gantry + pen on an open baseboard (no top plate). App + GRBL. Writes on paper and on a hand held over it | T2, T3, T4 pass |
| **MVP-1: first box** *(the prototype in the CAD)* | Base tray, 2-layer top plate with recess and window, forearm pad, 3 buttons via Pico, hand-present pad, laptop app, USB mic. Braille on screen only | T1–T10 run with ≥ 5 participants. Decide P1, P2, P4, P5 |
| **Phase 2: standalone** | Raspberry Pi 5 inside, piezo Braille cells, power button, enclosure finish (printed/moulded tray), left-hand plate | Usable without a screen. Braille synchronised with the pen |

## 12. Risks

| ID | Risk | Mitigation |
|---|---|---|
| R1 | **Throughput:** speech ~150 words/min vs palm ~6 words/min | Turn-taking indicator for the speaker. Skip-to-newest. Braille-only mode (faster). Optional opt-in summarising (open question 3) |
| R2 | A pointed tip feels sharp | Spring-limited force, interchangeable tips, test T6 |
| R3 | Fingers or objects in the open window | Hand-present interlock, low motor current, optional membrane (P4) |
| R4 | A bar racks (skews) if the belt ends are clamped unevenly | Both ends belt-driven from one sync shaft. Square the bar at assembly (§8.6) |
| R5 | Solenoid heat and noise | Hold current S400. A felt washer at the end stop |
| R6 | Speech errors write wrong words | Final-only results. Repeat/skip controls. Larger Vosk model on the Pi |
| R7 | The GRBL spindle pin mix-up (D11 vs the D12 shield label) | Wire by GRBL 1.1 pin number (§5.2) |
| R8 | Braille cell cost and availability | Phase 2. Keep a screen-Braille fallback |

---

## Appendix A: v0.1 (superseded)

v0.1 had the hand inserted palm up into an enclosed box, written on from above by a stylus on a 5-bar linkage with a hinged lift deck (`haptic_box.FCMacro`, `palm_writer.py --check`). It was replaced because the review chose:
- an open top with the palm down
- a pen from below
- one-plane XY motion
- buttons and Braille around the hand.

The v0.1 files stay in the repo for reference. Its kinematics check still runs.

## Appendix B: Regenerating the CAD and images

```
cd haptic-box
HAPTIC_DUMP=build/v2_mesh.json freecadcmd haptic_box_v2.FCMacro   # checks, .FCStd, .step, meshes
python3 render_views.py                                           # all renders → renders/
python3 render_views.py top section detail                        # selected views
freecad haptic_box_v2.FCMacro                                     # interactive 3D, animates TEXT
```

All dimensions are parameters at the top of `haptic_box_v2.FCMacro`, for example `BOX_W/L/H`, `WINDOW`, `PEN_PRESS`, `HAND`, `Z_YBAR/Z_XBAR`. After changing any of them, re-run both commands and update §4.1 and §4.3.
