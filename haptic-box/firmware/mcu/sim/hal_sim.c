/* Simulated board: the SAME firmware (src/) runs on the PC against a model of the box's hardware.
   This is what the demo app talks to.

     comlang_sim [--hw-in FD] [--hw-out FD] [--fb PATH]

   USB link       = stdin / stdout (exactly the bytes a real controller would get / send)
   hardware in    = --hw-in lines:  btn <wheel|repeat|mode|reset> <0|1>,  enc <counts>,
                    hand <0|1>,  jam <0|1> (something blocks the carriage),  quit
   hardware out   = --hw-out lines whenever an actuator changes:
                    pen <permille>,  br <mask> <mask> (pins latched up),  fb  (LCD frame written)
   Physical model (CoreXY, flat gimbal BLDC motors): torque = command x TAU_MAX on each rotor,
   belt force = torque / ring radius; the carriage (x) and gantry + carriage (y) masses plus the
   reflected rotor inertia, viscous + Coulomb friction, hard stops 1 mm past the home switches and
   3 mm past the travel; 14-bit magnetic encoders. Braille pins latch only after a long enough
   pulse. The carriage starts at an unknown position, so the firmware must home. Real time. */
#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <math.h>
#include <fcntl.h>
#include <poll.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

#include "../src/config.h"
#include "../src/fw.h"
#include "../src/hal.h"

static int hw_in = -1, hw_out = -1;
static const char *fb_path;
static uint16_t fb[LCD_H][LCD_W];
/* mechanics (SI units inside the model) */
#define TAU_MAX   0.08                  /* N m at |u| = 1 (2804-class gimbal motor at 12 V) */
#define R_RING    (RING_R_MM / 1000.0)
#define M_CARR    0.035                 /* kg: carriage + pen head */
#define M_GANTRY  0.090                 /* kg: Y-blocks, X-rods, idlers */
#define J_ROTOR   1.2e-6                /* kg m^2 per rotor + ring pulley */
#define C_VISC    0.6                   /* N per m/s */
#define F_COUL    0.25                  /* N */
static double px, py, vx, vy;           /* carriage position (m, from the switches) and speed */
static double a0, b0;                   /* belt coordinates at power-up (encoder zero) */
static double u_cmd[2];
static bool drivers_on, jammed;
static uint16_t pins_up, pulse_up, pulse_down;
static int pulse_ticks;
static bool buttons[BTN_COUNT], hand_on = true;
static int32_t enc;
static uint16_t pen_duty;
static char inbuf[65536];
static size_t in_r, in_w;
static int link_eof;

static uint64_t now_us(void) {
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return (uint64_t)t.tv_sec * 1000000u + (uint64_t)t.tv_nsec / 1000u;
}
static uint64_t t0;

static void hw(const char *fmt, ...) __attribute__((format(printf, 1, 2)));
#include <stdarg.h>
static void hw(const char *fmt, ...) {
    if (hw_out < 0) return;
    char b[128];
    va_list ap;
    va_start(ap, fmt);
    int n = vsnprintf(b, sizeof b, fmt, ap);
    va_end(ap);
    if (n > 0 && write(hw_out, b, (size_t)n) < 0) { /* demo gone */ }
}

/* ---- HAL */
void hal_init(void) {}
uint32_t hal_now_ms(void) { return (uint32_t)((now_us() - t0) / 1000u); }
void hal_watchdog_kick(void) {}
uint32_t hal_critical_enter(void) { return 0; }   /* single thread: tick runs from the loop */
void hal_critical_exit(uint32_t s) { (void)s; }
void hal_motor_enable(bool on) { drivers_on = on; }

static double belt_a(void) { return px + py; }
static double belt_b(void) { return px - py; }

float hal_motor_angle(int m) {
    double belt = (m == MOTOR_A ? belt_a() - a0 : belt_b() - b0);   /* m */
    double ang = belt / R_RING;
    const double q = 2 * 3.14159265358979 / 16384.0;               /* 14-bit encoder */
    return (float)(floor(ang / q) * q);
}

