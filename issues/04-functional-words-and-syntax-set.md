# Build Classical Chinese function-word and syntax evaluation set

## Goal
Measure whether segmentation reflects Classical Chinese lexical and syntactic patterns.

## Initial phenomena
- Negation: 不、未、無、非
- Judgment/aspect/final particles: 也、矣、焉
- Questions/rhetoric: 乎、耶、豈
- Patterns: 不亦…乎、何…之有 and other reviewed examples

## Scope
- Create sourced examples and annotation guidelines
- Mark spans and explain expected behavior
- Include polysemy and counterexamples
- Keep this evaluation set separate from tokenizer training data where possible

## Acceptance criteria
- [ ] Each example has provenance or a documented public-domain source
- [ ] Annotation rules are documented
- [ ] Inter-annotator review or a second-pass audit is completed
- [ ] Syntax-aware claims are not inferred from compression alone
