/* ComLang box controller firmware: main loop and tick. Board-independent; see hal.h. */
#include <stdarg.h>
#include <stdio.h>

#include "config.h"
#include "fw.h"
#include "hal.h"
#include "motion.h"

static uint32_t last_x, x_time;

void report(const char *fmt, ...) {
    char buf[160];
    va_list ap;
    va_start(ap, fmt);
    int n = vsnprintf(buf, sizeof buf - 1, fmt, ap);
    va_end(ap);
    if (n < 0) return;
    if (n > (int)sizeof buf - 2) n = (int)sizeof buf - 2;
    buf[n] = '\n';
    buf[n + 1] = 0;
    hal_link_write(buf);
}

void status_report(void) {
    motion_status_t s;
    motion_status(&s);
    report("A %ld %ld %d %d %d %d %d %d %d %d", (long)s.x, (long)s.y, s.pen, s.hold, controls_armed(),
           controls_hand(), s.homed, s.depth, s.braille[0], s.braille[1]);
}

void fw_init(void) {
    hal_init();
    motion_init();
    controls_init();
    display_init();
    braille_set(0, 0);
    report("# ComLang controller ready");
}

void fw_tick(void) { motion_tick(); }

void fw_loop(void) {
    static const char *const ERR[] = {"", "not_homed", "limit", "home_failed", "stall"};
    hal_watchdog_kick();
    link_poll();
    controls_poll();
    uint32_t now = hal_now_ms(), x = motion_executed();
    if (x != last_x && now - x_time >= X_REPORT_MS) {
        last_x = x;
        x_time = now;
        report("X %lu", (unsigned long)x);
    }
    int e = motion_take_error();
    if (e) report("err %s", ERR[e]);
    display_poll();
}
