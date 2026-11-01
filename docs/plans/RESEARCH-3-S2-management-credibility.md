# RESEARCH-3 S2 — Management credibility — Implementation Plan

**Origin:** `docs/specs/2026-10-27-research-3-thesis-analysis.md` §5 "S2" (approved r4,
gpt-6.1-sol `APPROVE`), with §0, §1, §3, §6 and the owner rulings. Bead `eqos-bnx`, slice 3 → S2.
S1 closed live on 2026-11-01. Format and lessons: `docs/plans/RESEARCH-3-S1-risk-probe.md`.
**Revision:** r4 (2026-11-01) fixes Sol's closing review (at `85521918`), marked "r4 (F<n>)": one prepare step before
the first write (F1, P12), target-year windows (F2, P7), links resolved through the pool (F3, P13), a reviewed
`reading` on each entry (F4, P14), all admitted XBRLs searched (F5), one reference contract (F6), a frozen
correction delta (F7), and the approving round's three simplifications.
r3 (2026-11-01) fixed Sol's r2 residuals (re-review at `a779bdfd`): R5's unrounded actual,
R3's cycles after successor resolution, R12's preservation gate on the recovery draft, and gate (e)'s
role changes; it records the rulings on C-13, the estimate and the deferred verification. Marked "r3".
r2 fixed the 14 findings of Sol's r1 review (at `09112a32`) and carried its rulings on C-4, C-8, C-12, the
provisional mapping predictions and the `Interim` simplification, marked "r2 (R<n>)". One mechanism answers
R1, R2, R4 and R8: a sealed record line per statement (P2). **No finding needs a migration.**
**Status:** approved r4 (2026-11-01) — approver gpt-6.1-sol, `APPROVE` on the re-review of the closing critical review's fixes (plan rounds r1–r3, closing review, re-review). The owner may overturn the S2 panel scope and C-15.
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

Checked at `2f422db8`; r2 rechecked at `09112a32`, r3 at `a779bdfd` and r4 at `85521918` (no code change between them). The
code won each of these unless stated.

| # | Spec says | Code or data says | Followed |
|---|---|---|---|
| C-1 | §0 line references (`run_draft.py:277-362`, `:632-672`, `citations.py:320-334`, others) | S1 moved them: `write_run_draft` `:311-399`, `_sections` `:683-728`, `resolve_location` `:352-374` | Code. This plan cites HEAD lines. |
| C-2 | §0: `Prior` holds only the predecessor's guidance entries | `preflight` takes **every** `SOURCE_QUOTE` (`run_draft.py:294`), and `_guidance` re-emits each unstated one as a guidance line (`:554-557`). Episode quotes would be carried into `management_ledger`. | Code: split them by section key (Task 3). |
| C-3 | §3 "Apar today": cables revenue growth has a filed measure "after the segment lines land"; "the other three metrics are unregistered" | No segment claim exists in any run draft, and both beads are open | Code: `ACTUALS` does not register cables. An unavailable measure reads "no filed measure", the true reason today. Cables rows state both reasons (P6). |
| C-4 | §3: an entry "gives" an entry digest | r2 (Sol ruling): a script could compute a stored hex, so typing is not the objection. A stored copy is redundant: the sealed row already holds the pin, and the file's copy would itself need recomputing to be trusted | Reduced form: the digest is computed at load over the fixed preimage in Task 1 (R8). The quote is in the file so a retired entry's pin still verifies. Pinning behaves as specified. |
| C-5 | §3: entries keyed by capture | Capture ids differ between databases (Sol S1 r3 #8) | Key on the capture's blob SHA-256 (`citation.source_sha256`). |
| C-6 | §3, §5: Q3 call "filed in January 2026", Q4 "filed in May 2026" | The pinned `retrieval-manifest-v2.json` has 04-Feb-2026 and 04-Jun-2026. Q2 is 06-Nov-2025. FY27_Q1 is 31-Jul-2026. | Manifest dates in tests. The spec's conclusions still hold: Q3 is in FY26, Q4 in FY27. |
| C-7 | §3: relative wording is `AMBIGUOUS` when the filing falls after "the run's period end" | Tested at every later run, the same entry would flip: a Q4 call's "this year" reads FY27 once the FY27_Q1 run carries it | r2 (R4): the window is validated once, at the entry's first use, against the statement's **originating** period end, held in its record line (P2) and never the consuming run's. The pin then holds it (P3). |
| C-8 | Approval note: year-specific rules need matching sealed contract bindings | True: `claim_check.py:119-121,158-165` fails an unbound drafted quote. Apar's quotes all have bindings, and S2 adds no rule. | A5 is proven at extraction and episode level only. r2 (Sol ruling): those tests are **not** end-to-end year-specific `AS_KNOWN` proof, and nothing in S2 claims it. The binding gap stays open for the first year-specific quarter; **file a bead**. |
| C-9 | §3: `better` lives only in `ACTUALS`, yet the revision rule needs direction for a plus-against-range comparison | Apar's metrics are unregistered | That one case renders `UNRESOLVED` ("direction not registered") (P5). Apar has no such pair: only point against plus. |
| C-10 | §3: "scope is the guidance contract's" | `guidance_extractor.py:115` hard-codes `CONSOLIDATED`, so a cables-segment metric reads `consolidated` and no standalone promise can arise from extraction | Followed the spec. Disclosed in the report (D4). The standalone case (A7) is synthetic. |
| C-11 | §0: `resolve_location` checks no issuer or cutoff | HEAD checks both | S3's concern. No S2 effect. |
| C-12 | Owner goal (`docs/goals/2026-10-27-research-report-targets.md:15`): a table showing "where credibility is rising or falling and what that means" | Not in spec §3; left to S3 model notes | Spec. Disclosed as absent (D1, `NOT_DONE`). r2 (Sol ruling): this deferral holds only if S3 explicitly delivers the owner's trend and thesis-consequence requirement. S3's plan must carry it as an acceptance case, and the S2 close records that in the bead. |
| C-13 | §3 "Apar today": cables revenue growth is `MULTI_YEAR` | r2 (R7): that holds for the CAGR and "a year" quotes. The FY26_Q2 pattern ends "% year on" (`aparinds-fy26-q2.yaml:123`), an undated comparison basis | Its entry is `AMBIGUOUS`. The spec's conclusion still holds: the rows stay `UNRESOLVED`. r3 (ruling): accepted. `AMBIGUOUS` is justified for the FY26_Q2 quote; the CAGR and "a year" statements stay `MULTI_YEAR`. The changed episode and link expectations freeze after source review (Task 3). |
| C-14 | r3: OD-7 (spec §3, §6): the row "shows the unrounded actual" | A claim holds a `Decimal`; `_trace` resolves a calculation claim to the trace's stored value (`citations.py:564-566`), which `check_claim` compares at the claim's precision (`claim_check.py:110-115`). `calculation_traces.exact_value` already holds the exact reduced fraction, unread here. | Spec. A narrow, explicit exact path in the resolver (P4). OD-7 is not amended. |
| C-15 | r4 (F4): §3 gives an entry no eligibility field; every extracted quote opens or joins an episode, and "Apar today" reads the cables quotes as one `MULTI_YEAR` promise. Only `same_as` is a reviewed judgment ("Sol checks each link") | The retained context does not support that for FY26_Q3 (PDF page 14, management's answer on progress): a rule match cannot tell a promise from a description of progress | Addition to the spec, not a contradiction: one reviewed `reading` field (P14). The spec's conclusion holds: those rows stay `UNRESOLVED`. |

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

- **P1, stateless rebuild (r2, R2).** Each run rebuilds every episode **and every event** from a
  pool: the previous-quarter head's recorded statements, then the statements this run's own
  transcript extracted (`run.guidance`). A guidance claim merely carried from a prior entry adds
  nothing: it is already in the pool, or its head predates S2 and D2 discloses the absence. Each pool
  claim finds its live entry by (ledger key, blob, anchor); statements order by (originating period
  end, ledger key, anchor). Events are never read back. A correction therefore recomputes the affected
  events under the live mappings in the new version, including a directional event that a definition
  correction makes `REVISED` ("basis changed"), while earlier versions stay sealed as written and the
  correction line discloses why the event moved.
- **P2, one sealed record line per statement (r2, R1, R2, R4, R8).** Every statement ever seen, mapped
  or not, is one `  - statement …` line under its row (grammar in Task 2), holding its entry and digest,
  originating period and end date, event, and a `ref` to its own `SOURCE_QUOTE` claim. The claim is the
  immutable reference: `.original` and `.latest`, plus `episode.<id>.stated.<entry id>` for each
  statement between them, so a corrected middle statement keeps its full contract and citation. Claims
  carry forward by copy, so no version-id or row-id reference is needed (a new statement could not name
  its own unwritten version). A `Retired entries:` block keeps the pins of superseded entries, so "a
  previously used entry that is missing refuses" holds forever. No new table, field or migration; the
  text is sealed.
- **P3, one window function, run at first use (r2, R4, R7).** `derive_window(text, filed_at,
  stated_end, month)` returns `FY<yy>`, `MULTI_YEAR` or `AMBIGUOUS`. Year-on-year names a comparison
  basis, not a period, so `year[- ]on(?:[- ]year)?`, `yoy`, `y-o-y` and `a year (?:ago|earlier)` are
  removed first. Then the first match wins:
  1. `CAGR`, `a year`, `per year`, `every year`, `each year`, `per annum`, `annually`, or a count of
     years (`<number or two to five>[- ]years?`) → `MULTI_YEAR`;
  2. one distinct explicit fiscal label → that year; several → `MULTI_YEAR`;
  3. `this year` or `current year` → reference fiscal year; `next year` → reference + 1. Each is
     `AMBIGUOUS` when the filing time is missing or falls in a later fiscal year than `stated_end`'s;
  4. otherwise `AMBIGUOUS`.

  So an undated "20% year on year" is `AMBIGUOUS`, "20% year on year in FY27" is `FY27`, "20% year on
  year this year" follows rule 3, and "year on year for the next three years" is `MULTI_YEAR`. A new
  entry whose declared `window` differs refuses, which covers the anchor-only year (A4).
- **P4, one comparison, including interim (r2, R5; r3).** A statement's binding bound is `L` for `HIGHER`,
  `U` for `LOWER`. **Exact:** the trace's `Fraction` (`CalculationResult.exact`;
  `StoredTrace.trace.exact_value` for a carried actual), the only verdict input. A verdict rounds it
  half-even to the statement's precision, once, and compares. Exact 9.495% against a whole-number bound of
  ten rounds to 9 (`MISSED`), not 10. The spec states this for ended windows only. Interim uses the same
  rule; the row discloses it. **Stored:** the trace's own `value` column at the policy's scale; S2 neither
  displays nor compares it.

  **Displayed (r3, R5), the unrounded actual.** Each `cred.*` claim carries the exact value's digits:
  - **Value.** `truncate_value(exact, EXACT_PLACES)`, the first six decimal places, cut toward zero. r4: it is
    `_scaled(int(value * 10**places), places)` (`canon/interval.py:109`), so there is no second conversion. `precision=6`, and the qualifier `EXACT_DIGITS`. The
    claim holds these digits; no second claim holds a stored figure. `rounding` stays `ROUND_HALF_EVEN`: the
    column's check (`migrations/0012_report_ledger.sql:70`) admits no truncating mode, and at six places on
    a six-place value the mode changes nothing.
  - **Validation.** `_trace` reads `exact_value` too. For a claim with `EXACT_DIGITS` it resolves to
    `truncate_value(Fraction(exact_value), claim.precision)`, otherwise exactly as today, so every existing
    claim keeps its path. `check_claim` is unchanged: a claim typing the stored 9.50, or six-place digits
    without the qualifier, is `VALUE_MISMATCH`. P7's only actual is a percentage, so no claim scale applies.
  - **Rendering.** `render_claim` is unchanged: `{{c:<key>|unit}}` prints `9.495000%`. Beside it the row
    writes one of two fixed, digit-free phrases, chosen by `exact == Fraction(claim.value)`: `ACTUAL_WHOLE` "(all
    computed digits)" or `ACTUAL_CUT` "(first six decimal places, cut and not rounded; more digits follow)",
    then `{{c:<key>|ref}}`, naming the trace. The scanner removes both placeholders, so the digits stay
    claim-backed and no scan rule changes.
  - **A non-terminating value,** the usual growth rate, reads `33.333333%` with `ACTUAL_CUT`. This honours
    OD-7: its purpose is that a reader sees the figure before the statement's rounding, and no shown digit
    has been altered by any rounding. For a statement precision up to five places, the digits and the phrase
    fix which side of a half-even tie the value falls on: exact 10.5 and 10.5000001 both print `10.500000%`,
    and only the phrase separates a true tie (rounds to 10) from a value above it (rounds to 11). At six or
    more the verdict still reads the exact value, though the shown digits no longer decide it. A literal
    expansion is impossible; the full reduced fraction stays in the cited trace.
