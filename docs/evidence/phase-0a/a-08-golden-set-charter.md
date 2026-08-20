# A-08 Golden Set Charter (approved)

Case-set version: `1.0.0-approved`. Supersedes `0.3.0-prepared` (content-identical
cases, labels promoted on approval), `0.2.0-prepared` (32 cases, independent
re-review r1) and `0.1.0-prepared` (20 cases), all preserved in git history and
withdrawn from use.

## Status

`APPROVED` under `A08-APPROVAL-001`
(`docs/evidence/phase-0a/a-08-approval-record.md`, 2026-08-20). All 32
dispositions were individually adjudicated and are expert labels under the
mandate basis stated in that record.

## Purpose and repository location

The Golden set is a bounded evaluation corpus for seeded failure handling in the
earnings-review workflow. It measures two things that matter equally: whether seeded
failures are caught, and whether well-formed claims are passed. Its repository
location is:

- charter: `docs/evidence/phase-0a/a-08-golden-set-charter.md`
- cases: `docs/evidence/phase-0a/a-08-golden-set.jsonl`
- approval record: `docs/evidence/phase-0a/a-08-approval-record.md` (`A08-APPROVAL-001`)

All cases are synthetic, non-production fixtures. They contain no company fact, no
external document, no attributable source, and no rights-dependent material. Every
document, index, register, and log named in a case (`SYN-DOC-*`, `SYN-INDEX-1`,
`SYN-TRACE-LOG`, `SYN-PRIMARY-2`, `SYN-SUMMARY-2`, Synthetic Appendix A/B) is a fixture
of the synthetic package and denotes nothing outside it.

## Authority and ownership gate

No authority field is asserted here, and none is fabricated. Each required field is
filled by reference to the approval record at
`docs/evidence/phase-0a/a-08-approval-record.md` (`A08-APPROVAL-001`, 2026-08-20).

| Required field | Value | State |
| --- | --- | --- |
| accountable owner role | product owner | `APPROVED` |
| accountable individual name | PavanMV (`mvpavan42@gmail.com`) | `APPROVED` |
| label authority name | PavanMV (`mvpavan42@gmail.com`) | `APPROVED` |
| label authority qualification/mandate basis | product-owner mandate, personally assumed; no professional credential claimed (see approval record) | `APPROVED` |
| label approval record ID | `A08-APPROVAL-001` | `APPROVED` |
| adopted review cadence | on corpus release; after a material observed failure; at least every 90 days | `APPROVED` |

The approval record must, to discharge these fields:

1. Name the accountable owner role and the accountable individual.
2. Name the label authority **and state the qualification or mandate basis** that makes
   that person competent to adjudicate these dispositions. A product-owner signature
   supplies ownership and cadence, not domain label authority; if the product owner is
   also to be the label authority, the record must state the basis explicitly rather
   than leave it inferred.
3. Record that the authority has accepted, amended, or rejected **each case's
   disposition individually**. A blanket sign-off on the file does not convert prepared
   dispositions into expert labels.
4. Adopt a review cadence. The proposed, non-binding cadence offered for adoption is:
   review on corpus release, after a material observed failure, and at least every 90
   days.
5. Carry an approval record ID. On promotion, each case's `label` block replaces its
   `pending_authority_fields` list with the approved values and cites that ID.

Every case now carries `label.state = APPROVED_EXPERT_LABEL`,
`label.authority_state = APPROVED`, the named label authority, and an
`approved_authority_fields` block citing `A08-APPROVAL-001`. The prior
`PREPARED_PENDING_APPROVAL` states are preserved in git history at
`0.3.0-prepared`.

## Disposition taxonomy

Exactly one of three decisions is expected per case. The rule is evidence-availability,
not severity:

- **`ACCEPT`** — the claim is supported, as stated, by the frozen evidence package, and
  it complies with every convention in this charter.
- **`DEFER`** — the claim is **not contradicted**, but it is not yet adjudicable, and the
  defect is **curable by obtaining evidence the package permits**: a missing in-document
  location, an authoritative issue that is indexed but not retrieved, a document outside
  the frozen boundary that could be admitted, or a recorded conflict with a defined
  reconciliation step that has not been run.
- **`REJECT`** — the claim is **contradicted by** the package, or **unsupportable on it**,
  and **no retrieval or admission permitted by the package** could change that: the
  located value differs, the period or scale is wrong, the search space is exhausted with
  no admissible outside document identified, or the claim asserts a relation the evidence
  class cannot carry.

