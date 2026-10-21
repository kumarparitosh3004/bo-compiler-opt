/* stencil: 2-D Jacobi 5-point stencil, repeated sweeps over two buffers.
 * Loop-heavy: unrolling, vectorization, predictive commoning.
 * usage: stencil <n> <sweeps>
 */
#include <stdio.h>
#include <stdlib.h>
#include "../common/bench_timer.h"
#include "../common/bench_rng.h"

static void sweep(int n, const double *in, double *out) {
    for (int i = 1; i < n - 1; i++)
        for (int j = 1; j < n - 1; j++)
            out[i * n + j] = 0.2 * (in[i * n + j] + in[(i - 1) * n + j] + in[(i + 1) * n + j] +
                                    in[i * n + j - 1] + in[i * n + j + 1]);
}

int main(int argc, char **argv) {
    int n = argc > 1 ? atoi(argv[1]) : 1024;
    int sweeps = argc > 2 ? atoi(argv[2]) : 100;
    size_t nn = (size_t)n * (size_t)n;
    double *a = malloc(nn * sizeof *a);
    double *b = malloc(nn * sizeof *b);
    if (!a || !b) return 2;

    bench_rng r;
    bench_rng_seed(&r, 99);
    for (size_t i = 0; i < nn; i++) a[i] = b[i] = bench_rng_f64(&r);

    uint64_t t0 = bench_now_ns();
    for (int s = 0; s < sweeps; s++) {
        sweep(n, a, b);
        double *t = a;
        a = b;
        b = t;
    }
    uint64_t t1 = bench_now_ns();

    double sum = 0.0;
    for (size_t i = 0; i < nn; i++) sum += a[i] * (double)(i % 5 + 1);
    bench_report_f64(sum, t1 - t0);
    free(a); free(b);
    return 0;
}
