# Sample-Efficient Selection of GCC Optimization Passes with Bayesian Optimization under Noisy Measurement

Authors: Aditya Agarwal, Priyanshu Krishna Srivastava, Kumar Paritosh, Maddulapalli Venkata Satya Abhinav Sarma
Affiliation: Compiler Lab, School of Computer Science and Engineering (SCOPE), Vellore Institute of Technology, Vellore, India

## Abstract

Compilers ship a few fixed optimization recipes, but the best set of passes depends on the program. We present a system that selects GCC 16 optimization flags per program with Bayesian Optimization (BO): a Gaussian-process surrogate with Expected Improvement proposes a configuration, which is compiled, checked for correct output and timed against `-O3` in alternating A-B/B-A rounds that cancel machine-speed drift. A verified, side-effect-aware encoding guarantees that the `-O3` vector reproduces `-O3` byte for byte, and binary-hash deduplication avoided re-timing 43% of evaluations. Over 9 programs (6 kernels and 3 real-world workloads on a 3.5 MB corpus of real text), 2 methods, 3 seeds and 50 evaluations each (2,700 evaluations), every best configuration was re-measured in 15 interleaved rounds. BO found statistically significant speed-ups over `-O3` on `recursive` (×1.157–×1.166, all seeds) and on the real-data `sha256` (×1.080–×1.092), and the gains held on 2× larger inputs (×1.29 and ×1.09). The other programs showed no measurable difference: `-O3` is already near-optimal for them. The geometric-mean speed-up was ×1.035 for BO and ×1.033 for random search. BO reached good configurations sooner, leading random search after 10 evaluations on 7 of 9 programs, but at 50 evaluations in this 14-bit space random search caught up.

## Index Terms

Compiler autotuning, Bayesian optimization, Gaussian processes, GCC, optimization flags, performance measurement.

## 1. Introduction

Production compilers offer dozens of optimization passes but ship only a few fixed recipes. The common choice, `-O3`, is tuned for "typical" code, yet a particular program may run faster with a different subset of passes. Finding that subset by trial is expensive: every candidate must be compiled, executed and timed, and the number of subsets grows as 2ⁿ. Exhaustively testing the 16,384 configurations of our search space would take about a day per program.

Bayesian Optimization (BO) is designed for such expensive black-box problems. It fits a probabilistic surrogate model to the evaluations made so far and spends the next evaluation where the model expects the largest improvement [1], [2]. Applying BO to compiler flags looks straightforward, but in practice two engineering problems decide whether the results can be trusted. First, the mapping from a bit vector to a compiler command line is not as simple as it appears: spelling out a flag can silently change other flags. Second, wall-clock measurements on a real machine drift by far more than the effects being sought [6].

This paper presents a complete, open, interactive system for per-program selection of GCC optimization passes with BO, and evaluates it on six synthetic kernels and three real-world programs that process real text. Our contributions are:

- **A side-effect-aware, verified encoding** of GCC flags. Flags are emitted only when they differ from the base level's defaults, which are read from the compiler itself. The `-O2`/`-O3` vectors are proven to build byte-identical executables to plain `-O2`/`-O3`.
- **A drift-cancelling paired objective**: each configuration alternates with `-O3` in A-B/B-A rounds, and the objective is the log of the median per-round time ratio.
- **Evaluation hygiene for autotuning**: binary-hash deduplication, output checks against a reference, retried transient timeouts, and a final re-measurement with bootstrap confidence intervals, a Mann–Whitney test and a noise-floor rule, which guards against the winner's curse.
- **An empirical study** of BO against `-O0`…`-O3` and against random search at equal budget: 9 programs × 2 methods × 3 seeds × 50 evaluations.
- **An interactive web system** to run, inspect and verify searches, including a configuration-matrix view of how the search converges.

## 2. Background and Related Work

**Optimization levels and flags.** GCC groups its passes into levels (`-O1`, `-O2`, `-O3`), each enabling a set of passes controlled individually by `-f<pass>` / `-fno-<pass>`. `gcc -Q --help=optimizers` reports the effective state of every flag for a given command line. GCC's internal pass order is fixed, so this work searches pass *selection*, not ordering.

**Iterative compilation and autotuning.** Searching flag settings per program dates back at least to genetic-algorithm approaches for code size [3]. Milepost GCC learns a mapping from static program features to good flags [4]. OpenTuner provides an ensemble of search techniques for general autotuning [5]. BOCA applies BO with a tree-based surrogate to compiler autotuning [8]. CompilerGym exposes compiler optimization as reinforcement-learning environments [9].

