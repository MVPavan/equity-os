# Independent review — inventory-review recording design r3 + recorder (bead `eqos-w78`)

## 0. Reviewer identity and independence

| Field | Value |
|---|---|
| Role | `REVIEWER` |
| `role_binding_path` | `CONTEXT.md` |
| `role_binding_sha256` | `8f2795af93ba6bf5303cf13227b8ce9e96295269887673a3a8b97d920b3198ce` |
| Model actually invoked | `claude-opus-5` |
| Effort actually invoked | `high` — the CONTEXT.md `REVIEWER` binding as dispatched. The harness effort setting is **not readable from inside the session**, so this is the dispatched value, not a value I measured. Flagged rather than asserted. |
| Review start (UTC) | `2026-08-17T14:17:55Z` |
| Review end (UTC) | `2026-08-17T14:28:51Z` |
| Review round | `r0` of the r3 artifact |

**Independence statement.** I authored no part of this package: not design r0/r1/r2/r3,
not `record_inventory_review.py`, not the rehearsal harness, not any of the 444
verdict artifacts, not the batch manifests. I am an independent agent and context,
distinct from the `IMPLEMENTER` dispatch that produced r3 and the recorder, and
distinct from the r0, r1 and r2 reviewers (goal L947-949, CONTEXT.md L137-139).
Every number below was recomputed in this session under
`scratchpad/w78/review/`; nothing is transcribed from the design, the build
report, or the bead. Where a number came out equal to the design's, I say so and
show how I got it.

### 0.1 Target hashes — recomputed at start and at end

| Path | SHA-256 at `14:17:55Z` | SHA-256 at `14:28:51Z` |
|---|---|---|
| `docs/goals/reviews/ledger/equity-os-blueprint-inventory-review-recording-design-r3.md` | `98d96672e9eec34f8b9698246257b6acc4b81d8113894d66e1105cbd188b61cc` | **identical** |
| `scripts/equity_os_blueprint/record_inventory_review.py` | `f22c73d47b9bd2764a50e5392c7e84b7782b46660e41929f8d2c783019d06fec` | **identical** |

Both match the task brief. Supporting pins re-measured and matching §1.1:
`CONTEXT.md` `8f2795af…`, canonical ledger `de236d7e…` (unchanged before and
after every probe below), r2 `adf908ac…`, r2-review `668a524b…`.

**Constraint compliance.** No canonical file edited. No file under
`docs/goals/reviews/ledger/inventory/` read-modified or written. The recorder
was run **only** with `--dry-run`. No commit, no Beads write (`bd --readonly`
only). The only file I created outside `scratchpad/` is this report. `git status`
outside `scratchpad/` at the end is byte-for-byte the session-start set plus
this report.

---

## 1. Per-item verification

| # | Item | Method (my own probes) | Result |
|---:|---|---|---|
| 1 | §2.2.1 contract == code | Wrote `scratchpad/w78/review/spec_parser.py` from §2.2.1 **prose only**, diffed against `parse_verdict_artifact` over all 444 artifacts | **444/444 identical, 0 divergences** under my primary reading; **58 divergences** under a second defensible reading of the value-normalization clause → **F-2 (Important)** |
| 2 | Ambiguity / laundering attacks (a)–(f) | 34 crafted fixtures under `scratchpad/w78/review/fakeroot/`, driven through `validate_batch_entry` | (a) (b) (d) (e) (f) all rejected with a documented reason; **(c) has an accepted laundering path → F-1 (Critical)** |
| 3 | `captured_at` provenance | Read the assertion; traced every write path; recomputed a batch | `validate_ledger_structural.py:346-349` is `timestamp >= captured_at` — **`>=`, equality accepted**; `:219` is `captured_at <= validation_now`. Recorder sets `captured_at` = the *same string* as `timestamp` (`record_inventory_review.py:661`, `:712`), so `captured_at > timestamp` is unreachable. **PASS** |
| 4 | Digest correctness | Rebuilt both batch candidates with the structural validator's own `ast`-extracted projections, independently of the recorder's transcribed copies | independent `candidate_sha256` = `b1689280…` (batch-01) and `b85b8efe…` (batch-doc) — **bit-identical to the recorder's dry-run output** |
| 5 | Manifest schema §3.2 vs code | Compared `load_manifest` key sets, checked both manifests, traced `ledger_prehash_sha256` / `baseline_dirty_paths` | **PASS** — top level and the 13 entry keys match §3.2 exactly; `captured_at` absent from both manifests and never read; prehash enforced at step 2 *and* re-compared as a CAS immediately before the rename (`:1478-1484`); the dirty-set check is real (it aborted my first run because the tree had drifted since the manifests were built) |
| 6 | Dry-run batch-01 and batch-doc | Regenerated manifests against the current tree, ran both with `--dry-run` | **exit 0** both. batch-01: pending 447→435 (−12), batch-doc: 447→429 (−18), `stale_after` 0, `structural_candidate_exit` **0**, `committed: false`, `dry_run: true`. Ledger SHA-256 `de236d7e…` **unchanged**; no temp file, journal, or lock residue |
| 7 | 370 strict-form regression | Re-parsed all 444 with the alias table and form A′ **disabled**, diffed field-by-field against the r3 parser | **370 parse strictly, 74 require r3 aliases, 0 of the 370 parse differently.** The r3 amendment is purely additive |
| 8 | §3.10 rollback rehearsal | Re-ran `rehearse.py` myself into my own replica base, after backing up and then byte-restoring the implementer's proof | **all five legs pass, exit 0**, zero non-volatile differences from the implementer's proof. L1 commits (447→435), L2/L3/L4 roll back with bytes **and** mode matching the preimage, L5 reaches `RECOVERY_REQUIRED` and the second invocation is refused at step 1. `assert_rehearsal_proof` accepts the stored proof against the current recorder digest |
| 9 | r2→r3 lineage hygiene | Full `diff` of r2 against r3 | **4 hunks, 3 deleted lines total** (title; the §0.0 lead sentence; the `captured_at` evidence row). Everything else is pure insertion: §0.0, the amended §2.2 row, the new §2.2.1, the new §3.2 manifest paragraph. Exactly what §0.0 claims — **no scope creep**. The "amended in place / still r3 / still UNREVIEWED" note is present at r3 L17-22. See F-9 for the one part I could not verify |

