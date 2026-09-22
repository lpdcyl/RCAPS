# Amendment to the final-validation audit

The earlier report
[`results/final_validation/helix_simulator_audit.md`](../final_validation/helix_simulator_audit.md)
reported that the repository exposed only an aggregate carbon-side simulator
and therefore marked request-level integration as blocked. That conclusion was
based on an incomplete source boundary: the audit did not include the original
Helix implementation under `simulator/` and its existing artifact runner under
`artifact_evaluation/single_cluster/`.

## Corrected conclusion

The original Helix request-level simulator is present and executable. It has:

- Azure Conversation arrivals through `OnlineRequestFeeder`;
- query decomposition into one initialization and one-token increment requests;
- event-driven transmission, queueing, and layer execution;
- `QueryInferenceHistory` records with source/sink timestamps and
  `PipelineStage` routes; and
- completed-query records in `QueryManager.finished_queries`.

The evidence and exact source locations are recorded in
`request_level_simulator_audit.md`. A deterministic LLaMA-30B, A100x4,
existing-ILP, GlobalFlow/Online baseline was run and its request-level CSVs
are in this directory.

## What remains true

This amendment does not claim that the carbon simulator is integrated into the
Helix event loop. The current phase adds only an independent metrics adapter,
an explicit placement/topology/route mapping boundary, a vanilla baseline
entry point, tests, and documentation. It does not create Challenge 4, modify
frozen Challenge 1/2/3 or Phase 3/3.5 outputs, replace the original
simulator/scheduler, or enable carbon-aware dispatch.

The old audit remains unchanged for historical traceability; this file is the
superseding correction for the request-level question.
