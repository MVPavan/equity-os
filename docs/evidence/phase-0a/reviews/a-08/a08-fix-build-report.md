# A-08 Golden Set — Revision Build Report (case-set `0.2.0-prepared`)

Responds to `scratchpad/phase-0a/a08-review/a08-golden-set-review-r0.md`
(Critical 3 / Important 7 / Minor 5).

Files changed (only these two):

- `docs/evidence/phase-0a/a-08-golden-set.jsonl` — 20 cases → 32 cases
- `docs/evidence/phase-0a/a-08-golden-set-charter.md` — rewritten

Prior version `0.1.0-prepared` is preserved in git at commit `1bba793`.

Scratch tooling (gitignored): `build_golden_set.py` (emits the JSONL),
`check_golden_set.py` (independent verifier).

---

## 1. Charter-level contracts settled first

Per the review's closing note, I3/I2/I4 were settled at charter level **before** any
case was authored or edited, so all 32 cases are written against one stable contract.

**(a) REJECT-vs-DEFER taxonomy.** One test: *is there a named, available next retrieval
that could settle this?* Yes → `DEFER` (claim not contradicted, defect curable by
evidence the package permits). No → `REJECT` (contradicted by, or unsupportable on, the
frozen package). `ACCEPT` → supported as stated and compliant with every charter
convention. `A08-SYN-004`/`A08-SYN-005` are named in the charter as the reference pair
for the boundary. Explicit: "`DEFER` is not a soft `REJECT`. A grader who cannot name the
curing retrieval must not answer `DEFER`."

**(b) `synthetic_reference` contract.** Evidence only: located facts (what a named
document records at a named location) plus standing package policy introduced by the
literal prefix `Package rule:`. The reference must never state or paraphrase the
disposition, and verdict language is banned. Stated rule: "The disposition must *follow
from* the reference, never *be read off* it."

**(c) Percent vs percentage points.** A change in a ratio-valued measure is reported in
percentage points; a relative change may be reported in percent **only** when the claim
explicitly labels it relative and discloses both endpoints; an unlabelled "rose N
percent" on a ratio is read as percentage points. Exercised by `A08-SYN-010` (violates)
and `A08-SYN-027` (complies).

**(d) Prompt-injection trust boundary.** Operator instructions arrive only in the task
request; text quoted from a source document is untrusted content under review, however
imperative. Injection cases now render the hostile string as an explicit
document-embedded excerpt in `synthetic_input` (`SYN-DOC-3 page 2 contains the text:
"..."`), so the boundary is visible in the stimulus rather than implied by the reference.

**Decision vocabulary.** Closed set `{ACCEPT, REJECT, DEFER}` — 3 codes over 32 cases,
replacing 20 unique per-case codes. Failure *type* is carried by `category` (fixed
nine-value vocabulary).

---

## 2. Resolution per review finding

### Critical

| ID | Resolution |
| --- | --- |
| **C1** — no positive controls | Added **12 `ACCEPT` cases** (`A08-SYN-021`…`032`), at least one per category, including 5 near-misses. A "reject everything" responder now scores 20/32 = 62.5% and fails **every** category. |
| **C2** — `009` penalises a correct answer | Rewritten as a real scale mismatch: input "measure is **5** base units" vs reference "recorded as 5 in a column headed *thousands of base units*" (i.e. 5,000). `REJECT` now unambiguous. Paired ACCEPT control `A08-SYN-026` states 5,000 on the same evidence. |
| **C3** — authority fields absent | Charter now carries all six authority fields, each filled **by reference** to a pending product-owner approval record at `docs/evidence/phase-0a/a-08-approval-record.md`, state `PENDING`, with the charter stating plainly the record does not yet exist and A-08 is not met until it does. No authority is fabricated. The charter adds five discharge conditions the record must meet — notably that the label authority's **qualification/mandate basis must be stated** (a product-owner signature supplies ownership and cadence, not domain label authority), and that the authority must adjudicate **each case individually** (blanket sign-off does not convert prepared dispositions into expert labels). Per-case `label` block updated to `PREPARED_PENDING_APPROVAL` / `PENDING` with an `approval_record` pointer. |

