# Define corpus manifest and provenance validation

## Goal
Make every corpus source auditable before training.

## Scope
- Define manifest schema
- Record source URL, version/commit, retrieval date, SHA-256, license, upstream provenance
- Document allowed acquisition routes and restrictions
- Add validation for missing mandatory metadata

## Acceptance criteria
- [ ] Every adopted source has a completed manifest row
- [ ] Unclear rights block inclusion in the release corpus
- [ ] CTP automated access restrictions are respected
- [ ] Large corpus files are excluded from Git
