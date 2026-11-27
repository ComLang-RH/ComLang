/* Hardware abstraction: everything the firmware needs from the board. Two implementations:
   rp2040/hal_rp2040.c (the real box) and sim/hal_sim.c (the simulated box the demo talks to). */
#pragma once
#include <stdbool.h>
#include <stdint.h>

enum { AXIS_X, AXIS_Y };
enum { MOTOR_A, MOTOR_B };            /* CoreXY: A moves the pen along x + y, B along x - y */
enum { BTN_WHEEL, BTN_REPEAT, BTN_MODE, BTN_RESET, BTN_COUNT };

void     hal_init(void);
uint32_t hal_now_ms(void);
void     hal_watchdog_kick(void);
uint32_t hal_critical_enter(void);           /* motion state shared with the tick interrupt */
void     hal_critical_exit(uint32_t saved);

void     hal_motor_enable(bool on);          /* drivers on (off = motors free-wheel) */
float    hal_motor_angle(int m);             /* rotor angle, rad, continuous (magnetic encoder) */
void     hal_motor_torque(int m, float u);   /* torque command -1..1; the HAL commutates (FOC) */
bool     hal_limit(int axis);                /* home switch closed (x / y) */
void     hal_pen_duty(uint16_t permille);    /* solenoid PWM, 0 = off */

bool     hal_button(int id);                 /* raw, true = pressed */
bool     hal_hand(void);                     /* raw hand-present sensor, true = hand */
int32_t  hal_encoder(void);                  /* thumb roller: counts (4 per detent) */

void     hal_braille_drive(uint16_t up, uint16_t down);  /* latching pins: energise these (bit =
                                                cell * 6 + dot - 1) up / down; (0, 0) = all off */

void     hal_lcd_fill(int x, int y, int w, int h, uint16_t rgb565);
void     hal_lcd_flush(void);                /* end of a frame */

int      hal_link_getc(void);                /* next byte from the host, or -1 */
void     hal_link_write(const char *s);