### Important

| ID | Resolution |
| --- | --- |
| **I1** — `010` ambiguous | Convention (c) written into the charter *and* the case reference; input changed to "rose 10 **percentage points**" against located 20% → 22%, so no defensible reading makes it correct. The defensible reading now lives in its own ACCEPT case (`027`). |
| **I2** — REJECT/DEFER undefined; 004/005 inconsistent | Taxonomy (a) added. `004` rewritten: an authoritative signed issue is indexed at `SYN-INDEX-1` but not yet retrieved → `DEFER` (curing retrieval nameable). `005` rewritten: full-text search of every manifest document returns no occurrence and the index lists nothing further → `REJECT` (search exhausted). The split is now derivable from the written rule. |
| **I3** — one code per case; codes leak the answer | Closed 3-code vocabulary (see above). Checker asserts no reference contains its own decision string: 0 hits. |
| **I4** — three reference contracts | Contract (b) fixed. Verdict-stating references rewritten to evidence for `004`, `005`, `013`, `015`, `019` (flagged) and, for contract uniformity, `001`, `002`, `003`, `006`, `011`, `012`, `014`, `016`, `017`, `018`, `020`. Policy sentences are now uniformly prefixed `Package rule:`. Example — `015` no longer says "causal support is absent"; it supplies the two co-occurring observations plus the fact that no controlled comparison, counterfactual, or attribution is recorded, and lets the grader draw the conclusion. |
| **I5** — miscategorised cases | `004` recategorised `source_confusion` → `source`. `020` rewritten as a genuine numerical-trace failure: the trace reproduces its own output (9/5 = 1.8, so the arithmetic check passes) but one operand does not match the source value the trace cites (`SYN-DOC-9` page 2 records 9 and **4**, which yield 2.25) — an input-provenance break, distinct from `013` (no trace) and `014` (operands contradict output). Stays in `numerical_trace`; the formula-registry framing is gone. |
| **I6** — injection cases lack document framing | Convention (d). Both `001` and `002` now embed the hostile string in a quoted, page-addressed document excerpt, and state the claim under review separately. |
| **I7** — `017` bundles two failures | "auto-accept" removed. `017` is now a pure materiality comparison: unverified key measure changed 40% (located 100 → 140) and is classified immaterial, against a `Package rule:` 20% threshold. The injection lure was not re-added elsewhere; no multi-label case was introduced (single-label expectation stays safe). |

### Minor

| ID | Resolution |
| --- | --- |
| **M1** — `expected_disposition.state` held approval state | Removed. `expected_disposition` is now `{decision, rationale}` and carries only the expectation; approval state lives solely in `label`. Label promotion no longer forces a digest rebuild for non-content reasons. |
| **M2** — no case count / set digest; zero margin | Charter records the expected case count (32), the full per-category composition table, six machine-checkable invariants, and the cases-file SHA-256. Margin over the ≥20 floor is now 12 cases. |
| **M3** — `018` tautological | Rewritten to require weighing: a 3-unit exception against a 4,000-unit population (far below the 20% quantitative threshold) that is nonetheless qualitatively material because the same control failed to operate in each of the four preceding periods. Paired ACCEPT control `032` is below threshold **with** the control operating as designed. |
| **M4** — inconsistent code granularity | Dissolved by the closed vocabulary; `001` and `002` both carry `REJECT`, distinguished by `category` and `rationale`. |
| **M5** — slug form mismatch | Charter declares `snake_case` canonical and carries the exact slug ↔ acceptance-criteria mapping table, with the instruction that validators normalise separators before comparing. |

### Not adopted, with reason

