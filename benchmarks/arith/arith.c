/* arith: Mandelbrot escape-time iteration counts over a fixed grid.
 * Arithmetic-heavy floating point with a data-dependent inner loop.
 * The checksum is an integer (sum of iteration counts), so it is exact.
 * usage: arith <width> <height> <max_iter>
 */
#include <stdio.h>
#include <stdlib.h>
#include "../common/bench_timer.h"

static int escape_time(double cr, double ci, int max_iter) {
    double zr = 0.0, zi = 0.0;
    int it = 0;
    while (it < max_iter && zr * zr + zi * zi <= 4.0) {
        double t = zr * zr - zi * zi + cr;
        zi = 2.0 * zr * zi + ci;
        zr = t;
        it++;
    }
    return it;
}

int main(int argc, char **argv) {
    int w = argc > 1 ? atoi(argv[1]) : 800;
    int h = argc > 2 ? atoi(argv[2]) : 600;
    int max_iter = argc > 3 ? atoi(argv[3]) : 512;

    uint64_t t0 = bench_now_ns();
    uint64_t sum = 0;
    for (int y = 0; y < h; y++) {
        double ci = -1.2 + 2.4 * (double)y / (double)h;
        for (int x = 0; x < w; x++) {
            double cr = -2.1 + 3.0 * (double)x / (double)w;
            sum += (uint64_t)escape_time(cr, ci, max_iter) * (uint64_t)(x % 3 + 1);
        }
    }
    uint64_t t1 = bench_now_ns();

    bench_report_u64(sum, t1 - t0);
    return 0;
}
