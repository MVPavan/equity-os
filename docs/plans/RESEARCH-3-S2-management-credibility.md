# RESEARCH-3 S2 — Management credibility — Implementation Plan

**Origin:** `docs/specs/2026-10-27-research-3-thesis-analysis.md` §5 "S2" (approved r4,
gpt-6.1-sol `APPROVE`), with §0, §1, §3, §6 and the owner rulings. Bead `eqos-bnx`, slice 3 → S2.
S1 closed live on 2026-11-01. Format and lessons: `docs/plans/RESEARCH-3-S1-risk-probe.md`.
**Status:** draft, awaiting Sol review
**Goal:** every Apar run draft carries a `management_credibility` section after `risk_probe`. Each
commitment episode shows its first and latest quote, its mapping entry and digest, its revision
events, and a code-computed outcome against both statements, or a stated reason why none exists.
The draft still validates `AS_KNOWN` with every claim `MATCH`.
**Out of scope:**
- S3: `ledger narrate`, `credibility_notes`, `drivers`, `thesis_narrative`, and any reading of
  whether credibility is rising or falling or what that means for the thesis.
- RESEARCH-4: the credibility adjustment to management's timeline.
- CAGR evaluation of multi-year windows (OD-5).
- Segment actuals. `eqos-djv` and `eqos-ghv` are open, and no run draft holds a segment line.
- Any extraction rule change or new Apar quarter. Existing run configs, the legacy renderer and
  import key serialization are untouched (spec §3).
- A sealed guidance-contract binding for a future year-specific rule (see C-8).
- Any change to the approved thesis. Runs still bind thesis version 13.
- Any migration. `eqos.numeric_claims` is unique only on `(version_id, claim_key)`; section keys,
  claim keys and quote citations already admit everything here (spec §0).
**Constraints:**
- The LLM is never the authoritative calculator (invariant 6). Events and outcomes are computed in
  code from cited claims. Entry quotes and locations are copied by script, never typed.
- Missing inputs fail closed per row; a structural fault raises `RunDraftError` (spec §1 rule 2).
- Every row and paragraph carries `{{e:…}}`. Labels and reasons hold no digits; dates, period
  labels and `sha256 <hex>` are structural (spec §1; `ledger/numeral_scan.py:27-45`).
- Migrations `0001`–`0045`, frozen manifests, pinned parsers, `evidence/vendor_ingest.py` and
  `pg/legacy_import.py` are not edited.
- Never open `stage4_holdout.yaml`, `stage4_manifest.yaml`, `data/holdout/` or
  `data/raw/onboarding/`. Never print vendor readings.
- Crisp minimal code (owner 2026-10-14; `.claude/rules/core/04-agent-stack.md` "Code size").
  Python rules: `.claude/rules/python/`.

## Spec against code at HEAD

Checked at `2f422db8`. The code won each of these unless stated.

