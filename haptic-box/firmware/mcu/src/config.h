/* ComLang box controller: machine constants. Motion limits and pen timing come from the host
   engine via generated.h; mechanical values are from DESIGN.md §4.3 / §5 (20 mm box: CoreXY,
   two flat gimbal BLDC motors with magnetic encoders, latching Braille pins). */
#pragma once
#include "generated.h"

#define TICK_HZ              10000      /* planner + motor control loop rate */
/* CoreXY: motor A moves the pen along x + y, motor B along x - y (belt mm) */
#define RING_R_MM            15.9f      /* GT2 50T ring pulley on each motor rotor (pitch radius) */
#define POLE_PAIRS           7          /* 2804-class gimbal motor, 12N14P */
#define TRAVEL_MM            75.0f      /* machine travel per axis, home switch at 0 */
#define PALM_CENTRE_MM       37.5f      /* default work zero; host sends the calibrated O */
#define V_MAX_MM_S           GEN_V_TRAVEL_MM_S
#define ACCEL                GEN_ACCEL_MM_S2
#define HOME_SPEED_MM_S      40.0f
#define HOME_PULLOFF_MM      2.0f
/* position control per motor (belt mm): torque command u in -1..1 of the motor's max */
#define KP_PER_MM            0.6f       /* u per mm of position error */
#define KD_PER_MM_S          0.004f     /* u per mm/s of velocity error */
#define KI_PER_MM_S          4.0f       /* u per mm*s of integrated error */
#define KFF_ACCEL            0.00009f   /* u per mm/s^2 of commanded acceleration (feed-forward) */
#define TORQUE_LIMIT         0.7f       /* caps the belt force (~3.5 N): limited pinch force */
#define FOLLOW_ERR_MM        1.5f       /* following error that counts as a stall / obstruction */
#define FOLLOW_ERR_MS        60
#define SETTLE_MM            0.15f      /* a move ends when the pen is this close to the target */
#define SETTLE_MAX_S         0.06f
#define BRAILLE_PULSE_MS     4          /* latching pin actuators: set / reset pulse length */
#define HOLD_RAMP_S          0.05f      /* hold / resume deceleration time */
#define PEN_PULLIN_S         0.03f      /* solenoid full current, then hold current */
#define PEN_HOLD_PERMILLE    400
#define PEN_SETTLE_S         GEN_T_PEN_S /* after re-lowering the pen on resume */

#define QUEUE_LEN            256        /* queued commands (power of two) */
#define LINE_MAX             1024
#define DEBOUNCE_MS          10
#define HAND_DEBOUNCE_MS     200
#define ENC_COUNTS_PER_DETENT 4      /* thumb roller: the HAL turns the roller angle into counts */
#define WHEEL_AWAY_POSITIVE  1          /* DESIGN.md P12: roll away from the palm = faster */
#define DISPLAY_MIN_MS       40         /* redraw the speaker display at most this often */
#define X_REPORT_MS          10

#define LCD_W 480
#define LCD_H 320
