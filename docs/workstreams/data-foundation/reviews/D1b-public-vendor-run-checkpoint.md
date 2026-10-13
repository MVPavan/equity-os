# D1b public vendor run checkpoint — 2026-10-13

Reviewer: Codex session (handoff run), independent public preflight reviewer, R2.
Scope: frozen public execution, exact generation preparation, corroboration rows,
transactional queue publication and by-ID replay. Actual SONACOMS acceptance is separate.

All original review findings:

| Finding | Verdict | Verified behavior |
|---|---|---|
| R1.1 currency proof occurred after writes | ADDRESSED | Exactly one eligible source-backed currency is required from the handoff before configuration pins or vendor append. Negative asserts unchanged counts. |
| R1.2 segment metadata lacked native proof | ADDRESSED within checkpoint | Namespace, qualified dimensions, entity, basis, period, description, original clocks and source-derived validity are checked. Four negatives and independent native positive pass. |
| R1.3 later basis record changed historical preflight | ADDRESSED | Recorded-at cutoff is applied before ambiguity discovery. Historical preparation is unchanged. |
| Empty-source NOT_APPLICABLE representative failure | ADDRESSED | Applicability returns before representative selection and produces no drafts. |
| Replay segment association escaped occurrence manifest | ADDRESSED | Loading refuses linked occurrence IDs outside the frozen set; independent closed positive and exact reader arguments pass. |

Root's frozen PostgreSQL packet: **31 passed in 81.30s**. Mechanical helper split:
**100 pure tests passed in 11.37s**; scoped Ruff and strict mypy passed. Reviewer
found no remaining Critical or Important defect in the bounded fix surface.

Permanent original six public refusal RED outcomes remain historical evidence;
eighteen later public cases are characterization, not newly claimed REDs. The original
41-line v1 test prefix is preserved. The R1 regression packet has six genuine REDs;
an invalid initial valid_to setup and an overlapping contaminated GREEN probe are
excluded. Root froze the original producer SHA before and after the corrected
valid_to probe, which failed with DID NOT RAISE ValueError before authorized repair.

Test split moves only Case, case, assembled, vendor_value and later into
vendor_rows_support.py. All 24 function/class ASTs, 64 assertions, numerical literals
and 100 node IDs are unchanged. Test/helper lengths are 712/267; production is unchanged
by the split. Original bytes and detailed logs remain in the ignored execution worktree.

Acceptance limits remain explicit:

- Existing segment association rows have no link-creation knowledge clock. Closing
  occurrence IDs cannot prove when a late link to an already-listed occurrence appeared.
- Actual retained multi-period segment acceptance is unverified: original production
  aggregates descriptions across periods; this guard requires the requested period.
- Actual SONACOMS positives, missing vendor captures, authenticated queue CLI,
  the independently approved frozen manifest and full D1b exit remain open.
- Full gate for the final combined witness/public checkpoint is reported separately.

VERDICT: APPROVE