| # | Spec says | Code or data says | Followed |
|---|---|---|---|
| C-1 | §0 line references (`run_draft.py:277-362`, `:632-672`, `citations.py:320-334`, others) | S1 moved them: `write_run_draft` `:311-399`, `_sections` `:683-728`, `resolve_location` `:352-374` | Code. This plan cites HEAD lines. |
| C-2 | §0: `Prior` holds only the predecessor's guidance entries | `preflight` takes **every** `SOURCE_QUOTE` (`run_draft.py:294`), and `_guidance` re-emits each unstated one as a guidance line (`:554-557`). Episode quotes would be carried into `management_ledger`. | Code: split them by section key (Task 3). |
| C-3 | §3 "Apar today": cables revenue growth has a filed measure "after the segment lines land"; "the other three metrics are unregistered" | No segment claim exists in any run draft, and both beads are open | Code: `ACTUALS` does not register cables. An unavailable measure reads "no filed measure", the true reason today. Cables rows state both reasons (P6). |
| C-4 | §3: an entry "gives" an entry digest | A stored hex is typed text that a model would have to compute, and it adds nothing over the pin | Reduced form: the digest is computed at load over all fields plus the quote. The quote is in the file so a retired entry's pin still verifies. Pinning behaves as specified. Sol to confirm. |
| C-5 | §3: entries keyed by capture | Capture ids differ between databases (Sol S1 r3 #8) | Key on the capture's blob SHA-256 (`citation.source_sha256`). |
| C-6 | §3, §5: Q3 call "filed in January 2026", Q4 "filed in May 2026" | The pinned `retrieval-manifest-v2.json` has 04-Feb-2026 and 04-Jun-2026. Q2 is 06-Nov-2025. FY27_Q1 is 31-Jul-2026. | Manifest dates in tests. The spec's conclusions still hold: Q3 is in FY26, Q4 in FY27. |
| C-7 | §3: relative wording is `AMBIGUOUS` when the filing falls after "the run's period end" | Tested at every later run, the same entry would flip: a Q4 call's "this year" reads FY27 once the FY27_Q1 run carries it | The window is validated once, at the entry's first use, against the stating run. The pin then holds it (P3). |
| C-8 | Approval note: year-specific rules need matching sealed contract bindings | True: `claim_check.py:119-121,158-165` fails an unbound drafted quote. Apar's quotes all have bindings, and S2 adds no rule. | Acceptance A5 is proven at extraction and episode level. The binding gap stays open for the first year-specific quarter; **file a bead**. |
| C-9 | §3: `better` lives only in `ACTUALS`, yet the revision rule needs direction for a plus-against-range comparison | Apar's metrics are unregistered | That one case renders `UNRESOLVED` ("direction not registered") (P5). Apar has no such pair: only point against plus. |
| C-10 | §3: "scope is the guidance contract's" | `guidance_extractor.py:115` hard-codes `CONSOLIDATED`, so a cables-segment metric reads `consolidated` and no standalone promise can arise from extraction | Followed the spec. Disclosed in the report (D4). The standalone case (A7) is synthetic. |
| C-11 | §0: `resolve_location` checks no issuer or cutoff | HEAD checks both | S3's concern. No S2 effect. |
| C-12 | Owner goal (`docs/goals/2026-10-27-research-report-targets.md:15`): a table showing "where credibility is rising or falling and what that means" | Not in spec §3; left to S3 model notes | Spec. Disclosed as absent (D1, `NOT_DONE`). |

## Investigation findings

**F-1. Episode copies pass the claim check as they are.** `bound_contract` finds the sealed import
by entity, quote text and capture location, never by the drafting claim's key
(`citations.py:202-214,316-349`). `check_version` calls it for any non-imported quote
(`lifecycle.py:278-280`). A copy keeping the contract fields and the citation therefore resolves
the same. Rendering, `{{c:…|quote}}` and `ref` work on any `SOURCE_QUOTE`.

**F-2. Rework already skips a `DERIVED` section** (`rework.py:224,236`), so episodes are re-derived
on every write. `plan` then has a wrong route for them: a rejected `episode.*` claim reaches
"supersede the thesis" (`:231-235`). It needs its own branch beside the probe's (`:225-230`).

**F-3. Captures.** `allowed_captures` admits only `prior.entries`' blobs (`run_draft.py:649-654`).
An `.original` can rest on a transcript no ledger entry cites any more, and a carried actual's
trace rests on captures outside the package, so both must join (spec §3).

**F-4. Scan.** A slug digit outside a period label blocks `UNREGISTERED_NUMBER`
(`numeral_scan.py:34,41`). `cables-growth-FY26_Q2` passes, as does `sha256 <64 hex>`. The version
check itself is the guard; no slug validator is needed.

**F-5. Filing time.** Only `Retrospective.published` holds it, for all the issuer's originals
(`api/cli.py:612`, `api/source_admission.py:390-404`). An ordinary run has none, so relative
wording stays `AMBIGUOUS`, as spec §3 allows. All four Apar transcripts have a time in the pinned
manifest.

**F-6. Revenue windows exist.** S1's Task 0 record shows one `MAPPED` `revenue_from_operations` at
H1 FY26, H1 FY25, annual FY26 and annual FY25 on the captures the runs admit, so the actual path
is testable on the retained pilot with no new read.

**F-7. PILOT-4 will refuse an episode quote** (`test_pilot_e2e.py:267-281`: any non-`GUIDANCE`
claim must route to a fact, trace or threshold). `test_report_export_gaps.py:42` pins the old
`NOT_DONE` line. Both change in the tests round. `figures` already excludes quotes (`:254`), and
`citations_allowed` admits the prior's blobs, which hold every earlier `.original`.

**F-8. Live reruns store no new trace.** S1's FY26_Q2 and FY26_Q4 reruns show no trace delta
(`calculation_traces` is content-addressed). Apar registers no actual, so S2 adds none.

## Design decisions (for review)

- **P1, stateless rebuild.** Each run rebuilds every episode from a pool: the predecessor's
  `episode.*` claims, then the run's guidance claims. Each pool claim finds its live entry by
  (ledger key, blob, anchor). There is no separate state machine; supersession, `same_as` and carry
  all follow from this one pass.
- **P2, the record is the row.** Each row ends `statements: entry <id> sha256 <hex> <EVENT>[ (reason)]; …`.
  A one-regex parse of the predecessor's section body yields its pins and events, and that text is
  already sealed. One `Retired entries:` line keeps pins of dropped episodes, so "a previously used
  entry that is missing refuses" holds forever. No new table, field or claim.
- **P3, one window function, run at first use.** `derive_window(text, filed_at, period_end, month)`
  returns `FY<yy>`, `MULTI_YEAR` or `AMBIGUOUS`; the first match wins:
  1. `CAGR`, `a year`, `per year`, `per annum` or `year[- ]on` → `MULTI_YEAR`;
  2. an explicit fiscal label → that year;
  3. `this year` or `current year` → reference fiscal year; `next year` → reference + 1. Each is
     `AMBIGUOUS` when the filing time is missing or falls in a later fiscal year than the run's;
  4. otherwise `AMBIGUOUS`.

  A new entry whose declared `window` differs refuses, which covers the anchor-only year (A4).
  "`year on`" is a per-year rate with no dated window, so `MULTI_YEAR` is the reading of spec §3's
  "multi-period"; Sol to confirm.
- **P4, one comparison, including interim.** A statement's binding bound is `L` for `HIGHER`, `U`
  for `LOWER`. The value is rounded half-even to the statement's precision and then compared. The
  spec states this for ended windows only. Interim uses the same rule, so one comparison decides
  both; the row discloses it.
- **P5, direction.** `better` comes from `ACTUALS`. A point against a `plus` needs no direction,
  since each has one bound. A closed range against a `plus` on an unregistered metric renders
  `UNRESOLVED` ("direction not registered"), and a `plus` on a `LOWER` metric renders spec §3's
  reason.
- **P6, both reasons.** Outcome step 1 names every reason that holds ("window not established; no
  filed measure"). Otherwise the row would hide the second gap.
- **P7, one real registry entry.** `ACTUALS` holds `(revenue_growth, consolidated)`: the default
  rule set's metric (`guidance_extractor.py:58-62`), computed as `run.change_pct` of
  `revenue_from_operations` over the window against a year earlier, with an interim rule. It makes
  the `cred.*` path real and testable on the retained pilot. Apar emits no such metric, so its
  report has no `cred.*` claim. Tests of scope and direction inject a registry.
- **P8, adverse cases are pure tests**, as S1's P8. Outcomes and events are pure functions of claims
  and values; the database proves only copies, carry, traces and refusals.
- **P9, pins are checked before the run's first write**, in the CLI right after `preflight`, like
  every other refusal there. The predecessor's digest is re-checked under lock, so one check holds.
- **P10, rejected credibility claims.** `plan` refuses with their own route: correct the mapping
  with a successor entry, or rerun `--full-successor`.

Considered and cut, for "could this be half?": a stored digest (C-4); a separate episode table or
claim-per-statement (P2); segment actuals (C-3); a CLI to author entries (a scratch seed script
does it); slug validators (F-4); a per-metric definition registry (`definition` is a plain string,
compared for equality).

## File map

| File | Change | Responsibility |
|---|---|---|
| `src/fundamentals/ledger/guidance_targets.py` | create | Rule H: `GUIDANCE_KEY`, `TargetEntry`, `Targets`, `load_targets`, `derive_window`, supersession and `same_as` resolution, `check_pins` |
| `src/fundamentals/ledger/credibility.py` | create | Pure half: registry, events, outcomes, episode build, section. Binding half: `bind_credibility` |
| `src/fundamentals/ledger/falsifier_status.py` | modify | `CREDIBILITY = "management_credibility"`, member of `DERIVED` |
| `src/fundamentals/ledger/run_draft.py` | modify | `Prior.episodes/credibility/actuals/actual_blobs`; `preflight` split (C-2); `RunDraft.credibility`; claims and section in `write_run_draft`; `allowed_captures`; the `NOT_DONE` line |
| `src/fundamentals/ledger/rework.py` | modify | `plan`: the credibility route (P10) |
| `src/fundamentals/api/cli.py` | modify | load targets, `check_pins` after `preflight`, `bind_credibility` in `before_commit`, pass to `RunDraft` |
| `config/guidance_targets/aparinds.yaml` | create | Eight Apar entries (Task 3) |
| `tests/fundamentals/test_credibility.py` | create | Pure: windows, entries, events, outcomes, carry, pins, correction, section text |
| `tests/fundamentals/test_credibility_binding.py` | create | Pilot: `check_credibility`, actuals on retained filings, a carried actual, the rework route |
| `tests/fundamentals/test_pilot_e2e.py` | modify | PILOT-4: quote route admits the section; calls `check_credibility` |
| `tests/fundamentals/test_report_export_gaps.py` | modify | `:42` follows the new `NOT_DONE` line |

Estimate: about **440 production lines** (`guidance_targets.py` ≈ 100, `credibility.py` ≈ 300,
wiring ≈ 40), inside the spec's 400–600. About **400 test lines** (`test_credibility.py` ≈ 280,
`test_credibility_binding.py` ≈ 110, edits ≈ 10), at the top of the spec's range because A1–A14 are
fourteen distinct behaviours. Expected sizes: `test_pilot_e2e.py` ≈ 680 (676), every new file
under 400; each ≤ 800.

## Test-first order, gate and sealing

1. **Tests round (one Opus round, before any production change).** Write `test_credibility.py`,
   `test_credibility_binding.py`, the two edits and `config/guidance_targets/aparinds.yaml` in final
   form. The file must exist so expected event kinds can be stated. A production name is imported
   inside the test or fixture, so every file collects on the pre-change source. The round runs
   `wc -l` on every test file it touched (≤ 800, or the gate routes `CONTRACT`) and
   `git grep -n "preflight(\|RunDraft(\|allowed_captures(" -- src tests`, then reports both outputs.
2. **Red capture, orchestrator only, on the pre-change source:**
   `scripts/verify.sh red RESEARCH-3-S2 tests/fundamentals/test_credibility.py
   tests/fundamentals/test_credibility_binding.py
   tests/fundamentals/test_pilot_e2e.py::test_pilot_end_to_end
   tests/fundamentals/test_report_export_gaps.py::test_the_run_draft_shows_what_the_panel_found_missing`.
   Every node must fail, with none missing. A node passing pre-change is vacuous: fix it and capture
   again, still before production code. These node names are binding.
3. **Implement** Tasks 1–3 without touching sealed files. A sealed test changes only through
   `scripts/verify.sh reseal RESEARCH-3-S2 <proof-file>`, with a proof file naming the amendment and
   showing the amended assertion failing against the implementation it was wrong about. The
   orchestrator stops, has the test amended, and reseals.
4. **Gate (S1 lessons).**
   - `S2_BASE` is the last gated commit before S2's first code commit: `2992ec9f` unless another
     slice gates later. It is recorded in the bead at the tests round. **Every** S2 gate runs
     `VERIFY_SCOPE_BASE=$S2_BASE scripts/verify.sh gate RESEARCH-3-S2` once work is committed;
     without it the diff-coverage and added-line rails are vacuous.
   - The gate is its own step. Its `ROUTE:` line is read before anything else runs. It is never
     chained with a live write or a push (the S1 lapse, bead note 2026-11-01).
   - A rail hit or flake is ruled on in the bead, not skipped; rerun the gate before any live step.

## Tasks

### Task 1: Rule H — the mapping file and its window rule

Goal:
- `config/guidance_targets/<symbol>.yaml` loads into frozen `Targets`. A missing file gives empty
  targets, so every row reads "window not mapped". A structural fault raises `RunDraftError`:
  duplicate id, a `same_as` or `supersedes` naming an unknown id, two successors of one entry, a
  cycle, an unknown window form, or `window_text` not a substring of `quote`.
- A digest over all fields plus the quote is computed at load (C-4).
- `live(key, blob, anchor)` returns the entry that is not superseded; `same_as` naming a superseded
  id resolves to its live successor.
- `check_pins` refuses when a pinned id is gone or its digest differs.
- `derive_window` follows P3 exactly.

Files:
- Create: `src/fundamentals/ledger/guidance_targets.py`
- Test: `tests/fundamentals/test_credibility.py`

Interfaces:
- Consumes: `RunDraftError` (`run_traces`).
- Produces:
  - `GUIDANCE_KEY`, moved here from `run_draft.py:102`, which imports it: an episode copy's ledger
    key is rebuilt from its metric, horizon and scope, and `credibility.py` cannot import `run_draft`.
  - `WINDOW_MULTI_YEAR = "MULTI_YEAR"`, `WINDOW_AMBIGUOUS = "AMBIGUOUS"`.
  - `TargetEntry` (frozen): `id, claim_key, source_sha256, anchor, quote, window_text, window,
    definition: str`, `same_as, supersedes: str | None`, and property `digest -> str`.
  - `Targets` (frozen) with `entries: Mapping[str, TargetEntry]`, `live(claim_key, sha, anchor) ->
    TargetEntry | None`, `root(entry) -> TargetEntry` (follows `same_as` through live successors)
    and `successor(entry_id) -> TargetEntry | None`.
  - `load_targets(symbol: str, root: Path = ROOT) -> Targets`.
  - `derive_window(text: str, filed_at: datetime | None, period_end: date, month: int) -> str`.
  - `check_pins(targets: Targets, pins: Mapping[str, str]) -> None`.

Approach: one module, no classes beyond the two models. The file name is the lower-cased symbol
(`config/identity/aparinds.yaml` is the precedent). The relative words are the closed list in P3.
A fiscal year is named by its end year, as `FY26` ends March 2026 at month 3.

Verification: `uv run pytest tests/fundamentals/test_credibility.py -k "window or entry or pin" -n 0`
passes. Cases: A3, A4, A6, A10, A13's missing entry, and each structural fault (parametrized).

Test seams: `load_targets` on a temp root, `derive_window`, `check_pins`. Pure.

Dependencies: None.

Risks: low. A wrong `derive_window` branch misdates a promise; the A6 cases pin it.

### Task 2: Events, outcomes, episode build and the section (pure)

Goal: given guidance claims, the predecessor's `episode.*` claims and section body, targets, actuals
and the run's period end, the module builds each episode and renders the section exactly as spec §3
and "Report disclosures" below.
- **Episode id** `<metric>.<scope>.<window key>`. The window key is the `FY<yy>` label, else
  `<class>.<root entry id>`. Claims are `episode.<id>.original` and `episode.<id>.latest`, copies
  of the guidance claim with `claim_key` and `section_key` changed and everything else kept.
- **Pool (P1).** `.original` is the first statement, `.latest` the last. A carried statement already
  in the record adds no event. New statements add one event each against the previous `.latest`,
  after their window is validated (C-7, against `run.period_end`). Prior events stay as recorded.
- **Events** follow the spec's three steps. Comparability first: metric, scope, unit, currency,
  constant-currency and `definition` must be equal, else `REVISED` ("basis changed"). Then the
  compared value: point; midpoint for a closed range; binding bound when one statement is open.
  Then the event: `REVISED_UP`, `REVISED_DOWN`, `REVISED` ("range widened" or "range narrowed"),
  `REAFFIRMED`. Direction names a number's move only. P5 applies.
- **Outcomes**, first match wins, per endpoint: the five spec steps, with endpoint comparability
  and P4, P6. `about` adds no tolerance. `ON_TRACK` and `BEHIND` are `{{e:inferred}}` with the fixed
  label.
- **Correction.** Each pinned entry now superseded and not yet in `Retired entries:` renders a line
  naming old and new ids, digests, windows and definitions, then joins that line. An episode id no
  longer built renders once as `UNRESOLVED` ("mapping corrected", naming the successor).
- **No evaluable row** (no mapped episode): one paragraph, naming each reason (spec §1 rule 2).

Files:
- Create: `src/fundamentals/ledger/credibility.py` (pure half)
- Test: `tests/fundamentals/test_credibility.py`

Interfaces:
- Consumes: Task 1; `_slot`, `refs` (`import_mapping`); `CREDIBILITY` (`falsifier_status`); `PERCENT`
  (`claim_check`); `NumericClaim`.
- Produces:
  - `EventKind(StrEnum)`: `OPENED, REVISED_UP, REVISED_DOWN, REVISED, REAFFIRMED, UNRESOLVED`.
    `Event` (frozen): `kind`, `reason: str | None`.
  - `Outcome(StrEnum)`: `ACHIEVED, MISSED, ON_TRACK, BEHIND, UNRESOLVED`.
  - `Better(StrEnum)`: `HIGHER, LOWER`.
  - `Interim` (frozen): `denominator: str`, `relation: str`, `label: str`. The two windows are one
    fixed rule: fiscal start to the run's period end, and the same fiscal months a year earlier
    (February 29 has no comparator, so `UNRESOLVED`).
  - `Actual` (frozen): `numerator: str, better: Better, unit: str, currency: str | None,
    definition: str, interim: Interim | None`. Its key is `ACTUAL_KEY =
    "cred.{metric}.{scope}.{window}"`; the interim value is `<that>.ytd`.
  - `ACTUALS: Mapping[tuple[str, str], Actual]` (P7).
  - `revision(before: Statement, after: Statement, better: Better | None) -> Event`.
  - `compare(statement: Statement, value: Decimal, better: Better) -> bool` (P4).
  - `assess(statement, window, actual_entry, ended, actual, ytd) -> tuple[Outcome, str | None]`.
  - `Statement` (frozen): `claim: NumericClaim`, `entry: TargetEntry`.
  - `Built` (frozen): `claims: tuple[NumericClaim, ...]`, `body: str`.
  - `pins_of(body: str | None) -> dict[str, str]`.
  - `build(guidance, prior_claims, prior_body, targets, *, actuals, registry=ACTUALS, period_end,
    month, filed_at) -> Built`, where `filed_at: Mapping[str, datetime]`.

Approach: table-free functions; one row renderer. Each row carries `{{e:observed}}` for the quotes,
`{{e:computed}}` for events and actuals, `{{e:inferred}}` for interim. `.latest` shows only its ref
when it is the same location as `.original`. The stored actual is the "unrounded" one OD-7 requires.

Verification: `uv run pytest tests/fundamentals/test_credibility.py -n 0` passes; the whole file is
a red-proof target. Named cases:
- (a) `revision`: `REVISED_UP`, `REVISED_DOWN`, basis changed, widened, narrowed, `REAFFIRMED`,
  plus against range on the binding bound, plus on `LOWER`, range against plus with no direction,
  point against plus with no direction.
- (b) Ended: same actual `MISSED` `.original`, `ACHIEVED` `.latest`, row shows the unrounded actual
  and "rounded to the guidance's stated precision"; a rounding-boundary value proves half-even.
- (c) A3, A4 rows; (d) FY26 and FY27 are two episodes; (e) A5's one-transcript case, with
  `extract_guidance_claims` on a fake `LoadedPdf` giving two claims and two episodes, and two
  same-horizon rules refusing through `_Body.add`.
- (f) A7, through an injected registry; neither scope's `.latest` touches the other.
- (g) A8; (h) A9; (i) A10; (j) A11, full correction path over two builds; (k) A12, including the
  side-by-side downward revision and a missing comparator; (l) A13; (m) A14.
- (n) `scan_section` on rendered bodies of all statuses returns no state.
- (o) every disclosure constant is in the body, and the no-evaluable-row paragraph.

Test seams: `revision`, `assess`, `build`. Pure, no I/O.

Dependencies: Task 1.

Risks: test-first. This is the financial logic of the slice; a wrong bound or direction is a wrong
verdict in a reader-facing report.

### Task 3: Actuals, wiring, the Apar file

Goal:
- Every `fundamentals run` writes `management_credibility` after `risk_probe` and before
  `open_questions`, with `AS_KNOWN` all `MATCH`.
- `bind_credibility` stores a `run.change_pct` trace and cites a `cred.*` claim for each registered
  window due in this run. Ended uses the window against a year earlier; open uses the year-to-date
  pair. A value already in `prior.actuals` is carried with its citation, and its captures are
  admitted.
- A used entry that changed refuses before the run's first write, and no version persists.
- A rejected `episode.*` or `cred.*` claim refuses with P10's route.

Files:
- Modify: `src/fundamentals/ledger/credibility.py` (binding half),
  `src/fundamentals/ledger/falsifier_status.py`, `src/fundamentals/ledger/run_draft.py`,
  `src/fundamentals/ledger/rework.py`, `src/fundamentals/api/cli.py`
- Create: `config/guidance_targets/aparinds.yaml` (tests round)
- Test: `tests/fundamentals/test_credibility_binding.py`, `tests/fundamentals/test_pilot_e2e.py`,
  `tests/fundamentals/test_report_export_gaps.py`

Interfaces:
- Consumes: Tasks 1, 2; `_Binder.filed/evaluate/store`, `CHANGE_PCT`, `cite`, `_valued`,
  `_fiscal_month`; `_OPERAND_BLOBS`.
- Produces:
  - `CredibilityInputs` (frozen): `targets: Targets`, `actuals: tuple[NumericClaim, ...]`,
    `fiscal_year_end_month: int`.
  - `bind_credibility(repo, update, targets, prior_actuals, shas, *, entity_id, versions,
    fiscal_year_end_month) -> CredibilityInputs`.
  - `RunDraft.credibility: CredibilityInputs`.
  - `Prior.episodes`, `Prior.actuals: tuple[NumericClaim, ...] = ()`, `Prior.credibility: str | None
    = None`, `Prior.actual_blobs: frozenset[str] = frozenset()`.

Approach:
- **`preflight` (C-2).** `quotes` stay the retention check. `entries` becomes those outside
  `CREDIBILITY`; `episodes` those inside; `credibility` the predecessor's section body; `actuals`
  its `cred.*` claims without `.ytd`; `actual_blobs` from `_OPERAND_BLOBS` over their traces.
- **`allowed_captures`** adds `episodes`' blobs and `actual_blobs`.
- **`write_run_draft`.** Build from the section's guidance claims (`body.claims`, with carried ones),
  add `Built.claims` and the used actuals to `claims` before `_check_sources`, append the section
  after `probe_section`. `filed_at` is `run.retrospective.published`, or empty on an ordinary run.
- **`bind_credibility`.** Windows due: live `FY<yy>` entries of registered metrics whose blob is in
  `shas` (the run's transcript plus prior episodes' blobs, so no later transcript's window computes
  early). Sources: the run's own XBRL, then the YoY comparator's, as `bind_probe` reads them.
  Missing either window leaves no claim, and the row reads as spec §3.
- **`NOT_DONE`.** "- a management-credibility assessment" becomes "- a judgment of management
  credibility: `management_credibility` holds only the mapped record, revision events and
  code-computed outcomes; no model explanation, trend or thesis consequence".
- **Apar file.** A scratch seed reads quote, blob and anchor from the S1 export's `ref` and quote
  text (`scratchpad/research3-s1/task6/live/export/APARINDS`). The implementer adds only `id`,
  `window_text`, `window`, `definition` and `same_as`, after reading each quote's transcript
  context. Predicted from the rule patterns; the transcript reading may change `same_as`:

  | Entry id | Quote from | Window (reason) | `same_as` | Definition |
  |---|---|---|---|---|
  | `conductor-ebitda-FY26_Q2` | FY26_Q2 | `AMBIGUOUS` (no year) | | `conductor_ebitda_per_mt` |
  | `cables-growth-FY26_Q2` | FY26_Q2 | `MULTI_YEAR` ("year on") | | `cables_revenue_growth` |
  | `cables-growth-FY26_Q3` | FY26_Q3 | `MULTI_YEAR` (CAGR) | `cables-growth-FY26_Q2` | `cables_revenue_cagr` |
  | `cables-margin-FY26_Q3` | FY26_Q3 | `AMBIGUOUS` (no year) | | `cables_ebitda_margin` |
  | `conductor-ebitda-FY26_Q4` | FY26_Q4 | `AMBIGUOUS` (no year) | `conductor-ebitda-FY26_Q2` | `conductor_ebitda_per_mt` |
  | `conductor-volume-FY26_Q4` | FY26_Q4 | `MULTI_YEAR` ("year-on-year") | | `conductor_volume_growth` |
  | `cables-growth-FY26_Q4` | FY26_Q4 | `MULTI_YEAR` ("a year") | `cables-growth-FY26_Q3` | `cables_revenue_growth` |
  | `cables-margin-FY27_Q1` | FY27_Q1 | `AMBIGUOUS` (no year) | `cables-margin-FY26_Q3` | `cables_ebitda_margin` |

  A no-year entry's `window_text` is its whole quote, the strictest input to P3. Cables' CAGR quote
  has its own definition, so its two events read `REVISED` ("basis changed"), not a numeric
  direction: a CAGR and an annual growth rate are not one measure. Conductor and margin carry the
  numeric events. Sol checks every entry and link at the phase review; an unsupported link is
  removed, so the quote stands as its own episode.
- **Permanence.** The file becomes append-only at the first live version: a later correction is a
  `supersedes` entry and a permanent correction line. Sol's entry review must close first.

Verification: `uv run pytest tests/fundamentals/test_credibility_binding.py tests/fundamentals/test_pilot_e2e.py tests/fundamentals/test_report_export_gaps.py tests/fundamentals/test_prep5_rework.py tests/fundamentals/test_prep2b_run_draft.py tests/fundamentals/test_pilot_citations.py -n 0`
passes (compose postgres plus retained originals). Named tests in `test_credibility_binding.py`:
- `check_credibility(pilot, version_ids)`, called by PILOT-4 for each quarter: the section follows
  `risk_probe`; every `management_ledger` key starts `ledger.`; the episode key set per quarter
  equals literals; `.original` stays unchanged across the chain while `.latest` moves; each event
  kind equals a literal; every row is `UNRESOLVED` with its literal reasons; pins equal the file's
  digests; no `cred.*`; all `MATCH`.
- `test_filed_actuals_on_retained_statements`: annual FY26 against FY25 and H1 FY26 against H1 FY25
  equal constants computed once by an independent scratch `Fraction` calculation from the filed
  figures, never by the probe or this code. Each claim resolves `MATCH` through `check_claim`.
- `test_a_carried_actual_keeps_its_citation_and_captures`: the next run's `cred.*` is the prior's
  citation, its blobs admitted; an unadmitted one refuses "captures not in the run's package".
- `test_a_changed_entry_refuses_before_any_write`: parametrized edit and delete; counts unchanged.
- `test_a_rejected_episode_claim_routes_to_a_mapping_correction`.

Test seams: the pilot's four-quarter run on its own `eqos_test_*` database; `bind_credibility`.

Dependencies: Tasks 1, 2.

Risks:
- Medium. C-2's filter is the main regression risk; `check_credibility` and the existing PREP-5
  tests guard it. Rework of Q3 or later must keep its episodes through `prior`, not `reworked`.
- The new section changes every future version's bytes, not any approved one's.

### Task 4: Regenerate the four live Apar drafts and close S2 (operational, orchestrator)

Goal: new `APPROVED` versions for FY26_Q2, FY26_Q3, FY26_Q4 and FY27_Q1, each carrying
`management_credibility`, in that order, each approved before the next, with Sol's `APPROVE` through
`ledger panel`.

Files:
- Create (never committed): `scratchpad/research3-s2/cred_gate.py`, `s2q.sh`, `s2panel.sh`,
  `make_brief.py`, adapted from S1's. Scratch outputs under `scratchpad/research3-s2/task4/`.

Interfaces:
- Consumes: Tasks 1–3 at the phase-approved commit, which has a passing gate and Sol's `APPROVE`;
  thesis version 13 and its digest; the LIVE-RUN-1 per-quarter table, `$RM`, `$CFGS`, `$LOC`,
  `$INTAKE`, `$SNAP` (`scratchpad/live-run-1/live-scratch/lq.sh`); `counts.py`, `delta.py`,
  `digests.py`; S1's `probe_gate.py`.
- Produces: four new `APPROVED` versions, their outputs, a post-run backup.

**Lineage (permanent).** Latest approved: FY26_Q2 v15, FY26_Q3 v16, FY26_Q4 v18, FY27_Q1 v19, on
thesis v13. The new drafts' `predecessor_id` are those heads, and each approval supersedes its head.
v14 and v17 stay `CHANGES_REQUESTED` as records. Regeneration order is forced: an S2 run opens its
episodes from its predecessor's, so FY26_Q3 run against S1's FY26_Q2 would lose the first
statements. v15 and v16 were written before `2992ec9f`, so the new FY26_Q2 and FY26_Q3 also gain the
limit-basis sentence in `risk_probe`; this is expected, and gate (d) allows only that section.

**Paths.** `OUT=scratchpad/research3-s2/task4/$ENV`, `ENV` = `rehearsal` or `live`, holding `out/`,
`responses/`, `verdicts/`, `gate/`, `counts/`, `logs/`, `export/` at close. No path is shared with S1
or between environments. Preflight before each environment's first write: `$OUT` does not exist,
and is then created `mkdir -m 700`; for each quarter no output exists and `$LOC/<Q>.json` and
`$INTAKE` are readable. Any failure stops before any write. Attempt `<n>` of a recovery uses
`<Q>-r<n>` on every path.

**Expected counts delta per write, stated before running.** `E` is the quarter's episodes from the
Task 3 table.

| Quarter | `E` | `run` (`report_versions`, `report_sections`, `numeric_claims`) | `check`, `panel` |
|---|---|---|---|
| FY26_Q2 | 2 | +1, +11, +91 (S1 87 + 2E) | states +91 |
| FY26_Q3 | 3 | +1, +11, +84 (S1 78 + 2E) | states +84 |
| FY26_Q4 | 4 | +1, +11, +97 (S1 89 + 2E) | states +97 |
| FY27_Q1 | 4 | +1, +11, +87 (S1 79 + 2E) | states +87 |

`calculation_traces` and `calculation_trace_operands` +0 on each run (F-8). `check`: `validations`
+1. `submit`: `decisions` +1. `export`: none. `panel`: `decisions` +1, `panel_reviews` +1,
`validations` +1. If Sol's entry review changes a link, `E` changes; the orchestrator updates this
table with the reason before the rehearsal. In the rehearsal, a delta differing from this table is a
deviation to explain before live. Then live must equal the rehearsal's delta, step for step.

Approach:
1. **Rehearsal, all four quarters, on a restored copy.** `db backup` → `db restore --database
   eqos_test_s2_runs` through the live environment, as LIVE-RUN-1 L1a; roots are `cp -a` copies under
   `$OUT/roots/`. Record each exit, id, delta, claim state and gate result. The rehearsal panel uses
   a `rehearsal` verdict file and an orchestrator-written response.
   - **Recovery rehearsal.** After the rehearsal FY26_Q2 is submitted: `ledger decide REPORT_VERSION
     <v> REQUEST_CHANGES --claim <an episode key>`. An ordinary `run` must refuse with P10's route.
     `run … --full-successor` must write a new draft that passes check and gate. The remaining
     quarters continue from it.
2. **Live, per quarter, in order; stop at the first deviation; never re-run a write that partly
   committed.** Reuse the quarter's locator; no `stage`.
   - `fundamentals-operator run …` → `run_draft_written version=<v>`; delta checked.
   - `ledger check` → all `MATCH`/`MATCH_UNTRUSTED`; delta checked.
   - **Gates, read-only, output to `$OUT/gate/<Q>.txt`:** S1's `probe_gate.py`, then `cred_gate.py`:
     - (a) the draft binds thesis v13 by its sealed digest;
     - (b) section order: `observable_falsifiers`, `risk_probe`, `management_credibility`;
     - (c) episodes, entries and pins equal the file's digests, with `.original` equal across the
       new chain;
     - (d) every claim also in the predecessor head has the same key, value and kind, and every
       section but `heading`, `not_performed` and (FY26_Q2, FY26_Q3 only) `risk_probe` is
       byte-identical: **no earlier number moved**;
     - (e) each event recomputed in `Decimal` from the version's own `.original` and `.latest`
       where the episode has two statements, and against the predecessor's `.latest` for a third;
     - (f) every outcome and reason equals the Task 3 literals;
     - (g) the results equal the rehearsal's.
   - `ledger submit` → `ledger export <v> --out $OUT/out/<Q>-v<v>.md` → a fresh Sol round on the
     export, with the brief below. The reply ends with `EQOS-BINDING`; saved to
     `$OUT/responses/<Q>.md`; verdict to `$OUT/verdicts/<Q>.json`. It is read before recording.
   - `ledger panel <v> …` → `APPROVED`; delta checked; `db check-live` exits 0 after every write.
3. **Close.** `ledger export --stock APARINDS --out $OUT/export --status-notes`; post-run `db backup`;
   bead notes record every id, the backup id and Sol's verdicts.

**S2 panel scope (treatment recommended by this plan, in force once Sol approves it; every brief
states it; the owner may overturn it).** The S1 amendment covers only S1, so S2 states its own:
- **Materiality.** The owner's 2026-10-29 ruling (`LIVE-RUN-1-report-export-gaps.md`, "Rulings
  needed") names LIVE-RUN-1. S2 applies the same treatment to its regenerated drafts only: approvable
  with materiality disclosed as not built; S06's materiality invariant does not bind this approval;
  S06 is unchanged and A-10 stays open. This extends an owner ruling a second time, so it is flagged
  in the handoff.
- **Drivers and thesis narrative.** Spec §4 assigns `drivers`, `credibility_notes` and
  `thesis_narrative` to S3. S2's acceptance is the record. The panel judges that these gaps are
  clearly disclosed, not that S2 fills them.
- **Risk probe.** S1 is approved. The R6 wording finding stays parked to S3; the panel reads the
  probe only for regressions.
- **Limits of this approval.** Limited to the S2 demonstration. A-04 and B-02 are not satisfied, and
  `CORE_RESEARCH_RELEASE` stays NO.

**Every brief also lists the rulings that bind S2 (S1 lesson 1):** OD-1 (C-12 measures machine
effort); OD-2 and invariant 7's extension (raw probe amounts); OD-5 (multi-year windows
`UNRESOLVED`); OD-6 (`BEHIND` only through an interim rule); OD-7 (no extra tolerance, row discloses
it); OD-8 (closing balances, for the unchanged probe); OD-9 (the window comes from `window_text`
alone); the owner's autonomous-approval directive (Sol's `APPROVE` is the approval). It points at
`config/guidance_targets/aparinds.yaml` and Sol's phase-review verdict on its entries, because the
panel otherwise sees no source evidence (`panel.py:194-196`).

