/* The real box: Raspberry Pi Pico (RP2040), Pico SDK 2.x. Two flat gimbal BLDC motors on DRV8313
   drivers with MT6701 magnetic encoders (voltage-mode FOC here, position control in servo.c),
   ST7796S LCD on SPI0; encoders and latching Braille pin drivers on SPI1.
   NOT YET COMPILED OR RUN ON HARDWARE (no ARM toolchain where this was written): build with
   PICO_SDK_PATH set (DESIGN.md §6) and check pins, LCD init and Braille order. */
#include <math.h>
#include <stdio.h>

#include "hardware/clocks.h"
#include "hardware/gpio.h"
#include "hardware/pwm.h"
#include "hardware/spi.h"
#include "hardware/sync.h"
#include "hardware/watchdog.h"
#include "pico/stdlib.h"

#include "../src/config.h"
#include "../src/fw.h"
#include "../src/hal.h"

/* pins: DESIGN.md §5.2 (all 26 GPIO used) */
#define PIN_X_LIM 0       /* home switches to GND, pull-up: closed = low */
#define PIN_Y_LIM 1
#define PIN_MA_U 2        /* motor A phases: PWM slice 1 A/B, slice 2 A */
#define PIN_MA_V 3
#define PIN_MA_W 4
#define PIN_MB_U 5        /* motor B phases: PWM slice 2 B, slice 3 A/B */
#define PIN_MB_V 6
#define PIN_MB_W 7
#define PIN_PEN 8         /* pen MOSFET gate: PWM slice 4 A */
#define PIN_HAND 9        /* TTP223 output, high = touched */
#define PIN_ENC_SCK 10    /* SPI1 (used only from the control interrupt): three MT6701 encoders */
#define PIN_BR_DATA 11    /* SPI1 MOSI: Braille driver shift registers (outputs change on latch) */
#define PIN_ENC_MISO 12
#define PIN_ENC_CS_A 13
#define PIN_ENC_CS_B 14
#define PIN_ENC_CS_ROLLER 15
#define PIN_LCD_DC 16
#define PIN_LCD_CS 17
#define PIN_SPI0_SCK 18   /* SPI0: LCD only (main loop) */
#define PIN_SPI0_MOSI 19
#define PIN_DRV_EN 20     /* both DRV8313 drivers enable (high = on); LCD reset is on the RUN line */
#define PIN_BR_LATCH 21   /* Braille drivers latch (LCD backlight is tied on) */
#define PIN_BTN_WHEEL 22  /* roller press switch */
#define PIN_BTN_REPEAT 26
#define PIN_BTN_MODE 27
#define PIN_BTN_RESET 28
#define V_SUPPLY 12.0f
#define V_LIMIT 6.0f      /* phase voltage at |u| = 1 (gimbal motor ~10 ohm: < 0.6 A) */
#define V_ALIGN 3.0f
#define PWM_WRAP 2499     /* 25 kHz centre-aligned at 125 MHz */
#define ROLLER_COUNTS_PER_REV 48   /* 12 knurl ribs = 12 detents x 4 counts */

static const uint BTN_PIN[BTN_COUNT] = {PIN_BTN_WHEEL, PIN_BTN_REPEAT, PIN_BTN_MODE, PIN_BTN_RESET};
static const uint PH[2][3] = {{PIN_MA_U, PIN_MA_V, PIN_MA_W}, {PIN_MB_U, PIN_MB_V, PIN_MB_W}};
static const uint ENC_CS[3] = {PIN_ENC_CS_A, PIN_ENC_CS_B, PIN_ENC_CS_ROLLER};
static float turns_ang[3], last_raw[3], e_off[2], mech[2];
static int32_t turns[3];
static bool drv_on;

static void in_pullup(uint pin) {
    gpio_init(pin);
    gpio_set_dir(pin, GPIO_IN);
    gpio_pull_up(pin);
}
static void out(uint pin, bool v) {
    gpio_init(pin);
    gpio_set_dir(pin, GPIO_OUT);
    gpio_put(pin, v);
}

/* ---- MT6701 over SSI (SPI1 mode 1, 24 bits: 14-bit angle + status + CRC) */
static float enc_read_raw(int i) {
    uint8_t rx[3] = {0, 0, 0}, tx[3] = {0, 0, 0};
    gpio_put(ENC_CS[i], 0);
    spi_write_read_blocking(spi1, tx, rx, 3);
    gpio_put(ENC_CS[i], 1);
    uint32_t v = ((uint32_t)rx[0] << 6) | (rx[1] >> 2);       /* 14-bit angle */
    return (float)v * (6.2831853f / 16384.0f);
}

static float enc_angle(int i) {                               /* continuous, multi-turn */
    float r = enc_read_raw(i), d = r - last_raw[i];
    if (d > 3.14159265f) turns[i]--;
    if (d < -3.14159265f) turns[i]++;
    last_raw[i] = r;
    turns_ang[i] = r + 6.2831853f * (float)turns[i];
    return turns_ang[i];
}

