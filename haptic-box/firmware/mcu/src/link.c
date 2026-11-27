/* Host link: assemble lines from USB CDC and dispatch them (format: comlang/protocol.py).
   Queued commands go to the motion queue; when it is full the line waits (and USB flow control
   holds the host back) until there is room. */
#include <stdlib.h>
#include <string.h>

#include "config.h"
#include "fw.h"
#include "hal.h"
#include "motion.h"

static char line[LINE_MAX];
static int len;
static bool ready, overflow;

static int ints(const char *s, int32_t *v, int n) {
    int got = 0;
    while (got < n) {
        char *e;
        long x = strtol(s, &e, 10);
        if (e == s) break;
        v[got++] = (int32_t)x;
        s = e;
    }
    return got;
}

/* returns false if the line must be retried later (queue full) */
static bool dispatch(const char *ln) {
    int32_t v[3] = {0, 0, 0};
    const char *args = ln + 1;
    switch (ln[0]) {
    case 'm': case 'p': case 'd': case 'b': {
        int need = ln[0] == 'm' ? 3 : ln[0] == 'b' ? 2 : 1;
        if (ints(args, v, need) != need) { report("err bad %s", ln); return true; }
        cmd_t c = {ln[0], v[0], v[1], v[2]};
        return motion_push(&c);
    }
    case '!': motion_abort(); break;
    case 'H': motion_hold(true); break;
    case 'R': motion_hold(false); break;
    case 'V': if (ints(args, v, 1) == 1) motion_speed(v[0]); break;
    case 'G': motion_home(); break;
    case 'O': if (ints(args, v, 2) == 2) motion_set_offset(v[0], v[1]); break;
    case '?': status_report(); break;
    case 'C':
        if (!strncmp(args, " hand_sensor ", 13)) controls_config_hand_sensor(atoi(args + 13) != 0);
        else report("err unknown config");
        break;
    case 'W': case 'T': case 'P': case 'S': display_set(ln); break;
    case 0: break;
    default: report("err unknown %c", ln[0]);
    }
    return true;
}

void link_poll(void) {
    for (int budget = 4096; budget > 0; budget--) {
        if (ready) {
            if (!dispatch(line)) return;          /* queue full: try again next loop */
            ready = false;
            len = 0;
        }
        int ch = hal_link_getc();
        if (ch < 0) return;
        if (ch == '\r') continue;
        if (ch == '\n') {
            line[len] = 0;
            if (overflow) report("err line too long");
            else ready = true;
            if (overflow) len = 0;
            overflow = false;
            continue;
        }
        if (len < LINE_MAX - 1) line[len++] = (char)ch;
        else overflow = true;
    }
}
