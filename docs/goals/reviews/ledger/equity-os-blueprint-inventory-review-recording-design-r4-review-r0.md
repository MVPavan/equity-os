# Independent review — inventory-review recording design r4 + recorder amendment

**Verdict: BLOCKED — 0 Critical, 2 Important, 5 Minor**

## 0. Identity and independence

| Field | Value |
|---|---|
| `role` | `REVIEWER` |
| `role_binding_path` | `CONTEXT.md` |
| `role_binding_sha256` | `8f2795af93ba6bf5303cf13227b8ce9e96295269887673a3a8b97d920b3198ce` |
| `model` (actually invoked) | `claude-opus-5` |
| `effort` (actually invoked) | `high` — the effort tier of the `REVIEWER` binding under which this agent was dispatched. Effort is not independently observable from inside the session; it is reported as dispatched, not as measured. |
| `review_round` | `r0` (of the r4 artifact) |
| `review start` (UTC) | `2026-08-17T14:44:00Z` |
| `review end` (UTC) | `2026-08-17T14:56:43Z` |
| Reviewer identity / session | Independent `REVIEWER`-role agent and context |

**Independence statement.** I authored no part of the reviewed package: not
design r0–r4, not `record_inventory_review.py`, not any of the 444 verdict
artifacts, not the build reports, and not the manifests. I am a distinct agent
and context from the `IMPLEMENTER` dispatch that produced r4 and from the r0,
r1, r2 and r3 reviewers. Every probe cited below was written and executed by me
under `scratchpad/w78/review-r4/`. The r3 reviewer's probes under
`scratchpad/w78/review/` and the implementer's under `scratchpad/w78/r4/` were
read for context but no code, fixture or number was reused from them — where
this review restates one of their figures it is because I recomputed it
independently and got the same value.

### 0.1 Target bytes, recomputed at review start and review end

| Path | SHA-256 at start | SHA-256 at end |
|---|---|---|
| `docs/goals/reviews/ledger/equity-os-blueprint-inventory-review-recording-design-r4.md` | `9ed08e186102bfe371d08b85b9101cbe4798562bb80bb616edabb84cae5fe5b5` | identical |
| `scripts/equity_os_blueprint/record_inventory_review.py` | `32947a029be450d81d032f428cf73bc026b663bbcda1047286510ef2fa934d7c` | identical |

Both match the digests named in the dispatch. Predecessor bytes were also
recomputed and match: r2 `adf908ac8cec01a55a53438624c6a8913f673f5b7cecd3e955fc4919f73803fb`,
r2-review `668a524bd499dce7851c4a4f0652526b89f1b904d34e1d21b5620fb3593dbf94`,
r3 `98d96672e9eec34f8b9698246257b6acc4b81d8113894d66e1105cbd188b61cc`,
r3-review `e05baabd249edd56bad211b9dbea200b28929e797ad33701f93063b4811ffd24`.
Canonical ledger `de236d7e8dcf02e307ec58797f5722ae2f85d1d8cdba57d4ecc07df5383c9c97`
at start **and** at end — unchanged by this review.

**Constraints honoured.** No canonical file edited; nothing under
`docs/goals/reviews/ledger/inventory/` read-modified or written; the recorder
was executed **only** with `--dry-run` (12 invocations, all logged); no commit,
no Beads mutation. The only file this review creates outside `scratchpad/` is
this report.

---

## 1. Per-item verification

Every row was executed, not reasoned about. Probe paths are relative to
`scratchpad/w78/review-r4/`.

