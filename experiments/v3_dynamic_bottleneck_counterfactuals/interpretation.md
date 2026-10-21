# Interpretation of the Three Dynamic-Bottleneck Tests

These conclusions use the paired three-seed, fixed 600 s results in `formal600_report.md`.

## 1. KV-capacity relaxation

At load 600, baseline and 2x KV capacity are identical in all reported metrics. KV capacity therefore does not explain latency in this completed, lower-load regime. At load 1100, all three baseline `C1_single/k1` windows terminate at the simulator's explicit `Exceed KV-cache capacity!` assertion, while all three paired 2x-KV windows complete. The supported conclusion is a **KV feasibility threshold** under high pressure. It is not a completed-window tail-latency comparison because the baseline has no valid latency sample after the assertion.

## 2. Link-rate and arrival-shape counterfactuals

For `C1_multi/k1`, doubling every deployed DAG link rate increases output throughput from 46.157 to 52.438 tokens/s (+13.6%), decreases TTFT P95 from 7.600 to 6.016 s (-20.8%), and decreases TPOT P95 from 1.890 to 1.266 s (-33.0%). `k3` already supplies the replicated suffix branches: its baseline throughput is 59.726 tokens/s, and rate doubling adds only 1.164 tokens/s (+1.9%). This interaction supports the mechanism that the replicated branches reduce sensitivity to limited communication capacity.

Uniformly spreading the same request sizes and ordering across the window does not improve `k1`: throughput decreases by 1.983 tokens/s and both P95 metrics increase. This trace therefore gives no evidence that arrival burstiness is the primary explanation. It should be reported as a negative result instead of omitted.

## 3. Fixed Decode route versus length-informed routing

The length-informed policy receives the true remaining output lengths of current sessions when admitting a prompt, but it keeps Decode on the selected prompt route and does not observe future arrivals. It performs worse than standard M3: output throughput decreases by 2.146 tokens/s, TTFT P95 increases by 3.968 s, and TPOT P95 increases by 0.281 s. Thus these experiments do not support an output-length-aware Decode-commitment mechanism as the next method contribution.

This policy is a bounded diagnostic, not a global clairvoyant optimum: a true future-arrival oracle would require an offline joint routing schedule. The negative result is still informative because the current M3 session-price heuristic is stronger than this direct remaining-length substitution in the tested condition.

## Paper-facing takeaway

The defensible mechanism narrative is: V3's branch copies improve online serving because they provide alternate capacity around communication-limited transitions; KV capacity separately bounds feasibility at high pressure. The results do not support an arrival-flattening explanation or a length-informed fixed-route enhancement in this workload.