Verification: four new `APPROVED` versions; both gates pass on each; recovery rehearsal passed;
`db check-live` exits 0 after every write; every delta matches. `digests.py` shows every earlier
sealed digest unchanged.

Dependencies: Tasks 1–3 committed, gate `ROUTE: PASS`, Sol's phase-end `APPROVE` covering the code
and each mapping entry.

Risks:
- Permanent writes. A panel `REQUEST_CHANGES` with no claims is recorded, and the quarter reruns
  from a verified fix as S1's v14 and v17 did; a code change re-enters the phase-end loop before any
  further live write.
- A rejected mapping after any live version pins it: a `supersedes` entry and a correction line,
  never an edit.

## Report disclosures (S1 lesson 2; fixed, digit-free, in `credibility.py`)

Sol's two S1 rejections were an undisclosed absence and an undisclosed basis. Each S2 limit is stated
in the report, and test (o) asserts each constant.

| Id | Limit | Sentence (implementer may tighten wording, not drop content) |
|---|---|---|
| D1 | No verdict | This section records stated guidance and code-computed comparisons. No overall credibility judgment, trend or thesis consequence is computed or drafted. |
| D2 | Coverage | Only quotes the run's extraction rules captured are tracked, and each rule keeps its first match, so this is not an inventory of management's commitments. Promises before this report chain's first period are absent. A captured quote is treated as a commitment because a rule matched it; surrounding context is not assessed. |
| D3 | Mapping basis | Each quote's window, definition and restatement link come from a reviewed mapping file written after these calls were published, not from the filing. Each row names its entry and digest. |
| D4 | Scope | Scope is the extracted guidance contract's field. Extraction labels every quote consolidated, so a metric naming a segment is identified by that name. |
| D5 | Event basis | Events compare a point, a range's midpoint, or a binding bound when one statement is open-ended. A qualifier such as "about" is ignored. Up and down state a number's move, not whether it is good or bad. |
| D6 | Measures | An outcome needs a registered filed measure. "No filed measure" means this pipeline computes no comparable actual, not that the company files none. |
| D7 | Windows | A quote with no single-year window cannot be scored achieved or missed, so its row stays unresolved. |
| D8 | Result | When true: "No row in this version reaches an achieved, missed or interim outcome." |
| Row | Tolerance, interim | OD-7's "rounded to the guidance's stated precision", beside the unrounded actual; the fixed "seasonality not adjusted; year-to-date assumed representative". |