void hal_motor_torque(int m, float u) { u_cmd[m] = u > 1 ? 1 : u < -1 ? -1 : u; }

bool hal_limit(int axis) { return (axis == AXIS_X ? px : py) <= 0.0; }

static void physics(double dt) {
    double fa = drivers_on ? u_cmd[0] * TAU_MAX / R_RING : 0;     /* belt forces, N */
    double fb = drivers_on ? u_cmd[1] * TAU_MAX / R_RING : 0;
    double jr = 2 * J_ROTOR / (R_RING * R_RING);                  /* reflected rotor inertia */
    double v[2] = {vx, vy}, f[2] = {fa + fb, fa - fb}, m[2] = {M_CARR + jr, M_CARR + M_GANTRY + jr};
    for (int i = 0; i < 2; i++) {
        double fr = C_VISC * v[i] + (v[i] > 1e-4 ? F_COUL : v[i] < -1e-4 ? -F_COUL : 0);
        if (fabs(v[i]) <= 1e-4 && fabs(f[i]) <= F_COUL) { v[i] = 0; continue; }   /* static friction */
        v[i] += (f[i] - fr) / m[i] * dt;
    }
    if (jammed) v[0] = v[1] = 0;                                  /* something blocks the carriage */
    vx = v[0];
    vy = v[1];
    px += vx * dt;
    py += vy * dt;
    double lo = -0.001, hi = (TRAVEL_MM + 3.0) / 1000.0;          /* hard stops */
    if (px < lo) { px = lo; vx = 0; }
    if (px > hi) { px = hi; vx = 0; }
    if (py < lo) { py = lo; vy = 0; }
    if (py > hi) { py = hi; vy = 0; }
    if (pulse_ticks > 0 && --pulse_ticks == 0) {                  /* latching pins: long enough pulse */
        uint16_t before = pins_up;
        pins_up = (uint16_t)((pins_up | pulse_up) & ~pulse_down);
        if (pins_up != before) hw("br %u %u\n", pins_up & 63, (pins_up >> 6) & 63);
    }
}

void hal_braille_drive(uint16_t up, uint16_t down) {
    if (up || down) {                                             /* pins move ~3 ms into a pulse */
        pulse_up = up;
        pulse_down = down;
        pulse_ticks = (int)(0.003 * TICK_HZ);
    } else if (pulse_ticks > 0) {
        pulse_ticks = 0;                                          /* pulse too short: nothing moved */
    }
}

void hal_pen_duty(uint16_t permille) {
    if (permille != pen_duty) { pen_duty = permille; hw("pen %u\n", permille); }
}
bool hal_button(int id) { return buttons[id]; }
bool hal_hand(void) { return hand_on; }
int32_t hal_encoder(void) { return enc; }

void hal_lcd_fill(int x, int y, int w, int h, uint16_t c) {
    if (x < 0) { w += x; x = 0; }
    if (y < 0) { h += y; y = 0; }
    if (x + w > LCD_W) w = LCD_W - x;
    if (y + h > LCD_H) h = LCD_H - y;
    for (int j = 0; j < h; j++)
        for (int i = 0; i < w; i++) fb[y + j][x + i] = c;
}

void hal_lcd_flush(void) {
    if (!fb_path) return;
    char tmp[1024];
    snprintf(tmp, sizeof tmp, "%s.tmp", fb_path);
    FILE *f = fopen(tmp, "wb");
    if (!f) return;
    fwrite(fb, sizeof fb, 1, f);
    fclose(f);
    rename(tmp, fb_path);
    hw("fb\n");
}

int hal_link_getc(void) {
    if (in_r == in_w) return -1;
    return (unsigned char)inbuf[in_r++ % sizeof inbuf];
}