### 1.1 Design claims I re-measured

| r3 claim | My measurement | Verdict |
|---|---|---|
| 444 parse, 0 do not | 444 / 0 | ✅ |
| 370 snake_case + 74 alias cohort | 370 / 74 | ✅ |
| 58 of the 74 carry the three-cell role-binding row | 58 | ✅ (but see F-4) |
| 424 `CLEAN`, 20 `ISSUES_FOUND` | 424 / 20 | ✅ |
| 15 components carry ≥1 `ISSUES_FOUND` | 15 | ✅ |
| `DISP-R-1` has no `r0` artifact | the only canonical row with no artifact directory | ✅ |
| 116 (artifact, field) pairs with two accepted rows, 0 disagree | 116 **excluding** the verdict line; 560 including it; 0 disagree either way | ⚠️ F-5 |
| `ARTIFACT_LABEL_ALIASES` / `ARTIFACT_ROLE_BINDING_ROW3_LABELS` "literally equal" to the §2.2.1 table | transcribed the design table by hand and compared: **equal**, and `ARTIFACT_FIELDS` is in the §2.2.1 order | ✅ |
| Every listed alias was measured in the 444 | all reached except the 2-cell `verdict` alias (0 artifacts) | ⚠️ F-6 |

---

## 2. Findings

### Critical

**F-1 — A non-CLEAN verdict artifact can be recorded as a `CLEAN` review. The
`NOT_CLEAN` skip reason is defeatable.**
*Where:* `record_inventory_review.py:162-165` (`ARTIFACT_VERDICT_RE`) and
`:523-543` (the line loop); r3 §2.2.1 "The verdict line" and the
`NOT_CLEAN` row of the skip-reason table.

Two unstated properties combine:

1. `ARTIFACT_VERDICT_RE` is anchored at both ends and accepts **only** a bare
   token: `verdict: <TOKEN>`, optionally bold-wrapped. It therefore does **not**
   match this repository's other established verdict form — the one this very
   report is required to end with. Measured in
   `docs/goals/reviews/ledger/*.md`, all of these exist today and **none**
   matches: `Verdict: BLOCKED — 0 Critical, 1 Important, 5 Minor`,
   `Verdict: BLOCKED — 1 Critical, 3 Important, 6 Minor`,
   ``**Verdict: `ISSUES_FOUND` — the inventory-review transition is not authorized.**``.
2. The parser is **Markdown-fence- and blockquote-blind**. §2.2.1 claims to be
   "the **whole** contract … Anything not stated here is not parsed", but says
   nothing about fenced blocks, and the code has no fence state. 422 of the 444
   artifacts contain fenced blocks.

