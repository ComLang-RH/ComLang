/* Speaker display (3.5" 480x320): the word being written with the current letter highlighted,
   the recent transcript (cancelled words struck through in red), and a status line. The content
   comes from the host (W / T / P / S messages, protocol.py); the drawing happens here. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "config.h"
#include "fw.h"
#include "generated.h"
#include "hal.h"

#define RGB(r, g, b) (uint16_t)((((r) >> 3) << 11) | (((g) >> 2) << 5) | ((b) >> 3))
#define C_BLACK  RGB(0, 0, 0)
#define C_WHITE  RGB(255, 255, 255)
#define C_GREY   RGB(154, 154, 154)
#define C_DIM    RGB(110, 110, 110)
#define C_YELLOW RGB(255, 216, 74)
#define C_RED    RGB(224, 88, 74)

static char word[40], trans[LINE_MAX], partial[200], mode[16] = "both";
static int k = -1, waiting, paused, hand_present = 1;
static bool dirty = true;
static uint32_t last_draw;

void display_init(void) { dirty = true; }

static void copy(char *dst, size_t n, const char *src) {
    snprintf(dst, n, "%s", src);
}

void display_set(const char *ln) {
    const char *body = ln[1] == ' ' ? ln + 2 : ln + 1;
    switch (ln[0]) {
    case 'W': {
        const char *sp = strrchr(body, ' ');
        if (!sp) return;
        size_t n = (size_t)(sp - body);
        if (n >= sizeof word) n = sizeof word - 1;
        memcpy(word, body, n);
        word[n] = 0;
        if (!strcmp(word, "-")) word[0] = 0;
        k = atoi(sp + 1);
        break;
    }
    case 'T': copy(trans, sizeof trans, body); break;
    case 'P': copy(partial, sizeof partial, body); break;
    case 'S': {
        char m[16];
        if (sscanf(body, "%15[^|]|%d|%d|%d", m, &waiting, &paused, &hand_present) == 4) copy(mode, sizeof mode, m);
        break;
    }
    default: return;
    }
    dirty = true;
}

/* ---- drawing */
static void glyph(int x, int y, char c, int sc, uint16_t fg, uint16_t bg) {
    if (c < 32 || c > 126) c = '?';
    const uint8_t *g = FONT[c - 32];
    hal_lcd_fill(x, y, FONT_W * sc, FONT_H * sc, bg);
    for (int r = 0; r < FONT_H; r++) {
        int col = 0;
        while (col < FONT_W) {                    /* runs of set pixels -> one fill each */
            if (!(g[r] & (0x80 >> col))) { col++; continue; }
            int c0 = col;
            while (col < FONT_W && (g[r] & (0x80 >> col))) col++;
            hal_lcd_fill(x + c0 * sc, y + r * sc, (col - c0) * sc, sc, fg);
        }
    }
}

static int text(int x, int y, const char *s, int n, int sc, uint16_t fg, uint16_t bg) {
    for (int i = 0; i < n && s[i]; i++, x += FONT_W * sc) glyph(x, y, s[i], sc, fg, bg);
    return x;
}

#define T_SC 2
#define T_CW (FONT_W * T_SC)
#define T_COLS ((LCD_W - 16) / T_CW)
#define T_TOP 78
#define T_LH 30
#define T_LINES 6

typedef struct { const char *s; int n; char st; } tok_t;

static void draw(void) {
    hal_lcd_fill(0, 0, LCD_W, LCD_H, C_BLACK);
    /* current word, scale 4 */
    int x = 8, n = (int)strlen(word);
    for (int i = 0; i < n && x < LCD_W - 32; i++) {
        uint16_t fg = i < k ? C_DIM : C_WHITE, bg = C_BLACK;
        if (i == k) { fg = C_BLACK; bg = C_YELLOW; }
        glyph(x, 8, word[i], 4, fg, bg);
        x += FONT_W * 4;
    }
    hal_lcd_fill(8, 68, LCD_W - 16, 2, C_DIM);
    /* transcript: tokens, wrapped, last T_LINES lines */
    static tok_t tok[160];
    int nt = 0;
    for (const char *p = trans; *p && nt < 159;) {
        while (*p == ' ') p++;
        if (!*p) break;
        const char *e = p;
        while (*e && *e != ' ') e++;
        char st = 'd';
        if (*p == '*' || *p == '+' || *p == '~') st = *p++;
        tok[nt++] = (tok_t){p, (int)(e - p), st};
        p = e;
    }
    if (partial[0]) tok[nt++] = (tok_t){partial, (int)strlen(partial), 'p'};
    int line[160], col = 0, ln = 0;
    for (int i = 0; i < nt; i++) {
        int w = tok[i].n > T_COLS ? T_COLS : tok[i].n;
        if (col && col + w > T_COLS) { ln++; col = 0; }
        line[i] = ln;
        col += w + 1;
    }
    int first = ln - T_LINES + 1 > 0 ? ln - T_LINES + 1 : 0;
    col = 0;
    int cur = -1;
    for (int i = 0; i < nt; i++) {
        if (line[i] != cur) { cur = line[i]; col = 0; }
        int w = tok[i].n > T_COLS ? T_COLS : tok[i].n;
        if (line[i] >= first) {
            int tx = 8 + col * T_CW, ty = T_TOP + (line[i] - first) * T_LH;
            uint16_t fg = tok[i].st == '*' ? C_YELLOW : tok[i].st == '+' ? C_WHITE :
                          tok[i].st == '~' ? C_RED : tok[i].st == 'p' ? C_DIM : C_GREY;
            text(tx, ty, tok[i].s, w, T_SC, fg, C_BLACK);
            if (tok[i].st == '~') hal_lcd_fill(tx, ty + FONT_H * T_SC / 2, w * T_CW, 3, C_RED);
        }
        col += w + 1;
    }
    /* status line */
    hal_lcd_fill(8, 276, LCD_W - 16, 2, C_DIM);
    const char *label = mode;
    for (int i = 0; i < MODE_COUNT; i++)
        if (!strcmp(mode, MODE_KEY[i])) label = MODE_LABEL[i];
    char s[96];
    snprintf(s, sizeof s, "%s | %d waiting%s%s", label, waiting, paused ? " | PAUSED" : "",
             hand_present ? "" : " | NO HAND");
    text(8, 288, s, (int)strlen(s), 2, C_GREY, C_BLACK);
    hal_lcd_flush();
}

void display_poll(void) {
    uint32_t now = hal_now_ms();
    if (dirty && now - last_draw >= DISPLAY_MIN_MS) {
        dirty = false;
        last_draw = now;
        draw();
    }
}
