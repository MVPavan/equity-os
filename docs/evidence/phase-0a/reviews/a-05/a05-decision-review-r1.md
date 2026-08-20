# A-05 Source-Rights Decision — Independent Adversarial Review (r1)

**Reviewer:** independent reviewer (did not author the artifacts under review)
**Reviewed at:** 2026-08-20
**Predecessor:** `scratchpad/phase-0a/reviews/a-05/a05-decision-review-r0.md` (1 C / 3 I / 6 M)
**Scope:** bounded r1 — (1) r0 fix verification, (2) digest recomputation, (3) checker
integrity, (4) md↔json cell drift, (5) the orchestrator's two inventory edits, (6) new
issues introduced by the fixes. r0-clean areas were not re-litigated.

---

## Verdict

**ISSUES_FOUND — 0 critical / 2 important / 3 minor**

All ten r0 findings are **genuinely fixed** — every one by correcting the underlying state,
not by relaxing an assertion or softening prose. The C-1 fix in particular was done the
fail-closed way (option (a): demote to `UNKNOWN`), which was the harder and better choice.
Both remaining IMPORTANTs are stale-restatement defects, one in the json, one in the
orchestrator's inventory edit; neither changes a disposition cell.

---

## 1. r0 fix verification — all 10 confirmed, none worked around

| r0 | Fix | Verified |
| --- | --- | --- |
| **C-1** | `DB-04.applies_to` → "OP-01 and OP-02 **only**"; six ops moved to `DB-03`. Independently confirmed from the grid: `CHN-03` = `A A U/D U/D U/D U/D U/D U/D D D U/D U/D`. `DB-04.rationale` now reads "The decider spoke to access; the retention, extraction, derived-output, machine-processing, capture, and hashing operations are **NOT** inferred from it"; `conditions_and_limits` adds "This basis authorizes access only". `DB-03.rationale` names CHN-03 explicitly as "deliberately not carried over from the Infosys allowance". `DB-04` cites only 2 cells. | **Fixed — option (a), the fail-closed route.** |
| **I-1** | `source_bytes_held`: `True` for SRC-01…SRC-08, `False` for CHN-01/02/03. Correct split — only the eight Infosys sources have bytes on disk. md payload gained `source_bytes_held_SRC-01_to_SRC-08: true`. | **Fixed.** |
| **I-2** | Re-ran my own sweep over all 10 envelope fields × every `UNKNOWN` cell: **0 leaks** (was 18/18 in r0, now 25/25 clean). Sample `CHN-03 × OP-03` is `UNKNOWN` on all ten. md:166ff rewritten to describe the actual behaviour ("neutral `UNKNOWN` on all 25 undecided cells… never displays an `ALLOWED`-looking string next to its `UNKNOWN` disposition"). | **Fixed — state corrected, not just the prose.** |
| **I-3** | Entailment disclosed in all three required places, in matching words: `DB-01.rationale`, `a-05-rights-decision-record.md:26`, and the md bases table — "recorded `ALLOWED` as **direct entailments of that instructed retrieval and of the manifest digests the decider was shown, not as separately spoken permissions**". Dispositions unchanged, as recommended. | **Fixed.** |
| **M-1** | `CHN-01 × OP-01` → `UNKNOWN`, `decision_ref: null`, envelope `NOT_COVERED`, sole basis the new `DB-08-NSE-HUMAN-BROWSING-OUT-OF-SCOPE`, whose rationale draws the right distinction ("Out of scope is not denied… no artifact in this program may rest on OP-01 against CHN-01"). This is a **stronger** fix than the r0 recommendation (I suggested a note field; they made the cell honest). Propagated to the NSE publisher-evidence paragraph and the decision record's NSE row. | **Fixed, better than proposed.** See **I-A** for one stale field left behind. |
| **M-2** | `fail_closed_rule` now "…except for the operations the authority independently marked ALLOWED, which are exactly the cells cited to A05-DECISION-001" — successor-version wording gone, json now matches md. | **Fixed.** |
| **M-3** | `OP-04` scope rewritten: "Any *additional* intermediate, proxy, CDN, or shared reuse cache of live-fetched source content. **Clarification, not a new permission:** a single retained local copy already covered by OP-03, re-read by the same principal, is OP-03 and not OP-04." The "clarification, not a new permission" hedge is the right instinct — it forecloses reading the disambiguation as a grant. Mirrored in md and in the Q0 downstream bullet. | **Fixed.** |
| **M-4** | `held_pending_q0_review` now carries `scope` (exact row numbers), 13 enumerated `items`, and `not_held_still_candidate_undecided` (3 named). Verified against §6: ⛔ rows are exactly 3,4,5,6,7,8,9,11,12,13,14 (11 rows); rows 1, 2, 10 are the three not held. Mirrored in the decision record and md. | **Fixed — ambiguity fully closed.** |
| **M-5** | `docs/research/external-tools-and-repos-inventory.md` §6 header and §7 rewritten; both now cite `A05-DECISION-001` and distinguish the 11 HELD rows from the 3 still-`CANDIDATE-UNDECIDED`. §7's "No item in §5 or §6 has a recorded decision" is gone. | **Fixed.** |
| **M-6** | `a-05-rights-decision-record.md:74-77` adds the clause, and it goes further than I asked — it names the stale status too: "its per-source `source_content_digest_state` stays `UNKNOWN` and its status stays `METADATA_ONLY_BLOCKED_FOR_SOURCE_RIGHTS`. The real content digests live only in this manifest." | **Fixed.** |