**Measurement bias.** Mytkowicz et al. showed that innocuous changes in the experimental setup can bias performance measurements by more than the effects under study [6]. Our paired objective and interleaved final measurement are direct responses to this problem.

**Gaussian-process BO.** A GP places a prior over functions. Conditioned on observations, it gives a predictive mean μ(x) and standard deviation σ(x) [7]. Expected Improvement (EI) [2] scores a candidate by the expected amount by which it beats the incumbent best y*, which balances exploitation (low μ) against exploration (high σ).

## 3. Method

### A. Search space and verified encoding

A configuration is a binary vector x ∈ {0,1}ᵈ. Bit 0 selects the base level (`-O2` or `-O3`), and bit i selects whether flag i is on. Starting from 21 candidate flags, we (i) confirmed with `gcc -Q` that each flag toggles at both levels, (ii) read each flag's real default at `-O2` and `-O3`, and (iii) screened each flag by flipping it alone and checking whether any benchmark executable changed (SHA-256). Thirteen flags changed at least one binary, giving d = 14 and 16,384 configurations. One dependency rule applies (`-ftree-partial-pre` needs `-ftree-pre`). Vectors that violate it are canonicalized to a single point.

Verification exposed two facts that break a naive encoding. GCC 16 enables `-funroll-loops` at `-O2`, unlike older manuals. And spelling out `-funroll-loops`, even at its default value, also enables `-fweb` and `-frename-registers`, so emitting every flag explicitly does not reproduce `-O3`. We therefore emit a flag only when its bit differs from the base level's default. With this rule, the `-O2` and `-O3` vectors build byte-identical executables to plain `-O2`/`-O3` on every program.

### B. Paired, drift-cancelling objective

On the measurement laptop, the same `-O3` executable took 228 ms in one run and 308 ms a few minutes later, after a change of power source. That is far larger than the 1–15% effects of interest. Each configuration is therefore measured in r = 5 rounds (after one warm-up round). In each round it runs together with an `-O3` reference build, in alternating order (A-B, then B-A). The objective, to be minimized, is

$$ y(x) = ln( median_r [ t_r(x) / t_r(-O3) ] ) $$

so y = −0.05 corresponds to about 4.9% faster than `-O3`. Because both executables experience the same machine state within a round, slow drift cancels in the ratio. Binary size and compile time are recorded for every evaluation but are not part of y.

### C. Bayesian Optimization

The surrogate is a GP with a constant × Matérn (ν = 5/2) kernel with one length scale per bit (automatic relevance determination), plus a white-noise kernel, fitted with scikit-learn and refitted after every observation. Each step maximizes EI (ξ = 0.01) over a pool of 2,000 random valid unseen configurations plus all 1-bit neighbours of the five best configurations so far. Each search starts with the `-O3` vector and seven random valid configurations, a design shared with the random-search control. Failed evaluations (compile error, crash, timeout, wrong output) enter the model with y = (worst successful y) + 1, so the GP learns to avoid them.

### D. Robust evaluation

Every executable is fingerprinted with SHA-256, and identical executables are measured only once. Every output is compared with a reference checksum from the `-O0` build. Every compile and run has a timeout that kills the whole process tree, and a timed-out run is retried once. Each run appends one CSV row per evaluation and writes a manifest with the compiler version, package versions, machine and seeds, so interrupted runs resume and every number can be traced to its source.

## 4. System Implementation

The system is a Python package (`bopass`) plus a web application. The optimizer exposes an ask/tell interface, so it was developed against a synthetic objective before the compiler was attached. A unit test shows that it beats random search on that objective over ten seeds. A Flask backend runs searches and comparisons in a single-worker job queue, so jobs never disturb each other's timings. A dependency-free single-page frontend shows live convergence, a configuration matrix (evaluations × flag bits), the GP's per-flag relevance, BO-versus-random comparisons and interleaved verification with forest plots. Users can also upload their own C programs. The test suite covers the encoding, the EI computation, every evaluator status path, storage and resume, real failure programs (crash, infinite loop, syntax error, wrong output) and end-to-end web flows.

## 5. Experimental Setup

**Platform.** All measurements ran on one laptop with an Intel Core i7-12650H (6 performance + 4 efficiency cores, 16 threads), Windows 11, GCC 16.1.0 (MinGW-w64, UCRT) and Python 3.12 with scikit-learn 1.9. The default `-march` was used, and `-ffast-math`, `-Ofast` and `-march=native` were excluded because they change semantics or the target.

