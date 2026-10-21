/* sort: recursive quicksort (median-of-three, insertion sort for small
 * partitions) over several random int32 arrays.
 * Exercises branches, recursion, inlining and memory traffic.
 * usage: sort <n> <rounds>
 */
#include <stdio.h>
#include <stdlib.h>
#include "../common/bench_timer.h"
#include "../common/bench_rng.h"

static void insertion_sort(int32_t *a, int lo, int hi) {
    for (int i = lo + 1; i <= hi; i++) {
        int32_t v = a[i];
        int j = i - 1;
        while (j >= lo && a[j] > v) {
            a[j + 1] = a[j];
            j--;
        }
        a[j + 1] = v;
    }
}

static inline void swap(int32_t *a, int i, int j) {
    int32_t t = a[i];
    a[i] = a[j];
    a[j] = t;
}

static int32_t median3(int32_t *a, int lo, int hi) {
    int mid = lo + (hi - lo) / 2;
    if (a[mid] < a[lo]) swap(a, mid, lo);
    if (a[hi] < a[lo]) swap(a, hi, lo);
    if (a[hi] < a[mid]) swap(a, hi, mid);
    return a[mid];
}

static void quicksort(int32_t *a, int lo, int hi) {
    while (hi - lo > 16) {
        int32_t p = median3(a, lo, hi);
        int i = lo, j = hi;
        while (i <= j) {
            while (a[i] < p) i++;
            while (a[j] > p) j--;
            if (i <= j) {
                swap(a, i, j);
                i++;
                j--;
            }
        }
        /* recurse into the smaller side, loop on the larger one */
        if (j - lo < hi - i) {
            quicksort(a, lo, j);
            lo = i;
        } else {
            quicksort(a, i, hi);
            hi = j;
        }
    }
    insertion_sort(a, lo, hi);
}

int main(int argc, char **argv) {
    int n = argc > 1 ? atoi(argv[1]) : 1000000;
    int rounds = argc > 2 ? atoi(argv[2]) : 4;
    int32_t *a = malloc((size_t)n * rounds * sizeof *a);
    if (!a) return 2;

    bench_rng r;
    bench_rng_seed(&r, 777);
    for (size_t i = 0; i < (size_t)n * rounds; i++) a[i] = (int32_t)bench_rng_u32(&r);

    uint64_t t0 = bench_now_ns();
    for (int k = 0; k < rounds; k++) quicksort(a + (size_t)k * n, 0, n - 1);
    uint64_t t1 = bench_now_ns();

    uint64_t sum = 0;
    for (int k = 0; k < rounds; k++) {
        const int32_t *b = a + (size_t)k * n;
        for (int i = 0; i < n; i++) {
            if (i > 0 && b[i - 1] > b[i]) return 3; /* not sorted: fail loudly */
            sum += (uint64_t)(uint32_t)b[i] * (uint64_t)(i + 1);
        }
    }
    bench_report_u64(sum, t1 - t0);
    free(a);
    return 0;
}