/* ---- three-phase PWM (sinusoidal commutation from the rotor angle) */
static void phase_volts(int m, float va, float vb, float vc) {
    float v[3] = {va, vb, vc};
    for (int k = 0; k < 3; k++) {
        float d = 0.5f + v[k] / V_SUPPLY;
        if (d < 0) d = 0;
        if (d > 1) d = 1;
        pwm_set_gpio_level(PH[m][k], (uint16_t)(d * PWM_WRAP));
    }
}

static void set_dq(int m, float ud, float uq, float th_e) {
    float s = sinf(th_e), c = cosf(th_e);
    float al = ud * c - uq * s, be = ud * s + uq * c;         /* inverse Park */
    phase_volts(m, al, -0.5f * al + 0.8660254f * be, -0.5f * al - 0.8660254f * be);   /* inverse Clarke */
}

static void motors_align(void) {
    /* hold the rotor at electrical angle 0 and read where it settled: that is the offset */
    for (int m = 0; m < 2; m++) {
        set_dq(m, V_ALIGN, 0, 0);
        sleep_ms(400);
        e_off[m] = (float)POLE_PAIRS * enc_angle(m);
        set_dq(m, 0, 0, 0);
    }
}

/* ---- ST7796S over SPI0 */
static void lcd_cmd(uint8_t c, const uint8_t *d, size_t n) {
    gpio_put(PIN_LCD_CS, 0);
    gpio_put(PIN_LCD_DC, 0);
    spi_write_blocking(spi0, &c, 1);
    gpio_put(PIN_LCD_DC, 1);
    if (n) spi_write_blocking(spi0, d, n);
    gpio_put(PIN_LCD_CS, 1);
}

static void lcd_init(void) {
    spi_init(spi0, 20 * 1000 * 1000);                  /* ~30 cm ribbon from the front board */
    gpio_set_function(PIN_SPI0_SCK, GPIO_FUNC_SPI);
    gpio_set_function(PIN_SPI0_MOSI, GPIO_FUNC_SPI);
    out(PIN_LCD_CS, 1);
    out(PIN_LCD_DC, 1);
    sleep_ms(120);                                     /* hardware reset comes from the RUN line */
    lcd_cmd(0x01, NULL, 0); sleep_ms(150);             /* software reset */
    lcd_cmd(0x11, NULL, 0); sleep_ms(120);             /* sleep out */
    uint8_t colmod = 0x55, madctl = 0x28 | 0x80 | 0x40; /* 16 bit; landscape, rotated 180 deg for the speaker */
    lcd_cmd(0x3A, &colmod, 1);
    lcd_cmd(0x36, &madctl, 1);
    lcd_cmd(0x21, NULL, 0);                            /* inversion on (IPS) */
    lcd_cmd(0x29, NULL, 0); sleep_ms(20);              /* display on (backlight tied on) */
}

void hal_lcd_fill(int x, int y, int w, int h, uint16_t c) {
    if (x < 0) { w += x; x = 0; }
    if (y < 0) { h += y; y = 0; }
    if (x + w > LCD_W) w = LCD_W - x;
    if (y + h > LCD_H) h = LCD_H - y;
    if (w <= 0 || h <= 0) return;
    uint8_t ca[4] = {(uint8_t)(x >> 8), (uint8_t)x, (uint8_t)((x + w - 1) >> 8), (uint8_t)(x + w - 1)};
    uint8_t ra[4] = {(uint8_t)(y >> 8), (uint8_t)y, (uint8_t)((y + h - 1) >> 8), (uint8_t)(y + h - 1)};
    lcd_cmd(0x2A, ca, 4);
    lcd_cmd(0x2B, ra, 4);
    static uint8_t buf[256];
    for (size_t i = 0; i < sizeof buf; i += 2) { buf[i] = (uint8_t)(c >> 8); buf[i + 1] = (uint8_t)c; }
    uint8_t ramwr = 0x2C;
    gpio_put(PIN_LCD_CS, 0);
    gpio_put(PIN_LCD_DC, 0);
    spi_write_blocking(spi0, &ramwr, 1);
    gpio_put(PIN_LCD_DC, 1);
    size_t left = (size_t)w * (size_t)h * 2;
    while (left) {
        size_t n = left < sizeof buf ? left : sizeof buf;
        spi_write_blocking(spi0, buf, n);
        left -= n;
    }
    gpio_put(PIN_LCD_CS, 1);
}

void hal_lcd_flush(void) {}

