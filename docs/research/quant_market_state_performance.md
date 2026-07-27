# Quant Market-State Performance Benchmark

Measured on 2026-07-24 with the repository Python environment and the balanced
preset:

```bash
python scripts/benchmarks/benchmark_quant_market_state.py --rows 100000 --preset balanced
```

| Rows | Runtime | Rows/second | Peak allocated memory | Output columns |
|---:|---:|---:|---:|---:|
| 100,000 | 35.404 s | 2,824.5 | 164.97 MiB | 76 |

Component timing:

| Component | Runtime | Share |
|---|---:|---:|
| KDS | 24.788 s | 70.0% |
| RLVS | 10.488 s | 29.6% |
| LMDS | 0.129 s | 0.4% |

The benchmark deliberately enables `tracemalloc`; its allocation tracing adds
material overhead to Python recursive loops, so this is a reproducible
instrumented benchmark rather than a claim about uninstrumented latency. KDS
and RLVS recursive filters are the expensive components. The one-million-row
case remains opt-in via `--include-million`: extrapolated allocation and runtime
were considered too environment-dependent to run automatically during routine
verification.

Correctness, float64 state recursion, robust updates, and causal invariance were
not relaxed for performance. A future optimization should benchmark an
equivalent compiled loop against the current batch reference before adoption.
