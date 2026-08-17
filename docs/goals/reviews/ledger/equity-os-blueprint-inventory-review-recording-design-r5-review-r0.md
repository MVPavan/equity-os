# Independent review — inventory-review recording design r5 + recorder amendment

**Verdict: BLOCKED — 0 Critical, 3 Important, 4 Minor**

## 0. Identity and independence

| Field | Value |
|---|---|
| `role` | `REVIEWER` |
| `role_binding_path` | `CONTEXT.md` |
| `role_binding_sha256` | `8f2795af93ba6bf5303cf13227b8ce9e96295269887673a3a8b97d920b3198ce` |
| `model` (actually invoked) | `claude-opus-5` |
| `effort` (actually invoked) | `high` — the effort tier of the `REVIEWER` binding (CONTEXT.md L147) under which this agent was dispatched. Effort is not observable from inside the session; it is reported as dispatched, not as measured. |
| `review_round` | `r0` (of the r5 artifact) |
| `review start` (UTC) | `2026-08-17T15:17:35Z` |
| `review end` (UTC) | `2026-08-17T15:41:12Z` |
| Reviewer identity / session | Independent `REVIEWER`-role agent and context |

**Independence statement.** I authored no part of the reviewed package: not
design r0–r5, not `record_inventory_review.py`, not any of the 444 verdict
artifacts, not the build reports, not the manifests, and not the rehearsal
harness. I am a distinct agent and context from the `IMPLEMENTER` dispatch that
produced r5 and from the r0, r1, r2, r3 and r4 reviewers. Every probe cited
below was written and executed by me under `scratchpad/w78/review-r5/`. The
earlier reviewers' probes (`scratchpad/w78/review/`, `scratchpad/w78/review-r4/`)
and the implementer's (`scratchpad/w78/r4/`, `scratchpad/w78/r5/`) were read for
context; no code, fixture or number was reused from them. Where this review
restates one of their figures it is because I recomputed it independently and got
the same value.

### 0.1 Target bytes, recomputed at review start and review end

| Path | SHA-256 at start | SHA-256 at end |
|---|---|---|
| `…inventory-review-recording-design-r5.md` | `eb81474d043ae4568059120bad3fd948a238d52d3a33c7d4bd713bbd389de4b4` | identical |
| `scripts/equity_os_blueprint/record_inventory_review.py` | `8d0410cd1803c82b276d801da30d47f877778c08eb10bb5db7f4c618b6fb3032` | identical |

Both match the dispatch. Lineage bytes also recomputed and matching: r2
`adf908ac8cec01a55a53438624c6a8913f673f5b7cecd3e955fc4919f73803fb`, r2-review
`668a524bd499dce7851c4a4f0652526b89f1b904d34e1d21b5620fb3593dbf94`, r4
`9ed08e186102bfe371d08b85b9101cbe4798562bb80bb616edabb84cae5fe5b5` (the digest
§0.0 pins as superseded), r4-review
`9a455342a3ad83d6cf37f9741a5e46395f615ebd5809cb5dc541f160bc841134`, `CONTEXT.md`
`8f2795af93ba6bf5303cf13227b8ce9e96295269887673a3a8b97d920b3198ce`.

### 0.2 A tree change that landed mid-review — read this before §1

Between the r5 build's dry-runs (15:12:05Z) and this review, a **concurrent**
commit `501f3e708099f26e15d0bbd018f1cb9b496fa490` — *"feat(ledger): execute
HR-0005 RECONCILE_AUTHORITY amendment (DISP-R-1 unpinned)"*, files written
15:14:09Z, committed 15:18:38Z — advanced the canonical ledger
(`de236d7e…` → `e52ed95c…`) and the structural validator
(`731d0d8b…` → `77faeaf3…`). Every §1.1 pin in the r5 package refers to the
former state. This is finding **I-3**; it is not an implementer error, and it
changes how items 6 and 8 below had to be verified. To verify anything that
needs the pinned pre-state I built a replica —
`git clone -s` + `checkout 7e620d4` + the untracked artifacts/designs/recorder —
and confirmed it reproduces the pinned bytes exactly (ledger `de236d7e…`,
validator `731d0d8b…`, recorder `8d0410cd…`, `CONTEXT.md` `8f2795af…`).

## 1. Per-item verification

Probe files are under `scratchpad/w78/review-r5/`.