## Acceptance map (spec §5 S2)

| # | Acceptance case | Proven by |
|---|---|---|
| A1 | Revision events, including plus against range | Task 2 (a) |
| A2 | Ended: `MISSED` `.original`, `ACHIEVED` `.latest`, unrounded actual, tolerance | Task 2 (b) |
| A3 | CAGR under `annual` → `MULTI_YEAR`, `UNRESOLVED` | Task 1; Task 2 (c); Apar via `check_credibility` |
| A4 | No year → `AMBIGUOUS`; anchor-only year refused | Task 1; Task 2 (c) |
| A5 | FY26 and FY27 two episodes; one transcript, one rule per year; same horizon refuses | Task 2 (d)(e) |
| A6 | Relative years, Q3 against Q4 | Task 1 |
| A7 | Standalone and consolidated | Task 2 (f) |
| A8 | Two `MULTI_YEAR` apart, linked one with an event | Task 2 (g); Apar cables |
| A9 | Basis-changing revision | Task 2 (h) |
| A10 | Editing or deleting a used entry refused on the next run | Task 1; Task 2 (i); Task 3 `test_a_changed_entry_…` |
| A11 | Correction with `supersedes` | Task 2 (j) |
| A12 | Interim, side by side, missing comparator | Task 2 (k); Task 3 `test_filed_actuals_…` |
| A13 | Plan note: both carried endpoints; a used entry gone | Task 2 (l); Task 1; `check_credibility` chain |
| A14 | Ended with no actual → "actual not yet filed" | Task 2 (m) |
| A15 | Apar regenerated with events and reasoned rows | Task 3 `check_credibility`; Task 4 |

