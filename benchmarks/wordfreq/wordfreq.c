/* wordfreq: word-frequency count of the real-world text corpus: tokenize
 * (lower-cased alphanumeric words), count in an open-addressing hash table,
 * then rank the vocabulary by frequency (the classic text-analytics kernel).
 * Exercises: character classification branches, hashing, random memory
 * access, sorting with a comparator.
 * usage: wordfreq <corpus file> <rounds>
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "../common/bench_io.h"
#include "../common/bench_timer.h"

#define TBITS 18
#define TSIZE (1u << TBITS)
#define TOPK 25

typedef struct {
    uint32_t off;     /* word start in the lower-cased text */
    uint32_t len;
    uint32_t count;
    uint32_t hash;
} entry;

static entry table[TSIZE];
static const uint8_t *g_text;

static inline int is_word(uint8_t ch) {
    return (ch >= 'a' && ch <= 'z') || (ch >= '0' && ch <= '9') || ch == '_';
}

static int by_count(const void *x, const void *y) {
    const entry *a = x, *b = y;
    if (a->count != b->count) return a->count < b->count ? 1 : -1;
    uint32_t m = a->len < b->len ? a->len : b->len;
    int c = memcmp(g_text + a->off, g_text + b->off, m);
    if (c) return c;
    return (a->len > b->len) - (a->len < b->len);
}

static uint64_t count_words(const uint8_t *text, size_t n, uint32_t *distinct) {
    memset(table, 0, sizeof table);
    uint32_t used = 0;
    size_t i = 0;
    while (i < n) {
        while (i < n && !is_word(text[i])) i++;
        size_t s = i;
        uint32_t h = 2166136261u; /* FNV-1a */
        while (i < n && is_word(text[i])) { h = (h ^ text[i]) * 16777619u; i++; }
        if (i == s) break;
        uint32_t len = (uint32_t)(i - s);
        if (h == 0) h = 1;
        uint32_t slot = h & (TSIZE - 1);
        for (;;) {
            entry *e = &table[slot];
            if (e->hash == 0) {
                e->hash = h; e->off = (uint32_t)s; e->len = len; e->count = 1;
                used++;
                break;
            }
            if (e->hash == h && e->len == len && memcmp(text + e->off, text + s, len) == 0) {
                e->count++;
                break;
            }
            slot = (slot + 1) & (TSIZE - 1);
        }
    }
    /* compact and rank */
    entry *list = malloc(sizeof(entry) * (used ? used : 1));
    uint32_t k = 0;
    for (uint32_t t = 0; t < TSIZE; t++)
        if (table[t].hash) list[k++] = table[t];
    g_text = text;
    qsort(list, k, sizeof(entry), by_count);
    uint64_t acc = 0;
    for (uint32_t r = 0; r < TOPK && r < k; r++) {
        uint64_t wh = 1469598103934665603ull;
        for (uint32_t c = 0; c < list[r].len; c++) wh = (wh ^ text[list[r].off + c]) * 1099511628211ull;
        acc = acc * 31 + (uint64_t)list[r].count * (r + 1) + (wh & 0xffff);
    }
    free(list);
    *distinct = k;
    return acc;
}

int main(int argc, char **argv) {
    if (argc < 2) return 2;
    int rounds = argc > 2 ? atoi(argv[2]) : 6;
    size_t n;
    uint8_t *raw = bench_read_file(argv[1], &n);
    if (!raw) return 2;
    if (n >= (1u << 31)) return 2;

    uint64_t t0 = bench_now_ns();
    uint64_t acc = 0;
    uint32_t distinct = 0;
    uint8_t *text = malloc(n + 1);
    for (int r = 0; r < rounds; r++) {
        for (size_t i = 0; i < n; i++) {               /* lower-case pass */
            uint8_t ch = raw[i];
            text[i] = (ch >= 'A' && ch <= 'Z') ? (uint8_t)(ch + 32) : ch;
        }
        acc = acc * 1000003u + count_words(text, n, &distinct);
    }
    uint64_t t1 = bench_now_ns();

    bench_report_u64(acc * 1000003u + distinct, t1 - t0);
    free(raw); free(text);
    return 0;
}
