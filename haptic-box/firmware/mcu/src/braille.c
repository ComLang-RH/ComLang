/* Pop-out Braille: two cells of six latching (bistable) pin actuators. A pin moves only during a
   short current pulse (up or down) and then stays without power, so changing a letter energises
   just the pins that change, for BRAILLE_PULSE_MS. Called from the motion tick, so the cells
   change exactly when the queued 'b' command is reached (in step with the pen). */
#include <stdint.h>

#include "config.h"
#include "fw.h"
#include "hal.h"

static uint16_t cur, want;               /* bit = cell * 6 + dot - 1 */
static uint32_t pulse;
static uint8_t shown[2];

static void start(void) {
    uint16_t up = want & ~cur, down = cur & ~want;
    if (!up && !down) return;
    hal_braille_drive(up, down);
    cur = want;
    pulse = (uint32_t)(BRAILLE_PULSE_MS * TICK_HZ / 1000) + 1;
}

void braille_set(uint8_t c1, uint8_t c2) {
    shown[0] = c1 & 63;
    shown[1] = c2 & 63;
    want = (uint16_t)(shown[0] | (shown[1] << 6));
    if (!pulse) start();                 /* else applied when the running pulse ends */
}

void braille_tick(void) {
    if (pulse && --pulse == 0) {
        hal_braille_drive(0, 0);
        if (want != cur) start();
    }
}

void braille_cells(uint8_t *c) {
    c[0] = shown[0];
    c[1] = shown[1];
}