| # | Item | Method | Result |
|---:|---|---|---|
| 1 | §2.2.1 contract == code | `spec_parser_r4.py` — an independent parser transcribed from §2.2.1's prose alone (fence state machine, forms A/A′/B, label normalization, parenthetical rule, alias table, value normalization 1–4, verdict line, verdict rule, per-field rule) — diffed against `parse_verdict_artifact` over all 444 artifacts (`diff_parsers.py`) | **PASS.** 444/444 parse under both; **0 divergences**, outcome or field. Additionally: the code's `ARTIFACT_LABEL_ALIASES`, `ARTIFACT_ROLE_BINDING_ROW3_LABELS` and all four regexes (A, A′, B, verdict) are **literally equal** to the strings printed in §2.2.1, as that section demands (mechanical comparison, modulo named-group syntax) |
| 2 | Ambiguity / laundering attacks | `attacks.py` — 42 hand-built fixtures under `fakeroot/`, each pushed through `validate_batch_entry` with a manifest built to agree with a *truthful* artifact | **PASS with 2 exceptions (I-1, M-1).** 32 rejected with the documented named reason, 10 accepted — 8 of which are correct accepts (the near-miss labels carried nothing and the artifact stayed truthful). See §2 |
| 2a | component_id disagrees with the path | fixture `(a)`, `(a2)` | REJECTED — `MANIFEST_DISAGREEMENT`; the reversed case (manifest siding with the body) is refused earlier by the `§2.2 requires the artifact under …/<CID>/` directory check |
| 2b | two rows, different values, one field | `(b)` `model`, `(b2)` `timestamp`, `(e5)` A′ sha vs 2-cell, `(e6)` A′ path vs 2-cell | REJECTED — `AMBIGUOUS_FIELD`, naming the field and both values |
| 2c | hidden `CLEAN` vs real `ISSUES_FOUND` | `(c)` fenced (c3 rebuild), `(c2)` unfenced, `(c3)` blockquoted | REJECTED — fenced/blockquoted → parses `ISSUES_FOUND` → `NOT_CLEAN`; unfenced → `AMBIGUOUS_VERDICT` |
| 2d | label one edit from an alias | `(d)` `component_ids`, `(d2)` `Model actually invoke`, `(d3)` `Role binding SHA256`, `(d4)` `Role binding location`, `(d5)` `Role bindings` 3-cell | **PASS.** All five carried nothing. `(d)` → `MISSING_FIELD`; the other four left the truthful value intact and did **not** inject the attacker's value (no `AMBIGUOUS_FIELD`, parsed values unchanged) |
| 2e | role / role_binding mismatch | `(e)`–`(e6)`, incl. uppercase sha | REJECTED — `MANIFEST_DISAGREEMENT` or `AMBIGUOUS_FIELD`. Note the reason token: a truthful manifest catches these before the dedicated `ROLE_MISMATCH` branch is reached (see M-5) |
| 2f | timestamp future / non-Z | `(f)` future, `(f2)` `+00:00`, `(f3)` naive, `(f4)` date-only | REJECTED. Against a *lying* manifest that repeats the bad value, `RFC3339_RE.fullmatch` and `timestamp > now` fire as `FUTURE_TIMESTAMP` (`record_inventory_review.py:714-723`) |
| 3 | `captured_at` provenance | Cited assertion read in the validator's own bytes; equality path re-derived on the batch-01 candidate (`digests.py`) | **PASS.** `validate_ledger_structural.py:346-349` is `assert all(timestamp >= parse_utc_rfc3339(evidence_by_id[ref_id]["captured_at"]) …)` — `>=`, so **equality is accepted**; `:219` is `assert parse_utc_rfc3339(evidence["captured_at"]) <= validation_now`. Both citations in §2.2.1 are exact. `captured_at` is written in exactly one place (`:779`), from the same `entry["timestamp"]` string that becomes the review's `timestamp` (`:802`), so `captured_at > timestamp` is unreachable: measured equal for all 12 batch-01 reviews. Provenance expression differs cosmetically from the design's wording — see M-3 |
| 4 | Digest correctness | `digests.py` — the four projection functions **ast-extracted by this review's own code** from `validate_ledger_structural.py` (the recorder's transcription deliberately not used), applied to the rebuilt batch-01 candidate | **PASS.** Rebuilt candidate hashes to `b168928031153a438bc71fd8eff5b859bd279031faff7b7e0e11c19b3aa15437`, byte-identical to what the recorder's dry-run reports. 12/12 `reviewed_input_sha256` and 12/12 `reviewed_inventory_sha256` match the validator-derived values; 12/12 `captured_at == timestamp`. `AUTH-DISP-001`: one shared input digest across its 3 reviews, 3 distinct inventory digests — §3.4's ordering rule behaving as specified |
| 5 | Manifest schema §3.2 vs code | Read `load_manifest` against §3.2; 9 hand-edited manifests dry-run end-to-end | **PASS with one gap (M-2).** Top level and all 13 per-entry keys match §3.2 exactly; `captured_at` is absent from both. `ledger_prehash_sha256`: wrong value → `ABORT §3.8 step 2: live ledger is de236d7e…, manifest prehash is 0000…`. `baseline_dirty_paths`: emptied → abort listing the full outside set; **and it fired for real** — a concurrent workstream added an untracked file mid-review, which correctly aborted the shipped manifests until the baseline was refreshed. Non-tautological `MANIFEST_DISAGREEMENT` confirmed by hand-editing `artifact_sha256`, `model`, `timestamp`, and `review_round` (`r0` instead of the normalized `0`) — all four rejected by name. §3.4 row atomicity confirmed separately: dropping one review type → `AUTH-DISP-001: §3.4 row atomicity — batch carries ['EVIDENCE','SCOPE'] but the row's applicable set is ['APPROVAL','EVIDENCE','SCOPE']` |
| 6 | Dry-run batch-01 and batch-doc | Executed by me | **PASS.** `batch-01-authority_clause`: exit **0**, 12 reviews, pending **447 → 435** (−12), `stale_after` 0, `structural_candidate_exit` **0**, `preimpl_exit` 2, `candidate_sha256` `b1689280…`, `committed: false`. `batch-doc-document_strategy_clause`: exit **0**, 18 reviews, pending **447 → 429** (−18), stale 0, structural 0, `candidate_sha256` `b85b8efe…`, `committed: false`. Ledger digest unchanged before/after; `git status` shows only the pre-existing ` M .beads/issues.jsonl`; no journal written, `staging/` empty, no lock file, no `.candidate.*` / `.preimage.*` beside the ledger |
| 7 | Regression — 370 strict-form artifacts | `regression_r3_r4.py` — alias table narrowed to the bare snake_case labels and A′ disabled, then re-parsed | **PASS.** Exactly **370** artifacts parse identically under the snake_case labels alone; the remaining **74** need the alias table. All 370 parse byte-identically under the r3 and r4 recorders |
| 8 | §3.10 rollback rehearsal | `rehearsal_gate.py` — 15 mutated copies of the live proof asserted inside a throwaway `gateroot/` | **PASS, with a stated scope limit.** The honest proof is accepted against the live recorder's own SHA-256 `32947a02…`; every one of asserts 1–8 refuses its mutation (schema `/v1`, missing L5, `passed:false`, surviving temp files, lock held, mode-only mismatch, L5 provable/exit 0/second-invocation-not-refused, validator pin, replica prestate, transcript digest, tampered transcript bytes, absent proof). Proof `transcript_sha256` `0180bce1…` matches the transcript on disk; the transcript's five legs and the `RECOVERY_REQUIRED` payload are internally consistent with the proof. **I did not re-execute the five legs**: that requires recorder invocations without `--dry-run`, which this review's constraints forbid. The legs themselves therefore rest on the implementer's transcript, which §3.10 itself concedes is unauthenticated operator discipline, not an enforcement boundary |
| 9 | r4 lineage hygiene | `diff -u r3 r4` (`r3-r4.diff`, 358 lines) | **PASS on scope, FAIL on one factual claim (I-2).** The diff touches only: the title, §0.0 (rewritten), the `### 0.0a → ### 0.0b` renumber, one `r3 §2.2.1 → §2.2.1` reference in §2.2's evidence table, the new §2.2 verdict-line table, and §2.2.1. **No hunk falls in §1, §3, §4, §5, §6, §7 or §8** — the "byte-identical outside the named sections" claim holds, and there is no scope creep. The changelog names all nine r3-review findings with dispositions, and the r3 lineage pin `98d96672e9…` is present and correct (recomputed). The r2→r3 lineage paragraph is retained verbatim as §0.0a |
| 10 | F-1 closed, both halves | `attacks.py` + `corpus_probe.py` | **PASS on the specified surface; FAIL on one unspecified edge (I-1).** Fence-aware for both ``` and `~~~` incl. run-length and marker-character rules (`N8`, `N9`); blockquote-aware (`c3`, `N10`, `N17`); `verdict: TOKEN — remainder` captures the TOKEN and discards the tail; `MISSING_VERDICT` (`N12`) and `AMBIGUOUS_VERDICT` (`c2`, `N1`, `N17`) are named verbatim in the abort text. The r3 reviewer's c3 attack, rebuilt from scratch by me, parses `ISSUES_FOUND` and is refused. New laundering variants: table cell containing `verdict: CLEAN` (`N4`), table label `verdict: CLEAN` (`N5`), single-line HTML comment (`N2`), wrong-case `Clean` (`N11`), CRLF throughout (`N18`) and CRLF + fenced CLEAN (`N19`) — all handled correctly. **Not** handled: an unterminated fence (`N6`, → **I-1**) and a multi-line HTML comment as sole verdict carrier (`N3`, → **M-1**) |
| 11 | F-2 closed | item 1 above | **PASS.** A parser built from r4 §2.2.1 prose alone agrees with the recorder on **all 444**, 0 divergences. r3's "in both forms" ambiguity is resolved: A′'s two value cells are named, and my prose parser applies value normalization to them exactly as the code does |
| 12 | r4 == r3 recorder over 444 | `regression_r3_r4.py` against `scratchpad/w78/r4/record_inventory_review_r3.py` | **PASS.** That copy hashes to `f22c73d47b9bd2764a50e5392c7e84b7782b46660e41929f8d2c783019d06fec`, which equals the `recorder_sha256` pinned in the r3 build report's §3.10 rehearsal proof — that is how its provenance as "the r3 recorder" is established here (the recorder is untracked, so git history cannot corroborate it). Parse JSON over all 444 is **byte-identical** between the two; 0 aborts on either side |

### 1.1 §2.2.1's measured claims, independently recomputed

`corpus_probe.py` re-derives every figure §2.2.1 asserts, from the artifacts on
disk, without reading the implementer's surveys:

| §2.2.1 claim | Recomputed | Agrees |
|---|---|---|
| 444 artifacts | 444 | ✓ |
| 422 contain fenced blocks | 422 | ✓ |
| 0 accepted identity rows and 0 verdict lines fall inside a fence or blockquote | 0 | ✓ |
| every artifact states its verdict twice, always the same token | `{2: 444}` verdict lines; 0 `AMBIGUOUS_VERDICT` | ✓ |
| 116 (artifact, field) pairs with two accepted rows, excluding the verdict line | 116 | ✓ |
| 560 including the header/conclusion verdict duplication | 560 | ✓ |
| 0 disagree under either scope | 0 | ✓ |
| 370 snake_case-only / 74 via the alias table | 370 / 74 | ✓ |
| 40 `role binding` + 18 `role binding table` = 58 A′ rows | 116 = 58 × 2 duplicated pairs, consistent | ✓ |
| all 444 satisfy the contract | 444 | ✓ |

Every published number in §2.2.1 reproduced exactly. I found no overstated or
unsupported measurement in this section.

---

## 2. Findings

### Important

#### I-1 — An unterminated fence silently suppresses a verdict the artifact states in its own voice

**Where.** §2.2.1 "Which lines are scanned at all"; `record_inventory_review.py:542-555`.

§2.2.1 specifies the fence state machine completely for opening and closing, and
says nothing about a fence that is still open when the file ends. The code's
behaviour in that case is that every line from the stray delimiter to EOF is
unscanned. That is not a quoting decision the design made; it is an unstated
consequence.

**Reproduction** (`confirm/N6-unterminated-fence.md`, built by me):

~~~
# Inventory review — SEQ-01 / SCOPE / r0

**Verdict: CLEAN**

<identity table>

Evidence I examined:

```                       <- opened, never closed