---

## 2. Digests — all four recomputed independently, all match

Recomputed with `python3`, same convention (SHA-256 of UTF-8 canonical JSON, recursively
sorted keys, `separators=(',',':')`, `ensure_ascii=False`, `record_digest` excluded):

| Artifact | Computed | Stated | |
| --- | --- | --- | --- |
| `a-05-rights-decision-record.md` payload | `4762d1976d36f2263247dbd41bff2f1a3c416bae9c141ee98a68ac484a3ec36b` | same | ✔ |
| `a-05-source-rights-package.json` canonical payload | `c53cbc8e420284203ed372951f672938501ca6e64e267825bfb7b0901b3d616a` | `record_digest` = same | ✔ |
| `a-05-source-rights-package.json` **file** sha256 | `9b2ef737f9b92bcb153d8fbb9c6d535892c911976e39750b30c7fa635c29ff9d` | bound in md payload **and** in the decision record's `updated_artifacts` | ✔ |
| `a-05-source-rights-package.md` payload | `b52ecce1d8db32addfd04bfe42f684a6ad2e5defbf37b70849555fe11d0fc7f1` | same | ✔ |
| retrieval manifest file sha256 | `0394c9ab53b7bde341ad38200ea0cf30565888fe700fcfd84d7840751b966d28` | unchanged, bound in all three | ✔ |

Prior digests preserved correctly: md carries v1.1.0 (`161196a3…`) **and** v1.0.0
(`6880c2a1…`); the decision record still cites `json@1.0.0` `b6881bca…` / `md@1.1.0`
`161196a3…` as the evidence version decided against — correct, since the decision was made
against that state and must not be re-pointed at the record it produced.

---

## 3. `verify_s2.py` — ALL PASS, exit 0, and the C-1 assertion was **strengthened**

`RESULT: ALL CHECKS PASS`, `EXIT=0`.

