# Establish project package, CLI, and CI

## Goal
Create a reproducible Python package for training and evaluating a Classical Chinese tokenizer on Apple Silicon macOS.

## Scope
- Package metadata and supported Python version
- `train` and `evaluate` CLI modules
- Unit tests for the sample corpus
- CI running tests and linting
- Document setup commands

## Acceptance criteria
- [ ] Fresh virtual environment installs the project
- [ ] Sample BPE model trains successfully
- [ ] Evaluation JSON is emitted
- [ ] Tests run on macOS and Linux CI
- [ ] No corpus dumps or model artifacts are committed
