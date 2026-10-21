/* Monotonic kernel timer shared by all benchmarks.
 *
 * Only the kernel is timed, so process start-up and input generation do not
 * pollute the measurement. Every benchmark prints exactly two lines:
 *   CHECKSUM=<value>
 *   KERNEL_NS=<integer nanoseconds>
 */
#ifndef BENCH_TIMER_H
#define BENCH_TIMER_H

#include <stdint.h>
#include <stdio.h>

#if defined(_WIN32)
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
static inline uint64_t bench_now_ns(void) {
    static LARGE_INTEGER freq;
    LARGE_INTEGER t;
    if (freq.QuadPart == 0) QueryPerformanceFrequency(&freq);
    QueryPerformanceCounter(&t);
    /* split to avoid overflow of t * 1e9 */
    uint64_t sec = (uint64_t)(t.QuadPart / freq.QuadPart);
    uint64_t rem = (uint64_t)(t.QuadPart % freq.QuadPart);
    return sec * 1000000000ull + rem * 1000000000ull / (uint64_t)freq.QuadPart;
}
#else
#include <time.h>
static inline uint64_t bench_now_ns(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec * 1000000000ull + (uint64_t)ts.tv_nsec;
}
#endif

static inline void bench_report_u64(uint64_t checksum, uint64_t kernel_ns) {
    printf("CHECKSUM=%llu\n", (unsigned long long)checksum);
    printf("KERNEL_NS=%llu\n", (unsigned long long)kernel_ns);
}

static inline void bench_report_f64(double checksum, uint64_t kernel_ns) {
    printf("CHECKSUM=%.17g\n", checksum);
    printf("KERNEL_NS=%llu\n", (unsigned long long)kernel_ns);
}

#endif /* BENCH_TIMER_H */