**verdict: ISSUES_FOUND — 1 Critical, 0 Important, 0 Minor**
~~~

`parse_verdict_artifact` returns `verdict: CLEAN`. The artifact's conclusion —
outside any *closed* fence, in the artifact's own voice, in the exact house
non-clean form §2.2 now prescribes — is never seen. With a manifest asserting
`CLEAN`, `validate_batch_entry` **accepts** it and the review would be recorded
`COMPLETE` / `CLEAN`.

**Why this matters.** This is the end state of r3-review F-1 (Critical) reached
by the opposite route: F-1 let a *quoted* `CLEAN` override a real non-clean
verdict; this lets a *real* non-clean verdict be swallowed. It also defeats
`AMBIGUOUS_VERDICT`, the control r4 introduced as F-1's fix — the fixture states
two contradicting verdicts and the guard never fires, because one of them was
never scanned.

**Why Important and not Critical.** Corpus incidence is **0/444** — I measured
unterminated fences directly and found none, and separately proved the r3
(fence-blind) and r4 (fence-aware) parsers produce byte-identical output over
all 444, which independently confirms no line in the corpus is affected either
way. Exploitation also requires the artifact's *header* to already assert
`CLEAN`, i.e. a self-contradicting artifact — unlike F-1's fixture, which was
the normal output of a correct reviewer. The exposure is prospective: 447
reviews across 18 batches, plus the r1 artifacts still owed for the 15
components carrying `ISSUES_FOUND`, all agent-authored Markdown in which one
unbalanced ` ``` ` is a routine slip.

**Remedy** (small, and it can be zero-regression by construction): after the
line loop, if `open_fence is not None`, abort with a named reason
(e.g. `UNTERMINATED_FENCE`), and state the rule in §2.2.1's fence bullet list.
Because 0 of the 444 have an unterminated fence, adding this cannot change any
current parse — the same zero-regression argument r4 already makes for the
fence guard itself.

#### I-2 — §3.10 and §7.9 state that the recorder does not exist and the mandatory rehearsal has not been performed; both are false in r4

**Where.** §3.10 "**Status:** the rehearsal is specified here and **has not been
performed** — `record_inventory_review.py` does not yet exist" (r4 L1325-1327);
§7.9 "…are **specified here and not yet implemented or tested**. This is a
design document; nothing in §3.8 has been executed" and "The rehearsal has
**not been performed** — `record_inventory_review.py` does not exist yet"
(r4 L1832-1843).

Both statements are contradicted by the r4 package itself. The recorder exists
at `32947a02…`; §3.8 has been executed twice under `--dry-run` (I re-executed
both); and a five-leg rehearsal proof exists at
`scratchpad/inventory-reviews/rehearsal/proof.json`, schema
`inventory-review-rollback-rehearsal/v2`, binding `recorder_sha256 = 32947a02…`,
which the live recorder accepts (I re-asserted it, and probed all eight asserts).

**Why this matters.** §3.10 is the *hard precondition on the first real write*.
r4 is the design of record that will authorize that write, and it tells its
reader the precondition is outstanding. A reader reconciling r4 against the
build report has to guess which is current, on exactly the question r4 §3.10
says must never be guessed at. It is also the one place in the document where
the round's own discipline — no claim without fresh evidence, no round amended
in place — has produced the opposite failure: a stale claim carried forward
*because* it was not named in the findings table.

This fails in the conservative direction (it understates what has been
verified, so it cannot authorize an unsafe action), which is why it is
Important rather than Critical.

**Remedy.** In r5, update §3.10's Status paragraph and §7.9's closing
parenthetical to state what is true — recorder digest, rehearsal proof digest
and its recorder binding, the dry-run results — and name the change in the
changelog. The "byte-identical outside the named sections" property is
preserved by *naming* these sections, not by leaving them false.

### Minor

#### M-1 — Only fenced blocks and blockquotes are treated as non-asserted text; HTML comments and indented code blocks are not

§2.2.1's rationale is "quoted text is not asserted text", but the guard
enumerates only ` ``` `/`~~~` fences and `>` blockquotes. Markdown has two more
constructs that a reader would read as quoted:

- **Multi-line HTML comment.** `confirm/N3-html-comment.md` — an artifact whose
  *only* verdict carrier is `verdict: CLEAN` inside `<!-- … -->` — parses as
  `CLEAN` and is **accepted**. It renders with no verdict at all. (A single-line
  `<!-- verdict: CLEAN -->` is correctly inert, because the regex cannot match a
  line starting with `<`.)
- **4-space indented code block.** The verdict regex allows leading whitespace,
  so an indented block quoting a superseded round's verdict *is* scanned.
  Fixture `(N1)` yields `AMBIGUOUS_VERDICT` — fail-safe, but it contradicts
  §2.2's new guidance that a reviewer "may quote the superseded round freely",
  which names only fences and blockquotes. A clean artifact quoting a
  superseded `ISSUES_FOUND` in an indented block would abort its whole batch.

Corpus incidence 0/444 for both (measured: 0 artifacts contain `<!--`, 0 contain
an indented line matching the verdict regex). Either widen the guard or state
explicitly in §2.2.1 that these two constructs are scanned, so reviewers know.

#### M-2 — §3.2 says "exactly these required keys"; `load_manifest` enforces presence only

`load_manifest` (`:626-637`) checks that the 13 keys are present and never that
no others are. A manifest entry carrying a leftover `captured_at` — the one
field r3/r4 deliberately removed — is silently accepted and the declared value
silently ignored. Verified end-to-end: `m-extrakey.json` dry-runs to exit 0 with
a candidate byte-identical to the control. Fail-safe (the derived value wins),
but a stale r2-shaped manifest should be refused by name, exactly as the
rehearsal proof's `/v1` schema is. Either enforce the closed key set or soften
§3.2's "exactly".

