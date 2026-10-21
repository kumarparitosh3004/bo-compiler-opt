# Phase 1 inventory (verification before Phase 2)

Recorded 2026-10-13 on the machine used for all measurements in this repository.

## Compiler and platform

| Item | Value |
| --- | --- |
| Compiler used | `C:/mingw64/bin/gcc.exe` - GCC 16.1.0 (MinGW-W64 x86_64-ucrt-posix-seh, WinLibs build by Brecht Sanders, r4) |
| Target | `x86_64-w64-mingw32`, default `-march` (no `-march=native`) |
| Other compilers present | `C:/MinGW/bin/gcc.exe` GCC 6.3.0 (32-bit, **not used**; it comes first on the system `PATH`, so set `BOPASS_CC`) |
| Binutils | `size.exe`, `objdump.exe` in the same directory as the compiler |
| OS / CPU | Windows 11 Home 10.0.26200, 12th Gen Intel Core i7-12650H (6 P-cores + 4 E-cores, 16 logical CPUs) |
| Python | 3.12.5, packages pinned in `requirements.txt` |
| Measurement machine | This laptop, on AC power for the study. It slept several times during the 36-hour sweep (see the threats-to-validity section). |

## Pass-control check (decides the Phase 2 path)

`gcc -Q --help=optimizers -O2` / `-O3` print the effective state of every `-f`
optimization flag, so the **GCC flag-toggling path** is used. Every candidate
flag's toggle was verified by `scripts/verify_flags.py` (see `docs/flag_catalog.md`).

## Findings that changed the plan

1. **GCC 16 enables `-funroll-loops` at -O2.** The plan's flag table (taken from
   the GCC 12 manual) listed it as off at every level. Defaults are therefore
   generated from `gcc -Q`, never typed by hand.
2. **Spelling a flag out can change other flags.** An explicit `-funroll-loops`,
   even at its default value, also enables `-frename-registers` and `-fweb` and
   changes `-funroll-completely-grow-size`. The encoding therefore passes a flag
   only when it differs from the base level's default. With that rule, the
   -O2/-O3 vectors build byte-identical binaries to plain -O2/-O3 on all six
   benchmarks.
3. **The Windows PE timestamp makes identical builds hash differently.**
   `-Wl,--no-insert-timestamp` is added to every build so that the binary-hash
   cache works.
4. **Windows path limits.** An executable whose path exceeds 260 characters
   cannot be started, and `scikit-learn` cannot load its OpenMP DLL from such a
   path either. When the project lives in a deep folder, the build directory
   falls back to `%TEMP%\bopass_build\...` (override with `BOPASS_BUILD_DIR`),
   and the virtual environment should be created in a short path.
5. **`gcc` timeouts on Windows leave `cc1.exe` running.** `cc1.exe` keeps the
   output pipes open, so `subprocess.run` hangs. All subprocesses run through
   `bopass/proc.py`, which kills the whole process tree on timeout.

## Existing Phase 1 files

The team's Phase 1 files were not available on this machine, so this
repository was created as a complete, self-contained implementation. To merge
the Phase 1 work, copy those files into the matching folders (sample programs
into `benchmarks/`, notes into `docs/`) and keep their git history. Nothing in
this repository depends on file names from Phase 1.
