#pragma once
#include <stdbool.h>
#include <stdint.h>

void fw_init(void);
void fw_loop(void);                  /* main loop body: link, controls, display, reports */
void fw_tick(void);                  /* TICK_HZ timer interrupt */

/* shared between modules (main loop only) */
void report(const char *fmt, ...);   /* one line to the host */
void controls_init(void);
void controls_poll(void);
void controls_config_hand_sensor(bool on);
bool controls_armed(void);
bool controls_hand(void);
void display_init(void);
void display_set(const char *line);  /* W / T / P / S message */
void display_poll(void);
void link_poll(void);
void status_report(void);
void braille_set(uint8_t c1, uint8_t c2);   /* braille.c */
void braille_tick(void);
void braille_cells(uint8_t *c);