**Programs.** Table 1 lists the nine programs. The six kernels use fixed-seed generated inputs. The three real-world programs process a 3.5 MB corpus of real human-written text (442,020 words): the CPython changelog, its documentation and library source code, taken from the local Python installation and committed with its SHA-256. Every program prints a checksum, and every optimized build must reproduce the `-O0` checksum.

Table: TABLE 1. Programs and baseline run time (median kernel time, ms)
| Program | Kind | Kernel | -O0 | -O2 | -O3 |
| --- | --- | --- | --- | --- | --- |
| matmul | synthetic | 700×700 double matrix multiply | 1179 | 235 | 234 |
| sort | synthetic | quicksort, 3 × 10⁶ int32 | 414 | 245 | 248 |
| search | synthetic | 1.5 × 10⁶ binary searches | 445 | 328 | 332 |
| stencil | synthetic | 2-D Jacobi, 1024², 400 sweeps | 1832 | 335 | 225 |
| recursive | synthetic | N-Queens(12) + Fibonacci(35) | 286 | 135 | 117 |
| arith | synthetic | Mandelbrot 800×600, 1024 iterations | 705 | 325 | 325 |
| compress | real data | LZ77/LZSS compress + decompress | 536 | 328 | 331 |
| sha256 | real data | SHA-256 (FIPS 180-4), 15 rounds | 835 | 214 | 211 |
| wordfreq | real data | tokenize, count, rank all words | 517 | 247 | 247 |

**Protocol.** Each program was searched by BO and by random search with seeds 0, 1 and 2, giving 54 searches of 50 evaluations each (2,700 evaluations, 5.05 hours of active search time). Then each search's best configuration was rebuilt together with `-O0`…`-O3` and measured in one warm-up round and 15 interleaved rounds, each with a newly shuffled order (Step B). Every output was re-checked (Step C), and the same binaries were re-measured on an input about 2× larger (Step D). The noise floor of each program is the coefficient of variation of 30 runs of its `-O3` build.

**Statistics.** Speed-up is median t(`-O3`) / median t(config). Its 95% confidence interval is a percentile bootstrap (10,000 resamples) of the ratio of medians, and significance is a two-sided Mann–Whitney U test. We call a configuration *faster* or *slower* only if p < 0.05, the confidence interval excludes 1, **and** the difference exceeds twice the program's noise floor. Averages across programs are geometric means of speed-ups.

## 6. Results

### A. RQ1: Does BO beat -O3?

Table 2 and Fig. 1 summarize the final, interleaved re-measurement. BO's best configurations were significantly faster than `-O3` on two programs in every seed. On `recursive` the speed-up was ×1.157–×1.166 (95% CI of the best seed [1.141, 1.174], p = 3.4×10⁻⁶), i.e. 13.6–14.2% less run time. On the real-data `sha256` it was ×1.080–×1.092 (p = 3.4×10⁻⁶ in every seed). `stencil` improved by ×1.019–×1.077, but this memory-bound kernel has a 9.7% noise floor, so no seed met the verdict rule. On `matmul`, `search`, `arith`, `compress` and `wordfreq` the results stayed within ±1.5% of `-O3`. One `matmul` configuration (BO, seed 1) that looked 0.6% faster during search was in fact 2.5% *slower* when re-measured, a direct instance of the winner's curse. Across all nine programs, the geometric-mean speed-up was ×1.035 for BO and ×1.033 for random search. Over the 27 runs per method, the verdicts were 6 faster, 20 no measurable difference and 1 slower, identical for both methods.

Table: TABLE 2. Final speed-up vs -O3 (median of 3 seeds, range in brackets; 15 interleaved rounds)
| Program | BO | Random | BO seeds faster / tie / slower | On 2× input (BO) |
| --- | --- | --- | --- | --- |
| matmul | ×0.988 [0.975–0.992] | ×0.996 [0.974–0.999] | 0 / 2 / 1 | ×1.008 |
| sort | ×1.018 [1.006–1.020] | ×1.018 [1.005–1.019] | 0 / 3 / 0 | ×1.015 |
| search | ×0.999 [0.990–1.009] | ×1.005 [1.005–1.007] | 0 / 3 / 0 | ×0.997 |
| stencil | ×1.062 [1.019–1.077] | ×1.046 [1.015–1.074] | 0 / 3 / 0 | ×1.029 |
| recursive | **×1.160** [1.157–1.166] | ×1.147 [1.116–1.155] | 3 / 0 / 0 | **×1.291** |
| arith | ×0.995 [0.995–1.009] | ×0.997 [0.987–1.003] | 0 / 3 / 0 | ×0.987 |
| compress | ×1.001 [0.998–1.011] | ×0.995 [0.987–1.006] | 0 / 3 / 0 | ×1.002 |
| sha256 | **×1.086** [1.080–1.092] | ×1.078 [1.074–1.091] | 3 / 0 / 0 | **×1.087** |
| wordfreq | ×1.011 [1.005–1.012] | ×1.010 [1.003–1.013] | 0 / 3 / 0 | ×1.003 |
| geometric mean | ×1.035 | ×1.033 | 6 / 20 / 1 | |

