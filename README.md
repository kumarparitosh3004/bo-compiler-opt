# Automatic Selection of Compiler Optimization Passes Using Bayesian Optimization

A system that uses Bayesian Optimization (BO) to choose which GCC optimization
passes to enable for each program. Each candidate configuration is compiled,
checked for correct output and timed against `-O3`, and the measurements guide
the next choice. The result is compared against `-O0`/`-O1`/`-O2`/`-O3`, and
against random search given the same evaluation budget. It runs on six
synthetic kernels and three real-world programs that process real text.

**Research question:** can BO find flag configurations that run faster than
`-O3`, and does it get there with fewer evaluations than random search?

## Results at a glance

Measured on one laptop (i7-12650H, GCC 16.1). There were 54 searches (9 programs × BO/random × 3 seeds × 50 evaluations = 2,700 evaluations), and every best configuration was re-measured against -O3 in 15 interleaved rounds.

| Program | BO speed-up vs -O3 | Random speed-up | Verdict (BO seeds) | On a 2× larger input |
| --- | --- | --- | --- | --- |
| recursive | **×1.160** (13.8% less time) | ×1.147 | faster in 3/3 | ×1.29 |
| sha256 (real data) | **×1.086** (7.9% less time) | ×1.078 | faster in 3/3 | ×1.09 |
| stencil | ×1.062 | ×1.046 | within noise (9.7% noise floor) | ×1.03 |
| matmul, sort, search, arith, compress, wordfreq | ×0.99–×1.02 | ×0.99–×1.02 | no measurable difference | ×0.99–×1.02 |
| **geometric mean** | **×1.035** | **×1.033** | 6 faster / 20 tie / 1 slower | |

- **BO beats -O3 where -O3's heuristics misjudge the program.** On recursive code, the winning configurations turn off function cloning and sibling-call optimization: they are faster *and* 12–16% smaller. On SHA-256, they turn on full loop unrolling. Elsewhere -O3 is already near-optimal, and the system reports a tie rather than noise.
- **BO is more sample-efficient early.** After 10 evaluations it is ahead of random search on 7 of 9 programs. In this 14-bit space, random search catches up by 50 evaluations.
- **The measurement safeguards matter.** Pairing removed a fake 33% "gain" caused by machine-speed drift, re-measurement exposed a 7.9% search-time outlier as a tie, and 43% of evaluations reused an identical binary.

Full tables: `results/tables/summary.md`. Figures: `results/figures/`. Paper: `docs/manuscript/`.


## Evaluation criteria: where each one is covered

| Criterion | Where | Summary |
| --- | --- | --- |
| **Parameter** | `config/experiment.yaml`, website: *Parameters* | every search, BO, measurement and environment parameter, plus the definition of every reported metric (speed-up, 95% CI, p-value, noise floor, verdict, best@N, ...) |
| **Novelty** | website: *Novelty*, manuscript section 3 | side-effect-aware flag encoding, drift-cancelling paired measurement, binary-hash deduplication, winner's-curse-aware evaluation, screened search space |
| **Front end** | `web/static/` (`core.js`, `pages-run.js`, `pages-project.js`, `style.css`) | single-page app with dashboard, live runs, configuration matrix, BO-vs-Random, forest plots, interactive GP demo, architecture diagram, light/dark theme |
| **Backend** | `web/app.py`, `web/jobs.py`, `web/custom.py` | Flask REST API, persistent single-worker job queue, program upload, CSV downloads, allow-listed compiler flags |
| **Algo** | `bopass/optimizer/`, website: *How BO works* | Gaussian process (Matérn 5/2, ARD) + Expected Improvement over a candidate pool, ask/tell interface, random-search control |
| **Real-life data** | `benchmarks/data/`, `benchmarks/{compress,sha256,wordfreq}`, website: *Real-world data* | LZ77 compression, SHA-256 and word frequency over a 3.5 MB corpus of real human-written text (CPython changelog, documentation and library source) |
| **Manuscript** | `docs/manuscript/` (`.docx` + `manuscript.md`), website: *Manuscript* | research paper with the method, setup, measured results, limitations and references |

