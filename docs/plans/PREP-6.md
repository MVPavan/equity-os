# PREP-6 Implementation Plan — review telemetry on ledger claims, and a seeded-error drill

**Origin:** `docs/backend-roadmap.md` §3 row PREP-6 ("Review telemetry wired to ledger claims
(B-04, B-13); seeded-error drill"; done when "Per-claim disposition and time recorded; drill
errors caught"; status "Instrument exists (`fundamentals review`); not yet on the ledger"), §4
PILOT-11 ("The seeded-error drill is caught") and PILOT-12 ("Owner review time recorded for PQ0
and each of PQ1–PQ3, with per-claim dispositions and correction categories"). Register v2
(`docs/blueprint/funda-blueprint-implementation-decision-register-v2.md`) B-04 (:54) and B-13
(:63). PREP-5 open question 3 (`docs/plans/PREP-5.md`): PREP-6 may read `decisions.rejected_claims`
as its rejected disposition if its review set also covers additions, replacements and
presentation changes.
Status: **implemented** (commits `aeecbf1`, `3c118f6`, `794c077`, `eb682a0`, `ed7c32f`). Plan
approved — Sol (gpt-6.1-sol) APPROVE 2026-10-19: plan review r1 REVISE (13) → r2 APPROVE;
closing review r1 REVISE (1 P1, 4 P2) → r2 APPROVE. See Realisation.
**Goal:** the owner reviews a submitted ledger version claim by claim with `fundamentals review`.
Each disposition, its correction category and its time are recorded, and the session ends in the
version's decision. Telemetry rows and the decision are written in one owner transaction. A
`REQUEST_CHANGES` names exactly the claims dispositioned edited or rejected, so PREP-5 reworks
them. A successor whose section bodies, in section order, are its predecessor's (only the
run-draft metadata heading is exempt) is re-reviewed only on claims that are not identical to
claims accepted in its predecessor's session; any other successor is reviewed whole. A seeded-error drill on a synthetic shadow version, in a temporary
test database, is an **instrumentation regression**: gate-class seeds are caught mechanically by
the deterministic check, review-class seeds pass the check, a scripted reviewer's per-claim
dispositions and times are recorded and scored against the answer key, and a miss is detected.
It does **not** show that a reviewer detects review-class seeds (stated limitation;
`eqos-4j2.30`). The shadow version cannot be approved.
**Out of scope:**
- Panel (model reviewer) telemetry or panel claim naming (`ledger/panel.py` untouched; `eqos-tqf`).
- A review UI with source jump, calculation inspection or diff display (register C-05).
- A human-reviewed drill, an automated "independent reviewer", and false-accept rates measured
  on a person (open question 1; `eqos-4j2.30`).
- The optional external spot-review procedure of B-13 (stated limitation).
- A materiality policy (open question 3).
- The Phase 1 economics gate and baselines (C-12); percentiles of any kind.
- A `ledger submit` CLI (`eqos-4j2.21`, unchanged).
- Register B-04/B-13 Status edits: the register is hash-pinned. Acceptance is recorded in the
  roadmap row and in this plan, as PREP-4 and PREP-5 did.
**Constraints:**
- Every task leaves `uv run pytest tests/fundamentals`, `uv run mypy --strict src`,
  `uv run ruff check src tests/fundamentals` and `uv run ruff format --check src tests/fundamentals`
  green. PostgreSQL tests run only on `eqos_test_*` databases (markers `pg` and `retained`; retained
  originals are read only). The drill writes only to its test database and `tmp_path`.
- Migrations 0001–0039 are immutable. One new migration: `0040`.
- Ledger rows are append-only. Recorded times and deciders are set by triggers. Status is
  derived from the decision log.
- Never open `stage4_holdout.yaml`, `stage4_manifest.yaml`, `data/holdout/`,
  `data/raw/onboarding/` or `data/raw/screen-exports/` bodies. Never touch `.env`, `~/.secrets` or
  the `equity_os` database.
- Owner, 2026-10-14: build the smallest thing that meets the acceptance, with no speculative seams.

## Findings that shape the design (verified in code)

1. **The instrument reviews a JSON file, not the ledger.** `review start --report-json`
   (`api/review_cli.py:40`) hashes an `EarningsUpdate` JSON and enumerates its claims from the
   artifact with `enumerate_claims` (`output/review_session.py:190`), using its own ids
   (`fact:<name>`, `calc:<slug>`). These ids are not ledger `claim_key`s. The session is
   `session.json` in a directory the reviewer picks (`save_session`, :298), and nothing goes to
   PostgreSQL. The pipeline plan records the instrument as built with "no sessions yet"
   (`docs/workstreams/fundamentals-pilot/phase-0.5-assisted-updates-plan.md:34`). No row of the
   source-of-truth matrix covers review telemetry (`docs/blueprint/source-of-truth-matrix.md:26–40`).
2. **What it already measures.** It records four dispositions and seven correction categories
   (`review_session.py:30`, :39), stored as lowercase enum values (`accepted`, `none`, …). A
   validator requires category `none` for an accepted claim and a correction category for an
   edited or rejected one; a deferred claim takes either (:81). The session model carries no
   instrument version (:106). Per-claim time is
   `--seconds`, which is optional and typed by the reviewer (`review_cli.py:51`;
   `seconds: int | None`, `review_session.py:77`). Report time is one session's finish minus
   start (:289). The overhead timer (`_with_elapsed`, `review_cli.py:62`) runs from dispatch entry
   (:130) to just before the session file is saved. So it excludes process startup and the save,
   and a refused command adds nothing (:139). The summary is totals only, with no distribution statistics (:124). Finish
   requires every claim to be reviewed (:269). Re-dispositions keep the replaced entry (`superseded`,
   :258). Source-locate and calculation-check times are **not** recorded, and B-04 requires them.
3. **The approval decision is the ledger's.** `APPROVE`, `REQUEST_CHANGES` and `REJECT` need head
   `SUBMIT` and the panel or owner role (`lifecycle.py:69`). The decider is set from
   `current_user` (0014 `decider_role`). `APPROVE` binds a passing `approval_check` made in the
   same transaction: every claim `MATCH`/`MATCH_UNTRUSTED` and no version state (`passes`, :228;
   `append_decision`, :357). `ledger decide` runs as the owner login and reads the ruling verbatim
   from stdin (`api/ledger_cli.py:164`, :168). `decide` (:323) opens its own transaction, while
   `approval_check` (:207) and `append_decision` are cursor-level. `submit` refuses a version
   whose predecessor is still open (:160), and 0012's `report_versions_one_root` allows one root
   per report. The ledger CLI's exception boundary is `ledger_cli.py:149`
   (`DatabaseUnavailableError`, `psycopg.Error`, `RoleSecretError`, `ValidationError`, `OSError`,
   `ValueError`, `LookupError`); today's review CLI catches fewer (`review_cli.py:139`), and
   `store.read_version` raises `LookupError` for an unknown id (`store.py:132`).
4. **Rejected claims already exist on the decision.** `decisions.rejected_claims` (0039) is set
   only on `REQUEST_CHANGES` of a `REPORT_VERSION`, is non-empty, has distinct keys and holds only
   claim keys of that version. PREP-5's rework treats each key as defective input
   (`rework.rejected`, `rework.plan`, `ledger/rework.py:203`). `REJECT` cannot carry keys.
5. **A rework successor's unchanged claims are byte-identical.** PREP-5 carries an unaffected
   claim's row whole, citation included, and keeps its line text. Its gate refuses any carried
   line or section scaffold that moved (`Gate.line`/`close`, `rework.py:80–119`). Additions,
   replacements and presentation changes can occur only on rerun lines. A `--full-successor`
   re-derives everything, but its content-hashed records make an unchanged claim equal again.
   A `--full-successor` can still delete a claim's line, reorder lines or move a claim across an
   explanatory line, and no claim-level diff sees that. A version's narrative is its section
   bodies rendered in ordinal order (`display.narrative`, `display.py:94`). `rework.plan` skips
   ordinal 0 as run metadata (`rework.py:235`), but ordinal 0 is not always metadata: the
   run-draft heading is ordinal 0 with key `run_draft.HEADING` and no claim placeholder
   (`run_draft.py:563`), while `ledger_support.SECTION` (`ledger_support.py:87`) and imported
   sections put claims at ordinal 0.
6. **What the deterministic check catches.** `check_claim` (`ledger/claim_check.py:72`) returns,
   in order: `UNRESOLVED`, `POST_CUTOFF`, `UNIT_MISMATCH` (value kind/unit/currency/scale),
   `KEY_MISMATCH` (claim measurement key ≠ cited record's), `VALUE_MISMATCH` (rounded value ≠
   cited value), `QUOTE_NOT_FOUND`, `QUOTE_MEANING_MISMATCH` (bounds and qualifiers against the
   quote), `MATCH_UNTRUSTED`, `MATCH`. `scan_section` (`ledger/numeral_scan.py:43`) raises
   `UNREGISTERED_NUMBER` for a bare numeral, and `submit` refuses it (`lifecycle.py:152`). Nothing
   checks that a line's label matches the claim on it, that a claim's `epistemic_class` is right,
   or that a consistently cited prior is the right comparator. Only a reviewer catches those.
7. **An unapproved version is not a *valid-version* memory support, but other routes exist.**
   `memory_version_valid` (0017:43) requires an `APPROVE`/`IMPORTED_APPROVAL` head, so a version
   whose approval is refused cannot support a claim- or version-backed `COMPANY_UNDERSTANDING`,
   `MANAGEMENT_TRACK_RECORD` or `THESIS_AND_WARNING` item (0017:79, :85). It can still back a
   `LESSON` as a `REJECT`ed version (:82), a `LESSON` may cite any decision (:96), and an
   `OWNER_RULING` any owner decision with a ruling (:97). So a refused approval alone does not
   isolate a shadow; the disposable test database does (decision 7).
8. **There is no materiality notion in the ledger.** `src/fundamentals/ledger` and
   `contracts/ledger.py` have no materiality field or policy. Invariant 7 treats every numeric
   claim as needing a citation. S07 (`docs/specs/equity-os-s07-…`) and S18 define richer telemetry
   (`ReviewDecisionTelemetry`, `SeededDrillIsolationRecord`) but are **DRAFT, awaiting review**,
   so they are inputs and not adopted contracts.
9. **Ledger test rigs exist.** `prep2b_support.Pilot` builds and approves the FY26_Q2 run draft
   on a test database. PREP-5's tests use it for submit, `REQUEST_CHANGES` with claims, and a
   rework run (`tests/fundamentals/test_prep5_rework.py`). `ledger_support.Ledger` has the
   role-pool helpers. The backup lists tables dynamically (`pg/backup.py:78`), and
   `pg/restore_check.table_rows` (:80) takes its table list as an argument;
   `test_pg_migrations.py` names no ledger table. The explicit list that 0040 breaks is the ACL
   matrix test (`test_ledger_integrity.py:565`): it discovers every `eqos` table, and a table
   outside `GATED` is expected to be runtime-insertable. `LEDGER_TABLES`
   (`ledger_support.py:46`) feeds the runtime and panel inserter sets, so the new tables must
   not join it.
10. **Only tests consume the JSON instrument besides its CLI.** `test_phase05_review_session.py`
    (12 tests) uses it, and `test_guidance_review_identity.py` imports `enumerate_claims` and the
    former's `_synthetic_update` (:9, :17). No `src` module imports `output/review_session.py`
    except `api/review_cli.py`.

## Decisions

1. **Retarget `fundamentals review` to ledger versions; delete the JSON path** (open question 2).
   `review start --version <id>` replaces `--report-json`. A claim is a `numeric_claims.claim_key`
   of that version. `output/review_session.py` moves into `ledger/review.py`, minus
   `enumerate_claims` and `EarningsUpdate`. Its four dispositions, seven categories, the
   category validator, atomic `save`/`load` and totals-only summary stay. Keeping both would leave
   two telemetry stores, one of them off the ledger. Rejected: a second, ledger-only command
   beside the JSON one.
2. **The reviewer works in a session file; the record is written once, at finish, with the
   decision.** `start`, `claim` and `list` keep today's working file (`session.json`: version id,
   `instrument_version` captured at `start`, start time, ordered claim events, command-handling
   seconds), with no database write. `claim`, `list` and `finish` refuse a session file whose
   `instrument_version` is not the running `INSTRUMENT_VERSION`; `finish` stores it.
   `finish --decision APPROVE|REQUEST_CHANGES|REJECT`, with the ruling on stdin as in `ledger decide`,
   writes in **one owner transaction**: the decision (`append_decision`, preceded by
   `approval_check` for `APPROVE`), then one `review_sessions` row and every claim event as
   `claim_reviews` rows. So telemetry exists only with its decision, and a refused decision
   writes no telemetry. An abandoned session leaves only a file, never a record. `--decider` goes
   (the trigger sets the decider). Rejected: writing each claim to PostgreSQL as it is recorded.
   That needs a third table, or mutable session state, to mark the finish.
