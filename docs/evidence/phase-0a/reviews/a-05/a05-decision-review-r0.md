# A-05 Source-Rights Decision — Independent Adversarial Review (r0)

**Reviewer:** independent reviewer (did not author the artifacts under review)
**Reviewed at:** 2026-08-20
**Scope:** uncommitted working-tree changes under `docs/evidence/phase-0a/` vs `HEAD`

| Artifact | State |
| --- | --- |
| `docs/evidence/phase-0a/a-05-rights-decision-record.md` | new — `A05-DECISION-001` |
| `docs/evidence/phase-0a/a-05-source-rights-package.json` | modified — `1.0.0` → `1.1.0`, `PARTIALLY_DECIDED_REMAINDER_PENDING` |
| `docs/evidence/phase-0a/a-05-source-rights-package.md` | modified — `1.1.0` → `1.2.0` |
| `docs/evidence/phase-0a/a-05-retrieval-manifest-infy-fy25.json` | new — URLs, byte counts, SHA-256 only |

---

## Verdict

**ISSUES_FOUND — 1 critical / 3 important / 6 minor**

Nothing here blocks the substance of the decision; the mechanical integrity of the
package is genuinely good. The one critical is an attribution/scope problem on
`CHN-03`, not a fabricated permission on the Infosys sources.

---

## Independently verified clean

These were re-derived from scratch, not taken from the implementer's own checker.

- **Record digests.** Recomputed with `python3` using the stated convention (SHA-256 of
  UTF-8 canonical JSON, recursively sorted keys, `separators=(',',':')`,
  `ensure_ascii=False`, `record_digest` excluded). All four match:
  - `a-05-source-rights-package.json` internal `record_digest` = `sha256:542f34b6…` ✔ (canonical-payload digest)
  - `a-05-source-rights-package.json` **file** sha256 = `98d632888b8d9278cd8edec6970fd381326ce20aea173b39dc124bc88dca2bd8` ✔ — matches the value bound in the md payload and in `a-05-rights-decision-record.md:99`
  - `a-05-source-rights-package.md` payload digest = `486c5791e01743e9a106bdc8e258e8b6e2bc5e6413eb60782ad104bae244789f` ✔ = stated
  - `a-05-rights-decision-record.md` payload digest = `18de9f647abd52d2acbace42c3dc9bd7e96c7c83991260f54ad25a1c7438fe25` ✔ = stated
  - retrieval manifest **file** sha256 = `0394c9ab53b7bde3…` ✔ = the value bound in all three places
- **Preserved prior digests are real.** `git show HEAD:` of the two files reproduces
  `b6881bca…` (json@1.0.0) and `161196a3…` (md@1.1.0) exactly as cited at
  `a-05-rights-decision-record.md:20`.
- **`scratchpad/phase-0a/s2-prep/verify_s2.py` → `RESULT: ALL CHECKS PASS`, `EXIT=0`.**
- **Retrieval evidence is real and matches.** All 8 PDFs exist under
  `/data/codes/equity-os/data/raw/infy-fy25/`; every byte count and every SHA-256 in the
  manifest matches the file on disk (8/8). `data/` is gitignored
  (`.gitignore:10`), `git check-ignore` confirms, and `git status data/` is empty — the
  "must never be committed" claim holds today.
- **Fail-closed mechanics (re-derived independently of `verify_s2.py`).**
  132 unique cells; 72/42/18; 0 vocabulary violations; **0 `ALLOWED` cells lacking
  `decision_ref: A05-DECISION-001` or `authority_envelope: A05-DECISION-001`**;
  **0 `UNKNOWN` cells carrying a `decision_ref`** (all 18 carry
  `NOT_COVERED_BY_A05-DECISION-001`); `cells_decided_by_A05-DECISION-001` = 114 = 72+42.
- **No source-level blanket access.** All 11 sources carry
  `source_level_access_decision: "NONE_RECORDED"`; `widening_check` reports 0/0 truthfully.
- **md ↔ json grid drift: zero.** Parsed the md grid independently (11 rows × 12 cells =
  132) and compared every cell to the json disposition — 0 drifting cells.
