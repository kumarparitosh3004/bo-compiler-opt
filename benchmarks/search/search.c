/* search: many lower-bound binary searches into a large sorted array.
 * Exercises unpredictable branches and cache misses.
 * usage: search <table_size> <queries>
 */
#include <stdio.h>
#include <stdlib.h>
#include "../common/bench_timer.h"
#include "../common/bench_rng.h"

static int cmp_u32(const void *x, const void *y) {
    uint32_t a = *(const uint32_t *)x, b = *(const uint32_t *)y;
    return (a > b) - (a < b);
}

/* first index i with table[i] >= key, or n if none */
static int lower_bound(const uint32_t *table, int n, uint32_t key) {
    int lo = 0, hi = n;
    while (lo < hi) {
        int mid = lo + (hi - lo) / 2;
        if (table[mid] < key)
            lo = mid + 1;
        else
            hi = mid;
    }
    return lo;
}

static uint64_t run_queries(const uint32_t *table, int n, const uint32_t *keys, int q) {
    uint64_t acc = 0;
    for (int i = 0; i < q; i++) {
        int pos = lower_bound(table, n, keys[i]);
        uint64_t hit = (pos < n && table[pos] == keys[i]);
        acc += (uint64_t)pos * 31u + hit;
    }
    return acc;
}

int main(int argc, char **argv) {
    int n = argc > 1 ? atoi(argv[1]) : 4000000;
    int q = argc > 2 ? atoi(argv[2]) : 3000000;
    uint32_t *table = malloc((size_t)n * sizeof *table);
    uint32_t *keys = malloc((size_t)q * sizeof *keys);
    if (!table || !keys) return 2;

    bench_rng r;
    bench_rng_seed(&r, 4242);
    for (int i = 0; i < n; i++) table[i] = bench_rng_u32(&r);
    qsort(table, (size_t)n, sizeof *table, cmp_u32); /* setup, not timed */
    for (int i = 0; i < q; i++)                       /* half the keys are present */
        keys[i] = (i & 1) ? table[bench_rng_u32(&r) % (uint32_t)n] : bench_rng_u32(&r);

    uint64_t t0 = bench_now_ns();
    uint64_t acc = run_queries(table, n, keys, q);
    uint64_t t1 = bench_now_ns();

    bench_report_u64(acc, t1 - t0);
    free(table); free(keys);
    return 0;
}
