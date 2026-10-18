# Establish character and BPE baselines

## Goal
Build reproducible reference measurements before introducing Classical Chinese-specific heuristics.

## Scope
- Character-level baseline metric
- BPE vocabulary sizes 16k, 32k, 64k
- Same document-level train/validation/test split
- TPC, encode/decode throughput, exact round-trip rate
- Machine-readable result files

## Acceptance criteria
- [ ] All runs record config, dataset version, environment, and commit SHA
- [ ] Evaluation uses held-out works
- [ ] Repeated timing measurements report median and variance
- [ ] Results clearly distinguish measured values from hypotheses