The r0 note warned that the checker's `[PASS] Infosys and SEC allow-set matches the
decision` line was the assertion encoding the C-1 error, and that it must be updated
deliberately rather than relaxed. It was **split and strengthened**:

- `[PASS] Infosys allow-set is exactly the eight operations the decision covers`
- `[PASS] SEC EDGAR is ALLOWED for access only (OP-01, OP-02) — **not widened by analogy** — the six operations the decider never spoke to are not carried over from Infosys`

with `SEC_ALLOW_OPS`/`SEC_UNDECIDED_OPS` as explicit named sets (`verify_s2.py:47-51,82-96`).
Eight further assertions were **added**, each pinning one r0 finding so it cannot silently
regress: counts-block agreement (107 decided), `CHN-01 × OP-01` UNKNOWN, "no UNKNOWN cell
carries a decided-looking supporting field — 25 cells × 10 fields", `source_bytes_held =
true` for the eight, `fail_closed_rule` wording, `OP-04` scope wording, "HELD scope is
exact: 13 held items, 3 named not-held", inventory §6 citing `A05-DECISION-001`, and the
recomputed D-1 split. Basis count moved 7 → 8. **No assertion was removed or weakened.**

I did not rely on the checker: every claim above was re-derived with my own script.

---

## 4. Independent re-derivation (not via `verify_s2.py`)

- 132 cells, 132 unique `(source_ref, operation)` keys.
- `Counter` = **66 ALLOWED / 41 DENIED / 25 UNKNOWN**; `counts` block agrees;
  `cells_decided_by_A05-DECISION-001` = 107 = 66 + 41; `open_decisions[D-1]` = 107/25.
- **0** `ALLOWED` cells missing `decision_ref`/`authority_envelope` `A05-DECISION-001`;
  **0** `DENIED` cells missing it; **0** `UNKNOWN` cells carrying a `decision_ref`,
  `decider`, `decision_date`, `evidence_version_decided_against`, or a wrong envelope.
- All 11 sources still `source_level_access_decision: "NONE_RECORDED"`; `widening_check` 0/0.
- **md↔json drift across all 132 cells: zero.** Parsed the md grid independently
  (11 rows × 12 cells) and compared each to the json disposition — 0 drifting cells.
- Basis usage sums to 132: DB-01 64, DB-03 24, DB-02 16, DB-07 12, DB-06 11, DB-04 2,
  DB-05 2, DB-08 1.
- Consistency spot-checks that had to move with the fixes and did: md `OP-11` sentence
  ("`UNKNOWN` for the other nine sources") still true; D-2 note in json and md both now
  carve out "P4 SEC, where the decider spoke to access only"; the Q0 downstream bullet now
  says CHN-03 is **access-only** and that nothing from EDGAR "may yet be retained,
  extracted, transformed, machine-processed, captured, or hashed" — the leak I was
  specifically looking for (a stale "Q0 may proceed against CHN-03") is **not** present.

---

## 5. Orchestrator's two inventory edits

Both are directionally accurate and neither invents a permission. Three restatement
defects, one important.

**Header, "Standing rights rule" (`docs/research/external-tools-and-repos-inventory.md:12-21`)** —
`66 ALLOWED / 41 DENIED / 25 UNKNOWN of 132` ✔ exact; "Infosys internal-only operations and
SEC EDGAR **access** allowed" ✔ correctly says *access*, matching the C-1 fix; "every
UNKNOWN cell remains denied by default" ✔; `until` → `unless` ✔ appropriate now that
dispositions exist. One inaccuracy — see **M-A**.

**§4 (`:73-83`)** — retitle ✔; row 1 NSE ✔ (matches the M-1 fix exactly, including "human
browsing declared out of scope, not decided"); row 2 BSE ✔; row 4 ✔ correctly adds the
retrieval fact and manifest ref; row 5 ✔; row 6 unchanged ✔; row 7 SEC ✔ on the main point
("Enters source list (D-5 answered); automated access within SEC fair-access limits
ALLOWED") — this row is the clearest evidence the edit was made against the *fixed* state,
since the pre-C-1 wording would have been much broader. Defects: **I-B** (row 3) and
**M-B** (row 7).

---

## Issues

### I-A (IMPORTANT) — `DB-06.applies_to` still claims "all twelve operations" after the M-1 fix

**File:** `docs/evidence/phase-0a/a-05-source-rights-package.json`, `decision_bases.DB-06-NSE-DENY.applies_to`

> `"applies_to": "CHN-01 (National Stock Exchange of India Ltd), all twelve operations"`

This is now false and is contradicted three ways inside the same object and file:
`DB-06.rationale` says "a decided deny for OP-02 … OP-12"; `DB-06.conditions_and_limits`
says "that is OP-02 … OP-12. … OP-01 is carried separately by
DB-08-NSE-HUMAN-BROWSING-OUT-OF-SCOPE"; and only **11** cells cite `DB-06` (verified). It
also drifts from the md bases table, which correctly renders the same basis as
"`DB-06-NSE-DENY` | CHN-01 × OP-02 … OP-12".

Same shape as r0's **I-1** — a scope field left behind when the state around it moved. No
disposition is wrong, but `applies_to` is the field a future reader or tool will treat as
the basis's authoritative scope, and it currently asserts a deny over a cell the decision
deliberately left `UNKNOWN`. Introduced by the M-1 fix.

**Fix:** `"applies_to": "CHN-01 (National Stock Exchange of India Ltd), operations OP-02 … OP-12
(OP-01 is carried by DB-08-NSE-HUMAN-BROWSING-OUT-OF-SCOPE)"`. Re-digest the json and update
the three bound digests. Consider adding a `verify_s2.py` assertion that each basis's
`applies_to` operation set equals the set of cells citing it — that would have caught this
mechanically, and it is the one class of error the current 8 new assertions do not cover.