*Failure scenario, executed:* `scratchpad/w78/review/c3.md` — an artifact whose
only human-visible verdict is
`**Verdict: ISSUES_FOUND — 1 Critical, 0 Important, 0 Minor**`, and which quotes
the superseded round in a fenced block containing the line `verdict: CLEAN`.
`parse_verdict_artifact` returns **`verdict = CLEAN`**; `validate_batch_entry`
**accepts** it; `build_candidate` writes `"verdict": VERDICT_CLEAN` and a
`COMPLETE` review object. No abort, no named reason, exit 0. §2.2.1's stated
guarantee — "An artifact that contradicts itself about its own identity is not
evidence of anything" — does not hold, because the contradiction is invisible to
the regex.

*Why this is live, not theoretical.* §2.2 specifies a line format **only for the
clean case** ("an explicit `verdict: CLEAN` line"); the non-clean form is
unspecified anywhere in r0–r3, so a reviewer writing a non-clean artifact has no
format to conform to and the house `Verdict: X — N Critical, …` form is the
natural choice. The 15 components carrying `ISSUES_FOUND` are precisely the ones
that get a fresh `r1` review round next, and an `r1` artifact quoting its `r0`
predecessor is the ordinary case.

*Current blast radius: zero.* I verified both halves: all 444 existing artifacts
state the verdict as a bare `**verdict: X**`, and **0 accepted identity rows lie
inside a fenced block** across all 444. So fence-guarding the parser and widening
the verdict rule are a **zero-regression** hardening on today's corpus — I
re-ran the full 444-artifact diff to confirm the strict cohort is unaffected.

*What would close it (design decision, not mine to make):* (a) make the parser
fence- and blockquote-aware, and state that in §2.2.1; and (b) either specify the
non-clean verdict line format in §2.2, or widen the verdict rule to capture a
trailing `— …` remainder and treat the captured token as the verdict. Either
alone leaves half the hole open.

### Important

**F-2 — §2.2.1's value-normalization clause does not cover form A′; the contract
as written parses 58 of the 444 artifacts differently from the code.**
*Where:* r3 §2.2.1, "**Value normalization.** In both forms, in this order:";
code `:520-521` and `:532-533`.

§2.2.1 defines **three** extraction forms — A, A′, B — but the normalization
clause says "in **both** forms". Under the literal reading, the two value cells
of the three-cell role-binding row are not backtick-unwrapped. I implemented both
readings in my spec-derived parser and ran each over all 444:

| Reading of "both forms" | Divergences vs the recorder |
|---|---:|
| A′ cells normalized (what the code does) | **0** |
| A′ cells not normalized (literal prose) | **58** |

All 58 fail with `AMBIGUOUS_FIELD`, e.g. `DOC-01/SCOPE-r0.md`:
`role_binding_path: ["CONTEXT.md", "`CONTEXT.md`"]`. That is exactly the 58
artifacts §2.2.1 says "always agree" — they agree only *after* an unwrapping step
the prose does not authorize for that shape. An independent implementer following
§2.2.1 literally therefore rejects 13% of the corpus.

This matters because it is the same defect class the round exists to close: §0.0
states "A format contract that only one side of the interface has ever seen is not
a contract." A contract that yields a different answer than the code on 58
artifacts is not yet exactly the contract. The fix is one word (`both` → `all
three`, or naming A′ explicitly). Behaviour is unaffected — the **code** is the
correct side here.

### Minor

**F-3 — Five of the eight named skip reasons never appear in any abort message.**
§2.2.1: "In the current recorder every one of these is surfaced as a
`RecorderAbort` naming the file and the reason." Measured by grep over the
recorder and by driving each path to its abort:
`MISSING_FIELD`, `AMBIGUOUS_FIELD`, `MALFORMED_REVIEW_ROUND` are named;
`ROUND_FILENAME_MISMATCH`, `NOT_CLEAN`, `MANIFEST_DISAGREEMENT`, `ROLE_MISMATCH`,
`FUTURE_TIMESTAMP` are **not** — they abort with descriptive prose only
(e.g. `role must be REVIEWER`, `timestamp is in the future`). All eight paths are
reachable and all reject correctly; only the taxonomy is missing, which costs
mechanical triage across an 18-batch, 447-review program.

**F-4 — The A′ example label is stated as covering 58 artifacts; the literal
label covers 40.** §2.2.1: "`| Role binding | CONTEXT.md | 8f2795af… |` appears
in the input-hash tables of 58 of the 74". Measured: `role binding` appears in
**40**, `role binding table` in the other **18**. The alias table lists both, so
the 58 total is right and nothing mis-parses; the sentence just attributes all 58
to one of the two labels.

