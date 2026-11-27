/* Closed-loop position control of the two flat BLDC motors (CoreXY).
   Belt coordinates: a = x + y (motor A), b = x - y (motor B), each = rotor angle x ring radius.
   Per motor: PID on the belt position + feed-forward of the commanded acceleration, torque
   limited (TORQUE_LIMIT) so the carriage can never push harder than a few newtons. A following
   error above FOLLOW_ERR_MM for FOLLOW_ERR_MS means something blocks the carriage: the motors
   are released and servo_fault() reports it (the motion layer stops the pen and holds). */
#include <math.h>
#include <stdbool.h>

#include "config.h"
#include "hal.h"
#include "servo.h"

#define DT (1.0f / TICK_HZ)

static float ref[2];                     /* raw (encoder) position of machine 0, per axis */
static float tgt[2], tgt_prev[2], acc_ff[2];
static float pos_prev[2], vel[2], integ[2];
static float err_max;
static uint32_t over_ticks;
static volatile bool fault;
static bool enabled;

static float belt(int m) { return hal_motor_angle(m) * RING_R_MM; }

static void raw_xy(float *x, float *y) {
    float a = belt(MOTOR_A), b = belt(MOTOR_B);
    *x = 0.5f * (a + b);
    *y = 0.5f * (a - b);
}

void servo_position(float *x, float *y) {
    raw_xy(x, y);
    *x -= ref[0];
    *y -= ref[1];
}

static void to_belts(float x, float y, float *ab) {   /* machine -> belt (raw) */
    float rx = x + ref[0], ry = y + ref[1];
    ab[0] = rx + ry;
    ab[1] = rx - ry;
}

void servo_init(void) {
    float x, y;
    servo_position(&x, &y);
    float ab[2];
    to_belts(x, y, ab);
    for (int m = 0; m < 2; m++) {
        tgt[m] = tgt_prev[m] = ab[m];
        pos_prev[m] = belt(m);
        vel[m] = integ[m] = acc_ff[m] = 0;
    }
    over_ticks = 0;
    fault = false;
    enabled = true;
    hal_motor_enable(true);
}

void servo_set_target(float x, float y, float ax, float ay) {
    float ab[2];
    to_belts(x, y, ab);
    tgt[0] = ab[0];
    tgt[1] = ab[1];
    acc_ff[0] = ax + ay;
    acc_ff[1] = ax - ay;
}

void servo_home_ref(int axis, float machine) {
    float x, y;
    raw_xy(&x, &y);
    ref[axis] = (axis == 0 ? x : y) - machine;
}

bool servo_fault(void) { return fault; }

void servo_clear_fault(void) { servo_init(); }

float servo_error(void) { return err_max; }

void servo_tick(void) {
    if (!enabled) return;
    float worst = 0;
    for (int m = 0; m < 2; m++) {
        float p = belt(m);
        float v = (p - pos_prev[m]) / DT;
        pos_prev[m] = p;
        vel[m] += 0.2f * (v - vel[m]);                     /* light low-pass on the speed */
        float vt = (tgt[m] - tgt_prev[m]) / DT;
        tgt_prev[m] = tgt[m];
        float e = tgt[m] - p;
        integ[m] += e * DT;
        if (integ[m] > 0.05f) integ[m] = 0.05f;
        if (integ[m] < -0.05f) integ[m] = -0.05f;
        float u = KP_PER_MM * e + KD_PER_MM_S * (vt - vel[m]) + KI_PER_MM_S * integ[m] + KFF_ACCEL * acc_ff[m];
        if (u > TORQUE_LIMIT) u = TORQUE_LIMIT;
        if (u < -TORQUE_LIMIT) u = -TORQUE_LIMIT;
        hal_motor_torque(m, u);
        if (fabsf(e) > worst) worst = fabsf(e);
    }
    err_max = worst;
    if (worst > FOLLOW_ERR_MM) {
        if (++over_ticks > (uint32_t)(FOLLOW_ERR_MS * TICK_HZ / 1000)) {
            fault = true;                                  /* blocked: let go */
            enabled = false;
            hal_motor_torque(MOTOR_A, 0);
            hal_motor_torque(MOTOR_B, 0);
            hal_motor_enable(false);
        }
    } else {
        over_ticks = 0;
    }
}