3. **Schema 0040: two append-only tables, owner-written.**
   `review_sessions(id, version_id → report_versions, decision_id UNIQUE NOT NULL → decisions,
   instrument_version, started_at, finished_at CHECK ≥ started_at, command_handling_ms ≥ 0,
   recorded_at)` and
   `claim_reviews(id, session_id → review_sessions, ordinal ≥ 0, UNIQUE(session_id, ordinal),
   claim_key, disposition, category, elapsed_ms ≥ 0, locate_seconds ≥ 0, check_seconds ≥ 0,
   note)`. `disposition` and `category` store the enums' lowercase values, each with an `IN`
   CHECK, and the category rule is
   `CHECK (disposition = 'deferred' OR (disposition = 'accepted') = (category = 'none'))`:
   accepted requires `none`, edited and rejected require a correction category, deferred takes
   either (the validator's rule, finding 2). Triggers do three things:
   - `recorded_at := store_now()`.
   - A BEFORE INSERT check refuses (23514) a session whose decision is not an owner review
     decision on its version (`subject_kind = 'REPORT_VERSION'`, `subject_id = version_id`,
     `decider = 'OWNER'`, `kind IN ('APPROVE', 'REQUEST_CHANGES', 'REJECT')`), and a claim review
     whose key is not a claim of its session's version.
   - `reject_mutation` and `refuse_after_promote` on both tables, as for every ledger table.
     `refuse_after_promote` is the 0018 rule.

   Only `eqos_owner` gets INSERT (with sequence usage). The runtime, panel, owner and purge roles
   get SELECT. `decision_id` UNIQUE makes one session per decision, and so at most one session
   per version that reaches a terminal decision. The decider check makes the reviewer the
   owner. Client times (`started_at`, `finished_at`) are measurement fields, distinct from
   `recorded_at`.
4. **Per-claim time is derived; locate and check times are entered and bounded** (open question 4).
   `elapsed_ms` for event *i* is its client time minus the previous event's time, or the
   session start for the first event. A clock moving backwards is refused at `review claim`, and
   `finish` refuses a finish time earlier than the last event's. The
   reviewer gives `--locate-seconds` and `--check-seconds`, both required and ≥ 0, and their sum
   must not exceed the derived elapsed time. `--seconds` goes. Two wall-clock session durations
   are reported. The **session** duration is `finished_at − started_at` of the version's own
   session. The **report** duration is the sum of the session durations of every version on the
   chain from the root to the requested version that has a session (0012: one linear chain). So
   a report reviewed 30 minutes at N and 5 at N+1 reports 35 at N+1. The CLI reads time through
   one `review_cli._now()`, read at command entry (the event or finish time) and again just before
   the session file is saved (at `finish`, before the first insert). **Command-handling time** is
   the sum of those intervals over the session's successful commands, as today's timer measures
   it (finding 2), and it is labelled for what it is. It excludes process startup, the session
   file save, `finish`'s database writes and commit, refused commands, and the reviewer's time
   between commands. Every event
   is stored, re-dispositions included, and the current disposition of a key is its last event.
   Code answers what code can (guideline 5); B-04's locate and check split cannot be observed by a
   CLI without a source-jump UI (C-05).
5. **Rejected disposition = `decisions.rejected_claims`; edits count as rejections for rework.**
   At finish, with the review set's current dispositions:
   - `APPROVE` requires every review-set key `ACCEPTED`; otherwise it is refused before any write.
   - `REQUEST_CHANGES` writes `rejected_claims` = the keys currently `EDITED` or `REJECTED`
     (NULL when there are none, which means a full rerun, as today).
   - `REJECT` writes no keys (0039 CHECK), whatever the dispositions: `finish` passes
     `claims` to `record_decision` only for `REQUEST_CHANGES`, and `()` otherwise.
   - `DEFERRED` is allowed only with `REQUEST_CHANGES` or `REJECT`.

   A sealed version cannot be edited, so an edit is a requested correction that PREP-5 must
   rework, just like a rejection. The dispositions still distinguish them for B-04's counts.
   Agreement between the stored dispositions and `rejected_claims` is enforced by the one writer
   in the one transaction and by a test, not by a deferred trigger (limitation).
6. **Review set: every changed claim; the whole version when any section body differs**
   (PREP-5 OQ3; open question 5 ruling). Take version V with predecessor P. V is reviewed
   **whole** unless all of these hold:
   - P has a `review_sessions` row;
   - V's sections equal P's as a sequence of whole `(section_key, body)` pairs in ordinal order,
     each skipping only the **metadata heading**: the ordinal-0 section whose key is
     `run_draft.HEADING` and whose body shows no claim placeholder (`display.PLACEHOLDER`). The
     heading must be skipped because it names the pinned prior and so differs on every
     successor. Any other ordinal-0 section is compared. A deleted, added or changed line, a
     claim moved across an explanatory line, a reordered line or section, or changed ordinal-0
     content all differ.

   When they hold, the review set is V's keys minus the *unchanged-accepted* keys: those whose
   current disposition in P's session is `ACCEPTED` and whose claim in V equals P's as a whole
   model (value, unit, measurement key, epistemic class, citation ids). So every changed claim,
   and every claim not accepted in P, is reviewed. One rule covers additions, replacements,
   deletions, reorders, presentation changes, a claim deferred in P and a `--full-successor`
   alike. It reads rows only and needs no evidence repository. `start`, `claim`, `list` and
   `finish` all compute the set from the database. A key outside it is refused, and `finish`
   requires every key in it.
7. **Seeded-error drill = one test-resident e2e on a synthetic shadow version** (open question 1).
   The drill runs in its own `eqos_test_*` database, dropped afterwards. It builds the Pilot
   FY26_Q2 run draft C (clean, approvable), then writes **shadow S**, a copy of C's
   `VersionDraft` with seeded mutations and a recomputed `content_hash`, as the first version of a
   separate report (`period = "FY26_Q2_DRILL"`). It submits S with `lifecycle.submit`. The bare
   number shadow S′ is the first version of a report of its own (`period = "FY26_Q2_DRILL_G5"`),
   because a report has one root (0012) and a successor of an open S is refused (`lifecycle.py:160`).
   Seeds:

   | Seed | Mutation (keys named in the test) | Class / epistemic | Caught by |
   |---|---|---|---|
   | G1 value | a `fact.*` FIGURE value + 1 in its scale | gate / observed | check `VALUE_MISMATCH` |
   | G2 period | a `cmp.*.prior` measurement key moved to another quarter, citation kept | gate / observed | check `KEY_MISMATCH` |
   | G3 calculation | a `calc.*` CALCULATION value off by one rounding unit | gate / computed | check `VALUE_MISMATCH` |
   | G4 guidance | a guidance claim's upper bound changed | gate / forecast | check `QUOTE_MEANING_MISMATCH` |
   | G5 bare number | a numeral typed into a results line (a second shadow, S′) | gate / — | `submit` refuses `UNREGISTERED_NUMBER` |
   | R1 swapped lines | the placeholders of two results lines exchanged | review / observed | reviewer |
   | R2 wrong comparator | the revenue QoQ prior replaced by the YoY prior's value, key and citation | review / observed | reviewer |
   | R3 wrong class | a guidance claim relabelled `observed` | review / forecast | reviewer |

   Each review seed passes every deterministic check: the label is not checked, the comparator
   is cited consistently, and the epistemic class is not compared (finding 6). The answer key
   expects every seed key (both R1 claims) to be not `ACCEPTED`, and every other key `ACCEPTED`.
   The drill is an **instrumentation regression**, not a detection test: the scripted reviewer
   is given the answer key, so (d) proves recording, scoring and the decision path, not that
   anyone catches a review seed (open question 1, limitation, `eqos-4j2.30`).
   A test-resident `_score(answer, dispositions)` derives the outcome of each claim:
   - `CAUGHT`: seeded, `EDITED`/`REJECTED`;
   - `MISSED`: seeded, `ACCEPTED`/`DEFERRED`;
   - `FALSE_REJECT`: clean, `EDITED`/`REJECTED`;
   - `CORRECT`: clean, `ACCEPTED`;
   - `FALSE_DEFER`: clean, `DEFERRED`.

   It also counts outcomes per epistemic class.
   **Pass condition (all must hold):**
   - (a) The validation of S gives each gate-seed key its expected state above. Every other key,
     the review seeds included, is `MATCH`.
   - (b) The owner's `APPROVE` of S is refused, so S is never `APPROVED` and is never a
     valid-version memory support (finding 7). The refusal comes from the check, not from a
     label.
   - (c) `submit(S′)` is refused naming `UNREGISTERED_NUMBER`.
   - (d) The scripted review of S through the CLI records a disposition and time for every key,
     scores every seed `CAUGHT` and makes no false reject or defer. Its `REQUEST_CHANGES` decision's `rejected_claims` equals the seed keys, and the
     per-class counts are the ones the test names.
   - (e) A second parametrization, in which the script accepts R1, is scored `MISSED` on both R1
     keys and the drill verdict is FAIL naming them. This proves the drill can fail.

   The answer key and score live in the test, since no `src` consumer exists. **The isolation
   boundary is the disposable test database.** Gate seeds (b) keep S unapproved, but a `LESSON`
   or `OWNER_RULING` could still cite S or its decisions (finding 7), and no guard is added on
   those routes. The test asserts that S has at least one gate seed.
8. **Summary for PILOT-12.** `review summary --version <id>` (runtime role) prints the B-04
   totals from the rows as JSON:
   - version, instrument version, decision kind;
   - claim count and review-set count;
   - disposition and category counts;
   - `session_wall_clock_minutes` and `report_wall_clock_minutes` (decision 4);
   - summed elapsed seconds, and summed locate and check seconds under keys marked
     self-reported (`locate_seconds_self_reported`, `check_seconds_self_reported`);
   - `command_handling_seconds` (decision 4's interval, not total overhead).

   It prints no percentiles. This replaces `summary.json` and `approval_record.md`, because the
   decision row is the approval record.

## Assumptions

- **A1** PILOT-12's reviewed artifacts are submitted run-draft versions (PQ0's FY26_Q2 run draft
  as the manual-baseline review, PQ1–PQ3's as assisted reviews), reviewed by the owner role. If
  PQ0's baseline is meant to be the imported bootstrap thesis instead (status `HISTORICAL`, which
  cannot take `APPROVE`/`REQUEST_CHANGES`), it is outside this instrument. Decision 2 then needs a
  decision-less finish, which is a local change to `finish` and makes `decision_id` nullable.
- **A2** The owner's `ledger decide` login is the review's finish login. The owner reviews in one
  terminal across several commands, so client time is consistent within a session.
- **A3** Every review seed passes the check (finding 6). If a DB CHECK or the check refuses one
  (R3 is the likeliest), that seed is a gate seed: reclassify it in the table and keep at least two
  review seeds.

## Open questions (orchestrator rules; none is the owner's financial judgment)

1. **Does PILOT-11's "drill caught" need a human reviewer?** Recommendation: **no** for PREP-6.
   The drill proves that gate seeds are caught mechanically, that review seeds are recorded and
   scored, that a miss is detected, and that the shadow cannot be approved. It does not prove
   that review seeds are detected: the scripted reviewer holds the answer key. Whether a person catches
   review seeds is a B-13 *measurement* that needs owner time beyond PILOT-12. It needs a shadow
   on a real ledger with label-independent isolation (an S07 `SeededDrillIsolationRecord`), and it
   belongs with C-05. Tracked as `eqos-4j2.30` (owner blind run).
2. **Delete the JSON instrument** (decision 1)? Recommendation: **yes**. It has never recorded a
   session (finding 1), and keeping it leaves a second, off-ledger telemetry path. Cost: delete
   `output/review_session.py` and `test_phase05_review_session.py`. Rewrite the
   `enumerate_claims` assertions in `test_guidance_review_identity.py` against
   `RenderedGuidance.metric` directly. `RenderedGuidance.metric` itself stays, since the pipeline
   writes it.
3. **Materiality stratum.** No materiality policy exists (finding 8). Recommendation: treat
   every numeric claim as material for PREP-6 (invariant 7's reading), stratify the drill by
   epistemic class only, and record the B-13 clause as partially met. A materiality policy is an
   owner/register item, not PREP-6 code.
4. **Locate/check times required on every claim** (decision 4)? Recommendation: **required**,
   with 0 allowed. A default of 0 would record an unobserved number as observed (invariant 10).
5. **Diff-only re-review of a `--full-successor`** (decision 6), against PREP-5 OQ3's "reviewed
   whole"? r0 recommended diff-only on claim rows, line membership and scaffolds. Sol r1
   rejected it as specified: a deleted claim line or a reorder left the set empty.

**Rulings.** r0 orchestrator (2026-10-19): 1–4 as recommended; 5 diff-only, provisionally.
Sol r1: OQ1 automated review acceptable in principle, but the answer-key script counts only as
an instrumentation regression; OQ2 approved (retire the JSON instrument); OQ3 accepted (partial
B-13); OQ4 approved; OQ5 diff-only rejected as specified, acceptable once deletions and order
changes are covered. Orchestrator r1 (2026-10-19), binding:
- OQ1: keep the scripted drill as an instrumentation regression and build no automated
  "independent reviewer". PREP-6's drill acceptance is: gate seeds caught mechanically;
  per-claim disposition and time recorded and scored; a miss detected. Detection of review-only
  seeds is **not demonstrated**; `eqos-4j2.30` tracks it as an owner blind run. The roadmap
  row's wording is changed by Task 4, not here.
- OQ5: one uniform rule (decision 6). The review set is every changed claim; if any section's
  ordered claim-line sequence (or scaffold) differs from the predecessor's, a predecessor line
  missing included, the whole version is reviewed. This covers `--full-successor`. Deletion and
  reorder are tested. Closing r1 (orchestrator, 2026-10-19) tightened it: whole section bodies
  in section order, with only the metadata heading exempt (decision 6).
- Finding 6: the disposable database is the isolation boundary; no guards on memory-support
  routes.

## Stated limitations

- **Locate and check times are self-reported** (decision 4), bounded by the derived elapsed
  time. Per-claim elapsed time attributes the time between commands to the next recorded claim,
  so a reviewer who records claims in a batch distorts it. `list` and the instructions say so.
- **Durations are wall-clock session time** (decision 4). Session and report durations include
  idle time between commands. A version with no session adds nothing to the report duration.
- **Overhead is measured only as command-handling time** (decision 4). It excludes process
  startup, the session file save, `finish`'s database writes and commit, and refused commands.
  So B-13's "overhead measured" is partial.
- **Detection of review-only seeds is not demonstrated** (open question 1). The drill's
  scripted reviewer is given the answer key, so R1–R3 being `CAUGHT` proves recording, scoring
  and the decision path, not that the owner, or anyone, catches a review-class error. No
  false-accept rate is measured on a person. Tracked as `eqos-4j2.30` (owner blind run).
- **Shadow isolation is the disposable test database** (finding 7, decision 7). A refused
  approval keeps S out of valid-version memory supports only; `LESSON` and `OWNER_RULING`
  routes are not closed for a shadow, and none is guarded.
- **Any presentation change makes the whole successor reviewed** (decision 6). A correction
  that changes any section text other than the metadata heading costs a full review, even where
  only one claim changed. That covers a line text, an added, deleted or moved line, and a section
  order. That fails safe.
- **No materiality stratum** (open question 3). **No external spot-review procedure.** B-13 is
  optional for that clause, and S07 is draft. B-13 therefore stays partially met. The roadmap row
  will say which clauses are met.
- **Disposition and `rejected_claims` agreement** is enforced by the single writer, not by the
  database (decision 5). An owner writing raw SQL can break it, and the owner is the trusted role.
- **Panel reviews are not instrumented.** The symmetry claim covers the owner's review across
  PQ0–PQ3: one instrument, one `instrument_version`.
- **Submission stays Python-only** (`eqos-4j2.21`). An operator running PILOT-12 calls
  `lifecycle.submit` before `review start`.

## How each requirement is met

| Requirement | Met by | Evidence |
|---|---|---|
| Roadmap: per-claim disposition and time recorded | `claim_reviews` rows (disposition, category, `elapsed_ms`, locate, check), written with the decision | Task 2 e2e |
| Roadmap / PILOT-11: drill errors caught, as ruled (r1) | gate seeds caught mechanically (a)–(c); per-claim disposition and time recorded and scored (d); a miss detected (e). Review-seed detection **not demonstrated** (`eqos-4j2.30`) | Task 3; **partial** |
| B-04 report total review time | `report_wall_clock_minutes`: summed session durations along the version chain; `session_wall_clock_minutes` per version (decision 4) | Task 2 (exact 30 + 5 = 35) |
| B-04 claim count | claim count and review-set count | Task 2 |
| B-04 per-claim disposition and time | decisions 2, 4 | Task 2 (exact `elapsed_ms` on a controlled clock) |
| B-04 source-locate and calculation-check time | required `--locate-seconds`/`--check-seconds`, summed under self-reported keys | Task 2 (bound refusal unit test, summary keys) |
| B-04 accepted/edited/rejected/deferred counts; correction categories | summary counts; category validator kept and mirrored by the 0040 CHECK | Task 1 (SQL boundaries), Task 2 |
| B-04 no report-level P90 at n=3 | summary is totals only | Task 2 asserts no percentile field |
| B-13 Quarter 0 not reused for assisted work | Pilot design: PQ0 is its own report and period, and a session binds one decision of one version (`decision_id` UNIQUE) | Task 1 (unique), procedure |
| B-13 symmetric instrumentation, overhead measured | one instrument; `instrument_version` captured at `start`, checked at `claim`/`list`/`finish`, stored on the session. Overhead: `command_handling_ms` only, which excludes startup, save, commit and refused commands | Task 2 (version refusal, exact e2e); overhead **partial** |
| B-13 shadow-mode drills cannot be promoted | the disposable test database is the isolation boundary; gate seeds make `APPROVE` refuse, so the shadow is never a valid-version memory support | Task 3 (b), isolation |
| B-13 false-accept/false-reject stratified by materiality and epistemic class | drill scoring per epistemic class; materiality: open question 3 | Task 3 (d); **partial** |
| B-13 optional external spot review defined | not built | limitation; **not met** |
| PREP-5 OQ3: review set covers additions, replacements, deletions, reorders, presentation | decision 6 | Task 2 `unchanged` unit cases (deletion, reorder, claim moved across a line, section reorder, ordinal-0 content), re-review and correction e2e |

## File map

| File | Change | Task |
|---|---|---|
| `migrations/0040_review_telemetry.sql` | create: two tables, checks, stamp, mutation/promote triggers, grants | 1 |
| `src/fundamentals/ledger/lifecycle.py` | factor `decide`'s body into cursor-level `record_decision(cursor, …)`; `decide` calls it | 1 |
| `src/fundamentals/ledger/review.py` | create: models and enums (moved), session file, `review_set`, `record`, `finish`, `summary` | 2 |
| `src/fundamentals/api/review_cli.py` | rewrite: `start --version`, `claim`, `list`, `finish --decision`, `summary`; one `_now()` clock | 2 |
| `src/fundamentals/api/ledger_cli.py` | `_sources` → public `decision_sources` (reused by `review finish`) | 2 |
| `src/fundamentals/output/review_session.py` | delete | 2 |
| `tests/fundamentals/test_phase05_review_session.py` | delete | 2 |
| `tests/fundamentals/test_guidance_review_identity.py` | drop `enumerate_claims` / `_synthetic_update` use; keep metric-field tests | 2 |
| `tests/fundamentals/test_ledger_integrity.py` | ACL matrix: the two tables join `GATED` and the owner's inserters only (owner-only INSERT and sequence usage) | 1 |
| `tests/fundamentals/test_prep6_review.py` | create | 1–3 |
| `docs/blueprint/source-of-truth-matrix.md`, `docs/backend-roadmap.md`, this plan | record | 4 |

## Size (estimates, not measured)

| Task | src Δ | tests Δ | docs Δ |
|---|---|---|---|
| 1 Schema 0040 and cursor-level decision | +60 (SQL ~50) | +110 (incl. ACL matrix ±5) | — |
| 2 Ledger-bound review instrument | +220 new, −339 deleted, CLI ≈ +5 | +370, −(12 tests) | — |
| 3 Seeded-error drill | — | +150 | — |
| 4 Record the realisation | — | — | ±30 |

Rows include every round. Net: about +285 src (50 of it SQL) against −339 deleted, and about
+630 test lines. Plan r1 added about +20 src and +110 tests. Closing r1 adds about +5 src net:
the whole-body comparison replaces the `claim_lines` extraction, and the chain-duration query,
the `_now()` clock and the `REQUEST_CHANGES`-only keys are added. It also adds about +50 tests:
three presentation mutations, the `REJECT` case, exact timings and 30 + 5. Implementer:
Opus for Tasks 1–3 (one worker, sequential, same test file), Sonnet for Task 4.

### Task 1: The ledger stores review telemetry only alongside its owner decision

Goal: migration 0040 and a cursor-level decision writer. An owner transaction can insert a
decision, its `review_sessions` row and its `claim_reviews`. Every other shape is refused by
the database.

Files:
- Create: `migrations/0040_review_telemetry.sql`
- Modify: `src/fundamentals/ledger/lifecycle.py`; `tests/fundamentals/test_ledger_integrity.py`
  (ACL matrix: `REVIEW_TABLES = {"review_sessions", "claim_reviews"}` joins `GATED` and
  `INSERTERS[OWNER_ROLE]` only, so the matrix expects owner-only INSERT and owner-only
  `*_id_seq` USAGE; not `LEDGER_TABLES`, which would grant runtime and panel)
- Test: `tests/fundamentals/test_prep6_review.py`

Interfaces:
- Consumes: `eqos.store_now`, `eqos.reject_mutation`, `eqos.refuse_after_promote`, the 0035 grant
  loop pattern; `approval_check`, `append_decision`.
- Produces: tables `eqos.review_sessions`, `eqos.claim_reviews` (decision 3);
  `lifecycle.record_decision(cursor, *, subject_kind, subject_id, kind, ruling, policy=None,
  catalog=None, snapshots=None, claims=()) -> DecisionRecord` (today's `decide` body);
  `decide` becomes the pool wrapper.

Approach: the SQL follows 0039's style. A single `check_review_telemetry()` BEFORE INSERT
trigger branches on `TG_TABLE_NAME`. For a session row it checks that the decision has
`subject_kind = 'REPORT_VERSION' AND subject_id = NEW.version_id AND decider = 'OWNER' AND kind
IN ('APPROVE', 'REQUEST_CHANGES', 'REJECT')`. For a claim review it checks that a
`numeric_claims` row `(version_id = session's version, claim_key = NEW.claim_key)` exists.
Either failure raises 23514. The trigger also stamps `recorded_at` on sessions. The category
rule is decision 3's CHECK on the lowercase values. `test_pg_migrations.py` and
`pg/restore_check.py` list no tables (finding 9); the ACL matrix test is the one explicit list.

Verification: `uv run pytest tests/fundamentals/test_prep6_review.py -m pg -k telemetry_schema`,
then, with no marker filter, `uv run pytest tests/fundamentals/test_ledger_integrity.py
tests/fundamentals/test_pg_migrations.py tests/fundamentals/test_ledger_lifecycle.py
tests/fundamentals/test_prep5_rework.py` (ACL matrix with 0040; decide refactor unchanged).

Tests (on the `Ledger` rig; happy path in Task 2):
- One parametrized refusal test; each case is refused with nothing written:
  - a claim review naming a key of another version (23514);
  - a session whose decision is on another version (23514);
  - a session on the version's `SUBMIT` decision, and on a panel `REQUEST_CHANGES` (23514);
  - an INSERT as the runtime or panel role (ACL);
  - an UPDATE as the migrator (`reject_mutation`).

  Why: telemetry must describe the owner's review decision on the version it decided.
  Asserting the SQLSTATE keeps an ACL error from passing for a missing trigger.
- Category rule through SQL, parametrized (why: the stored rule must equal the validator's, or
  SQL and Python disagree on what a review may say). Refused (23514): `accepted`/`wrong_value`,
  `edited`/`none`, `rejected`/`none`, and the uppercase `ACCEPTED`/`NONE`. Accepted:
  `accepted`/`none`, `edited`/`wording`, `deferred`/`none`, `deferred`/`wrong_value`.
- The ACL matrix test (`test_ledger_integrity.py`) passes with the two tables owner-only.

Dependencies: none.
Risk: low.

### Task 2: `fundamentals review` reviews a ledger version and finishes with its decision

Goal: `review start --version V --session D` on an `IN_REVIEW` version computes V's review set
(decision 6). `review claim --session D --claim K --disposition … --category …
--locate-seconds N --check-seconds M [--note …]` refuses a key outside the set or times
over the bound. `review list` prints each review-set key with its current disposition.
`review finish --session D --decision KIND [--stock … --snapshot-root …]`, with the ruling on
stdin, writes the decision, the session and every claim event in one owner transaction under
decision 5's rules. `review summary --version V` prints decision 8's JSON. The JSON path is gone.

Files:
- Create: `src/fundamentals/ledger/review.py`
- Modify: `src/fundamentals/api/review_cli.py`, `src/fundamentals/api/ledger_cli.py`
- Delete: `src/fundamentals/output/review_session.py`, `tests/fundamentals/test_phase05_review_session.py`
- Modify (tests): `tests/fundamentals/test_guidance_review_identity.py`
- Test: `tests/fundamentals/test_prep6_review.py`

Interfaces:
- Consumes: `record_decision`, `approval_check` (Task 1); `store.read_version`, `chain_head`,
  `version_status`; `display.PLACEHOLDER`; `run_draft.HEADING`; `decisions.rejected_claims`; `open_pool`, `load_login`,
  `PgRole.OWNER`/`RUNTIME`.
- Produces:
  - In `ledger/review.py`:
    - `Disposition`, `CorrectionCategory` (moved);
    - `ClaimEvent` (frozen: `claim_key`, `disposition`, `category`, `locate_seconds`,
      `check_seconds`, `note`, `at`);
    - `Session` (frozen: `version_id`, `instrument_version`, `started_at`, `events`,
      `command_handling_seconds`);
    - `unchanged(prior: VersionDraft, current: VersionDraft, accepted: frozenset[str]) ->
      frozenset[str]` (pure, decision 6; empty unless the ordered `(section_key, body)` pairs,
      metadata heading skipped, are equal);
    - `review_set(cursor, version_id) -> tuple[str, ...]` (in claim order);
    - `record(session, event, review_set) -> Session` (instrument version current, key in set,
      clock monotonic, locate + check ≤ elapsed);
    - `current(session) -> dict[str, ClaimEvent]`;
    - `finish(cursor, session, kind, ruling, *, at, catalog, snapshots) -> DecisionRecord`
      (`at` ≥ the last event's time);
    - `summary(cursor, version_id) -> ReviewSummary` (session and chain durations, decision 4);
    - `INSTRUMENT_VERSION`;
    - `save`/`load` (moved).
  - `ledger_cli.decision_sources(args)`; `review_cli._now()` (the CLI's one clock).

Approach: `review_set` reads V and P = `predecessor_id`. P's current dispositions are the last
`claim_reviews` row per key of P's session (one query). The set is V's keys minus
`unchanged(P, V, accepted)`, or all keys when there is no P or no session; `unchanged` returns
nothing unless P's and V's section bodies are equal in ordinal order, the metadata heading
skipped (decision 6). `finish` refuses a session
of another instrument version or a finish time before the last event, re-derives the set and
refuses a key left unreviewed, then applies decision 5. It calls `record_decision(…, claims=edited_or_rejected if kind is
REQUEST_CHANGES else ())` and inserts the session row (`decision_id`, client times,
`command_handling_ms`) and the events in order, each with `ordinal` and `elapsed_ms`. Refusals
raise `ValueError`/`DecisionRefusedError` before the first insert; database refusals roll the
whole transaction back. The CLI keeps today's dispatch and exit code 2, and catches the ledger
CLI's exception set (`ledger_cli.py:149`: `DatabaseUnavailableError`, `psycopg.Error`,
`RoleSecretError`, `ValidationError`, `OSError`, `ValueError`, `LookupError`) plus today's
`SystemExit`. `start`/`claim`/`list`/`summary` use the runtime pool; `finish` uses the owner
login, as `ledger decide` does. `--locate-seconds`/`--check-seconds` are required (open question
4). `summary` sums `finished_at − started_at` over the sessions of the versions on V's
`predecessor_id` chain, V included (one recursive query).

Verification: `uv run pytest tests/fundamentals/test_prep6_review.py -k
"review or rereview or correction or rollback or unchanged or timing or instrument or cli"`
(no marker filter), then `uv run pytest tests/fundamentals/test_guidance_review_identity.py
tests/fundamentals/test_prep5_rework.py`, then the full gate.

Tests:
- `unchanged` unit, parametrized (why: a claim wrongly treated as unchanged is approved unseen).
  The base case is a claim accepted and identical in P and V, which gives unchanged. Each
  variant below must remove it from the result:
  - a changed value;
  - a changed epistemic class;
  - a changed citation id;
  - the same claim on a changed line text;
  - a new key;
  - a changed explanatory (claim-free) line, which makes every key reviewed;
  - the claim's last disposition being `DEFERRED`;
  - `ACCEPTED` replaced by a later `EDITED`.

  And whole-version cases (Sol r1 1, closing r1 1), each asserting the result is empty, so
  every key of V is reviewed. Every claim and line text is identical unless stated:
  - P accepted A and rejected B, and V deletes B's line, keeping A's byte-identical;
  - V swaps two claim lines of one section;
  - V moves claim A's line to the other side of an explanatory line;
  - V swaps the order of two sections;
  - V changes the text of a claim-bearing ordinal-0 section (`ledger_support.SECTION`'s shape),
    and also when that section is keyed `run_draft.HEADING`.

  A control case: V changes only a claim-free run-draft heading, and the base claim stays
  unchanged. Why: the heading names the pinned prior and differs on every successor.
- Timing unit, parametrized: elapsed derived from consecutive events; a clock moving backwards is
  refused; locate + check over elapsed is refused; equal to elapsed is accepted; a finish time
  before the last event is refused; equal to it is accepted.
- Instrument version: a session file whose `instrument_version` differs from
  `INSTRUMENT_VERSION` is refused by `claim` and by `finish`, with nothing written. Why: one
  instrument across PQ0–PQ3 is B-13's symmetry claim.
- E2E telemetry (Pilot FY26_Q2, submitted), on a controlled clock: `review_cli._now` is
  monkeypatched to a scripted sequence of times, so the session spans exactly 30 minutes and
  every command has a known handling interval. `start`; dispositions through `main([...])` for
  every claim, with `fact.revenue` `REJECTED`/`WRONG_VALUE`, one guidance key `EDITED`/`WORDING`,
  one claim `DEFERRED` and the rest `ACCEPTED`, plus one re-disposition. Then `finish --decision
  REQUEST_CHANGES`. Assertions:
  - one decision whose `rejected_claims` = {`fact.revenue`, that guidance key};
  - one session row carrying `INSTRUMENT_VERSION`, the scripted `started_at`/`finished_at` and
    the exact `command_handling_ms`;
  - one `claim_reviews` row per event, re-disposition included, with the exact `elapsed_ms` the
    script implies (the re-disposition's measured from the event before it) and the entered
    locate/check seconds;
  - `review summary` gives exact values: disposition and category counts,
    `session_wall_clock_minutes` = `report_wall_clock_minutes` = 30, summed elapsed seconds,
    the locate/check sums under their self-reported keys and `command_handling_seconds`. It has
    no percentile key.

  Why: this is the roadmap acceptance, and it shows the rejected disposition drives PREP-5.
- E2E `REJECT` (closing r1 2): a fresh submitted FY26_Q2, with one key `EDITED` and one
  `REJECTED`, the rest `ACCEPTED`. `finish --decision REJECT` exits 0. The decision is `REJECT`,
  its `rejected_claims` is NULL, and the session and every event are stored. Why: forwarding the
  keys on `REJECT` fails 0039 (23514) and would lose the review.
- Refusals, each with no decision or telemetry row written:
  - `finish --decision APPROVE` with a non-accepted key;
  - `finish` with an unreviewed key;
  - `claim` with a key outside the review set;
  - `finish` as a version that is not `IN_REVIEW`.
- Rollback after the decision insert (Sol r1 10): on the submitted FY26_Q2 with every key
  `ACCEPTED`, `finish --decision APPROVE` (with sources) with the claim-review insert
  monkeypatched to name a claim key of another version, so the 0040 trigger raises 23514 after
  `record_decision` has inserted the validation and the decision. Assert exit 2, the version
  still `IN_REVIEW`, and unchanged counts of `decisions`, `validations`,
  `validation_claim_states`, `review_sessions` and `claim_reviews`. Why: decision 2's "telemetry
  exists only with its decision" holds in both directions only if one transaction holds both.
- CLI boundary (Sol r1 12), parametrized: `review start --version` an unknown id
  (`LookupError`) and `open_pool` monkeypatched to raise `DatabaseUnavailableError` each exit 2
  with a logged refusal, not a traceback.
- E2E re-review, no correction (Sol r1 7): continue from the telemetry e2e with PREP-5's rework
  run (no correction) to write N+1, then submit it. Its section bodies equal N's (heading aside), and its
  re-derived rows are N's, so `review_set(N+1)` is exactly the keys not `ACCEPTED` in N:
  {`fact.revenue`, the edited guidance key, the deferred key}. The revenue-dependent claims that
  were accepted in N and re-derived identically are not in it. Review those as `ACCEPTED`
  over a scripted 5-minute session; `finish --decision APPROVE` (with sources) passes the
  approval check. `review summary --version N+1` gives `session_wall_clock_minutes` = 5 and
  `report_wall_clock_minutes` = 35. Why: B-04's report time is the whole review of the report,
  not its last version's.
- E2E re-review, real correction: from a fresh submitted FY26_Q2, review with the revenue QoQ
  prior (`QOQ[0]`) `REJECTED`/`WRONG_VALUE` and every other key `ACCEPTED`, then `finish
  --decision REQUEST_CHANGES`. Rerun with PREP-5's corrected comparator filing (`_correct`,
  `ingest`, `QOQ` from `test_prep5_rework.py`), which changes the three QoQ values and leaves
  every line as N's. Assert `review_set(N+1) == set(QOQ)`. Why: Sol's PREP-5 OQ3 condition, that
  a successor is reviewed on everything that changed or was not accepted, shown with claims that
  actually changed.

Dependencies: 1.
Risk: medium. The likeliest misses are carried-claim equality (if a rework rebinds a carried
claim, `unchanged` misses it; that fails safe, because the claim is reviewed), a rework rerun
that does not reproduce a section body byte for byte (the whole successor is reviewed, which
fails safe; the no-correction re-review e2e shows it), the rollback
monkeypatch point and the guidance identity test rewrite.

### Task 3: A seeded-error drill on a shadow version: gate seeds caught, review seeds scored, a miss detected

Goal: decision 7's pass condition (a)–(e) holds on a test database. This is an
instrumentation regression; it does not demonstrate review-seed detection (`eqos-4j2.30`).

Files:
- Test: `tests/fundamentals/test_prep6_review.py`

Interfaces:
- Consumes: `Pilot` (FY26_Q2 draft), `store.read_version`, `store.create_report`,
  `store.create_version`, `display.content_hash`, `lifecycle.submit`/`validate`/`decide`, the
  `review` CLI (Task 2).
- Produces: test-only `_shadow(draft, seeds) -> VersionDraft`, `ANSWER`, `_score(answer,
  dispositions) -> dict[str, Outcome]` and `_verdict(outcomes) -> tuple[bool, list[str]]`.

Approach: the test builds C, then writes S as the root version of a new `FY26_Q2_DRILL` report
and S′ as the root of a separate `FY26_Q2_DRILL_G5` report (Sol r1 8), both as runtime, and
submits S. `_score`/`_verdict` are pure and live in the test
(decision 7). The scripted reviewer drives the real CLI: `start --version S`, one `claim` per
key from a parametrized script, then `finish --decision REQUEST_CHANGES`. The seeded keys are
named in the test, chosen from C's claims as PREP-5 did.

Verification: `uv run pytest tests/fundamentals/test_prep6_review.py -k drill` (no marker filter).

Tests (one test, parametrized over two scripts: `perfect` and `misses_r1`):
- (a) `lifecycle.validate(S)` gives the expected state per gate seed and `MATCH` for every other
  key. Why: the review seeds must be invisible to the checks, or the drill tests nothing the
  checks don't.
- (b) the owner's `APPROVE` of S (with sources) raises `DecisionRefusedError`, and S's status is
  not `APPROVED`. Also assert that S has at least one gate seed.
- (c) `submit(S′)` raises naming `UNREGISTERED_NUMBER`.
- (d) for `perfect`: every key has a recorded disposition, category and time, the verdict passes
  and `rejected_claims` = the seed keys. Counts are
  stratified by the answer key's true class, so R3 counts as forecast: CAUGHT observed 5 (G1, G2,
  both R1 keys, R2), computed 1 (G3), forecast 2 (G4, R3). There is no `MISSED`, `FALSE_REJECT`
  or `FALSE_DEFER` outcome.
- (e) for `misses_r1`: the verdict fails, naming both R1 keys as `MISSED`. Why: a drill that
  cannot fail proves nothing. `perfect` passing proves the scorer, not detection: its script
  holds the answer key.
- Isolation: the test touches only its disposable database and `tmp_path` (session dir), which
  are the isolation boundary (decision 7). No retained file is opened for writing.

Dependencies: 2.
Risk: medium. If assumption A3 fails for a review seed, reclassify it as described there.

### Task 4: Record the realisation

Files: `docs/blueprint/source-of-truth-matrix.md` (a "Review telemetry" row: authority
`review_sessions`/`claim_reviews` (0040); writer `review finish` · owner; the session file is a
working file, not a record), `docs/backend-roadmap.md` row PREP-6 (done, with the B-13 clauses
met, partial and not met, and the "drill errors caught" clause reworded to the r1 ruling: gate
seeds caught mechanically, per-claim disposition and time recorded and scored, a miss detected;
review-seed detection pending `eqos-4j2.30`), this plan (status, review tables, realisation).
Verification: the structural gate (doc links exist, `git status` shows only these files).
Dependencies: 1–3 and Sol's phase approval.
Risk: low.

## Interactions with open beads

- `eqos-4j2.8` (assisted updates Q1–Q3, owner reviewing each, seeded-error drill). PREP-6 supplies
  the instrument and the automated drill. The bead stays open: the reviews themselves are
  PILOT-12. Note on it that review-seed detection is deferred to `eqos-4j2.30` (open question 1).
- `eqos-4j2.30` (owner blind run of the seeded drill; named by the orchestrator's r1 ruling, not
  checked here with `bd`). It tracks what PREP-6's drill does
  not demonstrate: that review-class seeds are detected by a reviewer not given the answer key.
- `eqos-4j2.21` (no `ledger submit` CLI). Reviews need `IN_REVIEW` versions, so PILOT-12 operators
  submit through Python. That is unchanged and stated as a limitation.
- `eqos-tqf` (real panel reviewer adapter and CLI). No overlap: panel decisions carry no
  telemetry. If panel claim naming lands, it writes `rejected_claims` the same way.
- `eqos-7pr` (SQL-level `SUBMIT` skips the content-hash check). The drill submits through
  `lifecycle.submit`, so the shadow's recomputed `content_hash` is verified. Telemetry adds no
  SQL-level path.
- `eqos-z53` (admin credentials in the runtime `.env` allow owner escalation). Owner-only INSERT
  on the telemetry tables rests on the same role separation, so z53 weakens it equally.
- `eqos-3zl` (production cutover). Migration 0040 reaches `equity_os` with the cutover, and
  PILOT-12's real sessions need it.
- `eqos-4j2.23` (process clock vs store clock). Telemetry durations come from one client clock
  per session. `recorded_at` is the store clock. The two are never subtracted from each other.
- `eqos-0eu` (guidance contracts for new transcripts). PQ1–PQ3 guidance claims may fail the
  approval check. That affects PILOT-12's `APPROVE` and not PREP-6, whose tests use FY26_Q2,
  which approves today.
- `eqos-1kq`, `eqos-7fa`, `eqos-0bp`, `eqos-bhy`, `eqos-2c1` (flaky PG and clock tests). A
  verification run may hit them. Rerun once and report it; do not mask it.
- To file after PREP-6 (orchestrator): the materiality policy (B-13) and the external
  spot-review procedure (B-13, optional). The human drill is `eqos-4j2.30`.

## Not verified

- Whether any DB CHECK binds `epistemic_class` to a citation kind (assumption A3).
- The exact FY26_Q2 claim keys for the seeds. Tests name them from C, as PREP-5 did.
- Live database state. `tests/` and `data/` were not searched recursively.
- That a no-correction rework rerun reproduces every non-heading section body byte for byte.
  This is inferred from PREP-5's gate (carried lines and scaffolds) and from rerun lines being
  rendered from the same claims. The no-correction re-review e2e checks it; if it fails, the
  successor is reviewed whole (fails safe).
- That `test_prep5_rework.py`'s `_correct`, `ingest` and `QOQ` import cleanly into
  `test_prep6_review.py` (precedent: `test_guidance_review_identity.py` imports from another test
  module). If not, move them into `prep2b_support.py`.

## Self-review

- **Scope against acceptance.** Both roadmap clauses, every B-04 clause and PREP-5 OQ3 trace to a
  task and test. Two B-13 clauses (materiality, external spot review) are stated as not met
  rather than built speculatively. The stratification clause is partial by open question 3.
- **Size.** The net src change is negative (−339 deleted, about +285 added). There is one
  migration with two tables and no view. Scoring stays in the test because no product consumer
  exists. A session table, a per-claim live write path, materiality and a drill command were
  each considered and dropped.
- **Risky reads.** Decision 6 relies on PREP-5 carrying claim rows and lines whole. If that is
  wrong, the result fails safe (more claims, or the whole version, reviewed), not unsafe. Decision 5's edit-means-rework rule
  changes what an "edited" claim means compared with the JSON instrument, where the analyst
  edited the artifact. On a sealed ledger that is the only coherent reading, and it is flagged.
- **Honesty of the drill.** For review seeds, the scripted reviewer proves the plumbing and the
  scorer, not detection. That is stated in the goal, decision 7, open question 1, the
  limitations and the requirement table (partial), so PILOT-11's "caught" is not overclaimed;
  `eqos-4j2.30` tracks the owner blind run.
- **Constraints.** No change to migrations 0001–0039, retained data, frozen manifests or the
  held-out files. Paths are repo-relative. Tests write only to `eqos_test_*` databases and
  `tmp_path`.

## r1 findings → resolution

| # | Sol r1 finding / ruling | Resolution |
|---|---|---|
| 1 | Diff-only review misses deleted claims and reordered lines (P1) | Ruling: one uniform rule. Decision 6: the whole version is reviewed unless every section's ordered claim-line sequence (`rework.claim_lines`, compared as `Gate.close` does) and scaffold equal P's; otherwise every changed or not-accepted claim. Covers `--full-successor`. Task 2 `unchanged` deletion and reorder cases. Superseded by closing r1 1 |
| 2 | Answer-key script shows recording and scoring, not detection (P1) | Ruling: instrumentation regression, no automated reviewer. Goal, decision 7, OQ1, limitation ("detection of review-only seeds is not demonstrated", `eqos-4j2.30`), requirement row marked partial; Task 4 rewords the roadmap row |
| 3 | ACL matrix test fails after 0040 | Task 1 modifies `test_ledger_integrity.py`: `REVIEW_TABLES` join `GATED` and the owner's inserters only (owner-only INSERT and sequence USAGE), not `LEDGER_TABLES`; finding 9 corrected; Task 1 verification runs it |
| 4 | SQL category rule contradicts the validator | Decision 3: lowercase enum values with `IN` CHECKs; `CHECK (disposition = 'deferred' OR (disposition = 'accepted') = (category = 'none'))`; finding 2 corrected; Task 1 SQL boundary test |
| 5 | Session could attach to SUBMIT, panel or WITHDRAW decision | Decision 3 / Task 1 trigger: `decider = 'OWNER'` and `kind IN ('APPROVE','REQUEST_CHANGES','REJECT')`; Task 1 SUBMIT and panel `REQUEST_CHANGES` refusal cases |
| 6 | Failed approval does not close every memory-support route | Ruling: narrow the claim. Finding 7 rewritten (0017:79–97 routes); decision 7 and limitations name the disposable database as the isolation boundary; no route guards |
| 7 | Re-review assertion contradicts the rule | Task 2: no-correction e2e asserts exactly the keys not accepted in N; new real-correction e2e (PREP-5 `_correct`) asserts `review_set(N+1) == set(QOQ)` |
| 8 | S and S′ in one report break one-root / open-predecessor rules | Decision 7 and Task 3: S′ is the root of its own `FY26_Q2_DRILL_G5` report |
| 9 | Finish not checked against the last event | Decision 4, `review.finish(…, at)`: finish ≥ last event; Task 2 timing boundary cases |
| 10 | No rollback test after the decision insert | Task 2 rollback e2e: claim-review insert monkeypatched to a foreign key raises 23514 after `record_decision`; decision, validation, session and event counts unchanged |
| 11 | `-m "pg and retained"` deselects named regressions | Every explicit-file verification command runs without a marker filter (Tasks 1–3) |
| 12 | CLI misses `DatabaseUnavailableError` and `LookupError` | Task 2: the review CLI catches the ledger CLI's set (`ledger_cli.py:149`) plus `SystemExit`; CLI boundary test for both |
| 13 | No instrument version in the working session (P3) | Decision 2: captured at `start`, checked by `claim`/`list`/`finish`, stored on `review_sessions`; Task 2 refusal test |
| — | Note: locate/check are self-reported in the summary | Decision 8: summed under `locate_seconds_self_reported` / `check_seconds_self_reported`; Task 2 e2e asserts the keys |

## Closing r1 findings → resolution

| # | Sol closing r1 finding | Resolution |
|---|---|---|
| 1 | Separate claim-line and scaffold comparison misses a claim moved across a line, section order and ordinal-0 content (P1) | Decision 6: whole `(section_key, body)` pairs in ordinal order; only the claim-free ordinal-0 `run_draft.HEADING` section is exempt. `rework.claim_lines` dropped from the file map and Task 2. Finding 5 corrected. Task 2 `unchanged` cases: claim moved across a line, section swap, ordinal-0 content (heading-keyed too), heading-only control |
| 2 | Keys forwarded on `REJECT` fail 0039 (P2) | Decision 5 and Task 2 approach: `claims` only for `REQUEST_CHANGES`, `()` otherwise. Task 2 E2E `REJECT` with edited and rejected keys: exit 0, telemetry stored, `rejected_claims` NULL |
| 3 | Report time counts one version only (P2) | Decision 4 and 8: `session_wall_clock_minutes` per version, plus `report_wall_clock_minutes` summed over the sessions on the version chain. Re-review e2e asserts 30 + 5 = 35; limitation labels both wall-clock |
| 4 | Overhead claim exceeds what is measured (P2) | Decision 4: the interval is dispatch entry to just before the save, over successful commands. Renamed `command_handling_ms`/`command_handling_seconds`; exclusions stated (finding 2, limitation); B-13 overhead row marked partial. No new write path |
| 5 | DB assertion only `elapsed_ms ≥ 0` (P2) | Task 2 telemetry e2e on a monkeypatched `review_cli._now`: exact `elapsed_ms` (re-disposition included), session times, `command_handling_ms` and summary totals |

## Realisation

Sol phase review, 2026-10-19: r1 REVISE (5) → r2 REVISE (1) → r3 APPROVE; phase closing review
REVISE (3) → APPROVE.

- `lifecycle.record_decision` and `append_decision` take a `before_insert` hook, run after every
  check and just before the first insert. `review.finish` uses it to stop `command_handling_ms`
  at that point (`eb682a0`).
- `LEDGER_FAILURES` in `api/ledger_cli.py` is widened so the ledger and review CLIs refuse
  expired originals and snapshot and YAML errors with exit 2 (`ed7c32f`).
- `ledger/review.py` came out larger than estimated: 345 lines after the review fixes (336 at Task 2). Sol found no reduction.