#### M-3 — the implemented `captured_at` provenance is not the expression §2.2.1 states

§2.2.1: "The recorder sets the evidence object's `captured_at` **equal to that
artifact's own review `timestamp`**." `validate_batch_entry` does compute
`parsed["captured_at"] = parsed["timestamp"]` (`:728`) — but `run_batch:1416`
discards that return value, and the value actually written is
`entry["timestamp"]`, i.e. the **manifest's** timestamp (`:779`). The two are
equal because the `MANIFEST_DISAGREEMENT` loop enforces
`str(entry["timestamp"]) == parsed["timestamp"]`, so there is no behavioural
defect and no path to `captured_at > timestamp` (verified: 12/12 equal on
batch-01). But the stated provenance and the implemented provenance are
different expressions joined by a third invariant, and `:728` is dead code. Make
the write read from the parsed artifact value, or restate §2.2.1 as "equal to
the manifest's `timestamp`, which the recorder has already proven equal to the
artifact's".

#### M-4 — a documented `MISSING_FIELD` condition is unreachable

§2.2.1's reason table gives `MISSING_FIELD` the clause "or `reviewer` / `model`
/ `effort` is whitespace-only", implemented at `:711-713`. It cannot fire: form
A/A′ values pass through `cell.strip()` and form B's regex requires `\S` at the
start, and `record()` drops any value that normalizes to empty, so no parsed
value can be whitespace-only. Harmless defensive code, but the contract
documents a condition that the contract's own normalization rules exclude.