- **I3's suggested `failure_category` field.** The review proposed `ACCEPT/REJECT/DEFER`
  *plus* a `failure_category` reusing the 9 slugs. That field would be identical to the
  existing top-level `category` on every failure case and `"none"` on every ACCEPT case,
  i.e. dead and redundant. Instead `category` is redefined in the charter as the
  **evaluation dimension exercised** (not a verdict), which an ACCEPT case carries clean.
  The scoring capability the review wanted — per-category scores over a closed decision
  vocabulary — is fully preserved.
- **Multi-label case for I7's combined trap.** The review offered it as optional ("if the
  combined trap is wanted"). Not added: it would be the only multi-label record in the
  set and would break the uniform single-decision expectation.

---

## 3. Deliberate design note for the re-reviewer

`synthetic_reference` uniqueness is **24/32**, down from 20/20. This is intentional, not
duplication. Eight ACCEPT cases are **minimal pairs** that share their reference with a
REJECT/DEFER case and differ only in the claim: 003/023, 007/025, 009/026, 010/027,
012/028, 014/029, 015/031, 016/030. Identical evidence with opposite correct answers is
what forces a discriminating decision instead of a keyword reflex. Non-duplication is
therefore defined in the charter on the `(synthetic_input, synthetic_reference)` **pair**,
which is 32/32 unique, as is `case_id` and `synthetic_input`. The checker asserts pair
uniqueness and additionally asserts that every minimal pair spans more than one decision.

---

## 4. Verification

### 4.1 `python3 scratchpad/phase-0a/a08-fix/check_golden_set.py`

```
lines parsed as JSON : 32/32
case_id unique       : 32/32
synthetic_input uniq : 32/32
synthetic_ref  uniq  : 24/32 (shared refs are the intended minimal pairs)
(input,ref) pair uniq: 32/32
minimal pairs        : 8 -> A08-SYN-003/A08-SYN-023, A08-SYN-007/A08-SYN-025, A08-SYN-009/A08-SYN-026, A08-SYN-010/A08-SYN-027, A08-SYN-012/A08-SYN-028, A08-SYN-014/A08-SYN-029, A08-SYN-015/A08-SYN-031, A08-SYN-016/A08-SYN-030
schema uniform       : 1 distinct shape(s), matches contract True
sub-schemas uniform  : label=1 provenance=1 expected_disposition=1
digests recompute    : 32/32
case-set version     : ['0.2.0-prepared']
decision vocabulary  : ['ACCEPT', 'DEFER', 'REJECT'] (closed set respected: True)
decision split       : ACCEPT=12 REJECT=16 DEFER=4 total=32

per-category counts (total / REJECT+DEFER / ACCEPT):
  citation            3   2   1
  materiality         3   2   1
  numerical_trace     4   3   1
  period              3   2   1
  prompt_injection    4   2   2
  source              4   3   1
  source_confusion    3   2   1
  unit                4   2   2
  unsupported_claim   4   2   2

decision-leak scan   : 0 reference(s) contain the decision string
decision-code reuse  : 3 codes across 32 cases (most-used code covers 16)

cases file sha256    : bccf21aeeab18a93f2bb463ad2fbf62fc3e3b9b5b8c87ff9381b3ab175965dee

ALL CHECKS PASSED
```

Exit status 0.

### 4.2 Digest recomputation by a second, independent implementation

The builder and checker are both Python and share the author's reading of the scheme, so
the digests were also recomputed with `jq` (`jq -Sc 'del(.digest)' | sha256sum`), which
implements recursive key sorting and compact serialization independently:

```
jq-independent digest recompute: ok=32 bad=0
```

### 4.3 Counts

- Total cases: **32** (floor is 20; margin 12)
- Decisions: **ACCEPT 12 / REJECT 16 / DEFER 4**
- Categories: all 9 present; **every** category has ≥2 REJECT/DEFER **and** ≥1 ACCEPT
- Near-miss ACCEPT cases: 5 (`022`, `025`, `027`, `030`, `031`)
- Reject-everything responder score: 20/32 = 62.5%, failing every category

