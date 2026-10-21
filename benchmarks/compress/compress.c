/* compress: LZ77/LZSS compression with hash chains (the match finder used by
 * gzip/zlib-style compressors), followed by decompression and a byte-exact
 * round-trip check, over the real-world text corpus.
 * Exercises: string matching loops, branches, memory access patterns.
 * usage: compress <corpus file> <rounds>
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "../common/bench_io.h"
#include "../common/bench_timer.h"

#define WBITS 15
#define WSIZE (1u << WBITS)
#define WMASK (WSIZE - 1)
#define HBITS 15
#define HSIZE (1u << HBITS)
#define MINM 3
#define MAXM 258
#define MAXCHAIN 48

static int32_t head[HSIZE];
static int32_t prev_pos[WSIZE];

static inline uint32_t hash3(const uint8_t *p) {
    return (((uint32_t)p[0] << 10) ^ ((uint32_t)p[1] << 5) ^ p[2]) & (HSIZE - 1);
}

static inline void insert(const uint8_t *in, size_t n, size_t pos) {
    if (pos + MINM > n) return;
    uint32_t h = hash3(in + pos);
    prev_pos[pos & WMASK] = head[h];
    head[h] = (int32_t)pos;
}

/* Output format: groups of 8 items, each group preceded by a flag byte.
 * flag bit 1 = match (2 bytes distance, 1 byte length-3), 0 = literal byte. */
static size_t lz_compress(const uint8_t *in, size_t n, uint8_t *out) {
    for (uint32_t i = 0; i < HSIZE; i++) head[i] = -1;
    size_t op = 0, i = 0, flagpos = op++;
    int bit = 0;
    out[flagpos] = 0;
    while (i < n) {
        size_t best_len = 0, best_dist = 0;
        if (i + MINM <= n) {
            size_t maxlen = n - i < MAXM ? n - i : MAXM;
            int32_t j = head[hash3(in + i)];
            int chain = MAXCHAIN;
            while (j >= 0 && i - (size_t)j < WSIZE && chain-- > 0) {
                if (in[(size_t)j + best_len] == in[i + best_len]) {
                    size_t l = 0;
                    while (l < maxlen && in[(size_t)j + l] == in[i + l]) l++;
                    if (l > best_len) {
                        best_len = l;
                        best_dist = i - (size_t)j;
                        if (l == maxlen) break;
                    }
                }
                int32_t nj = prev_pos[(size_t)j & WMASK];
                if (nj >= j) break; /* slot was reused by a newer position */
                j = nj;
            }
        }
        if (best_len >= MINM) {
            out[flagpos] |= (uint8_t)(1u << bit);
            out[op++] = (uint8_t)(best_dist & 0xff);
            out[op++] = (uint8_t)(best_dist >> 8);
            out[op++] = (uint8_t)(best_len - MINM);
            for (size_t k = 0; k < best_len; k++) insert(in, n, i + k);
            i += best_len;
        } else {
            out[op++] = in[i];
            insert(in, n, i);
            i++;
        }
        if (++bit == 8) {
            bit = 0;
            flagpos = op++;
            out[flagpos] = 0;
        }
    }
    return op;
}

static size_t lz_decompress(const uint8_t *in, size_t m, uint8_t *out, size_t n) {
    size_t ip = 0, op = 0;
    while (op < n && ip < m) {
        uint8_t flags = in[ip++];
        for (int bit = 0; bit < 8 && op < n; bit++) {
            if (flags & (1u << bit)) {
                size_t dist = (size_t)in[ip] | ((size_t)in[ip + 1] << 8);
                size_t len = (size_t)in[ip + 2] + MINM;
                ip += 3;
                for (size_t k = 0; k < len; k++, op++) out[op] = out[op - dist];
            } else {
                out[op++] = in[ip++];
            }
        }
    }
    return op;
}

static uint32_t adler32(const uint8_t *p, size_t n) {
    uint32_t a = 1, b = 0;
    for (size_t i = 0; i < n; i++) {
        a = (a + p[i]) % 65521u;
        b = (b + a) % 65521u;
    }
    return (b << 16) | a;
}

int main(int argc, char **argv) {
    if (argc < 2) return 2;
    int rounds = argc > 2 ? atoi(argv[2]) : 2;
    size_t n;
    uint8_t *in = bench_read_file(argv[1], &n);
    if (!in) return 2;
    uint8_t *packed = malloc(n + n / 8 + 64);
    uint8_t *unpacked = malloc(n + 1);
    if (!packed || !unpacked) return 2;

    uint64_t t0 = bench_now_ns();
    uint64_t acc = 0;
    for (int r = 0; r < rounds; r++) {
        size_t m = lz_compress(in, n, packed);
        size_t back = lz_decompress(packed, m, unpacked, n);
        if (back != n || memcmp(in, unpacked, n) != 0) return 3; /* round trip must be exact */
        acc = acc * 1000003u + (uint64_t)m * 65536u + adler32(packed, m);
    }
    uint64_t t1 = bench_now_ns();

    bench_report_u64(acc, t1 - t0);
    free(in); free(packed); free(unpacked);
    return 0;
}
