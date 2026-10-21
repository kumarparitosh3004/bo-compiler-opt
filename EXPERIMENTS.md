# Reproducing the experiments

Every table and figure is regenerated from raw data by a script. Never type a
number into the report by hand. Run everything on **one** machine, on AC power,
with other applications closed.

Set the compiler once per shell if `gcc` on your `PATH` is not the one you want:

```bash
export BOPASS_CC=C:/mingw64/bin/gcc.exe        # Git Bash / Linux syntax
```

```powershell
$env:BOPASS_CC = "C:/mingw64/bin/gcc.exe"      # PowerShell
```

## Phase 2 - optimization space and baselines

| Step | Command | Output |
| --- | --- | --- |
| Real-world corpus (already committed; only to rebuild) | `python scripts/make_corpus.py` | `benchmarks/data/corpus.txt`, `CORPUS.md` |
| Reference checksums (-O0), cross-checked at -O1/-O2/-O3 | `python scripts/make_references.py` | `benchmarks/*/expected.txt` |
| Flag verification, encoding check, sensitivity screen | `python scripts/verify_flags.py` | `config/flags_gcc.yaml`, `docs/flag_catalog.md`, `results/verification/verify_report.json` |
| Baselines -O0..-O3 (T1) | `python scripts/run_baselines.py` | `results/baselines/baselines.csv` |
| Noise floor (30 runs of -O3) | `python scripts/noise_floor.py` | `results/baselines/noise_floor.csv` |

## Phase 3 - one search

```bash
python scripts/run_search.py --bench matmul --method bo --seed 0
```

Writes `results/search/matmul_bo_s0/{evals.csv,manifest.json,summary.json,log.txt}`.
Re-running the same command resumes an interrupted run.

## Phase 4 - full evaluation

| Step | Command | Output |
| --- | --- | --- |
| A. Search sweep: 9 programs (6 synthetic + 3 real-data) x {bo, random} x seeds {0,1,2} x 50 evaluations | `python scripts/run_all.py` | `results/search/*` |
| B+C. Interleaved re-measurement + correctness re-check | `python scripts/final_measure.py` | `results/final/{candidates,final_runs}.csv` |
| D. Generalization to a ~2x larger input | `python scripts/final_measure.py --alt` | `results/final/*_alt.csv` |
| Statistics and tables T1-T5 | `python scripts/analyze.py` | `results/tables/*.csv`, `results/tables/summary.md`, `stats.json` |
| Figures F1-F4 | `python scripts/make_plots.py` | `results/figures/*.png` |
| Manuscript | edit `docs/manuscript/manuscript.md`, then `python scripts/make_manuscript.py` | `docs/manuscript/*.docx` |

Settings are frozen in `config/experiment.yaml` (budget, seeds, repetitions, BO
hyperparameters, timeouts). Change them only before Step A, and record the change.

## Re-running on a second machine

The committed `results/` were measured on one Windows laptop (GCC 16.1,
x86-64). A sweep on another machine must be kept separate, because resuming
replays the recorded evaluations into the optimizer and the two sets of timings
would end up in one objective. `run_search.py` refuses to resume a run whose
manifest records a different compiler version or CPU architecture, and names
the drift when it does.

Use `--tag` on both steps to write beside the study instead:

```bash
python scripts/run_all.py --tag mac                      # results/search/*_mac
python scripts/final_measure.py --tag mac                # results/final/*_mac.csv
```

Use the same tag for both: `final_measure.py --tag mac` reads the `_mac`
searches and writes `candidates_mac.csv` / `final_runs_mac.csv`, so the
committed study files are never overwritten.

## Portability changes made after the study

- `-ffp-contract=off` is now in `fixed_flags` for every platform. GCC's default
  may fuse `a*b+c` into one FMA, which rounds once instead of twice. On AArch64
  (Apple Silicon, ARM64 Linux) FMA is in the baseline ISA, so `-O3` contracted
  while `-O0` did not, `benchmarks/arith` returned a different Mandelbrot
  checksum at the two levels, and the correctness check failed. Baseline x86-64
  has no FMA and never contracted, so the flag is a no-op on the machine that
  produced `results/` and those numbers stand.
- Code size is read per object format. GNU `size` prints Berkeley format, whose
  first column is `.text`; Apple's `size` prints page-aligned Mach-O *segments*,
  which read 16384 for every small binary here, so `size -m` is used on that
  format to get the real `__text` section. `check_setup.py` warns if the `size`
  on this machine reports the same code size at `-O0` and `-O3`.

## What each table/figure is built from

| Item | Source data |
| --- | --- |
| T1 | `results/baselines/baselines.csv`, `noise_floor.csv` |
| T2, T2b, F1 | `results/final/final_runs.csv`, `candidates.csv` (Step B only, never search-time numbers) |
| T3, T3b, F2 | `results/search/*/summary.json`, `evals.csv` |
| T4 | `results/final/candidates.csv` |
| T5 | `results/final/final_runs_alt.csv` |
| F3 | `length_scales` in `results/search/*_bo_*/summary.json` |
| F4 | `results/search/*/evals.csv` |

## Methodology notes

- **Paired objective.** Every measured configuration alternates with an -O3
  build (A-B, then B-A), and `y = ln(median per-round time ratio)`. On the
  measurement laptop, -O3 itself measured 228 ms and then 308 ms a few minutes
  later (power-source switch), which is far larger than the effects being
  measured. The aborted single-reference runs that showed this are kept in
  `results/archive/`. Setting `paired_reference: false` falls back to normalizing
  by the run's own first (-O3) evaluation.
- **Winner's curse.** A search's best configuration is optimistically biased. All
  comparisons use the Step B re-measurement, in which every candidate is run in
  each of 15 shuffled rounds, after one discarded warm-up round.
- **Verdicts.** "Faster" or "slower" requires all three: Mann-Whitney p < 0.05, a
  bootstrap 95% CI of the ratio of medians that excludes 1, and a difference
  larger than 2x the benchmark's noise floor. Anything else is reported as "no
  measurable difference".

- **Transient failures.** A run that times out is retried once before being
  recorded, and a failure of the -O3 reference itself is recorded as that
  evaluation's failure instead of stopping the sweep. The first sweep was
  stopped by exactly that when the laptop went to sleep. Its log is in
  `results/archive/`, and the affected run was deleted and re-run from scratch.
