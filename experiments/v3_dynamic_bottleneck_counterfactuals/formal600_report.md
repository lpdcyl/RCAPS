# V3 Dynamic-Bottleneck Counterfactual Results

The table reports means over completed fixed 600 s windows. Failed windows remain listed below and are not converted into latency values.

| Group | Treatment | Load | Passed | Output tok/s | TTFT P95 s | TPOT P95 s | Completion |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| kv | base | 600 | 3/3 | 95.097 | 5.105 | 1.279 | 0.567 |
| kv | kv2 | 600 | 3/3 | 95.097 | 5.105 | 1.279 | 0.567 |
| kv | kv2 | 1100 | 3/3 | 132.689 | 5.841 | 1.817 | 0.434 |
| network | k1_base | 320 | 3/3 | 46.157 | 7.600 | 1.890 | 0.505 |
| network | k1_bw2 | 320 | 3/3 | 52.438 | 6.016 | 1.266 | 0.628 |
| network | k1_flat | 320 | 3/3 | 44.174 | 8.091 | 2.000 | 0.472 |
| network | k3_base | 320 | 3/3 | 59.726 | 5.338 | 0.713 | 0.767 |
| network | k3_bw2 | 320 | 3/3 | 60.889 | 4.276 | 0.648 | 0.781 |
| oracle | fixed | 320 | 3/3 | 59.726 | 5.338 | 0.713 | 0.767 |
| oracle | length_oracle | 320 | 3/3 | 57.580 | 9.306 | 0.994 | 0.720 |

## Paired treatment minus control

Positive throughput/completion deltas favor the treatment; negative latency deltas favor it.

| Group | Comparison | Paired seeds | Δ output tok/s | Δ TTFT P95 s | Δ TPOT P95 s | Δ completion |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| kv | kv2 − base | 3 | 0.000 | 0.000 | 0.000 | 0.000 |
| network | k1_bw2 − k1_base | 3 | 6.281 | -1.584 | -0.624 | 0.123 |
| network | k1_flat − k1_base | 3 | -1.983 | 0.492 | 0.110 | -0.033 |
| network | k3_bw2 − k3_base | 3 | 1.164 | -1.062 | -0.065 | 0.014 |
| oracle | length_oracle − fixed | 3 | -2.146 | 3.968 | 0.281 | -0.047 |

## Failed windows

- `kv/base/load1100/seed1`: `AssertionError('Exceed KV-cache capacity!')`
- `kv/base/load1100/seed2`: `AssertionError('Exceed KV-cache capacity!')`
- `kv/base/load1100/seed3`: `AssertionError('Exceed KV-cache capacity!')`
