# Prototype a syntax-aware vocabulary selection method

## Goal
Test whether Classical Chinese-aware vocabulary candidates improve linguistic segmentation beyond ordinary BPE.

## Candidate approaches
- Candidate vocabulary injection for frequent lexical units
- Controlled protection of selected function words
- Score adjustment using corpus frequency and linguistic annotations

## Constraints
- Do not merge variable-length constructions such as 不亦…乎 into one literal token
- Keep a character fallback for rare and unseen text
- Compare one change at a time against the baseline
- Preserve reversibility

## Acceptance criteria
- [ ] Method and configuration are documented
- [ ] Ablation experiment is available
- [ ] Held-out works are used for evaluation
- [ ] Compression, speed, and linguistic coverage are all reported