### 4.4 `git status --short` (allowed files only)

```
 M docs/evidence/phase-0a/a-08-golden-set-charter.md
 M docs/evidence/phase-0a/a-08-golden-set.jsonl
```

All other entries in `git status` are untracked paths under `docs/goals/reviews/`,
`docs/specs/`, `scripts/`, and `tests/` that pre-date this task (present in the
session-start snapshot) and were not touched. No commits, no Beads mutations.

### 4.5 File SHA-256

```
bccf21aeeab18a93f2bb463ad2fbf62fc3e3b9b5b8c87ff9381b3ab175965dee  docs/evidence/phase-0a/a-08-golden-set.jsonl
fceaede42f6741873ab6d049d7a510a663f703595515a990f30674c09294b633  docs/evidence/phase-0a/a-08-golden-set-charter.md
```

The JSONL hash is recorded inside the charter (M2); verified to match the file on disk.

---

## 5. What still blocks A-08 acceptance

Evaluation-design blockers (C1, C2) and all Important/Minor findings are closed. **C3 is
structurally resolved but substantively still open by design**: the six authority fields
resolve to `docs/evidence/phase-0a/a-08-approval-record.md`, which **does not exist yet**.
Until the Orchestrator creates it, and it names the accountable owner and individual,
names the label authority *with a stated qualification basis*, adopts a cadence, carries
an approval ID, and records per-case adjudication, the labels remain preparation
hypotheses and A-08 is not met. Everything remains synthetic: no company fact, no real
filing text, no external document.

---

# Delta — r1 revision (case-set `0.3.0-prepared`)

Responds to `scratchpad/phase-0a/a08-review/a08-golden-set-review-r1.md`
(Important 2 / Minor 3; r0 findings confirmed resolved with 0 regressions).

Version bumped `0.2.0-prepared` → `0.3.0-prepared` per the charter's own change-control
rule. Records touched: `001`, `002`, `005`, `006`, `018`, `021`, `022`, `031` (8 of 32);
all 32 digests recomputed. `0.2.0-prepared` preserved in git history.

## Resolution per r1 finding

| ID | Sev | Resolution |
| --- | --- | --- |
| **N1** — `031` "asserts no relation" flips under reading (b) | Important | Input reworded to the reviewer's suggested form: "...both occurred in SYN-P0, **and characterises them as co-occurring without asserting that either caused the other**." Abstention is now explicit in the stimulus; no reading supports an affirmative independence claim, so the ACCEPT is recoverable without the rationale. Reference unchanged (still the verbatim `015` minimal pair). |
| **N2** — `prompt_injection` separable by `Package rule:` presence and reference length | Important | Fixed **structurally**, not cosmetically. `022` was re-authored into a true **minimal pair with `001`**: both now carry the *identical* reference (trust-boundary rule + the located `SYN-DOC-3` line), and differ only in the claim — `001` asserts the line *authorises* skipping validation (REJECT), `022` asserts the document *records* such a line (ACCEPT). A shared reference cannot separate the two answers it serves, so both cues die by construction rather than by tuning. The standing rule was additionally added to `021`, and `002`/`021` gained their located document text. `021` also gained a distractor (`SYN-DOC-7` page 4 records a *different* instruction, audit committee → management), so it is no longer a restatement of its own input: the claim's attribution must be checked against the right page. |
| **N3** — charter "(16 / 12 / 4)" reads positionally as ACCEPT 16 | Minor | Rewritten with labels inline: "(`REJECT` 16 / `ACCEPT` 12 / `DEFER` 4)". |
| **N4** — REJECT/DEFER overlap on the out-of-boundary case; `006` on the seam | Minor | Charter: REJECT's clause widened to "no retrieval **or admission** permitted by the package", with an explicit statement that the branches partition and that `006` falls on the DEFER side only. Case `006`: reference now names the curing action (`Package rule:` — an outside document is admitted on request to the package owner; contents are not evidence until admitted) and records that SYN-OUTSIDE-01 is available with no request made. Case `005` (the REJECT twin) tightened in the same motion — "no document outside the boundary has been identified as bearing on the measure" — so exhaustion now closes the admission branch too and only one branch fires on each. |
| **N5** — `018` rationale asserts a conclusion its rule does not supply | Minor | Rationale re-grounded on the procedural failure: the rule mandates a qualitative assessment when a control has repeatedly failed, page 2 records that failure, and the claim classifies "on size alone", omitting a mandated step — wrong "whatever the qualitative assessment would conclude". The rationale now states explicitly that the rule mandates the assessment but states no criterion for its outcome, and that none is assumed. No domain judgement is asserted. `032`'s rationale was re-read and needs no change (no qualitative trigger is recorded there, so the quantitative test alone governs). |

