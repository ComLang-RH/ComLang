#pragma once
#include <stdbool.h>
#include <stdint.h>

typedef struct { char op; int32_t a, b, c; } cmd_t;   /* queued: m p d b (protocol.py) */

enum { ERR_NONE, ERR_NOT_HOMED, ERR_LIMIT, ERR_HOME_FAILED, ERR_STALL };

typedef struct {                 /* snapshot for the status report */
    int32_t x, y;                /* work position, 0.01 mm, measured by the motor encoders */
    bool pen, hold, homed;
    int depth;
    uint8_t braille[2];
} motion_status_t;

void     motion_init(void);
bool     motion_push(const cmd_t *c);   /* false when the queue is full */
void     motion_abort(void);            /* stop now, drop the queue, pen off */
void     motion_hold(bool on);
bool     motion_holding(void);
void     motion_speed(int percent);
void     motion_home(void);
void     motion_set_offset(int32_t x, int32_t y);
void     motion_allow(bool allowed);    /* safety gate from the controls */
uint32_t motion_executed(void);
int      motion_take_error(void);
void     motion_status(motion_status_t *s);
void     motion_tick(void);             /* TICK_HZ control interrupt */
