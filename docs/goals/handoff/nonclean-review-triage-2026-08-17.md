# Non-clean inventory review triage (read-only agent, 2026-08-17)

Correction to earlier count: 20 non-clean artifacts over 15 components (DISP-G-3/4/5, DISP-M-1..7, REG-A-09, SEQ-02/03/04/08). DEF-01..13 are CLEAN (earlier grep hit the string ISSUES_FOUND in prose).

Root causes:
- RC-1 (10 EVIDENCE artifacts, DISP-G-3/4/5, DISP-M-1..7): row omits REQ-<CID>-SPEC-REVIEW required_evidence obligation. Reviewers say ALL 32 disposition_item rows share it (generate_initial_ledger.py:398-402,590 already emits it; ancestor = evidence-inventory-r0 Important-1, never remediated). Fix = ledger JSONL edit on 32 rows. No human decision needed.
  ** CONSISTENCY FLAG: 22 other disposition rows were reviewed CLEAN despite (per these reviewers) sharing the same defect. Either those CLEAN verdicts are wrong or RC-1 reviewers over-generalise. Must be resolved before recording ANY disposition_item review.
- RC-2 (8 artifacts, SEQ-02/03/04/08 APPROVAL+EVIDENCE): multi-spec rows carry approval/evidence obligations only for the first-listed spec. Reviewers say all 20 multi-spec rows (4 seq + 16 disp). Fix = ledger edit on 20 rows OR codify one-approval-covers-all rule. USER DECISION (policy). Partial REVIEWER_MISREAD risk: no text found stating per-spec obligations are required.
- RC-3 (DISP-M-3 APPROVAL + EVIDENCE F2): clause's human approval rule for vocabulary additions has no required_approvals entry (+ mirroring TYPED_APPROVAL evidence). Ledger edit 1 row; soft user decision on exact type/authority.
- RC-4 (REG-A-09 APPROVAL): missing PRODUCT_OWNER_DECISION approval per S01 §4/§5.2/§7. Ledger edit 1 row.

Mechanics: all affected fields are inside review_input_projection -> ledger edits must land BEFORE any review on those rows is digested (design r2 §3.4); all reviews on a row record all-at-once. So RC-1/RC-2 block whole review sets for 13-15 components (and possibly all 32 disposition rows + 20 multi-spec rows).
Not touched: goal doc, CONTEXT.md, preimpl validator, extractor. Ledger edits will require transitions/HR? -> check whether required_evidence/required_approvals edits need a journaled transaction (they are canonical ledger bytes).
Full per-artifact table: see agent transcript / summary in session; regenerate with grep if needed.
