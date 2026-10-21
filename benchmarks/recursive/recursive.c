/* recursive: N-Queens solution count (backtracking) plus naive Fibonacci.
 * Exercises calls, inlining, cloning and sibling-call optimization.
 * usage: recursive <queens_n> <fib_n>
 */
#include <stdio.h>
#include <stdlib.h>
#include "../common/bench_timer.h"

#define MAXN 16

static int safe(const int *col_of_row, int row, int col) {
    for (int r = 0; r < row; r++) {
        int c = col_of_row[r];
        if (c == col || c - col == r - row || c - col == row - r) return 0;
    }
    return 1;
}

static uint64_t queens(int *col_of_row, int row, int n) {
    if (row == n) return 1;
    uint64_t count = 0;
    for (int col = 0; col < n; col++) {
        if (safe(col_of_row, row, col)) {
            col_of_row[row] = col;
            count += queens(col_of_row, row + 1, n);
        }
    }
    return count;
}

static uint64_t fib(int n) {
    return n < 2 ? (uint64_t)n : fib(n - 1) + fib(n - 2);
}

int main(int argc, char **argv) {
    int n = argc > 1 ? atoi(argv[1]) : 11;
    int f = argc > 2 ? atoi(argv[2]) : 30;
    if (n < 1 || n > MAXN) return 2;
    int col_of_row[MAXN];

    uint64_t t0 = bench_now_ns();
    uint64_t q = queens(col_of_row, 0, n);
    uint64_t fb = fib(f);
    uint64_t t1 = bench_now_ns();

    bench_report_u64(q * 1000003ull + fb, t1 - t0);
    return 0;
}
