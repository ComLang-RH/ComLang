#pragma once
#include <stdbool.h>

/* CoreXY position control of the two motors, in machine mm (x, y). */
void  servo_init(void);
void  servo_set_target(float x, float y, float ax, float ay);   /* position + feed-forward accel */
void  servo_tick(void);                       /* TICK_HZ */
void  servo_position(float *x, float *y);     /* actual, from the encoders */
float servo_error(void);                      /* worst motor position error, mm */
void  servo_home_ref(int axis, float machine);/* homing: the actual position on `axis` is `machine` */
bool  servo_fault(void);                      /* stalled / obstructed: motors released */
void  servo_clear_fault(void);                /* hold where it is now and re-enable */
