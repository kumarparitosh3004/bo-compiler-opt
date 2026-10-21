/* matmul: dense double-precision C += A * B, naive i-j-k loop nest.
 * Exercises loop interchange, vectorization and unrolling.
 * usage: matmul <n>
 */
#include <stdio.h>
#include <stdlib.h>
#include "../common/bench_timer.h"
#include "../common/bench_rng.h"

static void matmul(int n, const double *a, const double *b, double *c) {
    for (int i = 0; i < n; i++)
        for (int j = 0; j < n; j++)
            for (int k = 0; k < n; k++)
                c[i * n + j] += a[i * n + k] * b[k * n + j];
}

int main(int argc, char **argv) {
    int n = argc > 1 ? atoi(argv[1]) : 400;
    size_t nn = (size_t)n * (size_t)n;
    double *a = malloc(nn * sizeof *a);
    double *b = malloc(nn * sizeof *b);
    double *c = calloc(nn, sizeof *c);
    if (!a || !b || !c) return 2;

    bench_rng r;
    bench_rng_seed(&r, 12345);
    for (size_t i = 0; i < nn; i++) a[i] = bench_rng_f64(&r) - 0.5;
    for (size_t i = 0; i < nn; i++) b[i] = bench_rng_f64(&r) - 0.5;

    uint64_t t0 = bench_now_ns();
    matmul(n, a, b, c);
    uint64_t t1 = bench_now_ns();

    double sum = 0.0;
    for (size_t i = 0; i < nn; i++) sum += c[i] * (double)(i % 7 + 1);
    bench_report_f64(sum, t1 - t0);
    free(a); free(b); free(c);
    return 0;
}