---

### I-B (IMPORTANT) — inventory §4 row 3 restates Infosys retrieval as unconditional, dropping the one-time-only limit

**File:** `docs/research/external-tools-and-repos-inventory.md:79` (and rows 4 and 5, which
inherit it via "Same as #3")

> "Human-directed retrieval, internal retention/processing/derived facts ALLOWED
> (internal-only); redistribution/public output DENIED; caching and commercial use remain
> UNKNOWN"

Accurate on redistribution and on the two UNKNOWN operations, but it omits the single most
load-bearing limit in the whole decision: `OP-02` is allowed **only** for the one-time
2026-08-20 fetch of the eight enumerated URLs, and "standing, scheduled, recurring, or
crawling retrieval is not decided and stays UNKNOWN" (`DB-01.conditions_and_limits`, and
carried in every `SRC-* × OP-02` cell as `automation:
"HUMAN_DIRECTED_ONE_TIME_ONLY — …"`). As written, a reader working from the inventory would
conclude that fetching more Infosys IR documents is already permitted.

This is the one place in the two edits that reads **broader** than the decided state — which
is exactly the check requested. Mitigating: the file's own header says "Listing an item here
is **not** adoption, permission, or a rights decision", so it is not an authority document.

**Fix:** append to row 3 — "retrieval limited to the one-time 2026-08-20 fetch of the eight
enumerated URLs; standing/scheduled/recurring retrieval remains UNKNOWN". Rows 4 and 5
inherit it through "Same as #3".

---

### M-A (MINOR) — header line understates the BSE deny and omits the NSE `OP-01` carve-out

**File:** `docs/research/external-tools-and-repos-inventory.md:16`

> "NSE/BSE automated collection decided-DENY"

Correct for NSE, but **BSE is decided-DENY on all twelve operations**, including `OP-01`
human reading — "automated collection" understates it. Conversely for NSE, `OP-01` is
`UNKNOWN`, not denied. Both nuances are stated correctly one screen down in §4 rows 1 and 2,
so the effect is contained, and the direction is under- rather than over-stating a deny.
**Fix:** "NSE automated collection (`OP-02`…`OP-12`) and **all** BSE operations decided-DENY;
NSE human browsing left UNKNOWN".

### M-B (MINOR) — inventory §4 row 7 says CHN-03's other operations "remain UNKNOWN"; two are DENIED

**File:** `docs/research/external-tools-and-repos-inventory.md:83`

> "retention/processing and other operations remain UNKNOWN"

`CHN-03 × OP-09` and `× OP-10` are `DENIED` under `DB-05-SEC-REDIST-DENY`, not `UNKNOWN`.
Understates a deny.
**Fix:** "…retention/processing and the remaining operations stay UNKNOWN; redistribution
and publication (`OP-09`, `OP-10`) are DENIED".

### M-C (MINOR) — the machine-readable `D-5` answer omits the access-only limit the rest of the record is careful about

**Files:** `a-05-source-rights-package.json` `open_decisions[D-5].answer`;
`a-05-source-rights-package.md` D-5 summary-table row

> "CHN-03 (SEC EDGAR) is ADDED to the source list, with automated access allowed within SEC
> published fair-access limits and the same internal-only output boundary."

True as far as it goes, and the md's D-5 **section** body directly below states the
access-only limit in full. But `open_decisions[D-5].answer` is the field a machine consumer
reads, and it is the one place in the post-fix json where "SEC EDGAR allowed" appears
without the access-only qualifier that C-1 existed to install.
**Fix:** append "The decider spoke to access only; `OP-03`…`OP-08`, `OP-11`, and `OP-12`
stay UNKNOWN." to the `answer` string and to the md D-5 row.

---

## Recommended disposition

**I-A** should be fixed before committing — it is a one-string edit, but it changes the json
and therefore all three bound digests, so it must go in the same pass as any other json
change (**M-C** is the only other one; do them together, re-digest, re-run `verify_s2.py`).
**I-B**, **M-A**, and **M-B** are markdown-only edits to
`docs/research/external-tools-and-repos-inventory.md` and touch no digest.

Nothing found in r1 affects a disposition cell, the fail-closed posture, decision fidelity
to the decider's statements, or the digest chain. Once **I-A** and **I-B** are applied I
would expect a clean pass.
