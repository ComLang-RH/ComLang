/* Motion: a queue of commands from the host, executed by the TICK_HZ control interrupt.
   Moves follow a trapezoidal speed profile; each tick sets the servo's position target (and the
   feed-forward acceleration) for both axes; servo.c turns that into motor torques (CoreXY).
   A move ends when the pen has settled on its end point. Hold / resume warp time down to zero and
   back (smooth stop), lifting the pen while held. The safety gate (hand present and armed) stops
   new commands from starting; the controls call motion_abort() when the hand leaves. A stall
   (something blocking the carriage) stops everything, lifts the pen and holds. */
#include <math.h>
#include <stddef.h>

#include "config.h"
#include "fw.h"
#include "hal.h"
#include "motion.h"
#include "servo.h"

#define DT (1.0f / TICK_HZ)

static cmd_t q[QUEUE_LEN];
static volatile uint32_t q_head, q_tail;          /* head: main loop, tail: tick */
static volatile uint32_t executed;
static volatile bool hold_req, allowed = true, home_req;
static volatile int speed_pct = 100;
static volatile int err;

static float pos[2];                              /* commanded machine position, mm */
static float off[2] = {PALM_CENTRE_MM, PALM_CENTRE_MM};
static bool homed, stalled;

enum { B_NONE, B_MOVE, B_DWELL, B_HOME };
static int b_type;
static float b_start[2], b_dir[2], b_len, b_v, b_tacc, b_tflat, b_T, b_t, b_dwell, b_settle;
static float rate;                                /* 0 = held, 1 = running */
static bool pen_on, pen_lifted;
static uint32_t pen_ticks, settle_ticks;
static int home_axis, home_phase;
static float home_pos;

void motion_init(void) {
    servo_init();
    servo_position(&pos[0], &pos[1]);
    hal_pen_duty(0);
    rate = 1.0f;
}

bool motion_push(const cmd_t *c) {
    uint32_t h = q_head;
    if (h - q_tail >= QUEUE_LEN) return false;
    q[h % QUEUE_LEN] = *c;
    __sync_synchronize();
    q_head = h + 1;
    return true;
}

static void pen_set(bool on) {
    pen_on = on;
    pen_ticks = 0;
    hal_pen_duty(on ? 1000 : 0);
}

static void stop_here(void) {                     /* hold the carriage where it is */
    servo_position(&pos[0], &pos[1]);
    servo_set_target(pos[0], pos[1], 0, 0);
}

void motion_abort(void) {
    uint32_t s = hal_critical_enter();
    uint32_t dropped = q_head - q_tail + (b_type == B_MOVE || b_type == B_DWELL ? 1 : 0);
    if (b_type == B_HOME) homed = false;
    q_tail = q_head;
    executed += dropped;
    b_type = B_NONE;
    home_req = false;
    pen_set(false);
    pen_lifted = false;
    settle_ticks = 0;
    if (!stalled) stop_here();
    hal_critical_exit(s);
}

void motion_hold(bool on) {
    if (!on && stalled) {                         /* resuming after a stall: hold here, re-enable */
        uint32_t s = hal_critical_enter();
        stalled = false;
        servo_clear_fault();
        stop_here();
        hal_critical_exit(s);
    }
    hold_req = on;
}

bool motion_holding(void) { return hold_req; }
void motion_speed(int percent) { speed_pct = percent < 10 ? 10 : percent > 400 ? 400 : percent; }
void motion_home(void) { home_req = true; }
void motion_allow(bool a) { allowed = a; }
uint32_t motion_executed(void) { return executed; }

void motion_set_offset(int32_t x, int32_t y) {
    off[0] = x / 100.0f;
    off[1] = y / 100.0f;
}

int motion_take_error(void) {
    int e = err;
    err = ERR_NONE;
    return e;
}

void motion_status(motion_status_t *s) {
    uint32_t c = hal_critical_enter();
    float x, y;
    servo_position(&x, &y);
    s->x = (int32_t)lroundf((x - off[0]) * 100.0f);
    s->y = (int32_t)lroundf((y - off[1]) * 100.0f);
    s->pen = pen_on;
    s->hold = hold_req;
    s->homed = homed;
    s->depth = (int)(q_head - q_tail) + (b_type != B_NONE ? 1 : 0);
    braille_cells(s->braille);
    hal_critical_exit(c);
}

/* ---------------------------------------------------------------- tick (interrupt) */
static bool start_move(const cmd_t *c) {
    float tx = c->a / 100.0f + off[0], ty = c->b / 100.0f + off[1];
    if (!homed) { err = ERR_NOT_HOMED; return false; }
    if (tx < 0 || ty < 0 || tx > TRAVEL_MM || ty > TRAVEL_MM) { err = ERR_LIMIT; return false; }
    float dx = tx - pos[0], dy = ty - pos[1];
    b_len = sqrtf(dx * dx + dy * dy);
    b_start[0] = pos[0];
    b_start[1] = pos[1];
    pos[0] = tx;
    pos[1] = ty;
    if (b_len < 1e-4f) { b_dir[0] = b_dir[1] = 0; b_T = 0; b_v = 1; b_tacc = b_tflat = 0; }
    else {
        b_dir[0] = dx / b_len;
        b_dir[1] = dy / b_len;
        b_v = c->c * speed_pct / 100.0f;
        if (b_v > V_MAX_MM_S) b_v = V_MAX_MM_S;
        if (b_v < 1.0f) b_v = 1.0f;
        b_tacc = b_v / ACCEL;
        if (ACCEL * b_tacc * b_tacc > b_len) {    /* triangle profile */
            b_tacc = sqrtf(b_len / ACCEL);
            b_v = ACCEL * b_tacc;
        }
        b_tflat = (b_len - ACCEL * b_tacc * b_tacc) / b_v;
        b_T = 2 * b_tacc + b_tflat;
    }
    b_t = b_settle = 0;
    b_type = B_MOVE;
    return true;
}