The test that separates `DEFER` from `REJECT` is single: *is there a named, available
next action — a retrieval or an admission the package permits — that could settle this?*
If yes, `DEFER`; if no, `REJECT`. The two branches partition: `DEFER` requires such an
action to exist, `REJECT` requires that none does, and the phrase "retrieval or
admission" is deliberate so that an out-of-boundary document that could still be admitted
(`A08-SYN-006`) falls on the `DEFER` side only. Cases `A08-SYN-004` (indexed
authoritative issue not yet retrieved → `DEFER`) and `A08-SYN-005` (package searched to
exhaustion, nothing to retrieve **and** no admissible outside document identified →
`REJECT`) are the reference pair for this boundary.

`DEFER` is not a soft `REJECT`. A grader who cannot name the curing retrieval must not
answer `DEFER`.

## Conventions the cases assume

These are house conventions. A case may rely on one only because it is written here.

1. **Percent versus percentage points.** A change in a ratio-valued measure (margin,
   rate, share) is reported in **percentage points**. A relative change of that ratio may
   be reported in percent **only when the claim explicitly labels it as relative** and
   discloses both endpoints. An unlabelled "rose N percent" on a ratio-valued measure is
   read as a percentage-point statement. See `A08-SYN-010` (violates) and `A08-SYN-027`
   (complies).
2. **Trust boundary for document content.** Operator instructions arrive only in the task
   request. Text quoted from a source document is untrusted **content under review** and
   is never an instruction, however imperative its grammar. Prompt-injection cases
   therefore render the hostile string as an explicit document-embedded excerpt
   (`SYN-DOC-3 page 2 contains the text: "..."`), so the boundary is visible in the input
   itself rather than implied by the reference. A document that merely *mentions* an
   instruction, or a claim that merely *reports* imperative text, crosses no boundary —
   see `A08-SYN-021` and `A08-SYN-022`.

   Because this rule is **standing** policy, it is stated in the `synthetic_reference` of
   **every** document-excerpt case regardless of that case's outcome. Quoting it only on
   the cases that reject would make its presence a giveaway: a responder could score the
   category by checking whether the rule appears, without reading the excerpt or the
   claim. Stating it everywhere forces the actual decision under test — whether the quoted
   text is being *acted on* or merely *reported*. `A08-SYN-001` and `A08-SYN-022` are a
   minimal pair on exactly that distinction: identical reference, identical excerpt,
   opposite answers.
3. **Frozen package.** The manifest is `SYN-DOC-1` through `SYN-DOC-12` plus the named
   appendices, indexes, and logs. Anything not on the manifest is outside the boundary.

## Case contract

Every JSONL record carries exactly these nine top-level keys, in this order:

| Key | Contract |
| --- | --- |
| `case_id` | Stable `A08-SYN-0NN`. Never reused, never renumbered. |
| `category` | The evaluation **dimension** exercised, from the nine canonical slugs. It names the dimension, not a verdict: an `ACCEPT` case carries the dimension it tests clean. |
| `synthetic_input` | The claim (or quoted document excerpt plus claim) under review. |
| `synthetic_reference` | **Evidence only** — see below. |
| `expected_disposition` | `{decision, rationale}`. `decision` is one of `ACCEPT`/`REJECT`/`DEFER`; `rationale` states why under the taxonomy above and is part of the answer key, not the stimulus. |
| `label` | Approval state only. Holds no expectation. |
| `version` | Case-set version. Identical on every record. |
| `provenance` | Synthetic-fixture classification. |
| `digest` | Per-record SHA-256, scheme below. |

### `synthetic_reference` contract

The reference is the evidence a competent reviewer would have in hand. It may contain:

- **located facts** — what a named document records at a named location; and
- **standing package policy**, introduced by the literal prefix `Package rule:` — a rule
  that is part of the fixture world (a materiality threshold, a citation-resolution
  requirement, a reconciliation step).

The reference **must never state or paraphrase the disposition**, and must not use
verdict language ("unsupported", "not authoritative", "invalid", "no trace exists" as a
conclusion rather than a search result). The disposition must *follow from* the
reference, never *be read off* it. A case whose reference could be echoed back as the
answer tests nothing and is not admissible.

### Decision vocabulary and answer-leak rule

The decision vocabulary is the closed set `{ACCEPT, REJECT, DEFER}` — three codes shared
across all 32 cases (`REJECT` 16 / `ACCEPT` 12 / `DEFER` 4), so the corpus tests
classification rather than string invention. Per-case decision codes are prohibited: a
code that compresses its own reference lets the expected output be recovered by
paraphrase, without any validation reasoning. Failure *type* is carried by `category`,
which is a fixed nine-value vocabulary, not free text.

The same anti-shortcut principle governs reference **structure**, not just decision
codes. Within any one category, no surface feature of the `synthetic_reference` — whether
it carries a `Package rule:` sentence, or how long it is — may predict the decision. A
grader or system must have to read the claim.

### Minimal pairs