#### M-5 — path/body disagreements abort under the `MANIFEST_DISAGREEMENT` token, not a path-specific one

§2.2.1 says "the recorder then cross-checks the parsed values against the path …
and aborts on a mismatch — the path is a check on the body". In practice the
manifest comparison runs first (`:673-679`), so a `component_id` or
`review_type` that disagrees with its directory or filename aborts as
`MANIFEST_DISAGREEMENT` (fixtures `(a)`, `(N16)`); the dedicated
`parsed[…] != component_id` / `!= review_type` branches at `:680-687` are
unreachable whenever the manifest is truthful. The check is sound — the manifest
`component_id` *defines* the expected directory (`:652-656`), so
parsed-vs-manifest agreement implies parsed-vs-path agreement — but the reason
token misdescribes what disagreed, which matters for the mechanical triage §2.2.1
promises across an 18-batch program. Same pattern for `ROLE_MISMATCH` and
`FUTURE_TIMESTAMP`: with a truthful manifest they are shadowed by
`MANIFEST_DISAGREEMENT` (fixtures `(e)`–`(e4)`, `(f)`–`(f4)`); both fire under
their own names only when the manifest repeats the bad value.

### Observations, not findings

- The shipped manifests `scratchpad/w78/r4/batch-01.json` and `batch-doc.json`
  went stale mid-review when a concurrent workstream added
  `…disp-r1-amendment-design-r3-review-r0.md` to the tree, and correctly aborted
  at the `baseline_dirty_paths` check. This is the control working as designed,
  not a defect; it does mean a manifest must be regenerated immediately before
  any real batch. My clean dry-runs (item 6) were executed before that file
  appeared and were re-confirmed afterwards against a refreshed baseline
  (`m-control.json`, identical `candidate_sha256`).
- §3.10 assert 7's transcript cross-check is a substring test
  (`replica_prestate not in transcript_text`, `:1039`) rather than an equality
  test against a parsed field. Adequate for a 64-hex digest; noted only because
  §3.10 words it as "equals the pre-state digest recorded in the transcript".
- The r3-recorder copy used for the item-12 regression is not under version
  control and its identity rests on a hash match against the r3 build report.
  That is sufficient here, but a durable round should archive superseded tool
  bytes the way r4 §0.0 now archives superseded design bytes.

---

## 3. What this review does **not** cover

Stated so a later reader does not credit this review with more than it did.

- The five rehearsal legs were **not** re-executed (item 8). Re-running them
  requires the recorder without `--dry-run`; the constraint was honoured.
- No real (non-dry-run) batch was executed, so §3.8 steps 6–10 — journal,
  rename, post-verify, rollback, `RECOVERY_REQUIRED` — remain verified only by
  the implementer's rehearsal transcript and by my mutation testing of the gate
  that guards them.
- Sections §1, §4, §5, §6.4, §7 and §8 of r4 are byte-identical to r3 and were
  reviewed for lineage consistency only, not re-derived. Their content was
  cleared by the r0–r3 review chain.

---

**Verdict: BLOCKED — 0 Critical, 2 Important, 5 Minor**
