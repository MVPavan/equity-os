# Independent review — inventory-review recording design r6 + recorder amendment

**Verdict: CLEAN — 0 Critical, 0 Important, 3 Minor**

## 0. Identity and independence

| Field | Value |
|---|---|
| `role` | `REVIEWER` |
| `role_binding_path` | `CONTEXT.md` |
| `role_binding_sha256` | `8f2795af93ba6bf5303cf13227b8ce9e96295269887673a3a8b97d920b3198ce` |
| `model` (actually invoked) | `claude-opus-5` |
| `effort` (actually invoked) | `high` — the effort tier of the `REVIEWER` binding (CONTEXT.md "Agent roles (harness-wide)", L127ff) under which this agent was dispatched. Effort is not observable from inside the session; it is reported as dispatched, not as measured. |
| `review_round` | `r0` (of the r6 artifact) |
| `review start` (UTC) | `2026-08-17T16:00:28Z` |
| `review end` (UTC) | `2026-08-17T16:13:46Z` |
| Reviewer identity / session | Independent `REVIEWER`-role agent and context |

**Independence statement.** I authored no part of the reviewed package: not design
r0–r6, not `record_inventory_review.py`, not any of the 444 verdict artifacts, not
the build reports, not the manifests, and not the rehearsal harness. I am a
distinct agent and context from the `IMPLEMENTER` dispatch that produced r6 and
from the r0–r5 reviewers. Every probe cited below was written and executed by me
under `scratchpad/w78/review-r6/`. The earlier reviewers' probes
(`scratchpad/w78/review/`, `review-r4/`, `review-r5/`) and the implementer's
(`scratchpad/w78/r4/`, `r5/`, `r6/`) were read for context and for attesting the
provenance of the archived r5 recorder; no code, fixture or number was reused from
them. Where this review restates one of their figures it is because I recomputed
it independently and got the same value.

### 0.1 Target bytes, recomputed at review start and review end

| Path | SHA-256 at start | SHA-256 at end |
|---|---|---|
| `…inventory-review-recording-design-r6.md` | `9291205e00f5a036335430c59049b8688de8683daba39185c3e98faf6c1e171d` | identical |
| `scripts/equity_os_blueprint/record_inventory_review.py` | `94c65444cda07978ecef4ec7b6a241e4dab2f62677795bdfc0c718a821423341` | identical |

Both match the dispatch. Lineage bytes also recomputed and matching: r2
`adf908ac8cec01a55a53438624c6a8913f673f5b7cecd3e955fc4919f73803fb`, r2-review
`668a524bd499dce7851c4a4f0652526b89f1b904d34e1d21b5620fb3593dbf94`, r5
`eb81474d043ae4568059120bad3fd948a238d52d3a33c7d4bd713bbd389de4b4` (the digest
§0.0 pins as superseded), r5-review
`cb156f4e54b5d20d428bd70519a5ddebf027a12c34f8dc84aabe8a64f020571f`, `CONTEXT.md`
`8f2795af93ba6bf5303cf13227b8ce9e96295269887673a3a8b97d920b3198ce`.

**Working-tree effect of this review.** `git status --porcelain` had 10 entries at
review start and 10 at review end; the canonical ledger was `e52ed95c…` before and
after every probe, including the five non-dry-run rehearsal legs. The only file
this review adds outside `scratchpad/` is this report.

**One scoped deviation from the dispatch constraints, stated explicitly.** The
dispatch says "no recorder run without `--dry-run`" and also (item 8) "reproduce
the §3.10 rollback rehearsal". A rehearsal leg is by definition a non-dry-run
invocation. I resolved this the way §3.10 itself does: the five legs ran **only
inside five disposable full-tree replicas outside the working tree**
(`$SESSION_SCRATCH/rev-r6-replicas/L1…L5`, `scratchpad/` excluded from the copy so
each replica's `git status` matches the canonical tree's), never against the
canonical repository. Against the canonical tree the recorder was run exactly
twice, both `--dry-run`. This is the first round in which the five legs have been
re-executed by a reviewer rather than verified from the proof object — the r5
reviewer explicitly declined for this reason (r5-review item 8).

---

## 1. Per-item verification

