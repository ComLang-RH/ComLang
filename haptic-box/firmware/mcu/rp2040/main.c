/* RP2040 entry point: the motion + motor control tick runs from a 10 kHz repeating timer,
   everything else in the main loop. NOT YET COMPILED (see hal_rp2040.c). */
#include "pico/stdlib.h"

#include "../src/config.h"
#include "../src/fw.h"

static bool tick_cb(repeating_timer_t *t) {
    (void)t;
    fw_tick();
    return true;
}

int main(void) {
    fw_init();
    static repeating_timer_t timer;
    add_repeating_timer_us(-(int64_t)(1000000 / TICK_HZ), tick_cb, NULL, &timer);
    for (;;) fw_loop();
}