## Verification summary

- `uv run ruff check src tests/fundamentals` and `uv run ruff format --check src tests/fundamentals`
- `uv run mypy --strict src`
- `uv run pytest tests/fundamentals` (compose postgres plus retained originals)
- Before Task 1: the tests round, then `scripts/verify.sh red RESEARCH-3-S2 <nodes>`, every node red
- `VERIFY_SCOPE_BASE=$S2_BASE scripts/verify.sh gate RESEARCH-3-S2`, its `ROUTE:` line read on its own
- `wc -l` of every changed test file ≤ 800
- `git status` shows only the files in the file map

## Self-review

- **Spec coverage.** Rule-H file, entries, digests → Tasks 1, 3. Episode claims, `Prior`, pinning →
  Tasks 2, 3. Events, rule A, outcomes, interim → Task 2. `ACTUALS` and `cred.*` → Tasks 2, 3. Spec §1
  rule 3's order and `DERIVED` → Task 3. Every acceptance case is in the map.
- **Placeholders.** None. Literal expected rows in tests are produced after the tests round reads
  the seeded quotes; no value is typed by a model (Task 3).
- **Name consistency.** `Targets`, `TargetEntry`, `load_targets`, `derive_window`, `check_pins`,
  `Statement`, `Event`, `Outcome`, `Better`, `Actual`, `Interim`, `ACTUALS`, `ACTUAL_KEY`, `revision`,
  `compare`, `assess`, `pins_of`, `build`, `Built`, `CredibilityInputs`, `bind_credibility`,
  `CREDIBILITY`, `check_credibility` are each produced once and consumed by name.
- **What has nobody named?**
  - Episode quotes re-emitted as guidance → C-2.
  - A later run flipping a relative window → C-7.
  - A superseded entry's pin after its episode is dropped → `Retired entries:` (P2).
  - An `.original` on a transcript no ledger entry cites → F-3.
  - The wrong rework route → F-2, P10.
  - Regeneration order and S1 chain → Task 4 lineage.
  - v15 and v16's missing limit sentence → Task 4 gate (d).
  - Hindsight in the mapping → D3.
  - The hard-coded `consolidated` → C-10, D4.
  - The status dashboard (`docs/status/dashboard.html`) is refreshed by the orchestrator after each
    committed task (routine, not a plan task).
  - Follow-up bead to file: sealed binding for a year-specific rule (C-8).
- **Unverified.** The same-as links and windows in Task 3's table rest on rule patterns, not the
  transcript context; the implementer reads it and Sol checks. `E` follows them. No test or database
  command was run for this plan. `S2_BASE` assumes no other slice gates before S2's first code commit.
- **Owner's financial judgment.** None is decided here: no credibility verdict is computed. Two
  items the owner may overturn: the materiality extension and the deferral of the "rising or falling"
  reading to S3.