![Fig. 1. Final comparison against -O3: dot = median of three seeds, line = range across seeds; the shaded band is ±2× the program's noise floor.](results/figures/F1_final_comparison.png)

### B. RQ2: Is BO more sample-efficient than random search?

Fig. 2 shows the best configuration found so far, as a function of the number of evaluations. BO led early. After 10 evaluations its median best was ahead of random search on 7 of 9 programs: on `sha256` +4.1% vs +1.8%, on `stencil` +4.6% vs +1.5%, on `wordfreq` +1.6% vs +0.5%. On `sha256` BO needed a median of 19 evaluations to come within 1% of its final best, against 34 for random search. By 50 evaluations the advantage had largely disappeared (median best +3.0% vs +3.4% across programs), and the verified final quality of the two methods was statistically indistinguishable. The space has 2¹⁴ points, yet only a few flags matter per program, so random search hits a good region within 50 draws often enough to catch up.

![Fig. 2. Convergence during search: median best-so-far across three seeds; bands show the best and worst seed.](results/figures/F2_convergence.png)

### C. RQ3: What did the search find?

The winning configurations are interpretable. On `recursive`, all six best configurations turned off `-foptimize-sibling-calls` and partial redundancy elimination, and five of six also turned off `-fipa-cp-clone` and `-fgcse-after-reload`. `-O3`'s function cloning inflates this call-heavy program's code (`.text` is 21,276 bytes at `-O3` vs 16,992 at `-O2`), and BO's configuration was both faster and 12–16% smaller than `-O3`. On `sha256`, all six bests turned on `-funroll-all-loops`, which fully unrolls the 64-round compression loop, for +3% code size. The GP's per-flag relevance (Fig. 3) agrees: `-finline-functions` dominated on `recursive`, the base level (the `-O3` vectorizer cost model) on `stencil`, and `-funroll-all-loops` on six of nine programs, a flag whose effect on run time is large in both directions.

![Fig. 3. Flag relevance learned by the GP (1 / ARD length scale, normalized per program).](results/figures/F3_flag_sensitivity.png)

### D. RQ4: What does the search cost?

A search of 50 evaluations took 1.5–5 minutes of active time on most programs (Table 3). 43% of all evaluations compiled to an executable that had already been measured and were not timed again. Only 6 of 2,700 evaluations (0.2%) failed, all of them timeouts (3 compiles, 3 runs) during periods when the laptop was asleep or loaded by other work. No optimized build ever produced a wrong output. The -O3 build paired with itself gave a mean time ratio of 1.002 (SD 0.024, n = 53), which confirms the paired measurement has no order bias. Compile times of the best configurations differed from `-O3` by −23% to +37%, but differences of the same size appeared for a configuration identical to `-O3`, so they reflect compile-time measurement noise rather than the flags.

Table: TABLE 3. Search cost per run (mean of 3 seeds)
| Program | Method | Unique binaries | Compile time (s) | Active search time (min) |
| --- | --- | --- | --- | --- |
| matmul | BO / Random | 11.3 / 10.7 | 43 / 45 | 1.8 / 1.5 |
| recursive | BO / Random | 34.3 / 29.7 | 59 / 50 | 3.3 / 2.3 |
| sha256 | BO / Random | 41.0 / 42.0 | 55 / 55 | 4.1 / 3.7 |
| stencil | BO / Random | 23.0 / 17.3 | 111 / 49 | 17.4 / 3.1 |
| all 54 searches | – | 1,541 measured | – | 303 min total |

![Fig. 4. Binary size against run time of every evaluated configuration for two programs.](results/figures/F4_size_vs_time.png)

## 7. Discussion

**Where tuning pays off.** Gains appear exactly where `-O3`'s heuristics misjudge the program. Aggressive cloning and sibling-call optimization hurt deep recursion, and unrolling helps a fixed-trip-count cryptographic loop. For regular loop nests (`matmul`), branchy searches and the remaining real-data workloads, `-O3` is already within measurement noise of the best configuration in this space. Searching per program is therefore worthwhile mainly as a check: it either finds a real gain or confirms that `-O3` is sufficient.

**BO vs random search.** In a 14-bit space where few bits matter, BO's model buys speed of discovery, not a better final answer at 50 evaluations. That is still valuable when each evaluation is expensive, for example longer-running programs or larger budgets per configuration. With a much larger space, for example more flags or `--param` values, the gap should grow. This is the natural next experiment.

**Measurement matters as much as search.** Without pairing, a power-source change produced a fake 33% "improvement". Without re-measurement, a 7.9% search-time outlier on `matmul` would have been reported, although it was a tie. And without the encoding check, the `-O3` vector would not even have reproduced `-O3`. These safeguards are what make the reported ×1.09–×1.16 speed-ups credible.

## 8. Threats to Validity

- **Internal.** Timing noise remains for memory-bound kernels. `stencil`'s 9.7% noise floor prevented any verdict despite a consistent median gain. The laptop slept several times during the 36-hour sweep. This caused 6 failed evaluations, one aborted run that was deleted and re-run from scratch, and inflated wall times for 3 runs. Pairing and interleaving protect the speed-up figures from such drift, but the absolute times in Table 3 for those runs are less reliable.
- **External.** One compiler version, one CPU and nine single-file programs. The corpus is real but represents one text domain. The results may not transfer to large multi-file applications or to other microarchitectures.
- **Construct.** Only pass selection is searched, not ordering or numeric `--param` values. Kernel time excludes process start-up. The objective is run time alone: binary size and compile time are reported but not optimized.
- **Statistical.** Three seeds per method limit the precision of the BO-vs-random comparison. The verdict rule is deliberately conservative, so small real gains (e.g. `sort` ×1.02 with p = 0.0008) are reported as ties because they fall inside twice the noise floor.

## 9. Conclusion

We built and evaluated a complete system for per-program selection of GCC optimization passes with Bayesian Optimization, with a verified encoding, a drift-cancelling paired objective and a strict re-measurement protocol. On real hardware, BO found configurations that beat `-O3` by ×1.086 (7.9% less run time) on a real-data SHA-256 workload and by ×1.16 (13.8% less run time) on a call-heavy recursive program, gains that held on larger inputs and came with smaller or similar code. Elsewhere `-O3` was already near-optimal, and the system reported ties rather than noise. BO reached good configurations in fewer evaluations than random search, though both converged to the same quality within 50 evaluations in this small space. Future work: larger search spaces (more flags and `--param` values), multi-objective tuning of size and speed, pass ordering with LLVM, and transferring models between programs.

## References

[1] J. Snoek, H. Larochelle, and R. P. Adams, "Practical Bayesian optimization of machine learning algorithms," in *Advances in Neural Information Processing Systems (NeurIPS)*, 2012.
[2] D. R. Jones, M. Schonlau, and W. J. Welch, "Efficient global optimization of expensive black-box functions," *Journal of Global Optimization*, vol. 13, no. 4, pp. 455–492, 1998.
[3] K. D. Cooper, P. J. Schielke, and D. Subramanian, "Optimizing for reduced code space using genetic algorithms," in *Proc. ACM SIGPLAN Workshop on Languages, Compilers, and Tools for Embedded Systems (LCTES)*, 1999.
[4] G. Fursin et al., "Milepost GCC: Machine learning enabled self-tuning compiler," *International Journal of Parallel Programming*, vol. 39, no. 3, pp. 296–327, 2011.
[5] J. Ansel et al., "OpenTuner: An extensible framework for program autotuning," in *Proc. International Conference on Parallel Architectures and Compilation Techniques (PACT)*, 2014.
[6] T. Mytkowicz, A. Diwan, M. Hauswirth, and P. F. Sweeney, "Producing wrong data without doing anything obviously wrong!," in *Proc. ASPLOS*, 2009.
[7] C. E. Rasmussen and C. K. I. Williams, *Gaussian Processes for Machine Learning*. MIT Press, 2006.
[8] J. Chen et al., "Efficient compiler autotuning via Bayesian optimization," in *Proc. IEEE/ACM International Conference on Software Engineering (ICSE)*, 2021.
[9] C. Cummins et al., "CompilerGym: Robust, performant compiler optimization environments for AI research," in *Proc. IEEE/ACM International Symposium on Code Generation and Optimization (CGO)*, 2022.
[10] F. Pedregosa et al., "Scikit-learn: Machine learning in Python," *Journal of Machine Learning Research*, vol. 12, pp. 2825–2830, 2011.
[11] Free Software Foundation, "Options that control optimization," GCC manual, gcc.gnu.org/onlinedocs.