static float s_at(float t, float *acc) {
    *acc = 0;
    if (t <= 0) return 0;
    if (t >= b_T) return b_len;
    if (t < b_tacc) { *acc = ACCEL; return 0.5f * ACCEL * t * t; }
    if (t < b_tacc + b_tflat) return 0.5f * ACCEL * b_tacc * b_tacc + b_v * (t - b_tacc);
    float r = b_T - t;
    *acc = -ACCEL;
    return b_len - 0.5f * ACCEL * r * r;
}

static void start_next(void) {
    while (q_tail != q_head) {
        cmd_t c = q[q_tail % QUEUE_LEN];
        __sync_synchronize();
        q_tail = q_tail + 1;
        switch (c.op) {
        case 'm':
            if (start_move(&c)) return;
            break;                                 /* rejected: counts as done */
        case 'd':
            b_dwell = c.a / 1000.0f * 100.0f / speed_pct;
            b_type = B_DWELL;
            return;
        case 'p':
            pen_set(c.a != 0);
            break;
        case 'b':
            braille_set((uint8_t)c.a, (uint8_t)c.b);
            break;
        default:
            break;
        }
        executed = executed + 1;
        if (hold_req || !allowed) return;          /* stop between commands too */
    }
}

static void update_rate(void) {
    const float k = DT / HOLD_RAMP_S;
    if (hold_req || !allowed) {
        rate -= k;
        if (rate < 0) rate = 0;
        if (rate == 0 && pen_on && !pen_lifted) {  /* never leave the pen pressed while held */
            pen_set(false);
            pen_lifted = true;
        }
    } else {
        if (pen_lifted) {
            pen_set(true);
            pen_lifted = false;
            settle_ticks = (uint32_t)(PEN_SETTLE_S * TICK_HZ);
        }
        if (settle_ticks) settle_ticks--;
        else if (rate < 1) {
            rate += k;
            if (rate > 1) rate = 1;
        }
    }
}

static void home_tick(void) {
    /* phase 0: drive the axis towards - until its switch closes; that point is machine 0;
       phase 1: back off to HOME_PULLOFF_MM. X first, then Y. */
    float step = HOME_SPEED_MM_S * DT;
    if (home_phase == 0) {
        if (hal_limit(home_axis)) {
            servo_home_ref(home_axis, 0.0f);
            float x, y;
            servo_position(&x, &y);
            pos[0] = x;
            pos[1] = y;
            home_pos = 0.0f;
            home_phase = 1;
            return;
        }
        home_pos -= step;
        if (home_pos < -(TRAVEL_MM + 10.0f)) {     /* no switch: stop, report */
            err = ERR_HOME_FAILED;
            b_type = B_NONE;
            stop_here();
            return;
        }
    } else {
        home_pos += step;
        if (home_pos >= HOME_PULLOFF_MM) {
            home_pos = HOME_PULLOFF_MM;
            pos[home_axis] = HOME_PULLOFF_MM;
            if (home_axis == AXIS_Y) { homed = true; b_type = B_NONE; return; }
            home_axis = AXIS_Y;
            home_phase = 0;
            float x, y;
            servo_position(&x, &y);
            home_pos = y;                          /* start Y from where it is (unreferenced) */
            pos[0] = HOME_PULLOFF_MM;
            pos[1] = y;
            servo_set_target(pos[0], pos[1], 0, 0);
            return;
        }
    }
    float t[2] = {pos[0], pos[1]};
    t[home_axis] = home_pos;
    servo_set_target(t[0], t[1], 0, 0);
}

void motion_tick(void) {
    braille_tick();
    if (pen_on && pen_ticks < (uint32_t)(PEN_PULLIN_S * TICK_HZ)) {
        if (++pen_ticks == (uint32_t)(PEN_PULLIN_S * TICK_HZ)) hal_pen_duty(PEN_HOLD_PERMILLE);
    }
    if (servo_fault() && !stalled) {               /* blocked carriage: stop, pen off, hold */
        stalled = true;
        uint32_t dropped = q_head - q_tail + (b_type == B_MOVE || b_type == B_DWELL ? 1 : 0);
        q_tail = q_head;
        executed += dropped;
        if (b_type == B_HOME) homed = false;
        b_type = B_NONE;
        pen_set(false);
        pen_lifted = false;
        hold_req = true;
        err = ERR_STALL;
    }
    servo_tick();
    if (stalled) return;
    update_rate();
    if (home_req && b_type == B_NONE) {
        home_req = false;
        homed = false;
        pen_set(false);
        b_type = B_HOME;
        home_axis = AXIS_X;
        home_phase = 0;
        float x, y;
        servo_position(&x, &y);
        pos[0] = x;
        pos[1] = y;
        home_pos = x;
    }
    if (b_type == B_HOME) { home_tick(); return; }
    if (b_type == B_NONE && !hold_req && allowed) start_next();
    if (b_type == B_MOVE) {
        b_t += DT * rate;
        float acc, s = s_at(b_t, &acc);
        acc *= rate * rate;
        servo_set_target(b_start[0] + b_dir[0] * s, b_start[1] + b_dir[1] * s, b_dir[0] * acc, b_dir[1] * acc);
        if (b_t >= b_T) {
            b_settle += DT;
            if (servo_error() < SETTLE_MM || b_settle > SETTLE_MAX_S) {
                b_type = B_NONE;
                executed = executed + 1;
            }
        }
    } else if (b_type == B_DWELL) {
        b_dwell -= DT * rate;
        if (b_dwell <= 0) {
            b_type = B_NONE;
            executed = executed + 1;
        }
    }
}
