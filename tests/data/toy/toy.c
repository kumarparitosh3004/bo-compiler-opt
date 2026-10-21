/* toy benchmark for tests: ~10-30 ms, vectorizable loop, integer checksum */
#include <stdio.h>
#include <stdlib.h>
#include "../../../benchmarks/common/bench_timer.h"

static unsigned long long kernel(const unsigned *a, int n, int rounds) {
    unsigned long long s = 0;
    for (int r = 0; r < rounds; r++)
        for (int i = 0; i < n; i++) s += (unsigned long long)(a[i] * 3u + (unsigned)r) ^ (a[i] >> 3);
    return s;
}

int main(int argc, char **argv) {
    int n = argc > 1 ? atoi(argv[1]) : 100000;
    int rounds = argc > 2 ? atoi(argv[2]) : 50;
    unsigned *a = malloc((size_t)n * sizeof *a);
    if (!a) return 2;
    for (int i = 0; i < n; i++) a[i] = (unsigned)i * 2654435761u;
    uint64_t t0 = bench_now_ns();
    unsigned long long s = kernel(a, n, rounds);
    uint64_t t1 = bench_now_ns();
    bench_report_u64(s, t1 - t0);
    free(a);
    return 0;
}
