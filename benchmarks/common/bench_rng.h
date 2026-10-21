/* Fixed-seed xorshift64* PRNG.
 *
 * rand() is not used because its sequence differs between C libraries; this
 * generator gives identical inputs on every platform and optimization level.
 */
#ifndef BENCH_RNG_H
#define BENCH_RNG_H

#include <stdint.h>

typedef struct { uint64_t s; } bench_rng;

static inline void bench_rng_seed(bench_rng *r, uint64_t seed) {
    r->s = seed ? seed : 0x9E3779B97F4A7C15ull;
}

static inline uint64_t bench_rng_u64(bench_rng *r) {
    uint64_t x = r->s;
    x ^= x >> 12;
    x ^= x << 25;
    x ^= x >> 27;
    r->s = x;
    return x * 0x2545F4914F6CDD1Dull;
}

/* uniform double in [0, 1) built from the top 53 bits */
static inline double bench_rng_f64(bench_rng *r) {
    return (double)(bench_rng_u64(r) >> 11) * (1.0 / 9007199254740992.0);
}

static inline uint32_t bench_rng_u32(bench_rng *r) {
    return (uint32_t)(bench_rng_u64(r) >> 32);
}

#endif /* BENCH_RNG_H */
