/* Read a whole input file into memory (outside the timed kernel). */
#ifndef BENCH_IO_H
#define BENCH_IO_H

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

/* Returns a malloc'd buffer (caller frees) and stores the size in *n; NULL on error. */
static uint8_t *bench_read_file(const char *path, size_t *n) {
    FILE *f = fopen(path, "rb");
    if (!f) return NULL;
    if (fseek(f, 0, SEEK_END) != 0) { fclose(f); return NULL; }
    long size = ftell(f);
    if (size < 0) { fclose(f); return NULL; }
    rewind(f);
    uint8_t *buf = malloc((size_t)size + 1);
    if (!buf) { fclose(f); return NULL; }
    size_t got = fread(buf, 1, (size_t)size, f);
    fclose(f);
    if (got != (size_t)size) { free(buf); return NULL; }
    buf[size] = 0;
    *n = (size_t)size;
    return buf;
}

#endif /* BENCH_IO_H */