| # | Item | Method | Result |
|---|---|---|---|
| 1 | §2.2.1 contract == code | Wrote `prose_parser.py` from §2.2.1's prose alone (separate structure: explicit scan pass, then carrier pass), diffed against `parse_verdict_artifact` over all 444 artifacts (`diff_corpus.py`) | **PASS with one exception.** 444/444 parse under both; **0 divergences** on accept/reject and on every field value. The one prose clause the code does not implement is the HTML-comment/fence interaction → **M-1** |
| 2a | component_id in a table disagreeing with the path | fixture (a1), truthful manifest | Rejected `PATH_BODY_MISMATCH` (r4 said `MANIFEST_DISAGREEMENT`) |
| 2a′ | review_type / round variants | (a2), (a3), (a4) | `PATH_BODY_MISMATCH`, `ROUND_FILENAME_MISMATCH`, `MALFORMED_REVIEW_ROUND` |
| 2b | two rows, one field, different values | (b1) two `model` rows; (b2) 2-cell vs A′ `role_binding_sha256`; (b3) agreeing control | `AMBIGUOUS_FIELD`, `AMBIGUOUS_FIELD`, control ACCEPTED |
| 2c | `verdict: CLEAN` hidden in prose vs a real `ISSUES_FOUND` | (c1) unfenced prose CLEAN; (c2) r3-reviewer's `c3` rebuilt (fenced CLEAN); (c3) fenced-only carrier; (c4) house non-clean form | `AMBIGUOUS_VERDICT`; `NOT_CLEAN`; `MISSING_VERDICT`; `NOT_CLEAN` |
| 2d | label one edit away from an alias | (d1) `Model actualy invoked`; (d2) `Role binding location`; (d3) `component-id` | all `MISSING_FIELD`. (d4) `Effort actually invoked (high)` is **accepted** — correct per the trailing-parenthetical rule, since the stripped label is an alias |
| 2e | role / role_binding mismatch | (e1) role `AUDITOR`; (e2) path `AGENTS.md`; (e3) uppercase hex; (e4) 63 hex | all `ROLE_MISMATCH` (r4: `MANIFEST_DISAGREEMENT`) |
| 2e′ | 64-hex sha that is not `CONTEXT.md`'s digest | (e5b), manifest truthful | Accepted — **correct by design**: `validate_ledger_structural.py:253-255` states `role_binding_sha256` is an immutable historical capture, deliberately not re-verified. Not a finding |
| 2f | timestamp future / non-Z | (f1) 2027; (f2) `+00:00`; (f3) no zone; (f4) `+05:30` | all `FUTURE_TIMESTAMP` |
| 3 | `captured_at` provenance | Cited assertion read in the live validator: `timestamp >= parse_utc_rfc3339(captured_at)` at **`validate_ledger_structural.py:346-349`** (`>=`, so **equality is accepted**), and `captured_at <= validation_now` at **`:219`**. Traced the only write path: `validate_batch_entry:813` sets `captured_at = parsed["timestamp"]` **after** the manifest-agreement loop → `run_batch:1506-1511` → `build_candidate:870` | **PASS.** Equality is structural, not incidental. My independent rebuild of both candidates confirms `captured_at == timestamp` for all 30 reviews and **no** case of `captured_at > timestamp` |
| 4 | Digest correctness | `independent_digests.py`: rebuilt both candidate ledgers from scratch using the four projection functions **ast-extracted from the pinned structural validator itself** (not the recorder's transcription), with row mutation written from §2.2/§3.4/§3.7 | **PASS.** `batch-01` → `b168928031153a438bc71fd8eff5b859bd279031faff7b7e0e11c19b3aa15437`; `batch-doc` → `b85b8efe71f407b007bdd7a0c187c8e90844602472b8cb8e1880ac557c29f21c` — **bit-identical** to what the recorder reports. Also confirmed `reviewed_input_sha256` is one value per row across all three types, `reviewed_inventory_sha256` per type |
| 4′ | transcription drift after HR-0005 | ast-compared the four reference functions between `7e620d4` and the live validator | **Identical ASTs.** HR-0005's 42-line validator edit is confined to the DISP-R-1/HR-0004 assertion region; the digest contract is untouched |
| 5 | Manifest schema §3.2 vs code | `manifest_probe.py`: 11 `load_manifest` cases + 4 real `--dry-run` step-2 cases | **PASS.** Extra top-level key, extra entry key, and a **stale `captured_at` entry key** all abort `MANIFEST_UNKNOWN_KEY`; missing keys, bad schema, uppercase prehash, duplicate entry, bad `review_type`, empty list all rejected. `ledger_prehash_sha256` wrong-but-well-formed → step-2 abort naming both digests; `baseline_dirty_paths` emptied or padded with one invented path → step-2 abort; unmodified control exit 0 |
| 6 | Dry-run both batches | Run by me. Against the **live** tree both abort exit 1 at `§3.10 assert 6` (see **I-3**). Against the pinned-pre-state replica: | **PASS (on the replica).** exit **0** for both; `batch-01` pending 447→435, `batch-doc` 447→429; `stale_after` 0; `structural_candidate_exit` 0; `preimpl_exit` 2 (expected — other blockers remain); `committed: false`; replica ledger still `de236d7e…`; canonical repo ledger untouched; no journal or lock left behind |
| 7 | 370 strict-form artifacts unchanged | `regress_and_cohort.py`: re-parsed all 444 with the alias table cut back to the snake_case labels only (A′ labels removed) | **PASS.** Exactly **370** still parse fully and **74** do not — reproducing the split independently — and all 370 yield field values **identical** to the full-alias parse (0 mismatches) |
| 8 | §3.10 rehearsal claim | Verified every claim in §3.10's Status table: proof digest `b075280cc2dd70e553fadeeee87bffed5cb0e592179239bd9bc4d1959c7d771f` ✓; transcript digest `e995f8191e26a611178822733992866a7ab6174d00c4141801b353471101648f` ✓ = the proof's field ✓; `recorder_sha256` = `8d0410cd…` = live recorder ✓; ran `assert_rehearsal_proof` in-process — **all 8 asserts pass** against the replica, and the assert-5 mechanism demonstrably rejects a different recorder digest; log and transcript show 5/5 legs with the exact per-leg outcomes §3.10 requires | **PASS, with one contradiction (M-2).** I did **not** re-execute the five legs: that requires non-dry-run recorder runs, which my dispatch forbids. What I verified is the proof's validity, its bindings, its internal consistency and the gate's behaviour — not an independent re-run |
| 9 | Lineage hygiene / surgical diff | `diff -u` r4→r5 (14 hunks) mapped to sections; `diff -u` r4→r5 recorder (15 hunks) mapped to functions | **PASS, one bookkeeping inexactness (M-4).** Every design hunk traces to a named r4-review finding (I-1, I-2, M-1…M-5); recorder hunks touch only the manifest key sets, the r5 scan constants, `parse_verdict_artifact`, `load_manifest`, `validate_batch_entry`, `build_candidate` and `run_batch`. No unrelated change; §3.3 is untouched (it appeared only as hunk context). r4's final digest `9ed08e18…` and the r4-review digest `9a455342…` are both pinned in §0.0 and both verified |
| 10 | F-1 both halves | Fence- and blockquote-awareness confirmed for both markers; `verdict: TOKEN — remainder` captures TOKEN (c4); `MISSING_VERDICT`/`AMBIGUOUS_VERDICT` named in the abort text; r3's `c3` rebuilt → `NOT_CLEAN`; r4's `N6` rebuilt → `UNTERMINATED_FENCE`. New variants: indented block (N12) → `NOT_CLEAN`; multi-line comment as sole carrier (N7) → `MISSING_VERDICT`; table cell holding `verdict: CLEAN` (N8) → `NOT_CLEAN`; never-closing fence (N6) → `UNTERMINATED_FENCE`; CRLF control (N10) → accepted, CRLF + fenced CLEAN (N11) → `NOT_CLEAN`; blockquoted identity table (N9) → `MISSING_FIELD`; tilde fence not closable by a backtick fence (N15) → `UNTERMINATED_FENCE` | **PASS for the constructs the design names**, but two human-visible non-clean assertions are silently ignored → **I-1**, **I-2** |
| 11 | F-2 closed | Item 1's parser diff | **PASS.** 0 divergences over 444, 0 `AMBIGUOUS_FIELD` |
| 12 | r5 == r4 output over 444 | `regress_and_cohort.py` against the r4 recorder copy at `32947a029be450d81d032f428cf73bc026b663bbcda1047286510ef2fa934d7c` — the digest the **r4 review** independently recomputed (r4-review §0.1), so the copy's provenance is attested outside the implementer's own report | **PASS.** **0 divergences** on all 444 (accept/reject and every field). Note the accepted-artifact set *is* changed for constructed inputs, in both directions: r5 newly rejects N6/N6b/N7/N15, and r5 newly **accepts** X1/X2 (→ **I-1**) |
| 13a | `UNTERMINATED_FENCE` fires | N6 rebuilt independently | **PASS.** Accepted under r4, `UNTERMINATED_FENCE` under r5 |
| 13b | M-1 rule stated == code, zero-regression remeasured | Re-measured all five figures myself over the 444: artifacts containing `<!--` **0**; accepted identity rows indented **0**; scanned verdict lines indented **0**; indented fence delimiters **0**; fences open at EOF **0** | **PASS on the measurements** (all five reproduce). The *rule* is stated and matches the code; its stated **premise** does not hold → **I-1** |
| 13c | §3.10 Status and §7.9 state the true state | Checked each claim against the files (see item 8). §7.9's rewritten item 9 correctly retracts "the recorder does not exist / nothing in §3.8 has been executed" and states what remains untested | **PASS**, subject to I-3 (the line "canonical ledger `de236d7e…` unchanged" was true when written and is now stale) |
| 13d | M-5 precedence documented == code | §2.2.1's 5-step precedence list vs `validate_batch_entry:745-806`; probes X9/X10/X11 and (a1)/(a2)/(e1)-(e4) run against **both** recorders | **PASS.** Order in code is exactly path/body → verdict → role → timestamp → manifest-last. Every r4→r5 token change I observed is reject→reject: the accepted set is unchanged by the reorder, as claimed |

## 2. Findings

### Important

**I-1 — r5's indented-line rule (M-1b) reopens the F-1 laundering class, and the
premise that licensed it is false for this corpus.**

`^(?: {4,}|\t)` is described in §2.2.1 as "a Markdown indented code block" and in
§2.2 is offered to reviewers as a quoting device. It is neither, in the two most
common Markdown contexts: an indented chunk **inside a list item** is content
indentation, not code, and an indented line **after a paragraph line** is a lazy
paragraph continuation — an indented code block cannot interrupt a paragraph.
Both render as ordinary asserted prose.

Demonstrated (`attacks.py`, cases X1, X2). A `CLEAN` header, the honest identity
table, and a conclusion written as a nested-bullet continuation:

```
- **F-1** — the component's scope statement is wrong.
    **Verdict: ISSUES_FOUND — 1 Critical, 0 Important, 0 Minor**
```

r4: `AMBIGUOUS_VERDICT`, batch aborted. **r5: ACCEPTED**, and
`build_candidate` writes `verdict: CLEAN` into the canonical ledger. X2 shows the
same with a tab-indented conclusion after a `Conclusion:` paragraph line.

This is not hypothetical shape. **13 of the 444 artifacts already contain
indented, non-fence, non-blockquote lines outside every fence**, and the ones I
sampled are nested-list reasoning prose, e.g.
`docs/goals/reviews/ledger/inventory/REG-B-07/APPROVAL-r0.md:83-84` and
`REG-C-01/APPROVAL-r0.md:82-83`. r5 already stops scanning those lines; today
none of them happens to carry a verdict or an identity row (the M-1 measurement
is correct), so there is no live regression — but the measurement only licenses
"no *current* parse changes", not the design's stronger claim that such lines are
what "a reader reads as quoted". And §2.2 now instructs the authors of the
remaining rounds (the 15 components carrying `ISSUES_FOUND` r0) to use exactly
this construct for quoting, which is when it starts being written deliberately.

The direction of failure is the one the whole gate exists to prevent: recording
`CLEAN` for an artifact whose rendered text concludes `ISSUES_FOUND`. r3-review
rated the fenced version of this defect Critical; r5 re-opens it through a
different construct, in a round whose own I-1 rationale says "the recorder must
not decide which of an artifact's assertions it happened to read; it refuses the
artifact."

Remedies, any one sufficient: (a) drop M-1(b) and keep M-1(a) + I-1 — M-1 was an
optional Minor, and dropping (b) restores r4's behaviour at zero measured cost;
(b) narrow the rule to a genuine indented code block (preceded by a blank line,
not inside a list item); (c) keep the skip but make an indented line that matches
the verdict-carrier regex a **named refusal** rather than a silent skip.

**I-2 — a `Verdict:`-prefixed line that fails the carrier regex is silently
ignored, so `AMBIGUOUS_VERDICT` misses near-miss verdict shapes.**

The verdict regex must match to end-of-line, so any deviation makes the line not
a carrier *at all* rather than a malformed one. With the header still asserting
`CLEAN`, the artifact is recorded `CLEAN`. Demonstrated (X3, X4, X5), all
**ACCEPTED** by r5 — and by r4, so this is inherited, not introduced:

- `**Verdict: ISSUES_FOUND (1 Critical, 0 Important, 0 Minor)**` — parenthesis
  instead of the em dash.
- `**Verdict: NOT CLEAN — 1 Critical**` — token `NOT`, then a space, so the
  whole line fails to match.
- a `>` blockquoted conclusion. `>` is used as a **callout** in this repository,
  not only for quotation — §2.2.1 states its own load-bearing `captured_at`
  decision inside one — and **375 of the 444** artifacts contain blockquote
  lines outside fences.

Current incidence is zero: I found **0** lines in the 444 that are
`verdict:`-prefixed but not valid carriers. §2.2 does fix the two admissible line
forms as contract, so this is defense-in-depth rather than a live
mis-recording — but it is the cheapest remaining hole in the highest-consequence
direction, and 447 reviews (plus r1 rounds) will be written against it.

Remedy: a tripwire, not a wider regex. Any **scanned** line matching
`^[ \t]*(?:\*\*)?[ \t]*[Vv][Ee][Rr][Dd][Ii][Cc][Tt][ \t]*:` that is not a valid
carrier → named reason (e.g. `MALFORMED_VERDICT_LINE`). Optionally the same for
skipped constructs whose verdict token differs from the accepted one, which would
also close I-1.

**I-3 — the package's pinned pre-state was superseded mid-round by HR-0005; the
recorder now refuses every batch, and §3.6's validator citations are stale.**

Not an implementer defect — the cause is the concurrent commit `501f3e7`
(§0.2) — but it is a blocking fact about the package as it now stands.

Measured against the live tree: structural validator `77faeaf3…` vs the §1.1 pin
`731d0d8b…`; canonical ledger `e52ed95c…` vs the pinned pre-state and both
manifests' prehash `de236d7e…`. Consequences I reproduced:

- Both `--dry-run` invocations abort exit 1 at
  `§3.10 assert 6: structural_validator_sha256 must equal the §1.1 value…`.
  The recorder fails closed, correctly — but it cannot run at all.
- `assert_rehearsal_proof` fails on the live tree for the same reason, so the
  rehearsal proof is also invalid there. Because assert 5 binds the recorder's
  bytes, re-pinning `PINNED_STRUCTURAL_SHA256` / `PINNED_LEDGER_PRESTATE_SHA256`
  changes the recorder and therefore **forces a fresh five-leg rehearsal**.
- §1.1, both manifests, §3.10's "canonical ledger `de236d7e…` unchanged", and
  §6.3's probe results now describe a state that no longer exists.

Second, independent half: §3.6 cites `EXPECTED_DISP_R1_REQUIREMENT` at
`:2674-2686` and the assertion at `:2756-2763`. HR-0005 renamed the constant
`EXPECTED_DISP_R1_REQUIREMENT_IDENTITY`, added
`DISP_R1_MUTABLE_FIELDS = {"status", "evidence_ref_ids"}`, and made DISP-R-1's
no-implementation requirement a **two-state** rule. Today the ledger still has it
`UNRESOLVED` with `evidence_ref_ids: []` (I checked), so the recorder's carve-out
remains correct and §3.6's behaviour is still the required one. But §3.6 states
that state as an invariant, and it is now one of two admissible states — and in
the other one the validator requires
`set(historical) <= set(review["evidence_ref_ids"])`
(`validate_ledger_structural.py:2719`), i.e. DISP-R-1's `EVIDENCE` inventory
review **must** link `EV-DISP-R-1-SPEC-DRAFT` — precisely what §3.6 and
`build_candidate:878-882` forbid. Given HR-0005's stated purpose ("DISP-R-1
unpinned"), the two workstreams must be reconciled before DISP-R-1's reviews are
recorded, or that row will be unrecordable by this tool.

Remedy: a re-pin round that refreshes §1.1, the manifests and §6.3, re-runs the
rehearsal, and reconciles §3.6 with the post-HR-0005 validator — including which
of the two DISP-R-1 states the program is targeting.

If the orchestrator prefers to treat concurrent tree drift as out of scope for
this design's verdict, the count without I-3 is 0 Critical / 2 Important /
4 Minor — still BLOCKED.

### Minor

**M-1 — §2.2.1's HTML-comment clause is not what the code does, and its
"mutually exclusive" claim is false.** §2.2.1 says every line while a comment is
open is unscanned "**including a fence delimiter** — a comment, once open,
swallows everything up to and including the first line containing `-->`", and
concludes "the two states are therefore mutually exclusive". In the code
(`parse_verdict_artifact:567-586`) the fence machine runs **unconditionally
first**, so a fence delimiter inside an open comment toggles fence state; both
states are then open at once, the `-->` line is consumed by the fence branch, and
the comment never closes. I built a second parser differing from the first only
in taking that sentence literally (`prose_parser_b.py`) — it still shows **0
divergences over the 444**, and on fixture X6 it parses the artifact and reads its
honest `ISSUES_FOUND`, where the recorder aborts `UNTERMINATED_FENCE`. Fail-closed
and zero corpus incidence (0 of 444 contain `<!--`), so this is a contract-text
defect, not a behavioural one. Also unstated: which of `UNTERMINATED_FENCE` /
`UNTERMINATED_COMMENT` wins when both are open (the code always says fence).
Remedy: either move the comment check ahead of the fence machine, or restate the
clause to describe the fence-first behaviour and give the precedence.

**M-2 — §3.10's L5 "the temp and preimage files are required to survive" is
contradicted by the rehearsal's own evidence, and the recorder's L5 exemption
rests on that premise.** The proof records L5 `temp_files_surviving: 0`; the
recorder exempts L5 from the temp-free check *because* step 10 supposedly
preserves those files, so the contradiction is invisible to the gate. Reading the
code, 0 is the honest outcome: the staged temp file was consumed by the forward
`os.replace`, and `rollback()` (line ~1382) does `os.replace(preimage, ledger)`
**before** hashing, so a corrupted preimage is consumed too — the journal's
`surviving_preimage_path` then names a file that no longer exists. That ordering
also means a corrupted preimage overwrites the structurally-validated candidate,
leaving a third state on the canonical path (recoverable from git, and the
journal does record expected vs observed digests). Remedy: hash the preimage
before the restoring rename, and either fix the L5 leg's assertion or correct
§3.10's wording.

**M-3 — the manifest-side path checks abort without a named reason token, so
§2.2.1's "triage is mechanical" claim has a hole.** `validate_batch_entry:716-731`
rejects a non-repo-relative `artifact_path`, a path outside
`…/inventory/<CID>/`, a filename that is not `<REVIEW_TYPE>-r<N>.md`, and a
non-regular file (symlink) with descriptive prose only — no token from the
14-token table (probes X11, X12). These are exactly the operator errors §2.2.1
says the manifest layer is responsible for. Remedy: give them tokens, or state
that the token contract covers artifact-content failures only.

**M-4 — "Every section not named in the table below is byte-identical to r4" is
not literally true.** Also changed, and not named: the title line (`r4` → `r5`),
the lineage heading renumbering (§0.0a/§0.0b/§0.0c), and one §2.2.1
cross-reference (`per §0.0a` → `per §0.0b`). All mechanical bookkeeping with no
semantic content, and identical in kind to what r4 itself did — but the claim is
what makes differential review sound, so it should carry the exception. Remedy:
one clause.

## 3. What I did not verify

- **The five rehearsal legs were not re-executed.** They require non-dry-run
  recorder runs, which my dispatch forbids. I verified the proof object, its
  bindings, its internal consistency, the transcript's digest and content, and
  the gate's accept/reject behaviour — not an independent re-run of L1–L5.
- **No real batch behaviour.** Everything in item 6 is `--dry-run`, per dispatch.
- **CommonMark rendering was not machine-checked.** No Markdown renderer is
  installed in this environment, so I-1's rendering claims rest on the CommonMark
  rules for list-item content indentation and paragraph continuation plus the 13
  corpus artifacts I inspected by hand — not on rendered output.

## 4. Handoff note

Creating this review file adds an untracked path under
`docs/goals/reviews/ledger/`. Both manifests' `baseline_dirty_paths` were
computed before it existed, so any future `--dry-run` with them will abort at
§3.8 step 2 until the baseline is regenerated. That regeneration is required
anyway by **I-3**.

Every probe cited here is reproducible from `scratchpad/w78/review-r5/`
(`prose_parser.py`, `prose_parser_b.py`, `diff_corpus.py`,
`regress_and_cohort.py`, `attacks.py`, `independent_digests.py`,
`manifest_probe.py`, and the `replica1/` clone at the pinned pre-state). No
canonical file, no file under `docs/goals/reviews/ledger/inventory/`, and no
Beads record was modified by this review.

---

**Verdict: BLOCKED — 0 Critical, 3 Important, 4 Minor**