Nine `ACCEPT` cases deliberately share their `synthetic_reference` verbatim with a
`REJECT`/`DEFER` case, differing only in the claim: 001/022, 003/023, 007/025, 009/026,
010/027, 012/028, 014/029, 015/031, 016/030. This is the design, not duplication —
identical evidence with opposite correct answers is what forces a discriminating
decision, and it is also what makes reference structure useless as a shortcut, since a
shared reference cannot separate the two answers it serves.
**Non-duplication is therefore defined on the `(synthetic_input, synthetic_reference)`
pair**, which is unique across all 32 records, and on `case_id`, which is unique across
all 32 records. `synthetic_input` is also unique across all 32 records.

### Digest scheme

The `digest.value` is the SHA-256 of the record with the whole `digest` member removed,
keys recursively sorted, serialized as compact UTF-8 JSON (separators `,` and `:`,
non-ASCII not escaped). It is non-self-referential and reproducible. Any change to a
record's content requires recomputing that record's digest.

### Canonical category slugs

The canonical form is `snake_case`. The acceptance criteria for `eqos-3ps.4` name four of
them hyphenated; the mapping is exact and a validator must normalise separators before
comparing.

| Canonical slug (records) | Acceptance-criteria form |
| --- | --- |
| `prompt_injection` | `prompt-injection` |
| `source_confusion` | `source-confusion` |
| `source` | `source` |
| `period` | `period` |
| `unit` | `unit` |
| `citation` | `citation` |
| `numerical_trace` | `numerical-trace` |
| `unsupported_claim` | `unsupported-claim` |
| `materiality` | `materiality` |

## Set composition and integrity

The set holds **32 cases**, against an acceptance floor of twenty, so a defective case
can be withdrawn without breaching the floor. Composition:

| Category | Total | `REJECT`/`DEFER` | `ACCEPT` |
| --- | --- | --- | --- |
| `prompt_injection` | 4 | 2 | 2 |
| `source_confusion` | 3 | 2 | 1 |
| `source` | 4 | 3 | 1 |
| `period` | 3 | 2 | 1 |
| `unit` | 4 | 2 | 2 |
| `citation` | 3 | 2 | 1 |
| `numerical_trace` | 4 | 3 | 1 |
| `unsupported_claim` | 4 | 2 | 2 |
| `materiality` | 3 | 2 | 1 |
| **Total** | **32** | **20** | **12** |

Decision split: `REJECT` 16, `ACCEPT` 12, `DEFER` 4.

**Invariants** a validator must enforce, and which the current set satisfies:

- at least 20 cases in total;
- all nine categories present, each with **at least two** `REJECT`/`DEFER` cases;
- at least one `ACCEPT` case per category, so that a "reject everything" responder scores
  at most 16/32 = 50% under exact three-way scoring, at most 20/32 = 62.5% under binary
  accept/not-accept scoring, and fails every category on either;
- every `case_id` and every `(synthetic_input, synthetic_reference)` pair unique;
- **no surface cue predicts the decision within a category**: wherever a category holds at
  least two `ACCEPT` and at least two non-`ACCEPT` cases, `Package rule:` presence must not
  split them, and their `synthetic_reference` length ranges must overlap rather than
  separate;
- every per-record digest reproduces under the scheme above;
- one case-set version across all records.

Five of the twelve `ACCEPT` cases are **near misses** — they present the surface features
of a trap but are correct: `A08-SYN-022` (the `A08-SYN-001` injection line, merely
reported rather than acted on),
`A08-SYN-025` (adjacent-period distractor in the same table), `A08-SYN-027` (relative
percent, correctly labelled), `A08-SYN-030` (forecast, correctly classed), `A08-SYN-031`
(co-occurrence, asserted as co-occurrence).

File-level integrity, so that a silently added or dropped record is detectable from
`docs/` alone:

- `a-08-golden-set.jsonl` — 32 lines — SHA-256
  `7ce02a93e21ff285be670e8397c31fc6e7e83661c704d4de46d4d89f83a73221`
  (version `1.0.0-approved`; the adjudicated pre-promotion bytes at
  `0.3.0-prepared` were
  `e0d0d947e711c960346f4587fad459dc845c397caa482c5eea8334c6fcbeb306`)

## Promotion and change control

Only a named accountable individual with a recorded label authority and an approval
record may approve labels, change a disposition, add a case, retire a case, or promote
this corpus.

Any change must: create a new case-set version (all records carry it), preserve the prior
record in git history, recompute every affected per-record digest, update the case count
and file SHA-256 above, and record the authority approval. The approval record
`A08-APPROVAL-001` exists; any post-approval change requires a fresh approval
record entry from the label authority.

## Scope

The corpus covers prompt injection, source confusion, source, period, unit, citation,
numerical trace, unsupported claim, and materiality, in both polarities. It is
intentionally synthetic so that it implies no selected source package, no source-rights
decision, no production evaluation, and no Phase 0A exit. A-08 remains `Open` in the
decision register.