/* ---- HAL */
void hal_init(void) {
    stdio_usb_init();
    in_pullup(PIN_X_LIM);
    in_pullup(PIN_Y_LIM);
    for (int i = 0; i < BTN_COUNT; i++) in_pullup(BTN_PIN[i]);
    gpio_init(PIN_HAND);
    gpio_set_dir(PIN_HAND, GPIO_IN);
    gpio_pull_down(PIN_HAND);
    out(PIN_DRV_EN, 0);
    for (int m = 0; m < 2; m++)                        /* 25 kHz centre-aligned phase PWM */
        for (int k = 0; k < 3; k++) {
            uint pin = PH[m][k], sl = pwm_gpio_to_slice_num(pin);
            gpio_set_function(pin, GPIO_FUNC_PWM);
            pwm_set_phase_correct(sl, true);
            pwm_set_wrap(sl, PWM_WRAP);
            pwm_set_gpio_level(pin, PWM_WRAP / 2);
            pwm_set_enabled(sl, true);
        }
    gpio_set_function(PIN_PEN, GPIO_FUNC_PWM);         /* pen: 20 kHz, level 0..1000 */
    uint ps = pwm_gpio_to_slice_num(PIN_PEN);
    pwm_set_clkdiv(ps, (float)clock_get_hz(clk_sys) / (20000.0f * 1000.0f));
    pwm_set_wrap(ps, 999);
    pwm_set_gpio_level(PIN_PEN, 0);
    pwm_set_enabled(ps, true);
    spi_init(spi1, 10 * 1000 * 1000);                  /* encoders */
    spi_set_format(spi1, 8, SPI_CPOL_0, SPI_CPHA_1, SPI_MSB_FIRST);
    gpio_set_function(PIN_ENC_SCK, GPIO_FUNC_SPI);
    gpio_set_function(PIN_ENC_MISO, GPIO_FUNC_SPI);
    gpio_set_function(PIN_BR_DATA, GPIO_FUNC_SPI);
    for (int i = 0; i < 3; i++) {
        out(ENC_CS[i], 1);
        last_raw[i] = enc_read_raw(i);
    }
    out(PIN_BR_LATCH, 0);
    lcd_init();
    gpio_put(PIN_DRV_EN, 1);
    drv_on = true;
    motors_align();                                    /* the carriage nudges < 1 mm at power-up */
    watchdog_enable(200, true);                        /* a hung loop resets: pen and motors off */
}

uint32_t hal_now_ms(void) { return to_ms_since_boot(get_absolute_time()); }
void hal_watchdog_kick(void) { watchdog_update(); }
uint32_t hal_critical_enter(void) { return save_and_disable_interrupts(); }
void hal_critical_exit(uint32_t s) { restore_interrupts(s); }

void hal_motor_enable(bool on) {
    drv_on = on;
    gpio_put(PIN_DRV_EN, on);
}

float hal_motor_angle(int m) {
    mech[m] = enc_angle(m);
    return mech[m];
}

void hal_motor_torque(int m, float u) {               /* voltage-mode FOC: q-axis voltage ~ torque */
    if (!drv_on) { phase_volts(m, 0, 0, 0); return; }
    float th_e = (float)POLE_PAIRS * mech[m] - e_off[m];
    set_dq(m, 0, u * V_LIMIT, th_e);
}

bool hal_limit(int axis) { return !gpio_get(axis == AXIS_X ? PIN_X_LIM : PIN_Y_LIM); }
void hal_pen_duty(uint16_t permille) { pwm_set_gpio_level(PIN_PEN, permille > 1000 ? 1000 : permille); }
bool hal_button(int id) { return !gpio_get(BTN_PIN[id]); }
bool hal_hand(void) { return gpio_get(PIN_HAND); }

int32_t hal_encoder(void) {                           /* thumb roller: angle -> counts */
    return (int32_t)floorf(enc_angle(2) / 6.2831853f * ROLLER_COUNTS_PER_REV);
}

void hal_braille_drive(uint16_t up, uint16_t down) {
    /* 24 outputs (an H-bridge per pin: up / down coil ends) via 3 shift registers on SPI1.
       Called from the control interrupt, like the encoder reads, so SPI1 is never shared
       across contexts. The registers shift during encoder reads too, but only latch here. */
    uint8_t b[3] = {0, 0, 0};
    for (int i = 0; i < 12; i++) {
        if (up & (1u << i)) b[(2 * i) / 8] |= (uint8_t)(1u << ((2 * i) % 8));
        if (down & (1u << i)) b[(2 * i + 1) / 8] |= (uint8_t)(1u << ((2 * i + 1) % 8));
    }
    uint8_t tx[3] = {b[2], b[1], b[0]};                /* last register first */
    spi_set_format(spi1, 8, SPI_CPOL_0, SPI_CPHA_0, SPI_MSB_FIRST);   /* 74HC595 samples on rising edge */
    spi_write_blocking(spi1, tx, 3);
    spi_set_format(spi1, 8, SPI_CPOL_0, SPI_CPHA_1, SPI_MSB_FIRST);   /* back to the encoders' mode */
    gpio_put(PIN_BR_LATCH, 1);
    busy_wait_at_least_cycles(30);
    gpio_put(PIN_BR_LATCH, 0);
}

int hal_link_getc(void) {
    int c = getchar_timeout_us(0);
    return c == PICO_ERROR_TIMEOUT ? -1 : c;
}

void hal_link_write(const char *s) {
    fputs(s, stdout);
    fflush(stdout);
}