| # | Item | What I did | Result |
|---|---|---|---|
| 1 | §2.2.1 contract == code | Wrote `prose_parser.py` from §2.2.1's prose alone (line loop, fence/comment/blockquote state, three field forms, label normalization + trailing parenthetical, closed alias table, value normalization, verdict regex quoted verbatim, the two tripwires, the two termination reasons), then diffed it against `parse_verdict_artifact` over all 444 (`diff_prose_vs_code.py`) | **PASS. 0 divergences.** 444/444 parse under both, every field equal, and no reason-token disagreement. Separately verified `ARTIFACT_LABEL_ALIASES` and `ARTIFACT_ROLE_BINDING_ROW3_LABELS` are **literally equal** to §2.2.1's alias table (11 fields, all label tuples, both A′ labels), as §2.2.1 requires |
| 2 | Ambiguity / laundering attacks | 42-case corpus (`attacks.py`), each run through the full `validate_batch_entry` chain in a throw-away fakeroot **and** through my prose parser | **PASS on every named case.** (a) `PATH_BODY_MISMATCH`; (b) `AMBIGUOUS_FIELD`; (c) unfenced prose `CLEAN` vs real `ISSUES_FOUND` → `AMBIGUOUS_VERDICT`, fenced `CLEAN` → `NOT_CLEAN`; (d) `Models actually invoked` and `Role binding location` → `MISSING_FIELD`; (e) `IMPLEMENTER` role, `AGENTS.md` binding path, non-64-hex binding sha → `ROLE_MISMATCH`; (f) `2027-01-01T00:00:00Z` and a `+00:00` offset → `FUTURE_TIMESTAMP`. Two residual classes are **not** rejected — see **M-2** |
| 3 | `captured_at` provenance | Read the live post-HR-0005 validator: `timestamp >= parse_utc_rfc3339(evidence_by_id[ref_id]["captured_at"])` at **`validate_ledger_structural.py:346-349`** (`>=`, so **equality is accepted**) and `captured_at <= validation_now` at **`:219`**. Traced the only write path: `record_inventory_review.py:886` sets `parsed["captured_at"] = parsed["timestamp"]` → `run_batch:1617-1619` → `build_candidate:963`. Independently re-derived `captured_at` for all 30 reviews by **re-parsing the artifact bytes myself**, not from the manifest | **PASS.** `captured_at == timestamp` for all 30; **0** cases of `captured_at > timestamp`. The design's `:346-349` and `:219` citations are exact against the live validator |
| 4 | Digest correctness | `independent_digests.py`: `ast`-extracted the four projection functions from the **live structural validator** (not the recorder's transcription), re-parsed each artifact's timestamp, and rebuilt both candidate ledgers from scratch | **PASS.** My candidate is byte-identical to the recorder's for **both** batches: `52debc487066fe87819a05389a797b8a3046379ef9e7ee9b9b92c8433dd47572` (batch-01) and `63e86747bc6359b6cb6b10e32a0f60a3bb511ac27e1bf560368f0a25ddb6fdac` (batch-doc) |
| 5 | Manifest schema §3.2 == code | Compared §3.2's two key lists against `MANIFEST_TOP_LEVEL_KEYS` / `MANIFEST_ENTRY_KEYS`; probed both closure directions | **PASS.** 5 top-level / 13 entry keys, exactly as §3.2 lists; `captured_at` absent from both. A stale entry declaring `captured_at` → `MANIFEST_UNKNOWN_KEY`; an unknown top-level key → `MANIFEST_UNKNOWN_KEY`. `ledger_prehash_sha256` is checked at step 2 against the live file **and** re-checked as a compare-and-swap at step 7 (`:1746-1751`). `baseline_dirty_paths` behaviour observed firing for real: my first replica run aborted at step 2 because I had left one extra file in the tree |
| 6 | Dry-run both batches | Ran both against the live tree | **PASS.** Both exit **0**, `committed: false`, `structural_candidate_exit: 0`, `stale_after: 0`, pending **447 → 435** (12 reviews) and **447 → 429** (18 reviews), `preimpl_exit: 2`. Canonical ledger `e52ed95c…` unchanged after both; no journal directory created |
| 7 | Strict-form regression | Determined the cohort myself by re-running the r6 parser with the alias table reduced to snake_case labels and form A′ disabled | **PASS. 370** artifacts parse fully and identically under snake_case labels alone; **74** need the alias table — exactly §2.2.1's split, computed independently. All 370 parse byte-identically under r5 and r6 |
| 8 | §3.10 rehearsal claim | Verified every Status-table digest (proof `437f7492…` ✓, transcript `75c61cb7…` ✓ = the proof's field ✓, `recorder_sha256` = `94c65444…` = live recorder ✓, prestate `e52ed95c…` ✓). Then **re-executed all five legs myself** (`rehearse.py`) on five fresh replicas, each seeded with its own proof, injecting at `post_replacement_verify` | **PASS, reproduced.** L1 `COMMITTED`, ledger changed, posthash == candidate, structural 0, 447→435, 0 temps, lock released. L2 `ROLLED_BACK`, bytes+mode match preimage, exit 1. L3 `ROLLED_BACK`, re-raised `KeyboardInterrupt`. L4 `ROLLED_BACK` via a **real** `SIGTERM`, re-raised `SystemExit`. L5 `RECOVERY_REQUIRED`, `observed_sha256 != expected_sha256`, exit 1, second invocation refused at step 1, surviving paths recorded, and both r6 M-2 fields present (`preimage_sha256_before_restore`, `surviving_preimage_exists: false`). My L5 recorded `temp_files_surviving: 0`, **independently confirming r6's M-2 correction** that r2–r5's "those files survive" was false |
| 9 | r6 lineage hygiene | Recomputed the pinned r5 (`eb81474d…`) and r5-review (`cb156f4e…`) digests; built a section-attributed r5→r6 diff (`lineage.py`) and a hunk map of the recorder diff | **PASS with a disclosure gap (M-3).** The changelog pins r5's **final** digest correctly; every one of the 7 findings maps to a change; the recorder diff is 13 hunks, all attributable to a finding (pins, DISP-R-1 constants, verdict tripwires, comment/fence handling, manifest path checks, preimage pre-hash). No behavioural scope creep found in either artifact. But four sections changed substantively that §0.0's exception list does not name — see **M-3** |
| 10 | F-1 both halves | Rebuilt the r3 reviewer's `c3` (fenced `CLEAN` quoting a superseded round) and the r4 reviewer's `N6` (unterminated fence) myself, plus new variants | **PASS.** Fence-aware for both markers and both directions; blockquote-aware; `verdict: TOKEN — remainder` captures TOKEN; `MISSING_VERDICT`/`AMBIGUOUS_VERDICT` named verbatim in the abort text. `c3` → `NOT_CLEAN`; `N6` → `UNTERMINATED_FENCE`; tilde fence not closable by a backtick fence → `UNTERMINATED_FENCE`; indented code block → `AMBIGUOUS_VERDICT`; HTML comment as sole carrier → `MISSING_VERDICT`; unterminated comment → `UNTERMINATED_COMMENT`; a fence opened inside an open comment → `UNTERMINATED_FENCE` (the r6 M-1 precedence, as documented); CRLF control accepted, CRLF + fenced `CLEAN` → `NOT_CLEAN`; blockquoted identity table → `MISSING_FIELD`; blockquoted/fenced identity-row override ignored (header value wins, correctly). **A table cell holding `verdict: ISSUES_FOUND` is accepted — see M-2** |
| 11 | F-2 closed | Item 1's prose parser, built from §2.2.1 alone | **PASS. 0 divergences over 444** |
| 12 | r6 == r5 output over 444 | `regress_r5_r6.py` against `scratchpad/w78/r6/record_inventory_review_r5.py`, sha256 `8d0410cd1803c82b276d801da30d47f877778c08eb10bb5db7f4c618b6fb3032` — the digest the **r5 review** independently recomputed (r5-review §0.1) and byte-identical to that reviewer's own replica copy, so provenance is attested outside the implementer's report | **PASS. 0 divergences** on all 444 (accept/reject and every field); the parse-output digest is `d0d7eb1bbe17aaeca5443c286d14b018891f79b3ed5b7a65742c36cf269005db` under both recorders. The accepted set *is* changed for constructed inputs, in the intended direction only: r6 newly rejects X1–X5 |
| 13 | r5-specific | `UNTERMINATED_FENCE` fires on my own N6. M-1's comment/fence clause: §2.2.1 L617-631 states the fence machine runs unconditionally first, both states can be open at once, and `UNTERMINATED_FENCE` wins at EOF — which is exactly `parse_verdict_artifact:605-626` and `:664-674`; I reproduced the zero-regression measurement (0 of 444 contain `<!--`). §3.10 Status and §7.9: every claim checked against the files — recorder `94c65444…` ✓, proof `437f7492…` binding it ✓, transcript ✓, both dry-runs ✓, ledger unchanged ✓. M-5 precedence: §2.2.1's 5-step list vs `validate_batch_entry:818-879` | **PASS**, except that the precedence list is incomplete for one check — see **M-1**. Order in code is path/body → `NOT_CLEAN` → `ROLE_MISMATCH` → `FUTURE_TIMESTAMP` → `MANIFEST_DISAGREEMENT`-last, exactly as documented |
| 14 | r6-specific | Recomputed all seven §1.1 pins against the **live** tree (goal `b77ea73d…`, ledger `e52ed95c…`, human-review `51bc4f9a…`, structural `77faeaf3…`, preimpl `f7a225a1…`, extractor `5d20d796…`, `CONTEXT.md` `8f2795af…`) — all match, and the recorder's four `PINNED_*` constants match. Rebuilt X1/X2 (nested-bullet and tab-indented conclusions), X3/X4/X5/X5c, and the §3.6 two-state probe | **PASS.** X1/X2 → `AMBIGUOUS_VERDICT` (M-1(b) demonstrably dropped). X3 (parenthesised remainder), X4 (`NOT CLEAN`), X5d (indented near-miss) → `MALFORMED_VERDICT_LINE`. X5 (blockquoted conclusion), X5c (commented-out conclusion) → `CONFLICTING_QUOTED_VERDICT`; a blockquoted verdict *agreeing* with the accepted one is correctly still accepted. §3.6: all four validator citations exact (`:2675` identity, `:2686` `DISP_R1_MUTABLE_FIELDS`, `:2759-2768` two-state block, `:2719` `set(historical) <= set(...)`); live state is `UNRESOLVED` / `[]` / `PENDING`; a candidate carrying DISP-R-1 links **only** `EV-DISP-R-1-INVREV-EVIDENCE` and passes structural **0**; flipping the requirement to `SATISFIED` in memory yields `DISP_R1_RESERVED_FOR_T2`; and a `SATISFIED` ledger that keeps the carve-out fails structural exit **1**, confirming the mutual exclusivity §3.6 argues. Rehearsal proof binds the r6 recorder hash ✓ |

Also run: `python3 -m py_compile` on the recorder, exit 0.

---

## 2. Findings

### Minor

**M-1 — §2.2.1's check-precedence list omits the `artifact_sha256` comparison,
so "`MANIFEST_DISAGREEMENT`, last" is not literally true.**

§2.2.1's precedence block says the manifest comparison runs last and that
`MANIFEST_DISAGREEMENT` therefore "fires only for an artifact that is otherwise
path-consistent, `CLEAN`, `REVIEWER`-bound and non-future — i.e. only when the
disagreement really is manifest-versus-artifact". That holds for the 11-field loop
at `record_inventory_review.py:873-879`, but not for the **artifact digest**
comparison at `:805-810`, which runs *before* `parse_verdict_artifact` is called at
all.

Demonstrated: an artifact that is simultaneously `NOT_CLEAN`, `IMPLEMENTER`-role
and future-timestamped, paired with a manifest carrying a stale
`artifact_sha256`, aborts `MANIFEST_DISAGREEMENT` — the exact shadowing that
r4-review M-5 objected to. With the digest corrected, the same artifact aborts
`NOT_CLEAN`, in the documented order.

The **code is right**: byte integrity must be established before the bytes are
interpreted, and every outcome here is reject-vs-reject, so no artifact's
accept/reject status is affected. Only the triage token is, and the triage token is
what the precedence contract exists for.

*Minimal remedy (documentation only): insert a step between §2.2.1's steps 0 and 1
— "0b. artifact-bytes agreement, before the artifact is parsed —
`MANIFEST_DISAGREEMENT`" — and qualify the closing sentence to the field loop.*

**M-2 — the I-2 tripwires close the line-start and blockquote-line classes but not
two adjacent ones, and §2.2.1 claims otherwise.**

§2.2.1 concludes the I-2 clause with: *"every construct that a human reads as a
verdict either counts toward `AMBIGUOUS_VERDICT` or aborts under its own name."*
Two constructs do neither:

- **(i) a verdict announced anywhere other than the start of a scanned line.**
  `MALFORMED_VERDICT_LINE` keys on `^[ \t]*(?:\*\*)?[ \t]*[Vv]…:`, so
  `| Note | verdict: ISSUES_FOUND |` (my case N8) — and equally
  `Final assessment — verdict: ISSUES_FOUND` — is neither a carrier nor a
  near-miss. With the header still asserting `CLEAN`, the artifact is **accepted**.
- **(ii) a blockquoted or commented-out 2-cell `| verdict | TOKEN |` row.**
  `note_quoted_verdict` (`:593-597`) applies only `ARTIFACT_VERDICT_RE`, so the
  2-cell verdict row — which §2.2.1 lists as a carrier form and the verdict rule
  explicitly counts ("verdict lines, **plus the 2-cell `verdict` row if present**")
  — is invisible to `CONFLICTING_QUOTED_VERDICT`. My cases Y1/Y2 are **accepted**.
  §2.2.1's own I-2 wording, "collects **any verdict token they carry**", reads
  wider than the code does.

I measured incidence over the 444: **0** for (i) and **0** for (ii). I rate this
Minor rather than Important, and the reasoning matters because r5's I-2 was
Important at the same zero incidence: r5's hole sat on constructs the house format
actively invites — the `**Verdict: X — N Critical**` shape with a near-miss, and
blockquote callouts that 375 of 444 artifacts use. r6 now refuses that entire class.
What is left requires a reviewer to state their conclusion inside a table cell under
a non-verdict label, or to blockquote a 2-cell verdict row that **0 of 444** use in
any position and that §2.2.1 itself discloses as unexercised — *and* to write
`CLEAN` in the header as well. That is the deliberate-forgery case §3.10 already
declares out of scope, not the honest-reviewer case the guard is for.

*Minimal remedy, either one sufficient: (a) documentation — replace the "every
construct" sentence with the narrower true claim and name these two residuals in the
reason table; or (b) two lines of code — apply `ARTIFACT_TABLE_FIELD_RE` +
`artifact_field_for_label` inside `note_quoted_verdict` so a quoted 2-cell verdict
row is collected, which closes (ii) at zero measured cost.*

**M-3 — the M-4 fix is itself incomplete: four sections changed substantively
outside §0.0's declared scope and its enumerated exceptions.**

§0.0 states that every section not named in the disposition table's "Where" column
is byte-identical to r5 *except* three enumerated bookkeeping classes (title line,
lineage-heading renumbering, four cross-references) — the r5 M-4 remedy, whose whole
point was to enumerate rather than wave. The declared set is §0.0, §1.1, §2.2,
§2.2.1, §3.6, §3.10, §6.3. My section-attributed diff finds four more that changed
with real content:

| Section | Change |
|---|---|
| §3.7 | the byte-exact writer claim re-scoped from `de236d7e…` to the live `e52ed95c…` |
| §3.9 | "unclearable by any ledger edit" → "…by any ledger edit *this tool can make*", plus a new post-HR-0005 paragraph |
| §7.9 | recorder / proof / pre-state digests updated, plus a **new** disclosure that §3.6's state-2 branch is exercised only in memory |
| §8 | the summary row on the preimplementation gate rewritten for the two-state rule |

All four changes are **correct and forced by I-3**; I found no unrequested behaviour
change anywhere in the r5→r6 diff. This is purely a disclosure gap — but it is the
second consecutive round in which this specific sentence has been inaccurate, which
is why it is worth naming rather than absorbing.

*Minimal remedy: add §3.7, §3.9, §7.9 and §8 to I-3's "Where" column, or to the
"Scope of change" exception paragraph.*

---

## 3. What I did not do

- **No canonical or `inventory/` file was edited**, no commit, no Beads mutation.
- **Probes A–H of §6.3 were not re-executed** — r6 does not re-execute them either
  and says so; I verified the three claims r6 does carry forward as current.
- **Real (non-dry-run) recording against the canonical ledger was not performed**,
  and remains unperformed by anyone.
- The rehearsal legs I re-executed used **my own seeded proof objects** in each
  replica, since a leg is a real write and the recorder gates real writes on a
  proof. This is the same bootstrap the implementer's harness must use, and it
  confirms §3.10's own statement that the gate is operator discipline over an
  unauthenticated file, not an enforcement boundary.

---

## 4. Conclusion

The three items the r5 review blocked on are closed, and I confirmed each by
construction rather than by reading: X1/X2 are refused again (I-1), X3/X4/X5/X5c are
refused by name (I-2), and the package is re-pinned to the live post-HR-0005 state
with a fresh rehearsal bound to the r6 recorder's exact bytes (I-3). The contract in
§2.2.1 is what the code does — a parser built from the prose alone agrees on all 444
artifacts, and the alias table is literally equal to the design's. The digests are
independently reproducible from the live validator's own projection functions, for
both batches, to the byte. `captured_at` provenance is sound, structural by `>=`
rather than by coincidence, and unreachable in the wrong direction. The five-leg
rollback rehearsal reproduces, including the L5 `temp_files_surviving: 0` result that
r6 corrected the design to admit.

The three Minors are documentation precision (M-1, M-3) and a disclosed-but-overstated
residual (M-2); none blocks recording, and none requires a code change to be safe.
Fixing them is a text edit to §2.2.1 and §0.0 — which, note, changes the recorder's
bytes not at all and therefore does **not** invalidate the rehearsal proof.

**Verdict: CLEAN — 0 Critical, 0 Important, 3 Minor**