- **No contradiction with A-01 / A-02 / the inventory.**
  `source-package-inventory.json` provenance says "No source bytes fetched… **by this
  task**", which is still true and is not falsified by the later authorized fetch.
  A-01's prohibition of public/paid/personalized/execution-linked modes is restated,
  not weakened, at `a-05-rights-decision-record.md:88-89`.
- **Decision fidelity on the load-bearing points.** Verbatim statement (1) ("we can use my
  suggested libs") is correctly recorded as **superseded** and the libs are held/denied —
  this was the easiest place to over-read the decider and the record does not.
  Decider identity, self-assumed mandate, "no legal credential claimed", "no legal review
  performed or obtained", "no review cadence set", NSE decided-deny, BSE decided-deny,
  D-5 answered, D-6 answered, D-3/D-4 explicitly still open: all faithful.

---

## Issues

### C-1 (CRITICAL) — `CHN-03` allow-set is broader than the SEC decision, and the extension is not disclosed

**Files:**
- `docs/evidence/phase-0a/a-05-source-rights-package.json:4612` (`DB-04.applies_to`)
- `docs/evidence/phase-0a/a-05-source-rights-package.json:4614` (`DB-04.rationale`)
- `docs/evidence/phase-0a/a-05-rights-decision-record.md:27`
- `docs/evidence/phase-0a/a-05-source-rights-package.md:160`

The decision on SEC EDGAR is *automated access within SEC fair-access limits* plus
*enters the source list* (answering D-5). The record grants **eight** operations for
`CHN-03` — `OP-01, OP-02, OP-03, OP-05, OP-06, OP-07, OP-08, OP-12` — i.e. it also grants
retention of source bytes, fact extraction, derived outputs, LLM/machine processing,
source-location capture, and hashing. Those six were carried over by analogy from the
Infosys allowance; the decider spoke to access, not to them.

Worse, `DB-04.rationale:4614` asserts them as spoken:

> "The product owner allowed automated access to SEC EDGAR … **together with retention and internal processing**, and added CHN-03 to the source list"

This breaks the record's own rule, stated one basis earlier at
`a-05-source-rights-package.json:4604` (`DB-03`):

> "**No disposition is inferred from the operations that were decided.**"

and the fail-closed rule's own "broader-than-evidence decisions are UNKNOWN". It is also
inconsistent with how the implementer handled every other inference: `DB-02` and `DB-05`
both explicitly flag "the decider did not separately distinguish… so the deny is applied
… fail-closed", and `DB-01` explicitly narrows `OP-02`. `DB-04` is the only basis that
silently widens.

Substantive legal risk here is low (SEC EDGAR filings are US-government material and the
SEC page quoted says "Anyone can access and download this information for free"), but the
record's value is faithful attribution, and this cell block attributes permissions to the
decider that the decider did not give.

**Fix (pick one, (a) preferred as it is what the record's own DB-03 rule demands):**

(a) Demote `CHN-03 × OP-03, OP-05, OP-06, OP-07, OP-08, OP-12` to
`UNKNOWN (denied by default)` under `DB-03-NOT-COVERED-UNKNOWN`, leaving `CHN-03` with
`OP-01`/`OP-02` `ALLOWED` and `OP-09`/`OP-10` `DENIED`. Grid becomes
**66 ALLOWED / 42 DENIED / 24 UNKNOWN**, `cells_decided_by_A05-DECISION-001` = 108, D-1
"108 of 132". Update the md grid row, the DB table, `counts`, `open_decisions[D-1]`, the
decision record's Dispositions table and `cell_counts`, then re-digest all three files.

(b) Keep the eight `ALLOWED` but rewrite `DB-04.rationale`, `a-05-rights-decision-record.md:27`
and `a-05-source-rights-package.md:160` to say plainly that only *automated access within
SEC fair-access limits* and *entry into the source list* were decided, and that
`OP-03/05/06/07/08/12` are recorded ALLOWED as the recording agent's entailment of "enters
the source list" for an internal-research register — flagged in the same words `DB-02` and
`DB-05` use for their inferences.

---

### I-1 (IMPORTANT) — `source_bytes_held` is still `false` on all eight Infosys sources, and it is now untrue

**File:** `docs/evidence/phase-0a/a-05-source-rights-package.json:288, 311, 334, 357, 380, 403, 426, 449`

Every source object still carries `"source_bytes_held": false`. For `SRC-01 … SRC-08` this
is now false-as-in-wrong: the bytes are held (verified — 8 PDFs on disk, digests matching
the manifest). It directly contradicts, in the same file,
`declarations.source_content_fetched_or_hashed: true` and the whole `authorized_retrieval`
block.

This is the same class of stale-false the implementer correctly flipped at the top level
(judgment call **d**) — it was just missed one level down. The `authorized_retrieval.note`
disclaimer covers only `source_content_digest_state`, not `source_bytes_held`, so this is
an oversight, not a disclosed choice.

**Fix:** set `source_bytes_held: true` for `SRC-01 … SRC-08` (leave `CHN-01/02/03` false),
re-digest the json, and update the three places that bind its file digest
(`a-05-source-rights-package.md` payload, `a-05-rights-decision-record.md:99`
`updated_artifacts`, and both stated record digests). If the field is *meant* to be scoped
to "held in the repository", say so in its own note — but it currently reads as a plain
fact and is wrong as read.

---

### I-2 (IMPORTANT) — md claims the supporting per-cell fields "stay `UNKNOWN` elsewhere"; all 18 UNKNOWN cells contradict it

**Files:** `docs/evidence/phase-0a/a-05-source-rights-package.md:166-169` vs the 18
`UNKNOWN` cells in `normalized_disposition_grid`

The md says:

> "Supporting per-pair fields … now carry the decided values for every decided cell and
> **stay `UNKNOWN` elsewhere**."

Verified: **18 of 18** `UNKNOWN (denied by default)` cells carry non-`UNKNOWN` values for
`access_method`, `automation`, `retention`, `transformation_derived_output`, and
`redistribution`. Concretely, the `SRC-01 × OP-04` (caching) cell — a cell whose whole
point is that caching is *not* decided — displays `"retention": "ALLOWED — internal
retention of retrieved source bytes for private research"` and
`"transformation_derived_output": "ALLOWED — internal derived facts and claims only"`.

Two defects in one: md↔json factual drift (dimension 5 requires zero), and a fail-closed
readability hazard — a downstream consumer reading a single undecided cell sees `ALLOWED`
strings sitting next to `disposition: "UNKNOWN (denied by default)"`.

**Fix:** the fields are a source-level envelope repeated per cell, so either
(i) reword md:166-169 to say exactly that — the envelope fields describe the source's
decided envelope and are repeated on every cell of that source, and `disposition` is the
only authoritative per-cell value — and add a matching `field_scope` note in the json; or
(ii) null the envelope fields on the 18 `UNKNOWN` cells. (i) loses no information and is
cheaper.

---

### I-3 (IMPORTANT) — Infosys `OP-05` and `OP-12` are presented as spoken permissions, not as the entailments they are

**Files:**
- `docs/evidence/phase-0a/a-05-rights-decision-record.md:26`
- `docs/evidence/phase-0a/a-05-source-rights-package.json:4584` (`DB-01.rationale`)

This is judgment call **(c)**. The disposition itself is **sound** — `OP-05`
(source-location capture) was already performed in S1 and confers nothing new, and `OP-12`
(hashing) is directly entailed by an instructed fetch whose per-file SHA-256s the decider
was shown. The problem is presentation. The decision record line 26 folds "source-location
capture, content digesting" into the list of what the decider allowed, and `DB-01.rationale`
lists retrieval, retention, AI processing, and derived facts but **never mentions OP-05 or
OP-12 at all** — yet `DB-01.applies_to` includes both. The entailment was flagged honestly
to this reviewer; it is not flagged anywhere in the artifacts a future reader will have.

**Fix:** append one clause to `DB-01.rationale` and one parenthetical to
`a-05-rights-decision-record.md:26`, e.g. "`OP-05` (source-location capture) and `OP-12`
(content digesting) are recorded `ALLOWED` as direct entailments of the instructed
retrieval and of the manifest digests the decider was shown, not as separately spoken
permissions." No disposition change needed.

---

### M-1 (MINOR) — `CHN-01 × OP-01` `DENIED` states more than the NSE decision

**Files:** `docs/evidence/phase-0a/a-05-rights-decision-record.md:28`,
`docs/evidence/phase-0a/a-05-source-rights-package.md:162`,
`a-05-source-rights-package.json` `DB-06.conditions_and_limits`

The decider denied *all automated collection* from NSE and placed human browsing *out of
scope*. "Out of scope" is not "denied", but the grid marks `CHN-01 × OP-01` (human
interactive access and reading) `DENIED`, which literally says a person may not read a
public NSE page. Narrowing, fail-closed, and **fully disclosed** in all three artifacts
(`DB-06.conditions_and_limits` says exactly this) — hence minor.
**Fix:** add `"out_of_scope_not_denied": true` (or an equivalent note field) to the
`CHN-01 × OP-01` cell so the caveat travels with the cell, not only with the basis.

### M-2 (MINOR) — `fail_closed_rule` in the json is stale and no longer matches the md

**File:** `docs/evidence/phase-0a/a-05-source-rights-package.json:45`

Still reads "…except for operations a competent authority independently marks ALLOWED **in
a successor version**." The decision did not arrive as a successor version; it arrived as a
separate decision record. The md's parallel sentence *was* updated to "…the authority
independently marked `ALLOWED`, which are exactly the cells cited to `A05-DECISION-001`".
Phrasing-level md↔json drift.
**Fix:** conform the json string to the md wording.

### M-3 (MINOR) — the `OP-03` retention / `OP-04` caching boundary is not sharp enough to rely on before Q0

**File:** `docs/evidence/phase-0a/a-05-source-rights-package.json:62` and `:68`

`OP-03` is "Keeping the retrieved file beyond transient display, in any store"; `OP-04` is
"Any intermediate, proxy, or **reuse cache** of the source or its bytes." Q0 will re-read
`data/raw/infy-fy25/*.pdf` rather than re-fetch. That is retention under one reading and a
reuse cache under the other — and `OP-04` is `UNKNOWN`/denied. Leaving `OP-11` (judgment
call **e**) `UNKNOWN` is unambiguously correct; `OP-04` is not, purely because of this
definitional overlap.
**Fix:** one disambiguating clause in the `OP-04` scope, e.g. "`OP-04` means an
*additional* intermediate/proxy/CDN or shared reuse cache; a single retained local copy
under `OP-03` re-read by the same principal is `OP-03`, not `OP-04`."

### M-4 (MINOR) — the HELD scope is ambiguous about non-exchange repositories in §6

**Files:** `docs/evidence/phase-0a/a-05-rights-decision-record.md:30`,
`a-05-source-rights-package.json` `held_pending_q0_review.items[2]`

"the candidate repositories listed in `docs/research/external-tools-and-repos-inventory.md`
§6 (`nsepython`, `nselib`, `jugaad-data`, `NseIndiaApi`, `BseIndiaApi` **and similar**)"
reads as all 14 §6 rows, while the parenthetical names only exchange wrappers. §6 rows 1,
2 and 10 (`FinceptTerminal`, `machine-learning-for-trading`, `openscreener`) are not
exchange wrappers or aggregator clients.
**Fix:** state whether the hold is "all 14 rows of §6" or "the ⛔-marked rows of §6 plus
Screener.in and Tijori".

### M-5 (MINOR) — the file the hold points at still says the opposite

**File:** `docs/research/external-tools-and-repos-inventory.md:167` and `:192`

The record says the hold "stays discoverable" via `held_pending_q0_review`, but the
inventory it directs readers to still says "All entries below are **CANDIDATE-UNDECIDED**"
(:167) and "**No item in §5 or §6 has a recorded decision**" (:192). Both are now false.
Outside the reviewed file set, but it is a cross-reference this record leans on.
**Fix:** one line in §6/§7 pointing at `A05-DECISION-001` and its HELD disposition.

### M-6 (MINOR) — the standalone decision record never says the S1 inventory was left unamended

**File:** `docs/evidence/phase-0a/a-05-rights-decision-record.md:67-73`

Reviewed against the brief's explicit test — *"check this is stated clearly, not hidden"* —
the non-amendment **passes**: it is stated in four places
(`a-05-source-rights-package.md:56-62`, its Downstream-effect bullet,
`a-05-source-rights-package.json` `authorized_retrieval.note`, and `open_decisions[D-4].note`),
each saying the per-source `source_content_digest_state` continues to mirror the unamended
S1 inventory and that the real digests live in the manifest. Nothing is hidden. The one gap
is that `a-05-rights-decision-record.md` — the document most likely to be read alone —
says only that the manifest carries digests, never that `source-package-inventory.json`
still reports `UNKNOWN` and still carries status
`METADATA_ONLY_BLOCKED_FOR_SOURCE_RIGHTS`.
**Fix:** one clause at :72, e.g. "`source-package-inventory.json` is deliberately not
amended: its per-source digest state stays `UNKNOWN` and the real content digests live only
in this manifest."

---

## Adjudication of the five flagged judgment calls

| # | Call | Verdict |
| --- | --- | --- |
| **(a)** | `OP-09` internal redistribution `DENIED` rather than `UNKNOWN` for Infosys/SEC | **Sound and honestly recorded.** Both `DB-02` and `DB-05` state in terms that the decider did not distinguish internal from external redistribution and that the deny is applied to both fail-closed. It is a narrowing, not a broadening, and the practical difference from `UNKNOWN` is nil (both denied). Marginal note: it counts 9 inferred cells inside the 114 "decided" total — acceptable because the inference is disclosed at the basis. |
| **(b)** | `OP-02` Infosys `ALLOWED` but conditioned to the one-time fetch; standing retrieval `UNKNOWN` | **Sound and honestly recorded.** The cell itself carries `automation: "HUMAN_DIRECTED_ONE_TIME_ONLY — … standing, scheduled, recurring, or crawling automation is UNKNOWN and denied"`, and `DB-01.conditions_and_limits` repeats it and names the manifest as the evidence of the single authorized execution. This is the correct shape: the permission is real but not standing, and the condition travels with the cell rather than living only in prose. |
| **(c)** | `OP-05` capture and `OP-12` hashing `ALLOWED` as entailed | **Disposition sound; recording not honest enough.** See **I-3**. Fix by disclosure, not by changing the cells. |
| **(d)** | `source_content_fetched_or_hashed` flipped `false`→`true`; `records_a_rights_decision: true` added while `is_a_rights_decision: false` retained | **Sound and correct.** The flip is the truthful move and the right instinct — a declaration that had gone stale was corrected rather than defended. The `is_a_rights_decision: false` + `records_a_rights_decision: true` + `grants_or_implies_permission: false` + `permission_source` quartet is precisely right: this file transcribes a decision, the decision record makes it. Only defect is that the same truthfulness pass missed `source_bytes_held` one level down (**I-1**). |
| **(e)** | Caching (`OP-04`) and commercial use (`OP-11`) left `UNKNOWN` | **Correct, and the single most important thing the record got right.** The decider was silent on both; silence is `UNKNOWN`; `DB-03` says so and refuses to infer. `OP-11` is additionally A-01-prohibited, so nothing turns on it. `OP-04` carries the small definitional caveat in **M-3**, which is about op vocabulary, not about the judgment. |

---

## Recommended disposition

Fix **C-1** and **I-1** before committing (both change the json and therefore every bound
digest — do them in one pass and re-run `verify_s2.py`). **I-2** and **I-3** are text-only
and should ride along. **M-1 … M-6** can be folded into the same pass or deferred, but
**M-3** should be settled before Q0 begins reading `data/raw/`.

Note for whoever fixes this: `scratchpad/phase-0a/s2-prep/verify_s2.py` currently asserts
`72 / 42 / 18` and "Infosys and SEC allow-set matches the decision". If **C-1** is fixed via
option (a), that checker must be updated in the same commit or it will fail — and its
`[PASS] Infosys and SEC allow-set matches the decision` line is precisely the assertion
that encodes the C-1 error, so it should be updated deliberately rather than relaxed.
