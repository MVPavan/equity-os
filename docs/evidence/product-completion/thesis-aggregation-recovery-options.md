# Apar thesis aggregation and recovery — decision options

**Status: PROPOSED.** Prepared 2026-10-02 for `eqos-4j2.14`. No option is human-approved or implemented by this document.

The [approved Q0 machine twin](../phase-0.5/q0-approved-thesis.yaml) explicitly leaves aggregation and recovery undefined. A quarter-level breach currently says `WEAKENED`; it does not decide whether the standing approved thesis recovers. Choose one policy below before implementing that distinction. These are workflow proposals, with no calibrated severity, probability, valuation or investment conclusion.

## Fixed inputs and proposed grouping

The [approved falsifiers](../phase-0.5/q0-approved-thesis.md#approved-thesis) remain F1: revenue YoY <11.55%; F2: PBT margin <5.53%; F3: PAT YoY <14.90%; F4: EPS YoY <=0%; F5: effective tax rate >26.78%. All five retain their individual outcomes and evidence. Equality therefore passes F1/F2/F3/F5 and breaches F4.

**PROPOSED grouping, common to all three options:**

| Group | Members | Reason and limitation |
|---|---|---|
| Growth | F1 | Company revenue growth. |
| Earnings | F2, F3, F4 | Margin, profit and per-share growth can reflect the same earnings mechanism; three simultaneous breaches form one review episode. Dilution can be independent, so every member remains visible. |
| Tax | F5 | Preserve the separately approved tax test; show its possible relationship to PAT/EPS alongside the earnings episode. |

**PROPOSED classification, independently for each group each quarter, in this precedence order:** `BREACH` if any evaluable member breaches, even when another member is missing, conflicted or ineligible; otherwise `CLEAN` if every member is evaluable and passes; otherwise `UNKNOWN` (displayed as `UNEVALUABLE`). An unavailable member stays individually `UNEVALUABLE`; a known breach is never erased by missingness. Missing Earnings members cannot interrupt fully observed Growth or Tax. This classification applies to A, B and C.

Grouping is an administrative correlation hypothesis, not an established causal or statistical relationship. Do not add group counts into a severity score: Tax and Earnings can still be correlated. A member moving within a group does not start another group episode. Count both member breaches and group episodes so grouping cannot hide dilution or tax evidence. Management commitments stay in their own ledger; no segment promise becomes a company-level falsifier.

## Three PROPOSED choices

| Choice | Aggregation | Recovery effect | Main tradeoff |
|---|---|---|---|
| A — quarter snapshot | Display groups breaching in the latest evaluable quarter. Any breach opens an episode. | One fully evaluable clean quarter closes that group's monitoring episode. | Least review backlog, but one clean quarter may overstate durable recovery. |
| B — persistence with two-quarter recovery | First breached quarter is `WATCH`; two consecutive breached quarters in the same group yield `PERSISTENT`. A different member of that group can breach in the second quarter. | A persistent episode requires two consecutive fully evaluable clean quarters: first `RECOVERY_PENDING`, second `RECOVERED`. An isolated watch closes on one clean quarter as `WATCH_CLEARED`. | Filters transient signals and makes recovery inspectable; delays persistence recognition and recovery. Two quarters is a proposed operational choice, not a calibrated economic threshold. |
| C — analyst-closed episodes | First breach opens a latched group episode immediately. Further breaches append evidence to it. | Clean quarters append recovery evidence; episode stays `OPEN_FOR_REVIEW` until an analyst records closure and rationale. | Greatest human control; highest unresolved-episode burden. |

For every choice, each raw predicate breach is still reported immediately as the approved `WEAKENED` outcome. Proposed episode labels are a separate monitoring layer. Neither a clean quarter nor episode closure changes the approved narrative, publishes a successor, or promotes memory. Those require the existing human decisions and artifact bindings.

**PROPOSED recommendation: B.** It exposes transient versus repeated grouped breaches without automatically treating every correlated metric as another strike. Accept its slower recovery and the possibility that alternating earnings members establish persistence. If that behavior is unacceptable, select C rather than silently changing B. No policy adoption is recorded here.

## Deterministic synthetic sequence

Every number below is synthetic. S1–S8 are consecutive illustrative quarters, not Apar observations or forecasts. All five inputs are available in every row; percentages use the approved metric definitions.

| Quarter | Revenue YoY | PBT margin | PAT YoY | EPS YoY | Tax rate | Breached members | Breached groups |
|---|---:|---:|---:|---:|---:|---|---|
| S1 | 20 | 5 | 10 | -1 | 25 | F2,F3,F4 | Earnings |
| S2 | 20 | 6 | 20 | 5 | 27 | F5 | Tax |
| S3 | 20 | 6 | 20 | 5 | 25 | none | none |
| S4 | 20 | 6 | 20 | 5 | 25 | none | none |
| S5 | 10 | 6 | 20 | 5 | 25 | F1 | Growth |
| S6 | 10 | 6 | 20 | 5 | 25 | F1 | Growth |
| S7 | 20 | 6 | 20 | 5 | 25 | none | none |
| S8 | 20 | 6 | 20 | 5 | 25 | none | none |

There are **six member breach occurrences**, four breached group-quarter occurrences, and three distinct affected groups. The three correlated Earnings breaches at S1 create one episode. S5–S6 are one continuing Growth episode, not two.

| Quarter | A — snapshot episodes | B — persistence/recovery | C — latched episodes, no analyst closure supplied |
|---|---|---|---|
| S1 | Earnings open | Earnings WATCH | Earnings open |
| S2 | Earnings recovered; Tax open | Earnings WATCH_CLEARED; Tax WATCH | Earnings, Tax open |
| S3 | Tax recovered; none open | Tax WATCH_CLEARED; none pending | Earnings, Tax open |
| S4 | none open | none pending | Earnings, Tax open |
| S5 | Growth open | Growth WATCH | Earnings, Tax, Growth open |
| S6 | Growth continues | Growth PERSISTENT | Earnings, Tax, Growth open |
| S7 | Growth recovered; none open | Growth RECOVERY_PENDING (1 clean quarter) | Earnings, Tax, Growth open |
| S8 | none open | Growth RECOVERED (2 clean quarters) | Earnings, Tax, Growth open |

An analyst closing Earnings under C at S4 would leave Tax open; it would not close all groups. This is a conditional example, not a supplied approval.

## Edge cases and decision record

All rules, states and examples in this section are **PROPOSED monitoring policy**, not accepted owner policy or issuer facts. Apply the group classification above before updating any episode. Return a per-group classification, member outcomes, episode state and (for B) counters; never replace the approved raw predicate outcomes with these labels.

**A actual return states:** `BREACH` returns `OPEN`, continuing an existing episode if present. `CLEAN` returns `CLOSED` when closing an open episode, otherwise `NEUTRAL`. `UNKNOWN` returns `UNKNOWN_OPEN` when an episode remains open, otherwise `UNEVALUABLE`; it never closes an episode. The example table's “recovered” means this proposed `CLOSED` state only.

**B counters and actual return states:** keep separate consecutive breach (`b`) and clean (`c`) counters, initially `(0,0)`, and watch/persistent episode flags for each group. Counters saturate at 2. `BREACH` increments that group's `b` and sets `c=0`; `CLEAN` sets `b=0` and increments `c`; `UNKNOWN` sets both to zero for that group only. Persistence latches when `b=2` and is cleared only by two consecutive `CLEAN` quarters. Unknown never closes a watch or persistent episode.

| Group input | Existing episode | B return state and episode effect |
|---|---|---|
| BREACH | No persistent episode | `WATCH` at b=1; `PERSISTENT` at b=2, latching persistence. |
| BREACH | Persistent, including recovery pending or unknown | `PERSISTENT`, even if b=1 after interruption; c=0 cancels recovery progress. |
| CLEAN | Persistent | `RECOVERY_PENDING` at c=1; `RECOVERED` at c=2, closing the episode. |
| CLEAN | Unresolved watch, including after unknown | `WATCH_CLEARED`, closing the watch. |
| CLEAN | No unresolved episode | `NEUTRAL`. |
| UNKNOWN | Persistent | `PERSISTENT_UNEVALUABLE`, retaining the persistent episode with (b,c)=(0,0). |
| UNKNOWN | Watch or no unresolved episode | `UNEVALUABLE`, retaining any unresolved watch with (b,c)=(0,0). |

`WATCH_CLEARED` and `RECOVERED` are closure-event return states, not permanent latches. A subsequent breach starts a new `WATCH` at (1,0); a subsequent clean returns `NEUTRAL`; a subsequent unknown returns `UNEVALUABLE`. After `WATCH → UNEVALUABLE`, another breach returns `WATCH`, not `PERSISTENT`, because consecutiveness was interrupted. After `PERSISTENT → RECOVERY_PENDING`, another breach returns `PERSISTENT`, not `WATCH`, because persistence remains latched. After `PERSISTENT_UNEVALUABLE`, a clean returns `RECOVERY_PENDING` at (0,1).

**C actual return states:** `BREACH` opens or continues `OPEN_FOR_REVIEW`. `CLEAN` keeps an existing episode `OPEN_FOR_REVIEW`, otherwise returns `NEUTRAL`. `UNKNOWN` keeps an existing episode `OPEN_FOR_REVIEW_UNKNOWN`, otherwise returns `UNEVALUABLE`. Only an explicit analyst closure returns `CLOSED` and clears that group's episode; another breach opens a new one. No analyst closure is supplied in these examples.

### Exact small PROPOSED sequences

Each numbered sequence starts independently with no episode and B counters (0,0). All percentages are synthetic; `—` means an unavailable member, never zero. Fully observed passing Earnings is (F2,F3,F4)=(6%,20%,5%); fully observed breaching Earnings is (5%,20%,5%). Tax is 25% throughout; Growth is 20% except where specified. State/counter pairs below are actual proposed B returns.

| Sequence | Consecutive group inputs | Exact proposed returns |
|---|---|---|
| 1 — partial missingness | Earnings (5%,—,5%) → (6%,—,5%) → (6%,20%,5%): BREACH → UNKNOWN → CLEAN | B: `WATCH` (1,0) → `UNEVALUABLE` (0,0), watch retained → `WATCH_CLEARED` (0,1). A: `OPEN` → `UNKNOWN_OPEN` → `CLOSED`. C: `OPEN_FOR_REVIEW` → `OPEN_FOR_REVIEW_UNKNOWN` → `OPEN_FOR_REVIEW`. |
| 2 — WATCH, unknown, breach | Earnings (5%,20%,5%) → (6%,—,5%) → (5%,20%,5%): BREACH → UNKNOWN → BREACH | B: `WATCH` (1,0) → `UNEVALUABLE` (0,0) → `WATCH` (1,0). A: `OPEN` → `UNKNOWN_OPEN` → `OPEN`. C: `OPEN_FOR_REVIEW` → `OPEN_FOR_REVIEW_UNKNOWN` → `OPEN_FOR_REVIEW`. |
| 3 — interrupted persistent recovery | Earnings (5%,20%,5%) → (5%,20%,5%) → (6%,20%,5%) → (5%,20%,5%): BREACH → BREACH → CLEAN → BREACH | B: `WATCH` (1,0) → `PERSISTENT` (2,0) → `RECOVERY_PENDING` (0,1) → `PERSISTENT` (1,0). A: `OPEN` → `OPEN` → `CLOSED` → `OPEN`. C: `OPEN_FOR_REVIEW` at all four steps. |
| 4 — independent Growth | Two quarters both have Earnings (6%,—,5%) and revenue YoY=10%: Earnings UNKNOWN → UNKNOWN; Growth BREACH → BREACH | B Earnings: `UNEVALUABLE` (0,0) twice; B Growth: `WATCH` (1,0) → `PERSISTENT` (2,0). A Earnings: `UNEVALUABLE` twice; A Growth: `OPEN` twice. C Earnings: `UNEVALUABLE` twice; C Growth: `OPEN_FOR_REVIEW` twice. |

Historical corrections produce a versioned replay referencing superseded evaluations; history and approvals remain inspectable. Replay never creates an analyst closure under C.

Alternating F2-only then F4-only breaches are one group at each quarter: A continues its episode, B becomes persistent on the second quarter, C remains latched. This precise consequence is part of the B decision, rather than evidence of one shared cause.

Record the chosen option, acceptance or amendments to grouping/unknown handling, policy version and document hash, analyst identity, actual decision time, verbatim ruling and intended prospective/replay scope. Preserve the approved falsifier file unchanged. A modified option needs a successor proposal before implementation. The [decision packet](analyst-review-decision-packet.md#review-order-and-time-records) locates this decision in the human review sequence.
