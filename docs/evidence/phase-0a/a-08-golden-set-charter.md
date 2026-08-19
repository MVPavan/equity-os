# A-08 Golden Set Charter (prepared, blocked)

## Status

`BLOCKED` / `PREPARED_NOT_APPROVED`. This charter and its fixtures are
non-production preparation only. They do not satisfy A-08 acceptance and no
prepared expected disposition is an expert label or production approval.

## Purpose and repository location

The Golden set is a bounded evaluation corpus for seeded failure handling in
the earnings-review workflow. Its prepared repository location is:

- charter: `docs/evidence/phase-0a/a-08-golden-set-charter.md`
- cases: `docs/evidence/phase-0a/a-08-golden-set.jsonl`

All initial cases are synthetic, non-production fixtures. They contain no
company fact, external document, attributable source, or rights-dependent
material.

## Authority and ownership gate

No current attributable evaluation/domain authority or accountable individual
has been found. Therefore this charter deliberately names neither an owner nor
an individual and cannot supply authority-approved labels.

| Required field | Current value | State |
| --- | --- | --- |
| accountable owner role | absent | `MISSING` |
| accountable individual name | absent | `MISSING` |
| evaluation or domain authority name | absent | `MISSING` |
| qualification/mandate basis | absent | `MISSING` |
| label approval record ID | absent | `MISSING` |
| accountable review cadence | not operable until authority appointment | `BLOCKED` |

Prepared, non-binding cadence for the appointed authority to accept, reject,
or replace: review on corpus release, after a material observed failure, and
at least every 90 days. This is a proposal, not an adopted cadence.

## Case contract

Every JSONL record has a stable `case_id`, a required failure `category`,
bounded `synthetic_input` and `synthetic_reference`, a prepared expected
disposition, label and authority state, version, provenance, and a digest.
The digest is SHA-256 of the record after recursively sorting keys and
serializing as compact UTF-8 JSON, **excluding the `digest` member**. It is
therefore non-self-referential and reproducible.

`label.state = PREPARED_NOT_APPROVED` and `label.authority_state = MISSING`
mean that the disposition is a test preparation hypothesis only. It must not
be represented as an expert label, an accepted golden-set result, or an A-08
acceptance result.

## Promotion and change control (blocked)

Only a future named accountable individual with a recorded evaluation/domain
authority and an approval record may: approve labels, change a disposition,
add a case, retire a case, or promote this corpus. A change must create a new
case-set version, preserve the prior record, update the digest, and record the
authority approval. Until then, all records remain `BLOCKED` /
`PREPARED_NOT_APPROVED`.

## Scope

The prepared corpus covers prompt injection, source confusion, source,
period, unit, citation, numerical trace, unsupported claim, and materiality
failures. It is intentionally synthetic so that it does not imply a selected
source package, a source-rights decision, production evaluation, or Phase 0A
exit. A-08 remains `Open` in the decision register.