- **P5, direction (r2, R10).** `better` comes from `ACTUALS`. A point against a `plus` needs no direction,
  since each has one bound. A closed range against a `plus` on an unregistered metric renders
  `UNRESOLVED` ("direction not registered"). A `plus` on a `LOWER` metric renders `UNRESOLVED` ("open
  bound in the wrong direction") in the revision event **and** at endpoint assessment, ended or interim:
  `assess` decides that beside endpoint comparability, so `compare` never treats a floor as a maximum.
- **P6, both reasons.** Outcome step 1 names every reason that holds ("window not established; no
  filed measure"). Otherwise the row would hide the second gap.
- **P7, one real registry entry (r2, Sol note).** `ACTUALS` holds `(revenue_growth, consolidated)`: the
  default rule set's metric (`guidance_extractor.py:58-62`), computed as `run.change_pct` of
  `revenue_from_operations` over the window against a year earlier, with the interim rule. The spec's
  interim fields have one supported form, so `Actual.interim` is a plain `bool` and the label a constant.
  r4 (F2): the target is `FY<yy>`, from the day after the prior fiscal year's end to its own end. A run's
  period end before that start is `NOT_STARTED`: `UNRESOLVED` ("not due: target year not started") with no
  interim actual. Inside it is `OPEN`: the numerator runs from the target's start to the period end, so it lies
  in the target year, and the comparator is the same months a year earlier. On or after its end is `ENDED`.
  It makes the `cred.*` path real and testable on the retained pilot. Apar emits no such metric, so its
  report has no `cred.*` claim. Tests of scope and direction inject a registry.
- **P8, adverse cases are pure tests**, as S1's P8. Outcomes and events are pure functions of claims
  and values; the database proves only copies, carry, traces and refusals.
- **P9, two heads, kept apart (r2, R1).** Episode state comes only from the **previous-quarter** head
  (`Prior.version_id`). Pin history comes from that head **and the same-period head**
  (`Prior.same_period_id`, the version a rerun replaces), loaded before `preflight`'s bootstrap return so
  FY26_Q2 has it too. Each head's pins are checked separately (a merge could hide a digest that differs
  between them), in the CLI right after `preflight`, before the run's first write. Under lock `write_run_draft` rechecks both identities and sealed digests; the
  same-period check is new. A correction line renders for each pin now superseded and not retired in the
  **previous-quarter** head, so a rerun of a period restates a correction its replaced version disclosed.
- **P10, rejected credibility claims (r2, R13).** `plan` refuses with their own route: diagnose; append a
  `supersedes` entry if the mapping is wrong; then rerun `--full-successor`. A correction alone never
  unblocks an ordinary run, because `preflight` calls `plan` first (`run_draft.py:281-284`).
- **P11, undefined growth is a row (r2, R6).** Before evaluating, `bind_credibility` requires the
  comparator's `interval.lower > 0`, the same test as the probe's denominator guard
  (`risk_probe.py:248`). Otherwise no trace or claim exists and the row reads `UNRESOLVED` ("comparator
  revenue not positive or its uncertainty reaches zero"), so `run_traces.py:349-350` cannot abort the
  report. Several mapped interpretations of a key still raise (`_Binder.filed`): that one is structural.
- **P12, prepare before the first write (r4, F1).** `prepare` is pure and does every check a mapping or pool can
  fail: the statement join, first-use windows, link presence (P13), episode construction and the pin superset. The
  CLI calls it first in `before_commit`, after the head check and before `bind_computed` stores a trace or `_admit`
  selects a fact, then runs `admit` on its statement blobs and carried-actual blobs. `bind_credibility` and `build`
  take its `Prepared` result and repeat none of it.
  - **Guaranteed zero on every table:** `preflight`, `check_pins`, `check_head`, the rework gate, `prepare`, `admit`.
  - **Late:** the under-lock identity and digest checks, `_Binder.filed`'s structural raise, and `AS_KNOWN`
    validation. The version rolls back, but traces and facts already committed in their own transactions stay
    (`evidence/repository.py:636`). These occur only through a concurrent head change or a store fault, not a
    mapping fault, and the run reports them as refusals with no such guarantee.
- **P13, a link resolves through the pool (r4, F3).** Episode identity depends on every entry on `chain(entry)`.
  Each entry on a statement's chain must name a triple present in the pool, checked on every `prepare`, else
  `RunDraftError`. So every entry that decides a recorded root is itself a recorded, pinned statement, and no
  second pin mechanism exists. A link to a pre-chain statement is refused; the author drops the `same_as`, and D2
  already discloses earlier promises as absent.
- **P14, a reviewed reading (r4, F4).** Each entry has `reading`: `COMMITMENT` (management states or restates a
  target) or `DESCRIPTIVE` (the quote describes performance or anything else short of a promise). It is judged from
  the quote's transcript context, is in the digest, and is what source review can reject. A `DESCRIPTIVE` entry
  keeps its quote and record line as evidence, in its own episode `<metric>.<scope>.DESCRIPTIVE.<entry id>`, whatever
  its window. Its event is `DESCRIBED`, its outcome `UNRESOLVED` (`REASON_DESCRIPTIVE`, alone: P6's other reasons
  concern a promise). It binds no actual, computes no revision, and may neither link nor be linked.

Considered and cut, for "could this be half?": a stored digest (C-4); a separate episode table or a
version-id reference per statement (P2); parsing events back (P1); an `Interim` model (P7); segment
actuals (C-3); a CLI to author entries (a scratch seed script does it); slug validators (F-4); a
per-metric definition registry (`definition` is a plain string, compared for equality). r3: a displayed
fraction (a claim value is a `Decimal`, and a ratio of two long integers helps no reader; the trace holds it);
a stored and an exact claim per actual (one exact claim suffices); a truncating `Rounding` member (needs a
migration, changes nothing at six places); a new display style or scan rule. r4: pinning the link chain in the
record (P13 needs one membership check and no grammar change); a separate eligibility table or a model verdict
on context (one reviewed field, P14); a mapping validator in the writer (P12).

## File map

| File | Change | Responsibility |
|---|---|---|
| `src/fundamentals/ledger/guidance_targets.py` | create | Rule H: `GUIDANCE_KEY`, `TargetEntry`, `Targets`, `load_targets`, `derive_window`, supersession and `same_as` resolution, `check_pins` |
| `src/fundamentals/ledger/credibility.py` | create | Pure half: registry, events, outcomes, episode build, section. Binding half: `bind_credibility` |
| `src/fundamentals/ledger/falsifier_status.py` | modify | `CREDIBILITY = "management_credibility"`, member of `DERIVED` |
| `src/fundamentals/ledger/run_draft.py` | modify | `Prior.episodes/credibility/actuals/actual_blobs`; `preflight` split (C-2); `RunDraft.credibility`; claims and section in `write_run_draft`; `allowed_captures`; the `NOT_DONE` line |
| `src/fundamentals/ledger/rework.py` | modify | `plan`: the credibility route (P10) |
| `src/fundamentals/canon/interval.py` | modify | r3 (R5): `truncate_value` beside `store_value` |
| `src/fundamentals/ledger/display.py` | modify | r3 (R5): the `EXACT_DIGITS` constant beside `FILED`; no rendering change |
| `src/fundamentals/ledger/citations.py` | modify | r3 (R5): `_trace` resolves an `EXACT_DIGITS` claim from `exact_value` |
| `src/fundamentals/api/cli.py` | modify | load targets, `check_pins` after `preflight`, `bind_credibility` in `before_commit`, pass to `RunDraft` |
| `config/guidance_targets/aparinds.yaml` | create | Eight Apar entries (Task 3) |
| `tests/fundamentals/test_credibility.py` | create | Pure: windows, entries, events, outcomes, carry, pins, correction, section text |
| `tests/fundamentals/test_credibility_binding.py` | create | Pilot: `check_credibility`, actuals on retained filings, a carried actual, the rework route |
| `tests/fundamentals/test_pilot_e2e.py` | modify | PILOT-4: quote route admits the section; calls `check_credibility` |
| `tests/fundamentals/test_report_export_gaps.py` | modify | `:42` follows the new `NOT_DONE` line. r4 (F6): the assertion at `:88-94` stays as it is and binds the new section |
| `tests/fundamentals/test_prep5_rework.py` | modify | r2 (R11): `test_a_relabelled_guidance_rework_changes_only_its_claim` admits the regenerated episode copies |

r4 estimate: about **600 production lines** (`guidance_targets.py` ≈ 140, `credibility.py` ≈ 390, wiring
≈ 70), at the top of the spec's 400–600, up from r3's 555: `prepare` about 20 net, the source search about 10,
`reading` about 8, target windows about 5, link presence about 2; the shared walk and `_scaled` save about 2 each.
F6 and F7 add none (F7 is scratch). About **685 test lines** (`test_credibility.py` ≈ 405,
`test_credibility_binding.py` ≈ 255, edits ≈ 25), **over the spec's 300–400**, up from r3's 590. r3 (ruling): the
overrun is justified, since the spec gives an estimate, not a ceiling. r4: keep each distinct adverse assertion, and
parametrize only shared setup (window variants, invalid-entry cases, comparator-domain cases, the F1 refusal cases);
do not remove coverage merely to reach 400 lines. Expected sizes: `test_pilot_e2e.py` ≈ 680 (676), `test_prep5_rework.py` ≈ 765 (754), every new file
under 500; each ≤ 800.

## Test-first order, gate and sealing

1. **Tests round (one Opus round, before any production change).** Write `test_credibility.py`,
   `test_credibility_binding.py`, the three edits and `config/guidance_targets/aparinds.yaml` in final
   form. r2 (R11): `test_prep5_rework.py` is imported by the pilot test and enters the red-proof seal, so
   its amendment lands here. The YAML must exist so expected event kinds can be stated. A production name
   is imported inside the test or fixture, so every file collects on the pre-change source. The round
   runs `wc -l` on every test file it touched (≤ 800, or the gate routes `CONTRACT`) and
   `git grep -n "preflight(\|RunDraft(\|allowed_captures(" -- src tests`, then reports both outputs.
2. **Red capture, orchestrator only, on the pre-change source:**
   `scripts/verify.sh red RESEARCH-3-S2 tests/fundamentals/test_credibility.py
   tests/fundamentals/test_credibility_binding.py
   tests/fundamentals/test_pilot_e2e.py::test_pilot_end_to_end
   tests/fundamentals/test_prep5_rework.py::test_a_relabelled_guidance_rework_changes_only_its_claim
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
  - duplicate id, or an id outside `[A-Za-z0-9_-]+`; an unknown window form or r4 (F4) `reading`; `window_text` not
    a substring of `quote`;
  - r2 (R3): more than one live entry for one `(claim_key, source_sha256, anchor)`;
  - `supersedes` naming an unknown id or an entry with a different `(claim_key, source_sha256, anchor)`
    or `quote`; two successors of one entry; a cycle;
  - r2 (R3): `same_as` naming an unknown id or an entry not earlier in the file, or a target that, **after
    resolving to its live successor**, has a different metric, scope or window class. A correction that
    breaks a link therefore refuses until the linking entry is also corrected. Metric and scope are read
    from the two `claim_key`s; `FY<yy>` windows must also be equal.
  - r3 (R3): a cycle in the resolved graph, a self-link included. File order cannot exclude one: `A`; `B`
    `same_as: A`; `A2` `supersedes: A`, `same_as: B` has only backward references, yet resolves to
    `B → A2 → B`. r4: one walk, `chain(entry)`: entry → live successor → `same_as` → its live successor, refusing
    on a revisited entry. Load calls it for each entry and `root` is its last element, so `root` always terminates.
  - r4 (F4): a `same_as` whose linking entry or resolved target is `DESCRIPTIVE`.
- r2 (R8): the digest is computed at load: SHA-256 of the UTF-8 bytes of `json.dumps({…},
  sort_keys=True, ensure_ascii=False, separators=(",", ":"))` over exactly `id, claim_key,
  source_sha256, anchor, quote, window_text, window, reading, definition, same_as, supersedes`, an absent option
  as `null`. No other field joins without changing every pin, so the list is a constant.
- r2 (R3), r4 (F1): at join time (`prepare`, Task 2) an entry's `quote` must equal the joined claim's `citation.quote`, else
  `RunDraftError`. With the claim check's `resolved.quote_text == citation.quote`
  (`claim_check.py:117`), that gives the chain: `window_text` ⊂ entry quote = claim quote = retained span.
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
  - r4 (F4): `Reading(StrEnum)`: `COMMITMENT, DESCRIPTIVE`.
  - `TargetEntry` (frozen): `id, claim_key, source_sha256, anchor, quote, window_text, window,
    definition: str`, `reading: Reading`, `same_as, supersedes: str | None`, and property `digest -> str`.
  - `Targets` (frozen) with `entries: Mapping[str, TargetEntry]`, `live(claim_key, sha, anchor) ->
    TargetEntry | None`, r4 `chain(entry) -> tuple[TargetEntry, ...]` (P13), `root(entry) -> TargetEntry` (its last
    element) and `successor(entry_id) -> TargetEntry | None`.
  - `load_targets(symbol: str, root: Path = ROOT) -> Targets`.
  - `derive_window(text: str, filed_at: datetime | None, stated_end: date, month: int) -> str`.
  - `check_pins(targets: Targets, pins: Mapping[str, str]) -> None`.

Approach: one module, no classes beyond the two models. The file name is the lower-cased symbol
(`config/identity/aparinds.yaml` is the precedent). The relative words are the closed list in P3.
A fiscal year is named by its end year, as `FY26` ends March 2026 at month 3.

Verification: `uv run pytest tests/fundamentals/test_credibility.py -k "window or entry or pin" -n 0`
passes. Cases: A3, A4, A6, A10, A13's missing entry, and each structural fault (parametrized), including
r2 (R3): two live entries on one triple; a successor of another statement; a successor with another
quote; a later `same_as`; a `same_as` to another metric or scope; a `same_as` incompatible only after
successor resolution. r3 (R3): the three-entry `A`, `B`, `A2` cycle above; `A2` `supersedes: A`, `same_as: A`,
a self-link only after resolution; the same chain without the cycle still loads. r4 (F4): a `same_as` from and to a
`DESCRIPTIVE` entry, including one that becomes so only after successor resolution. r2 (R7): explicit-year, relative-year, undated, truncated ("year on") and recurring
year-on-year, and "a year ago". r2 (R8): one literal digest computed once by an independent scratch
`hashlib` call pins the preimage, and changing any listed field changes it.

Test seams: `load_targets` on a temp root, `derive_window`, `check_pins`. Pure.

Dependencies: None.

Risks: low. A wrong `derive_window` branch misdates a promise; the A6 cases pin it.

### Task 2: Events, outcomes, episode build and the section (pure)

Goal: given the run's stated guidance claims, the previous-quarter and same-period records, targets,
actuals and the run's period, the module prepares (P12) and builds each episode and renders the section exactly
as spec §3 and "Report disclosures" below.
- **Episode id** `<metric>.<scope>.<window key>`. The window key is the `FY<yy>` label, else
  `<class>.<root entry id>`; r4 (F4) a `DESCRIPTIVE` entry's is always `DESCRIPTIVE.<entry id>` (P14). r2 (R4): an unmapped statement is `UNMAPPED.<blob prefix>.<anchor>`, so it is
  retained until mapped; that key appears only inside placeholders, whose digits the scan removes. Claims
  are `episode.<id>.original`, `.latest` and, r2 (R2), `.stated.<entry id>` for each statement between
  them, copies of the guidance claim with `claim_key` and `section_key` changed and everything else kept.
- **Pool (P1).** A statement already in the previous-quarter record keeps its record period. A statement
  new to the pool has this run's period. A live entry not yet pinned is validated once (C-7, against the
  statement's originating `stated_end`), then pinned. So a post-year-end Q4 statement unmapped in the Q4
  run and first mapped in Q1 stays `AMBIGUOUS` under its Q4 period (R4). An event is computed for each
  consecutive pair on every build (R2). r4 (F3): every entry on a statement's `chain` names a pool triple (P13).
- **Record (P2, r2, R8).** Under each row, one line per statement, fully matching:
  ```
    - statement (<entry id> sha256 <64 hex>|unmapped) stated <FY<yy>_Q<n>> ended <YYYY-MM-DD>: <EVENT>[ (<reason>)] {{c:<key>|ref}}[ {{c:<key>|ref}}]
  ```
  A one-statement episode's line has both refs (`.original`, `.latest`); otherwise one each. A reason
  holds no digit or parenthesis. The section ends with:
  ```
  {{e:computed}} Retired entries:
  - retired <entry id> sha256 <64 hex> successor <entry id>
  ```
  or `- none`. `read_record(body, claims)` parses completely and refuses with `RunDraftError`:
  - no credibility section (a legacy head) → an empty `Record`, never a refusal;
  - a section without the `Retired entries:` header, a line in that block not matching, or any line
    whose stripped form starts `- statement` or `- retired` not matching;
  - a duplicate entry id or claim key across lines;
  - any `episode.*` claim of that version not named by exactly one line, or a line naming a claim that
    version lacks. That catches an omitted statement, and a future format change, which must add a new
    header and parser rather than edit this one.

  r4 (F1): `prepare` refuses if its record's pins are not a superset of the input pins, so a dropped retired
  line cannot be written.
- **Events** follow the spec's three steps. Comparability first: metric, scope, unit, currency,
  constant-currency and `definition` must be equal, else `REVISED` ("basis changed"). Then the
  compared value: point; midpoint for a closed range; binding bound when one statement is open.
  Then the event: `REVISED_UP`, `REVISED_DOWN`, `REVISED` ("range widened" or "range narrowed"),
  `REAFFIRMED`. Direction names a number's move only. P5 applies.
- **Outcomes**, first match wins, per endpoint: the five spec steps, with endpoint comparability
  and P4, P5, P6, P11's reason. `about` adds no tolerance. `ON_TRACK` and `BEHIND` are `{{e:inferred}}`
  with the fixed label.
- **Correction (r2, R1, R2).** Each pin in either head now superseded and not retired in the previous-quarter
  head renders a line naming old and new ids, digests, windows and definitions, where new is the live
  entry at the end of its chain. It joins the retired block. An episode id no longer built for such an entry
  renders once as `UNRESOLVED` ("mapping corrected", naming the successor).
- **Empty against unscorable (r2, R14).** Two distinct cases. **No statement at all:** one paragraph, "no
  guidance quote has been extracted in this report chain", plus the retired block. **Statements exist but
  no row reaches `ACHIEVED`, `MISSED`, `ON_TRACK` or `BEHIND`,** which is the expected Apar result: the rows
  render, then D8 names every distinct row reason (spec §1 rule 2).

Files:
- Create: `src/fundamentals/ledger/credibility.py` (pure half)
- Test: `tests/fundamentals/test_credibility.py`

Interfaces:
- Consumes: Task 1; `_slot`, `refs` (`import_mapping`); `CREDIBILITY` (`falsifier_status`); `PERCENT`
  (`claim_check`); `NumericClaim`.
- Produces:
  - `EventKind(StrEnum)`: `OPENED, REVISED_UP, REVISED_DOWN, REVISED, REAFFIRMED, UNRESOLVED`, r4 `DESCRIBED`.
    `Event` (frozen): `kind`, `reason: str | None`.
  - `Outcome(StrEnum)`: `ACHIEVED, MISSED, ON_TRACK, BEHIND, UNRESOLVED`.
  - `Better(StrEnum)`: `HIGHER, LOWER`.
  - r2 (Sol note), r4 (F2): `INTERIM_RULE_LABEL`, no model. The two windows are one fixed rule: the **target
    year's** start to the run's period end, and the same fiscal months a year earlier (February 29 has no
    comparator, so `UNRESOLVED`). The year-to-date value is compared directly.
  - r4 (F2): `WindowState(StrEnum)`: `NOT_STARTED, OPEN, ENDED`; `window_state(label, period_end, month) ->
    WindowState`, the one reading of P7's boundaries.
  - `Actual` (frozen): `numerator: str, better: Better, unit: str, currency: str | None,
    definition: str, interim: bool`. Its key is `ACTUAL_KEY =
    "cred.{metric}.{scope}.{window}"`; the interim value is `<that>.ytd`.
  - `ACTUALS: Mapping[tuple[str, str], Actual]` (P7).
  - `revision(before: Statement, after: Statement, better: Better | None) -> Event`.
  - `compare(statement: Statement, exact: Fraction, better: Better) -> bool` (P4).
  - `assess(statement, window, actual_entry, state: WindowState, exact, ytd, reason) -> tuple[Outcome, str |
    None]`, where `reason` is P11's or F5's.
  - `Statement` (frozen): `claim: NumericClaim`, `entry: TargetEntry`.
  - r4 (F1): `Prepared` (frozen): `statements` (each with its episode id, event inputs and, once validated, its
    entry), `corrections`, `pins: Mapping[str, str]`, `windows: Mapping[tuple[str, str, str], WindowState]` ((metric, scope, `FY<yy>`) of
    live `COMMITMENT` entries whose state is not `NOT_STARTED`), `blobs: frozenset[str]`, `period`, `period_end`,
    `month`.
  - `Built` (frozen): `claims: tuple[NumericClaim, ...]`, `body: str`.
  - `Recorded` (frozen): `claims: tuple[NumericClaim, ...]`, `stated: str`, `stated_end: date`,
    `entry_id, digest: str | None`.
  - `Record` (frozen): `statements: tuple[Recorded, ...] = ()`, `retired: Mapping[str, str] = {}`, property
    `pins -> dict[str, str]`.
  - `read_record(body: str | None, claims: Sequence[NumericClaim]) -> Record`.
  - r4 (F1): `prepare(stated_claims, record, same_period, targets, *, period, period_end, month, filed_at,
    actual_blobs) -> Prepared`, where `filed_at: Mapping[str, datetime]`.
  - `build(prepared, *, actuals, exact, unavailable, registry=ACTUALS) -> Built`, where `exact: Mapping[str,
    Fraction]`, `unavailable: Mapping[str, str]`.

Approach: table-free functions; one row renderer. Each row carries `{{e:observed}}` for the quotes,
`{{e:computed}}` for events and actuals, `{{e:inferred}}` for interim. r4 (F6), one contract: **a line that shows
a claim references exactly the claims it shows** (`test_report_export_gaps.py:88-94`, unweakened). A one-statement
row shows and references `.original` only; its `.latest` is the same statement, so its one reference is the
ref-only record line (P2), which shows nothing. A row with two statements shows and references both. r3 (R5): a row's actual is the `cred.*` claim's digits, its
`ACTUAL_WHOLE` or `ACTUAL_CUT` phrase and its trace `ref` (P4). Rows render the metric id, never
`metric_label`.

Verification: `uv run pytest tests/fundamentals/test_credibility.py -n 0` passes; the whole file is
a red-proof target. Named cases:
- (a) `revision`: `REVISED_UP`, `REVISED_DOWN`, basis changed, widened, narrowed, `REAFFIRMED`,
  plus against range on the binding bound, plus on `LOWER`, range against plus with no direction,
  point against plus with no direction.
- (b) Ended: same actual `MISSED` `.original`, `ACHIEVED` `.latest`, row shows the unrounded actual and the
  disclosure; a rounding-boundary value proves half-even. r2 (R5), r3: exact 9.495 against a whole-number
  bound of ten is `MISSED`, where the two-place 9.50 would give `ACHIEVED`, and its row shows `9.495000%` with
  `ACTUAL_WHOLE`. r3: exact 100/3 shows `33.333333%` with `ACTUAL_CUT`; a negative value cuts toward zero;
  exact 10.5 and 10.5000001 against a whole-number eleven both show `10.500000%`, with different phrases
  and verdicts (`MISSED`, `ACHIEVED`). r2 (R10): `plus` on `LOWER` is `UNRESOLVED` for an ended and an interim
  endpoint.
- (c) A3, A4 rows; (d) FY26 and FY27 are two episodes; (e) A5's one-transcript case, with
  `extract_guidance_claims` on a fake `LoadedPdf` giving two claims and two episodes, and two
  same-horizon rules refusing through `_Body.add`. This is episode-level proof only (C-8).
- (f) A7's episode separation, through an injected registry; neither scope's `.latest` touches the other.
  Binding proof is Task 3 (R9).
- (g) A8, synthetic: r4 (F4) Apar no longer proves it; (h) A9; (i) A10; (j) A11, full correction path over two builds; (k) A12, including the
  side-by-side downward revision and a missing comparator; (l) A13; (m) A14.
- r4 (F2): (m2) a statement in an FY26 period targeting FY27, on a registered metric, whose FY26 year-to-date value
  would meet the bound (and, parametrized, miss it): `UNRESOLVED` ("not due: target year not started"), never
  `ON_TRACK` or `BEHIND`, no `.ytd`. The same statement in FY27's first quarter reads FY27's months against the same
  months a year earlier. Boundaries: the period end on the target's last day is `ENDED`, on its first quarter's end
  `OPEN`.
- r4 (F3): (j5) an entry `B` whose `same_as` target `A` has no pool statement, with `B` recorded and unchanged,
  parametrized on `A` unedited, edited and superseded: each `prepare` refuses; `A` deleted refuses at load. With
  `A` in the pool, editing or deleting `A` refuses through `check_pins`, and superseding it renders the correction.
- r4 (F4): (j6) a `DESCRIPTIVE` entry, including one declaring `FY26`: its own episode, `DESCRIBED`, `UNRESOLVED`
  with only `REASON_DESCRIPTIVE`, no event against a same-metric statement, no due window. A `supersedes` correction
  from `COMMITMENT` to `DESCRIPTIVE` moves the quote through the correction path and shows both readings.
- r4 (F1): (j7) `prepare` refuses a new entry with a different quote and a declared window failing first use.
- r4 (F6): (n2) every line of a one- and a two-statement episode's body satisfies the reference contract.
- r2 (R2): (j2) A → B → C with B corrected into another episode: B keeps its full contract and citation,
  A → C is recomputed, and the earlier body is unchanged. (j3) A definition-only correction turns a
  directional event into `REVISED` ("basis changed"), with a correction line.
- r2 (R4): (j4) a post-year-end Q4 statement unmapped in the Q4 build and mapped in the Q1 build stays
  `AMBIGUOUS` under `stated FY26_Q4`, and a declared `FY27` refuses.
- r2 (R8): (r) `read_record` refuses each of: malformed, duplicate entry, duplicate claim, an omitted
  statement line, an extra line, a malformed retired line, a missing header. It returns empty on a legacy
  head and returns every pin after multiple corrections (A → B → C). `build` output round-trips through it.
- r2 (R14): (s) no statement renders the empty paragraph; an all-unresolved section renders its rows and
  D8 naming each distinct reason.
- (n) `scan_section` on rendered bodies of all statuses returns no state.
- (o) every disclosure constant is in the body.

Test seams: `revision`, `assess`, `prepare`, `build`. Pure, no I/O.

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
  admitted. r2 (R5): each used actual's exact `Fraction` is returned, read from the carried trace through
  the repository. r3 (R5): the claim holds its `truncate_value` digits under `EXACT_DIGITS`, and the check
  resolves them from the trace's `exact_value` (P4). r2 (R6): an ineligible comparator gives P11's reason,
  not a claim.
- A used entry that changed, or r4 (F1) a new entry failing `prepare`, refuses before the run's first write:
  every table unchanged.
- A rejected `episode.*` or `cred.*` claim refuses with P10's route.

Files:
- Modify: `src/fundamentals/ledger/credibility.py` (binding half),
  `src/fundamentals/ledger/falsifier_status.py`, `src/fundamentals/ledger/run_draft.py`,
  `src/fundamentals/ledger/rework.py`, `src/fundamentals/api/cli.py`,
  `src/fundamentals/canon/interval.py`, `src/fundamentals/ledger/display.py`,
  `src/fundamentals/ledger/citations.py`
- Create: `config/guidance_targets/aparinds.yaml` (tests round)
- Test: `tests/fundamentals/test_credibility_binding.py`, `tests/fundamentals/test_pilot_e2e.py`,
  `tests/fundamentals/test_report_export_gaps.py`, `tests/fundamentals/test_prep5_rework.py`

Interfaces:
- Consumes: Tasks 1, 2; `_Binder.filed/evaluate/store`, `CHANGE_PCT`, `cite`, `_valued`,
  `_fiscal_month`; `_OPERAND_BLOBS`.
- Produces:
  - `CredibilityInputs` (frozen): r4 (F1) `prepared: Prepared`, `actuals: tuple[NumericClaim, ...]`,
    `exact: Mapping[str, Fraction]`, `unavailable: Mapping[str, str]`.
  - r4: `stated_claims(cursor, guidance, update, prior, catalog) -> tuple[NumericClaim, ...]` (`run_draft.py`), the
    run's `_quote`d claims with a rework's carried form. `_guidance` is unchanged.
  - `bind_credibility(repo, update, prepared, prior_actuals, *, entity_id, versions, registry=ACTUALS) ->
    CredibilityInputs`.
  - `RunDraft.credibility: CredibilityInputs`.
  - r3 (R5): `truncate_value(value: Fraction, places: int) -> Decimal` (`canon/interval.py`);
    `EXACT_DIGITS = "exact_digits"` (`display.py`); `EXACT_PLACES = 6`, `ACTUAL_WHOLE`, `ACTUAL_CUT`
    (`credibility.py`).
  - `Prior.episodes`, `Prior.record: Record = Record()`, `Prior.same_period_id: int | None = None`,
    `Prior.same_period_digest: str | None = None`, `Prior.same_period_record: Record = Record()`,
    `Prior.actuals: tuple[NumericClaim, ...] = ()`, `Prior.actual_blobs: frozenset[str] = frozenset()`.

Approach:
- **`preflight` (C-2, r2, R1, R8).** Before the bootstrap return, a closed same-period head loads its id,
  sealed digest and `read_record`. Then, for the previous-quarter head: `quotes` stay the retention check;
  `entries` becomes those outside `CREDIBILITY`; `episodes` those inside; `record` its `read_record`;
  `actuals` its `cred.*` claims without `.ytd`; `actual_blobs` from `_OPERAND_BLOBS` over their traces.
- **`allowed_captures`** adds `episodes`' blobs and `actual_blobs`.
- **`write_run_draft`.** r2 (R1): under lock, `current` must equal `prior.same_period_id` with the same
  sealed digest, else `RunDraftError`, beside the existing previous-quarter check. r4 (F1): `build` from
  `run.credibility.prepared`, add `Built.claims` and the used actuals to `claims` before `_check_sources`, append
  the section after `probe_section`.
- **`before_commit`, r4 (F1, P12).** First, in one read-only cursor: the head check, then
  `prepare(stated_claims(…), prior.record, prior.same_period_record, targets, …, actual_blobs=prior.actual_blobs)`,
  then `admit(update, prepared.blobs)`. `filed_at` is `retrospective.published`, or empty on an ordinary run. Only then
  `bind_computed`, `bind_probe`, `bind_credibility` and `_admit`.
- **`bind_credibility`.** r4 (F1, F2): windows due are `prepared.windows` of registered metrics: a pool statement's
  entry, so no later transcript's window computes early, and never `NOT_STARTED`. r4 (F5): sources are **every
  admitted XBRL** in the fixed order own, QoQ, YoY, as `bind_probe` reads them (`risk_probe.py:471-478`; admitted at
  `cli.py:343-347`). Each required operand is sought separately through `_Binder.filed` in every source: no source
  has it, so no claim and the row reads as spec §3 (ended: "actual not yet filed"); every value found equal, so the
  first in order is used; values differing, so no claim, no trace and `UNRESOLVED` ("filed value differs across
  admitted captures").
  r2 (R9): `measurement_key` hard-codes `Basis.CONSOLIDATED` (`import_mapping.py:372-385`), so operand and
  output keys take `.model_copy(update={"basis": Basis(scope.upper()), "period": …})`. `_Binder.filed`
  matches on `key.digest()`, which includes basis, so scope selects the operand and stays on the output.
- **`NOT_DONE`.** "- a management-credibility assessment" becomes "- a judgment of management
  credibility: `management_credibility` holds only the mapped record, revision events and
  code-computed outcomes; no model explanation, trend or thesis consequence".
- **Apar file.** A scratch seed reads quote, blob and anchor from the S1 export's `ref` and quote
  text (`scratchpad/research3-s1/task6/live/export/APARINDS`). The implementer adds only `id`,
  `window_text`, `window`, r4 (F4) `reading`, `definition` and `same_as`, after reading each quote's transcript
  context. **Provisional predictions from the rule patterns (r2, R7 revisited them):**

  | Entry id | Quote from (PDF page) | Reading | Window (reason) | `same_as` | Definition |
  |---|---|---|---|---|---|
  | `conductor-ebitda-FY26_Q2` | FY26_Q2 (12) | `COMMITMENT` | `AMBIGUOUS` (no year) | | `conductor_ebitda_per_mt` |
  | `cables-growth-FY26_Q2` | FY26_Q2 (20) | `COMMITMENT` | `AMBIGUOUS` (undated "year on") | | `cables_revenue_growth` |
  | `cables-growth-FY26_Q3` | FY26_Q3 (14) | `DESCRIPTIVE` | `MULTI_YEAR` (CAGR) | | `cables_revenue_cagr` |
  | `cables-margin-FY26_Q3` | FY26_Q3 (30) | `COMMITMENT` | `AMBIGUOUS` (no year) | | `cables_ebitda_margin` |
  | `conductor-ebitda-FY26_Q4` | FY26_Q4 (9) | `COMMITMENT` | `AMBIGUOUS` (no year) | `conductor-ebitda-FY26_Q2` | `conductor_ebitda_per_mt` |
  | `conductor-volume-FY26_Q4` | FY26_Q4 (16) | `COMMITMENT` | `AMBIGUOUS` (undated "year-on-year") | | `conductor_volume_growth` |
  | `cables-growth-FY26_Q4` | FY26_Q4 (16) | `COMMITMENT` | `MULTI_YEAR` ("a year") | | `cables_revenue_growth` |
  | `cables-margin-FY27_Q1` | FY27_Q1 (8) | `COMMITMENT` | `AMBIGUOUS` (no year) | `cables-margin-FY26_Q3` | `cables_ebitda_margin` |

  A no-year entry's `window_text` is its whole quote, the strictest input to P3. The FY26_Q2 cables quote
  is `AMBIGUOUS`, so r1's link from the CAGR quote fails the window-class check (R3) and that quote opens
  its own episode. r4 (F4), from reading the retained pages: the FY26_Q3 quote is management's answer on progress
  against an existing program, so it is `DESCRIPTIVE`. The FY26_Q4 quote looks forward, but page 16 ties it to what the
  program needed at launch, not to a change from the Q3 quote, so r3's link and its "basis changed" event are removed.
  It cannot link the FY26_Q2 quote either, since the window classes differ (R3); those two rows stand side by side
  with no event. Conductor and margin carry the numeric events; FY27_Q1 restates standing guidance while explaining
  the quarter, the weakest `COMMITMENT` reading, and Sol's review must rule on it. No episode reaches three
  statements, so Apar holds no `.stated.*` claim.
- **Freeze before rehearsal (r2, Sol ruling; r4, F4).** The table, `E` and the delta table are planning inputs only.
  After the implementer's transcript reading, Sol's phase-end review judges each entry's **reading**, window, definition
  and link against the source, by page and section, and rejects any link or commitment the context does not
  support. The orchestrator then commits the approved entries, readings, windows, links, event and reason literals
  and recomputed deltas to this plan as **frozen expectations**, naming Sol's verdict and date. Task 4 does
  not start before that commit. An observed rehearsal delta or row that differs is a deviation; it never
  replaces a frozen value. Changing one needs a recorded reason and a fresh Sol round.
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
  figures, never by the probe or this code. r3 (R5): each constant is compared as the exact `Fraction` and
  as its six cut digits. Each claim resolves `MATCH` through `check_claim`.
- `test_a_carried_actual_keeps_its_citation_and_captures`: the next run's `cred.*` is the prior's
  citation, its blobs admitted; an unadmitted one refuses "captures not in the run's package".
- `test_a_changed_entry_refuses_before_any_write`: parametrized edit and delete; counts unchanged.
- r4 (F1) `test_a_new_invalid_entry_refuses_before_upstream_writes`, through `pilot.run` on FY26_Q2 on a database
  where it has not run, so upstream work has records to add. Parametrized on a new entry whose quote differs from the
  joined claim, a declared window failing first use, and a link to an absent statement: each refuses with every
  table's count unchanged. Then the same run with a valid file succeeds and `calculation_traces` **and** the admitted
  facts strictly increase, which proves the refused run had new writes to make. A fourth case has a prior episode's
  capture fail `check_blobs` (for example published after the run's cutoff); its fixture is settled in the tests round,
  before red sealing, and must not mock the call order.
- r4 (F5) `test_an_ended_target_reads_its_operands_from_the_qoq_capture`, same synthetic fixture as R9: an FY26 target
  first mapped in the FY27_Q1 run, with both annual operands seeded only on that run's QoQ capture and no carried
  actual: a `cred.*` claim whose operands name that capture, `MATCH`, not "actual not yet filed". Parametrized: the
  same operand on own and QoQ with one value uses own; with differing values gives no trace and the disagreement
  reason; on no capture gives "actual not yet filed". Sol did not reproduce a stored case; this fixture is the proof.
- r4 (F2) `test_a_future_target_binds_no_interim_actual`, same fixture: FY27 target at an FY26 run with year-to-date
  operands present: no `.ytd`, no trace added, the "not due" row.
- `test_a_rejected_episode_claim_routes_to_a_mapping_correction`: the ordinary run refuses naming the route
  with zero writes, **even after** a `supersedes` entry is appended; `--full-successor` then writes a draft
  carrying the correction line.
- r2 (R1) `test_a_same_quarter_rerun_holds_that_quarters_pins`, on the bootstrap FY26_Q2 whose head has S2
  pins and no previous-quarter head, under a head both rejected and approved: an edited and a deleted used
  entry each refuse with zero writes; a superseded one reruns, its full successor rendering the correction
  line and the "mapping corrected" row. A stale `same_period_id` or digest refuses under lock.
- r2 (R9) `test_standalone_and_consolidated_bind_their_own_statements`: a synthetic-interpretation fixture
  seeds standalone revenue in the pilot's test database, at both windows, with values different from the
  consolidated ones, on the same capture and pins. Through `bind_credibility` with an injected registry
  and then `build`, each `cred.*` has its own key basis, operand interpretation ids and value, each equal
  to an independent scratch `Fraction` result.
- r2 (R5), r3 `test_a_verdict_reads_the_exact_trace_value`, same fixture: operands giving exact 9.495, whose
  trace stores 9.50; `exact` holds 9.495; the `cred.*` claim is `9.495000` under `EXACT_DIGITS`, the rendered
  row shows `9.495000%`, `ACTUAL_WHOLE` and its trace `ref`, and the row is `MISSED` against a whole-number
  ten, in the binding run and in a next run carrying the claim, whose `exact` comes from the stored trace.
  Through the real `resolve_citation` and `check_claim`, that claim is `MATCH`, while a copy typing `9.500000`,
  and a copy of the true digits without the qualifier, are each `VALUE_MISMATCH`. Parametrized with operands
  giving 100/3: `33.333333`, `ACTUAL_CUT`, `MATCH`.
- r2 (R6) `test_an_undefined_comparator_is_a_row_reason`, same fixture, parametrized: point zero, negative,
  and an interval crossing zero give no trace, no claim, P11's reason, and a written draft. Two mapped
  interpretations of one key still raise.
- r2 (R11) `test_a_relabelled_guidance_rework_changes_only_its_claim` (amended in `test_prep5_rework.py`):
  claims outside `CREDIBILITY` keep today's assertion; that guidance claim's `.original` and `.latest` copies
  take the corrected label and otherwise equal the head's; every other episode claim is unchanged; the
  two-moved-lines assertion stands, because rows render no `metric_label`.

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
thesis v13. A first S2 draft's `predecessor_id` is that head, and each approval supersedes its head.
v14 and v17 stay `CHANGES_REQUESTED` as records. Regeneration order is forced: an S2 run opens its episodes from its previous-quarter head's, so
FY26_Q3 run against S1's FY26_Q2 would lose the first statements. v15 and v16 were written before
`2992ec9f`, so the new FY26_Q2 and FY26_Q3 also gain the limit-basis sentence in `risk_probe`; this is
expected, and gate (d) allows only that sentence. The orchestrator verified these heads and thesis v13 as
`APPROVED` on 2026-11-01.

**Three head ids, r2 (R12), r3.** `$S1` is the quarter's fixed S1 version, the preservation baseline; it has
no `.latest` and never changes. `$SAME` is the current same-period head and the new draft's `predecessor_id`
(`run_draft.py:374`): `$S1` on a first attempt, and the latest S2 draft on any attempt after a rejection, so
it may already hold `management_credibility`. `$PREV` is the previous quarter's **new** S2 head, the only
source of episode carry.

| Quarter | `$S1` | `$SAME`, first attempt | `$PREV` |
|---|---|---|---|
| FY26_Q2 | v15 | v15 | none (bootstrap) |
| FY26_Q3 | v16 | v16 | new FY26_Q2 |
| FY26_Q4 | v18 | v18 | new FY26_Q3 |
| FY27_Q1 | v19 | v19 | new FY26_Q4 |

r3: gate (d) always compares with `$S1`, gate (d2) with `$SAME` when `$SAME` is not `$S1`, gate (e) with `$PREV`.

**Paths.** `OUT=scratchpad/research3-s2/task4/$ENV`, `ENV` = `rehearsal` or `live`, holding `out/`,
`responses/`, `verdicts/`, `gate/`, `counts/`, `logs/`, `rulings/`, `export/` at close. No path is shared with S1
or between environments. Preflight before each environment's first write: `$OUT` does not exist,
and is then created `mkdir -m 700`; for each quarter no output exists and `$LOC/<Q>.json` and
`$INTAKE` are readable. Any failure stops before any write. Attempt `<n>` of a recovery uses
`<Q>-r<n>` on every path.

**Expected counts delta per write, stated before running (provisional until the freeze, Task 3).** `E` is
the quarter's episodes from the Task 3 table. Each episode adds `max(2, its statements)` claims; Apar's
maximum is two statements, so `2E`.

| Quarter | `E` | `run` (`report_versions`, `report_sections`, `numeric_claims`) | `check`, `panel` |
|---|---|---|---|
| FY26_Q2 | 2 | +1, +11, +91 (S1 87 + 2E) | states +91 |
| FY26_Q3 | 4 | +1, +11, +86 (S1 78 + 2E) | states +86 |
| FY26_Q4 | 6 | +1, +11, +101 (S1 89 + 2E) | states +101 |
| FY27_Q1 | 6 | +1, +11, +91 (S1 79 + 2E) | states +91 |

`calculation_traces` and `calculation_trace_operands` +0 on each run (F-8). `check`: `validations`
+1. `submit`: `decisions` +1. `export`: none. `panel`: `decisions` +1, `panel_reviews` +1,
`validations` +1.

r2 (R13), recovery writes, rehearsal only:

| Step | Delta |
|---|---|
| r4 (F7): the correction drill's `run --full-successor` on FY27_Q1 | the quarter's `run` row, same claim count |
| `ledger decide … REQUEST_CHANGES --claim <key>` | `decisions` +1 |
| The refused ordinary `run` | every table 0 |
| Appending a mapping correction, when one is needed | every table 0 (a file change, committed) |
| `run --full-successor` | the quarter's `run` row, same claim count |
| Its `check`, `submit`, `panel` | as above |

r4 (F1): any other Task 4 refusal from P12's guaranteed-zero list is 0 on every table. A late refusal (P12) rolls
back its version but may leave traces and facts: stop, record the measured delta, and explain it. It is never expected,
never retried blindly, and a live one is a deviation. In the rehearsal, a delta differing from these tables
is a deviation to explain before live. Then each live step must equal its rehearsal step's delta; the
recovery steps have no live counterpart.

Approach:
1. **Rehearsal, all four quarters, on a restored copy.** `db backup` → `db restore --database
   eqos_test_s2_runs` through the live environment, as LIVE-RUN-1 L1a; roots are `cp -a` copies under
   `$OUT/roots/`. Record each exit, id, delta, claim state and gate result. The rehearsal panel uses
   a `rehearsal` verdict file and an orchestrator-written response.
   - **Recovery rehearsal, r2 (R13), complete sequence, on FY26_Q2:**
     1. `run`, `ledger check`, gates, `ledger submit`, as a normal quarter;
     2. `ledger decide REPORT_VERSION <v> REQUEST_CHANGES --claim <an episode key> <
        $OUT/rulings/FY26_Q2-recovery.txt`, the ruling a file written first, since `decide` reads it
        verbatim from stdin (`ledger_cli.py:227`); deltas checked;
     3. an ordinary `run` must refuse with P10's route, all deltas 0;
     4. diagnosis: the rejection is a drill with no real mapping fault, so nothing is appended. The
        correction branch is proven by `test_a_rejected_episode_claim_…`, never by editing the shared file;
     5. `run … --full-successor` writes `<v2>`; `<Q>-r1` on every path; deltas checked;
     6. `ledger check`, gates on `<v2>`, `ledger submit`, `ledger export`, the rehearsal response and verdict,
        `ledger panel <v2>` → `APPROVED`. `<v2>` must be approved, since FY26_Q3 needs an `APPROVED`
        previous-quarter head. r3 (R12): the gates run on `<v2>` with `$S1` = v15 and `$SAME` = `<v>`: (d) and
        (d2) must both pass, and `$OUT/gate/FY26_Q2-r1.txt` names both baselines. This is the recovery gate's
        exercise before any live work; a failure is a deviation that stops the rehearsal.

     The remaining quarters continue from `<v2>`.
   - **Correction drill, r4 (F7), on FY27_Q1, the last quarter, so nothing depends on it.** After its normal `run`,
     `check`, gates and `submit`: `REQUEST_CHANGES --claim <an episode key>`; then copy `src` to `$OUT/drill-src` and
     change one disclosure sentence there, a real S2 wording correction, never committed and never on a live path;
     write its delta file (below); `PYTHONPATH=$OUT/drill-src run --full-successor` writes `<v2>`. Before submit, the
     gate must **fail** with an empty delta, and with a delta naming `risk_probe`, and **pass** with the true one. Then
     `submit`, `export`, response, verdict, `panel` → `APPROVED`. An unaffected section or claim moving is a deviation.
     Apar has no `cred.*` claim, so the delta's `cred.*` branch is not exercised live; `cred_gate.py` is run on a
     scratch pair of `model_dump()`s to prove that branch.
   - **Rehearsal health, r2 (R13).** `db check-live` refuses an `eqos_test_*` database by design
     (`db_cli.py:136-137`), so it is not a rehearsal step. After each rehearsal write the checks are the counts
     delta, `ledger check`'s states and the gates; `digests.py` runs at the rehearsal's close. `db check-live`
     is live only.
2. **Live, per quarter, in order; stop at the first deviation; never re-run a write that partly
   committed.** Reuse the quarter's locator; no `stage`.
   - `fundamentals-operator run …` → `run_draft_written version=<v>`; delta checked.
   - `ledger check` → all `MATCH`/`MATCH_UNTRUSTED`; delta checked.
   - **Gates, read-only, output to `$OUT/gate/<Q>.txt`:** S1's `probe_gate.py`, then `cred_gate.py`:
     - (a) the draft binds thesis v13 by its sealed digest;
     - (b) section order: `observable_falsifiers`, `risk_probe`, `management_credibility`;
     - (c) episodes, entries and pins equal the file's digests, with `.original` equal across the
       new chain;
     - (d) r2 (R12), r3, **no earlier number moved**, against `$S1` on every attempt. Section keys are `$S1`'s,
       in order, plus `management_credibility` after `risk_probe`. Every section is byte-identical except:
       `heading`; `not_performed`, whose one credibility line alone differs; and, FY26_Q2 and FY26_Q3 only,
       `risk_probe`, which must equal `$S1`'s once the `2992ec9f` sentence ("The thesis limits are derived
       … that limitation.") and its leading space are removed, and must contain it exactly once. Every
       `$S1` claim's full `model_dump()` equals the new claim's: bounds, precision, qualifiers, label,
       measurement key and citation included. **The citation exception list is empty.** If the rehearsal
       shows a citation id moved, that is a deviation: one named id field may be excused only where its
       record has the same key digest, file and value, with the reason in the bead and Sol's review;
     - (d2) r3 (R12), r4 (F7), **the recovery changed only what its delta names**, against `$SAME`, only when `$SAME`
       is not `$S1`. Section keys are equal, in order, and `heading` names `$SAME` as the full successor's head
       (`run_draft.py:706`). Every section and claim the delta does not name is identical; every named one must
       differ, so no stale exception passes. The delta is `$OUT/rulings/<Q>-r<n>-delta.json`, written before the
       successor runs: `sections` ⊆ {`management_credibility`, `not_performed`}, `claims` (exact keys added, changed or
       removed, each `episode.*` or `cred.*`), `reason`, `review`. No delta file means an empty delta. Live, `review`
       names Sol's `APPROVE` and date on the fix, and the delta and any changed literal in (c), (e) and (f) are committed
       to this plan as frozen expectations (Task 3) first. A `supersedes` correction and a code fix use this one
       mechanism. Gate (d) still holds against `$S1`, so no correction can reach earlier content;
     - (e) r2 (R12), r3, each event recomputed in `Decimal` from the version's own statement claims in record
       order. Every `$PREV` statement is in the new record with the same entry, digest and period, and the
       same claim under `model_dump(exclude={"claim_key"})`, so its contract, citation and originating period
       are preserved, unless a correction line names it. Only the key's role may move, as the statement count
       requires: when a later statement arrives, a lone statement's `.original`/`.latest` pair, which must be
       equal but for the key, becomes `.original` alone, and a former `.latest` that is now between two
       statements becomes `.stated.<entry id>`. FY26_Q2 has no `$PREV`;
     - (f) every outcome and reason equals the frozen literals (Task 3);
     - (g) the results equal the rehearsal's, r4 (F7) on each quarter's approved attempt, or, for FY27_Q1, its
       first attempt, since the drill's wording is not live's.
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
`db check-live` exits 0 after every live write; every delta matches. `digests.py` shows every earlier
sealed digest unchanged.

Dependencies: Tasks 1–3 committed, gate `ROUTE: PASS`, Sol's phase-end `APPROVE` covering the code
and each mapping entry, and the frozen-expectations commit (Task 3).

Risks:
- Permanent writes. A panel `REQUEST_CHANGES` with no claims is recorded, and the quarter reruns
  from a verified fix as S1's v14 and v17 did; a code change re-enters the phase-end loop before any
  further live write, r4 (F7) and gate (d2) reads its frozen delta.
- A rejected mapping after any live version pins it: a `supersedes` entry and a correction line,
  never an edit, then P10's route.

## Report disclosures (S1 lesson 2; fixed, digit-free, in `credibility.py`)

Sol's two S1 rejections were an undisclosed absence and an undisclosed basis. Each S2 limit is stated
in the report, and test (o) asserts each constant.

| Id | Limit | Sentence (implementer may tighten wording, not drop content) |
|---|---|---|
| D1 | No verdict | This section records stated guidance and code-computed comparisons. No overall credibility judgment, trend or thesis consequence is computed or drafted. |
| D2 | Coverage (r4, F4) | Only quotes the run's extraction rules captured are tracked, and each rule keeps its first match, so this is not an inventory of management's commitments. Promises before this report chain's first period are absent. Whether a captured quote is a commitment is a reviewed reading of its context; a quote read as descriptive is kept as evidence and is never scored or compared as a promise. |
| D3 | Mapping basis | Each quote's reading, window, definition and restatement link come from a reviewed mapping file written after these calls were published, not from the filing. Each row names its entry and digest. |
| D4 | Scope | Scope is the extracted guidance contract's field. Extraction labels every quote consolidated, so a metric naming a segment is identified by that name. |
| D5 | Event basis | Events compare a point, a range's midpoint, or a binding bound when one statement is open-ended. A qualifier such as "about" is ignored. Up and down state a number's move, not whether it is good or bad. |
| D6 | Measures | An outcome needs a registered filed measure. "No filed measure" means this pipeline computes no comparable actual, not that the company files none. |
| D7 | Windows | A quote with no single-year window cannot be scored achieved or missed, so its row stays unresolved. |
| D8 | Result (r2, R14) | When statements exist and no row reaches an outcome: "No row in this version reaches an achieved, missed or interim outcome. Reasons: <each distinct row reason>." |
| D9 | Empty (r2, R14) | When no statement exists: "No guidance quote has been extracted in this report chain, so no commitment is tracked." |
| Row | Tolerance, interim | OD-7's "rounded to the guidance's stated precision", beside the actual, and r3 (R5): "the verdict rounds the exact computed value once", with `ACTUAL_WHOLE` or `ACTUAL_CUT` on the digits shown (P4). The fixed "seasonality not adjusted; year-to-date assumed representative". |

## Acceptance map (spec §5 S2)

| # | Acceptance case | Proven by |
|---|---|---|
| A1 | Revision events, including plus against range | Task 2 (a) |
| A2 | Ended: `MISSED` `.original`, `ACHIEVED` `.latest`, tolerance, r3 (R5) and the unrounded actual: a traced, checked claim of the exact value's digits, whole or declared cut (P4) | Task 2 (b); Task 3 `test_a_verdict_reads_…` |
| A3 | CAGR under `annual` → `MULTI_YEAR`, `UNRESOLVED` | Task 1; Task 2 (c). r4 (F4): Apar's CAGR quote is `DESCRIPTIVE`; its "a year" quote shows `MULTI_YEAR`, `UNRESOLVED` via `check_credibility` |
| A4 | No year → `AMBIGUOUS`; anchor-only year refused | Task 1; Task 2 (c) |
| A5 | FY26 and FY27 two episodes; one transcript, one rule per year; same horizon refuses | Task 2 (d)(e): extraction and episode level, not end-to-end `AS_KNOWN` (C-8) |
| A6 | Relative years, Q3 against Q4 | Task 1 |
| A7 | Standalone and consolidated | Task 2 (f); r2 (R9) Task 3 `test_standalone_and_consolidated_…` |
| A8 | Two `MULTI_YEAR` apart, linked one with an event | Task 2 (g), synthetic. r4 (F4): Apar has no such link |
| A9 | Basis-changing revision | Task 2 (h) |
| A10 | Editing or deleting a used entry refused on the next run | Task 1; Task 2 (i); Task 3 `test_a_changed_entry_…`; r2 (R1) `test_a_same_quarter_rerun_…` |
| A11 | Correction with `supersedes` | Task 2 (j)(j2)(j3); r2 (R1) `test_a_same_quarter_rerun_…` |
| A12 | Interim, side by side, missing comparator; r4 (F2) a future target not due | Task 2 (k)(m2); Task 3 `test_filed_actuals_…`, `test_a_future_target_…` |
| A13 | Plan note: both carried endpoints; a used entry gone | Task 2 (l); Task 1; `check_credibility` chain |
| A14 | Ended with no actual → "actual not yet filed"; r4 (F5) only after every admitted capture | Task 2 (m); Task 3 `test_an_ended_target_…` |
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
  `Statement`, `Event`, `Outcome`, `Better`, `Actual`, `INTERIM_RULE_LABEL`, `ACTUALS`, `ACTUAL_KEY`,
  `revision`, `compare`, `assess`, `Recorded`, `Record`, `read_record`, `build`, `Built`,
  `CredibilityInputs`, `bind_credibility`, `CREDIBILITY`, `check_credibility`, r3 `truncate_value`,
  `EXACT_DIGITS`, `EXACT_PLACES`, `ACTUAL_WHOLE`, `ACTUAL_CUT`, r4 `Reading`, `REASON_DESCRIPTIVE`, `chain`, `prepare`,
  `Prepared`, `stated_claims`, `WindowState`, `window_state` are each produced once and consumed by name.
- **What has nobody named?**
  - Episode quotes re-emitted as guidance → C-2.
  - A later run flipping a relative window → C-7.
  - A superseded entry's pin after its episode is dropped → the retired block (P2).
  - Same-quarter pins on a rerun → P9. A middle statement's reference → P2. A late mapping's period → P3.
  - An `.original` on a transcript no ledger entry cites → F-3.
  - The wrong rework route → F-2, P10.
  - Regeneration order and S1 chain → Task 4 lineage.
  - v15 and v16's missing limit sentence → Task 4 gate (d).
  - r3: a recovery draft's predecessor already holding S2 → Task 4 `$S1`, gate (d2).
  - r4: a mapping fault found after upstream writes → P12. Next year's target scored on this year → P7. A root outside
    the pins → P13. A description read as a promise → P14. An operand only in the QoQ capture → Task 3. A legitimate S2
    fix blocked by the recovery gate → the delta in (d2).
  - Hindsight in the mapping → D3.
  - The hard-coded `consolidated` → C-10, D4.
  - The status dashboard (`docs/status/dashboard.html`) is refreshed by the orchestrator after each
    committed task (routine, not a plan task).
  - Follow-up bead to file: sealed binding for a year-specific rule (C-8).
  - S3's duty to deliver the trend and thesis-consequence requirement → C-12, bead note at close.
- **Unverified.** r4: the readings, links and windows rest on one reading of the retained pages named in the Task 3
  table, not on Sol's review; they, `E` and the deltas are provisional until the freeze (Task 3). That `_quote` and the
  rework gate write nothing, on which P12's guarantee rests, is read from the code, and F1's test proves it. The empty citation-exception list in gate (d) is
  inferred from the code, not observed. r3 (ruling): deferring it to the rehearsal is accepted, provided a
  deviation stops progression and any exception gets the review gate (d) specifies. The synthetic fixture's
  write mechanism is settled in the tests round, before red sealing and production changes, and must demonstrate
  actual binder selection, not mock it away. No test or database command was run for this plan. `S2_BASE`
  assumes no other slice gates before S2's first code commit. Verified: the database heads (Task 4 lineage).
- **Owner's financial judgment.** None is decided here: no credibility verdict is computed. Two
  items the owner may overturn: the materiality extension and the deferral of the "rising or falling"
  reading to S3.