**F-5 — The "116 pairs with two accepted rows" figure silently excludes the
verdict line.** 116 is exactly 58 × 2 (the A′ role-binding duplications).
Counting every field, including the header/conclusion verdict duplication that
the same paragraph cites as its first example, the figure is **560**. 0 disagree
under either scope. State the scope, or use 560.

**F-6 — "Every string below was measured in the 444 artifacts" is not exactly
true.** The 2-cell `verdict` alias is reached by **0** artifacts — every one of
the 444 carries its verdict via the verdict line. §2.2.1 flags `review timestamp`
as reachable only via the parenthetical rule but does not flag `verdict` as
unexercised, and the table's parenthetical ("the verdict line is the usual
carrier") understates it: it is the *only* carrier.

**F-7 — An empty-valued accepted row is silently dropped, and §2.2.1 does not say
so.** `record()` returns early on `not value` (`:508-509`). Form A's `[^|]*` cell
can be empty, so `| Model actually invoked |  |` carries nothing rather than
carrying `""`. I tested both readings across all 444: **0 divergences either way**
today, so this is documentation-only — but it is another unstated rule inside a
section that claims "Anything not stated here is not parsed."

**F-8 — The supplied dry-run evidence cannot test `MANIFEST_DISAGREEMENT`.**
`scratchpad/w78/make_manifest.py:74-84` fills every manifest field by calling the
recorder's own `parse_verdict_artifact`, so the artifact-vs-manifest cross-check
is a tautology for `batch-01.json` and `batch-doc.json`. The implementer states
this plainly in the script docstring — this is a note for later readers, not a
concealment. I exercised the check independently (fixtures g2/g3/g4: a manifest
disagreeing on `verdict`, on `model`, and on `artifact_sha256` are each rejected)
and it works.

**F-9 — The "amended in place" scope claim is unverifiable from the artifacts on
hand.** §0.0 asserts the amendment is "confined to this §0.0 (change 4 and the
'Measured effect' paragraph) and to §2.2.1". The **r2→r3** claim I verified in
full (4 hunks, 3 deleted lines). The **pre-amendment-r3 → post-amendment-r3**
claim I cannot verify: no pre-amendment r3 snapshot or hash is retained anywhere
in the package. Amending a document in place without pinning the superseded
bytes removes the differential-review property r3 itself relies on for r2. Pin
the pre-amendment digest, or say the amendment scope is self-attested.

### Explicitly checked and **not** findings

- **`role_binding_sha256` is accepted as any lowercase 64-hex, never compared to
  `CONTEXT.md`.** Correct and required: §2.1 pins it as an immutable historical
  capture "never re-verified against current bytes". My fixture e5 (a valid-shape
  but wrong digest) is accepted by design.
- **`COMPONENT ID` in caps resolves.** Case-folding is step 4 of the documented
  normalization.
- **Dry-run creates and removes a dot-prefixed temp file in `docs/goals/`.**
  §3.8 step 4 specifies a same-directory temp; the `finally` block removes it. I
  confirmed no residue and an unchanged ledger digest after both dry-runs.
- **The register-row `SCOPE` slot.** `AUTH-REG-00x` are `authority_clause`, not
  `register_row`; my independent rebuild derived the applicable set from
  `row["kind"]` per `validate_ledger_preimplementation.py:200-204` and asserted
  agreement for every batched row.
- **No unaddressed predecessor findings.** `…-design-r2-review-r0.md` is
  `Verdict: CLEAN` with 0 Critical / 0 Important, so r3's delta is correctly
  driven by `eqos-w78` alone.

---

## 3. Assessment

The transaction machinery is in good shape and I could not break it: the digests
are reproducible bit-for-bit from the validator's own projections, the ordering
rule holds, `captured_at` is derived in exactly one place and equality is what the
validator wants, the dry-runs are clean and inert, and the five-leg rehearsal
reproduces independently including the `RECOVERY_REQUIRED` wedge. The r2→r3 diff
is genuinely surgical. The alias table is a faithful, closed transcription and it
is purely additive over the 370 strict-form artifacts.

The parsing contract is where it is not yet finished. F-2 shows §2.2.1 and the
code still disagree on 58 artifacts under a literal reading — the same
one-side-only-contract failure that produced `eqos-w78`. F-1 is the one that
blocks: the single field the whole gate turns on can be read as `CLEAN` from an
artifact that says otherwise, because the verdict rule accepts only one of the two
verdict-line forms this repository actually uses and the parser cannot tell
quoted text from asserted text. It costs nothing on today's corpus to close, and
the next review round is exactly where it would bite.

---

Verdict: BLOCKED — 1 Critical, 1 Important, 7 Minor