## Surface-cue metric — confirmed dead

The checker now enforces this permanently (new `surface-cue guard` block): within any
category holding ≥2 ACCEPT and ≥2 non-ACCEPT cases, `Package rule:` presence must not
split them and reference-length ranges must overlap. Three categories are testable; all
three report `no cue`:

```
  category           rule:ACC/non  len ACCEPT       len non-ACCEPT   verdict
  prompt_injection   2/2:2/2      [329, 388]       [329, 400]       no cue
  unit               1/2:1/2      [88, 207]        [88, 207]        no cue
  unsupported_claim  0/2:0/2      [124, 217]       [124, 217]       no cue

  prompt_injection carries the standing rule on 4/4 references
  set-wide rule-present split: ACCEPT=4 REJECT=5 DEFER=3 (rule present on 12/32)
```

- Rule present on **4/4** prompt_injection references (was 2/4, perfectly predictive).
- Lengths **329/388 (ACCEPT)** vs **329/400 (non-ACCEPT)** — overlapping, sharing the
  329 pair reference. Was 118/70 vs 245/229, cleanly disjoint.
- Set-wide the cue remains non-diagnostic: ACCEPT 4 / REJECT 5 / DEFER 3.
- The six other categories stay `n/a (<2 a side)` — a single rule-bearing case cannot
  establish a pattern, which was the reviewer's own standard.

Charter changes backing this: convention (d) now states the standing rule appears in
every document-excerpt reference *regardless of outcome*, with the reason; the anti-leak
section is extended from decision codes to reference **structure**; and a new invariant
makes the no-surface-cue property machine-checkable.

## Verification (r1)

`python3 scratchpad/phase-0a/a08-fix/check_golden_set.py` → **ALL CHECKS PASSED**, exit 0.

- 32/32 parse; case_id 32/32 unique; `(input, reference)` pair 32/32 unique
- `synthetic_reference` 23/32 unique — **9** minimal pairs now (001/022 added), each
  spanning more than one decision; charter list updated 8 → 9
- digests recompute 32/32 (Python) and **ok=32 bad=0** under independent `jq -Sc
  'del(.digest)' | sha256sum`
- schema and all sub-schemas uniform; case-set version `0.3.0-prepared` on all 32
- decision split unchanged: ACCEPT 12 / REJECT 16 / DEFER 4; all 9 categories keep ≥2
  REJECT/DEFER and ≥1 ACCEPT; 0 decision-word leaks
- `git status --short` → only the two permitted files modified; no commits, no Beads

File SHA-256 after r1:

```
e0d0d947e711c960346f4587fad459dc845c397caa482c5eea8334c6fcbeb306  docs/evidence/phase-0a/a-08-golden-set.jsonl
6d44c9160feca9d489c1b46414a1ab2a711b5757a047c83b982206f9d39bb0f2  docs/evidence/phase-0a/a-08-golden-set-charter.md
```

The JSONL hash inside the charter was updated to match and verified against disk.

C3 is unchanged and remains the sole outstanding blocker: `a-08-approval-record.md` does
not exist, so all labels stay `PREPARED_PENDING_APPROVAL` / `PENDING`.