void hal_link_write(const char *s) {
    fputs(s, stdout);
    fflush(stdout);
}

/* ---- simulator main */
static void hw_line(char *ln) {
    static const char *const NAMES[BTN_COUNT] = {"wheel", "repeat", "mode", "reset"};
    char name[16];
    int v;
    if (sscanf(ln, "btn %15s %d", name, &v) == 2) {
        for (int i = 0; i < BTN_COUNT; i++)
            if (!strcmp(name, NAMES[i])) buttons[i] = v != 0;
    } else if (sscanf(ln, "enc %d", &v) == 1) enc += v;
    else if (sscanf(ln, "hand %d", &v) == 1) hand_on = v != 0;
    else if (sscanf(ln, "jam %d", &v) == 1) jammed = v != 0;
    else if (!strncmp(ln, "quit", 4)) exit(0);
}

int main(int argc, char **argv) {
    for (int i = 1; i + 1 < argc; i += 2) {
        if (!strcmp(argv[i], "--hw-in")) hw_in = atoi(argv[i + 1]);
        else if (!strcmp(argv[i], "--hw-out")) hw_out = atoi(argv[i + 1]);
        else if (!strcmp(argv[i], "--fb")) fb_path = argv[i + 1];
    }
    srand((unsigned)time(NULL));
    px = (10 + rand() % 50) / 1000.0;                          /* unknown start: must home */
    py = (10 + rand() % 50) / 1000.0;
    a0 = belt_a();
    b0 = belt_b();
    t0 = now_us();
    fcntl(0, F_SETFL, fcntl(0, F_GETFL) | O_NONBLOCK);
    fw_init();
    uint64_t ticked = now_us();
    char hwbuf[512];
    size_t hwlen = 0;
    for (;;) {
        struct pollfd p[2] = {{0, POLLIN, 0}, {hw_in, POLLIN, 0}};
        poll(p, hw_in >= 0 ? 2 : 1, 1);
        if (!link_eof && (p[0].revents & (POLLIN | POLLHUP))) {
            while (in_w - in_r < sizeof inbuf - 1) {          /* back-pressure when the firmware is busy */
                size_t room = sizeof inbuf - (in_w - in_r), at = in_w % sizeof inbuf;
                size_t chunk = sizeof inbuf - at < room ? sizeof inbuf - at : room;
                ssize_t n = read(0, inbuf + at, chunk);
                if (n > 0) in_w += (size_t)n;
                else { if (n == 0) link_eof = 1; break; }
            }
        }
        if (hw_in >= 0 && (p[1].revents & (POLLIN | POLLHUP))) {
            ssize_t n = read(hw_in, hwbuf + hwlen, sizeof hwbuf - 1 - hwlen);
            if (n <= 0) exit(0);                                 /* demo closed the pipe */
            hwlen += (size_t)n;
            char *nl;
            while ((nl = memchr(hwbuf, '\n', hwlen))) {
                *nl = 0;
                hw_line(hwbuf);
                size_t used = (size_t)(nl - hwbuf) + 1;
                memmove(hwbuf, nl + 1, hwlen - used);
                hwlen -= used;
            }
        }
        /* run the motion interrupt for the real time that has passed */
        uint64_t t = now_us();
        uint64_t due = (t - ticked) * TICK_HZ / 1000000u;
        if (due > TICK_HZ / 10) due = TICK_HZ / 10;
        for (uint64_t i = 0; i < due; i++) {
            fw_tick();
            physics(1.0 / TICK_HZ);
        }
        ticked += due * 1000000u / TICK_HZ;
        if (t - ticked > 200000u) ticked = t;                  /* fell behind: let time slip */
        fw_loop();
        if (link_eof && in_r == in_w) {
            /* host gone: finish what is queued, then stop */
            static uint64_t idle_since;
            if (!idle_since) idle_since = t;
            if (t - idle_since > 30000000u) return 0;
        }
    }
}