## How it works

```
benchmark source --> Bayesian optimizer (GP + Expected Improvement) --ask()--> config vector x
        |                        ^                                                   |
        |                        | tell(x, y)                                         v
        |                 results storage (CSV) <-- objective y = ln(t / t_O3) <-- search space: x -> GCC flags
        |                                                   ^                         |
        +------------------------------------------> compiler driver --> executable (size, SHA-256)
                                                            |                         |
                                          paired timing (A-B / B-A vs -O3) <-- correctness check (checksum)
```

- **Search space:** 1 bit for the base level (`-O2`/`-O3`) plus 13 GCC flags that
  survived verification and a sensitivity screen (`docs/flag_catalog.md`). That
  gives 2^14 = 16,384 configurations. A flag is passed to GCC only when its bit
  differs from the base level's default. Pass *ordering* is not searched,
  because GCC's pass order is fixed.
- **Objective:** minimize `y = ln(median over rounds of t(config) / t(-O3))`.
  Each configuration's runs alternate with runs of an -O3 build (A-B, then B-A),
  so changes in machine speed cancel out. Binary size and compile time are
  recorded but not optimized.
- **BO engine:** a Gaussian process (Matérn 5/2 with per-flag length scales, plus
  a noise term) from scikit-learn. The next configuration maximizes Expected
  Improvement over 2,000 random unseen configurations plus the 1-bit neighbours
  of the 5 best so far. The first 8 evaluations are `-O3` plus 7 random configurations.
- **Robustness:** every compile and run has a timeout (whole process tree
  killed; transient timeouts are retried once); wrong outputs are archived;
  failures get a penalty value; identical executables are measured once
  (SHA-256 cache); interrupted runs resume.

## Programs

| Program | Kind | Kernel |
| --- | --- | --- |
| matmul, sort, search, stencil, recursive, arith | synthetic kernels | matrix multiply, quicksort, binary search, Jacobi stencil, N-Queens + Fibonacci, Mandelbrot |
| compress | real-world data | LZ77/LZSS compression + decompression round-trip of the corpus |
| sha256 | real-world data | FIPS 180-4 SHA-256 over the corpus, with a known-answer self-test |
| wordfreq | real-world data | tokenize, count and rank every word of the corpus |

The corpus (`benchmarks/data/corpus.txt`, 3.5 MB) is real human-written text from
the local CPython installation, about 70% English prose and 30% source code.
Its provenance and SHA-256 are in `benchmarks/data/CORPUS.md`, and
`scripts/make_corpus.py` rebuilds it. Any other C program can be added from the
website.

## Install and run

The easiest way is the setup script for your system; it installs what is
missing, checks every benchmark, and the run script opens the website.
Step-by-step instructions are in **[HOW_TO_RUN.md](HOW_TO_RUN.md)**.

| System | One-time setup | Start the website |
| --- | --- | --- |
| macOS | `bash setup_mac.sh` | `bash run_mac.sh` → http://127.0.0.1:5050 |
| Windows | double-click `setup_windows.bat` | double-click `run_windows.bat` → http://127.0.0.1:5000 |

Requirements: GCC 10+ (the study used GCC 16.1, MinGW-w64 on Windows; on macOS
Homebrew GCC, because `gcc` there is Apple clang) and Python 3.10+.
`python scripts/check_setup.py` checks an existing installation.

