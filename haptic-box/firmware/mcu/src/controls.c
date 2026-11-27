/* Controls and the safety rule. Buttons and the hand sensor are debounced here; the thumb
   wheel is a quadrature encoder. Every control is reported to the host ('E <action>'), but the
   safety-relevant ones act LOCALLY first, without waiting for the host:
     wheel press  -> hold / resume (only with the hand on the box; also re-arms after removal
                     and resumes after a stall)
     Reset        -> stop now, drop the queue, pen off
     hand removed -> stop now, hold, disarm: nothing moves until the hand is back AND the
                     wheel is pressed
   The pen can only start a command while (no sensor configured) or (hand present and armed). */
#include "config.h"
#include "fw.h"
#include "generated.h"
#include "hal.h"
#include "motion.h"

static struct { bool raw, stable; uint32_t t; } btn[BTN_COUNT], hand;
static int32_t enc_last;
static bool armed, hand_sensor = true;

static void act(int a) { report("E %s", ACTION_NAME[a]); }
static bool hand_ok(void) { return !hand_sensor || hand.stable; }

void controls_init(void) {
    for (int i = 0; i < BTN_COUNT; i++) btn[i].raw = btn[i].stable = hal_button(i);
    hand.raw = hand.stable = hal_hand();
    armed = hand.stable;                 /* a hand already resting at power-up may write */
    if (!armed) motion_hold(true);       /* no hand: held, like after a removal (host agrees) */
    enc_last = hal_encoder();
}

void controls_config_hand_sensor(bool on) {
    hand_sensor = on;
    if (!on && !armed) {                 /* bench without a sensor: release the power-up hold */
        armed = true;
        motion_hold(false);
    }
}

bool controls_armed(void) { return armed; }
bool controls_hand(void) { return hand.stable; }

static void pressed(int id) {
    switch (id) {
    case BTN_WHEEL:
        if (hand_ok()) {
            armed = true;
            motion_hold(!motion_holding());
        }
        act(ACT_PAUSE);
        break;
    case BTN_REPEAT: act(ACT_REPEAT); break;
    case BTN_MODE: act(ACT_MODE); break;
    case BTN_RESET:
        motion_abort();
        act(ACT_RESET);
        break;
    }
}

static void hand_changed(bool present) {
    if (!present) {
        motion_abort();
        motion_hold(true);
        armed = false;
        act(ACT_HAND_OFF);
    } else {
        act(ACT_HAND_ON);
    }
}

void controls_poll(void) {
    uint32_t now = hal_now_ms();
    for (int i = 0; i < BTN_COUNT; i++) {
        bool r = hal_button(i);
        if (r != btn[i].raw) { btn[i].raw = r; btn[i].t = now; }
        else if (r != btn[i].stable && now - btn[i].t >= DEBOUNCE_MS) {
            btn[i].stable = r;
            if (r) pressed(i);
        }
    }
    if (hand_sensor) {
        bool r = hal_hand();
        if (r != hand.raw) { hand.raw = r; hand.t = now; }
        else if (r != hand.stable && now - hand.t >= HAND_DEBOUNCE_MS) {
            hand.stable = r;
            hand_changed(r);
        }
    }
    int32_t d = hal_encoder() - enc_last;
    while (d >= ENC_COUNTS_PER_DETENT || d <= -ENC_COUNTS_PER_DETENT) {
        int s = d > 0 ? 1 : -1;
        enc_last += s * ENC_COUNTS_PER_DETENT;
        d -= s * ENC_COUNTS_PER_DETENT;
        act((s > 0) == (WHEEL_AWAY_POSITIVE != 0) ? ACT_FASTER : ACT_SLOWER);
    }
    motion_allow(!hand_sensor || (hand.stable && armed));
}