Manual setup:

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt      # Windows (Git Bash)
# .venv/bin/python -m pip install -r requirements.txt        # Linux / macOS
```

Set the compiler for your machine in `config/local.yaml` (git-ignored), for
example `compiler: C:/mingw64/bin/gcc.exe` or `compiler: /opt/homebrew/bin/gcc-15`,
or set the `BOPASS_CC` environment variable. On Windows, keep the project in a
short path such as `C:\proj\bo-compiler-opt`, because DLLs and executables
cannot be loaded from paths longer than 260 characters.

## The website

```bash
python web/app.py            # then open http://127.0.0.1:5000 (macOS: 5050)
```

macOS reserves port 5000 for AirPlay Receiver, so the app uses 5050 there.

| Section | Pages |
| --- | --- |
| Overview | **Dashboard**: KPIs, per-program leaderboard, recent searches |
| Experiments | **Optimize**: run BO / random / both on one or all programs; the live run view shows the convergence chart, EI over time, a configuration matrix, every evaluation, the GP's flag relevance and the log · **BO vs Random**: all seeds, median curves and min–max bands · **Verify & baselines**: interleaved comparison with a forest plot, CI, p-value and verdict · **History** |
| Algorithm & system | **How BO works**: interactive 1-D Gaussian-process demo + pseudocode · **Search space**: interactive configuration builder, flag impact grid, dependency rules · **Architecture**: clickable component diagram, REST API, tech stack |
| Project | **Parameters** · **Novelty** · **Real-world data** · **Study results** (tables T1–T5, figures F1–F4) · **Manuscript** (preview + .docx download) |
| Data | **Programs**: view source, add your own C program |

Jobs run one at a time, because parallel runs would disturb each other's
timings, and they survive a server restart. The frontend is plain
HTML/CSS/JS/SVG: no build step and no internet needed. Fonts load from Google
Fonts when online and fall back to system fonts otherwise.

## Quick start (command line)

```bash
python -m pytest                                    # full test suite (needs gcc)
python scripts/make_references.py                   # reference outputs
python scripts/verify_flags.py                      # verify flags -> config/flags_gcc.yaml
python scripts/run_baselines.py --bench matmul      # -O0..-O3 for one program
python scripts/run_search.py --bench matmul --method bo --seed 0 --budget 15 --tag demo
python scripts/make_plots.py --experiment matmul_bo_s0_demo
```

The full experiment pipeline is in [EXPERIMENTS.md](EXPERIMENTS.md).

## Repository layout

| Path | Purpose |
| --- | --- |
| `benchmarks/` | 9 single-file C programs, shared timer/PRNG/IO headers, manifest, reference outputs, `data/` corpus |
| `config/` | `flag_candidates.yaml` (hand-written), `flags_gcc.yaml` (generated by `verify_flags.py`), `experiment.yaml` (frozen settings) |
| `bopass/` | engine: `space`, `compiler_driver`, `runner`, `proc`, `correctness`, `optimizer/`, `objective`, `evaluator`, `orchestrator`, `storage`, `stats`, `compare`, `env_info` |
| `web/` | Flask backend (`app.py`, `jobs.py`, `custom.py`) and frontend (`static/`) |
| `scripts/` | Phase 2–4 entry points, corpus builder, manuscript builder |
| `tests/` | unit, integration and web end-to-end tests, toy and failure-case programs |
| `results/` | baselines, search runs, final measurements, tables, figures, archived aborted runs |
| `docs/` | Phase 1 inventory, flag catalog, report, manuscript |

## Team

Team 12, Compiler Lab, School of Computer Science and Engineering (SCOPE),
Vellore Institute of Technology, Vellore.

| Member | Name | Reg. no. | Owns |
| --- | --- | --- | --- |
| Member 1 - compiler and correctness | Aditya Agarwal | 24BCE0587 | `compiler_driver.py`, `correctness.py`, `proc.py`, `verify_flags.py`, `make_references.py`, `web/custom.py`, flag catalog |
| Member 2 - benchmarks and measurement | Priyanshu Krishna Srivastava | 24BCE2464 | `benchmarks/` (incl. real-data programs and corpus), `space.py`, `runner.py`, `run_baselines.py`, `noise_floor.py`, `final_measure.py` |
| Member 3 - Bayesian Optimization | Kumar Paritosh | 24BCE2863 | `optimizer/`, `objective.py`, `stats.py`, `compare.py`, `analyze.py`, the *How BO works* page |
| Member 4 - integration and experiments | Maddulapalli Venkata Satya Abhinav Sarma | 24BAI0125 | `evaluator.py`, `storage.py`, `orchestrator.py`, `env_info.py`, `run_search.py`, `run_all.py`, `make_plots.py`, `web/app.py`, `web/jobs.py`, frontend |
