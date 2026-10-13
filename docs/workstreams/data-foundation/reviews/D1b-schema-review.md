# D1b Task 2 schema, serialization and approval boundary review

VERDICT: APPROVE — all five first-pass findings addressed in the frozen fix surface.

Reviewer: Codex session (handoff run), `/root/review_verifier_and_amendment`.
Review date: 2026-10-13.
Scope: Task 2 source-qualified contracts, migration 0006, run-model/store/config extensions, common retained-vendor admission and protected receipt producer/consumer; tracked diff against `22a3c78` and the assigned new files. Task 3/4/5 adapter/corroboration findings are outside this review.

## Final re-review: every finding

The coordinator confirmed the source freeze. The independent reviewer inspected every fix and its regression assertions; no database or redundant test execution was performed by this reviewer.

| Finding | Verdict | Frozen-source evidence and covering regression |
|---|---|---|
| S1: computed vendor result accepts first-party child trace | ADDRESSED | `migrations/0006_review_queue.sql:40–50,127–134` recursively collects actual leaf representations and requires exactly one matching HTML/JSON representation as well as the single matching capture/source/surface. `tests/fundamentals/test_vendor_sql_boundaries.py:18–37` supplies a real seeded first-party child with its correct source/surface and requires SQL rejection. |
| S2: existing 0005 result provenance changes on upgrade/replay | ADDRESSED | `src/fundamentals/compare/run_store.py:397–407,618–638` applies the old source-ref view only when the stored manifest has no vendor requests, vendor extractors or authority pin. Actual source identities remain backfilled in SQL. `tests/fundamentals/test_vendor_upgrade.py:31–49,90–136` publishes real retained Apar evidence under byte-identical 0001–0005, applies only 0006, verifies actual source backfill, unchanged persisted manifest/identity hashes and equal stored/replayed results. The tracked test has no scratch snapshot dependency. |
| S3: final SQL disposition omits sealed amount/trace binding | ADDRESSED | `migrations/0006_review_queue.sql:306–313` requires both amount fields to be `IS NOT DISTINCT FROM` the reviewed proposal before proving code-trace or owner amount origin. `tests/fundamentals/test_vendor_sql_boundaries.py:40–105` requires rejection of a genuine code amount attached to an accepted amount-free proposal. Constructed privileged SQL evidence is explicitly labeled binding proof, not actual independent approval. |
| S4: blanket grant restores protected-clock sequence access | ADDRESSED | `migrations/0006_review_queue.sql:348–353` lists only the new identity sequences and explicitly preserves the runtime clock-sequence revoke. `tests/fundamentals/test_vendor_sql_boundaries.py:108–112` requires runtime direct `nextval` to raise insufficient privilege. |
| S5: SQL permits first-party roles with vendor representations | ADDRESSED | `migrations/0006_review_queue.sql:114–115` restricts FIRST_PARTY/REPORTED_COUNTERPART to XBRL/PDF. `tests/fundamentals/test_vendor_sql_boundaries.py:115–131` independently checks SQL rejection for both first-party roles; source-qualified vendor representation round-trip tests remain intact. |

New breakage in the fix surface: none identified. Current Critical/Important/Minor issues: none. The historical first-pass findings below are preserved for traceability; all are now addressed.

## Fresh verification evidence

The implementer supplied these exact final frozen-state results:

```sh
uv run --no-sync pytest -q \
  tests/fundamentals/test_vendor_schema.py \
  tests/fundamentals/test_vendor_sql_boundaries.py \
  tests/fundamentals/test_vendor_generation_scope.py \
  tests/fundamentals/test_vendor_upgrade.py \
  tests/fundamentals/test_pg_evidence_schema.py \
  tests/fundamentals/test_compare_config_pins.py \
  tests/fundamentals/test_compare_runs.py::test_every_enum_value_round_trips_through_its_check \
  tests/fundamentals/test_compare_runs.py::test_replay_reads_by_id_only_and_equals_stored \
  --tb=short
```

Result: **32 passed in 14.27s, exit 0**. The command used a local writable UV-cache override, omitted above for portability.

- `test_pg_migrations.py` plus `test_evidence_contract_boundaries.py`: **15 passed, exit 0**.
- Full Ruff/format and strict mypy: GREEN; **431 files formatted, 256 source files checked**.
- `scratchpad/execution/data-foundation-autonomous-2026-10-13/old-run-witness.log`: actual hash-verified `22a3c78` producer upgrades/replays successfully; the separate deliberately restored pre-fix reader reproduces the real stored-result equality failure. The witness's sole modern-model adapter restores the old producer's original ten SQL pins; no financial row or digest is rewritten.
- Initial RED artifacts and authorized fixture-reopening notes remain intact in `scratchpad/gate/`. Reopened fixture digests now name actual stored capture/occurrence ids, and the computed vendor child has actual stored vendor interpretation provenance. No financial value or required round-trip assertion was weakened.
- The coordinator's final stable full-project verifier remains a separate integration gate. This checkpoint approval does not claim that command has completed or that the final project is accepted.

## Historical first-pass severity-ranked findings

### Critical

None.

### Important

1. **S1 — Computed vendor result accepts a first-party child trace.** `migrations/0006_review_queue.sql:112–116` validates a computed vendor side by a single leaf capture's source/surface only. It does not require those leaf interpretations to use HTML/JSON or the declared result representation. A first-party XBRL/PDF child trace can be labeled an INDEPENDENT_VENDOR/DIAGNOSTIC HTML/JSON result when its actual first-party source/surface is included in the vendor request. The `VENDOR_CAPTURE` operand trigger is on a different table and does not protect this result-source-value branch. Require genuine vendor leaf representations and matching result representation; add a negative first-party-child regression.

2. **S2 — Existing 0005 result provenance changes across migration and replay.** Migration 0006 backfills existing first-party source/surface identities from real capture/attempt/trace provenance at lines 72–86. `src/fundamentals/compare/run_store.py:612–628` reconstructs those identities, and pair refs inherit them at lines 417–425. However replay's unchanged first-party producer constructs default-None identities in `src/fundamentals/compare/engine_rows.py:104–116,142–154,196–198`. Thus a pre-0006 stored run loads upgraded source refs while recomputation still produces old None refs. Empty-default manifest serializers preserve manifest hashes but do not fix result/pair-ref replay equality. Add a genuinely seeded 0005→0006 legacy-run upgrade/replay regression and an explicit compatible read/recompute strategy.

3. **S3 — SQL final-disposition binding omits reviewed amount fields.** `migrations/0006_review_queue.sql:259–269` matches kind/reason/proposer/evidence reference against the sealed proposal, but does not match `explained_amount` and `amount_trace_id`. An authenticated privileged direct insert may consume an ACCEPT receipt for an amount-free proposal and attach an unrelated genuine code-trace amount; the trace-value check passes although that amount was absent from the reviewed proposal digest. The ordinary Python finalizer copies proposal fields correctly, so this is a protected SQL binding gap within the actual migrator boundary, not a runtime authorization bypass. Bind both fields using `IS NOT DISTINCT FROM` before checking their trace/owner origin, and test a receipt paired with a different amount/trace.

4. **S4 — Broad sequence grant restores runtime access to the protected clock sequence.** `migrations/0006_review_queue.sql:304` grants runtime USAGE on every sequence in `eqos`, including `eqos.store_clock_us`. Applied migration 0004 lines 16–18 explicitly revoked direct runtime access to that server-owned clock sequence. This new blanket grant broadens runtime privileges and permits direct `nextval` calls against the protected clock. Grant only the new identity sequences or explicitly preserve the clock-sequence revoke, and verify the privilege remains absent after upgrading.

5. **S5 — SQL permits first-party result roles with vendor-only representations.** Migration 0006 expands result representations to HTML/JSON but its source-role CHECK only restricts vendor roles. FIRST_PARTY/REPORTED_COUNTERPART HTML/JSON rows remain permitted by SQL, while `SourceRef` explicitly rejects that combination in `src/fundamentals/contracts/comparison.py`'s representation validator. Runtime SQL can therefore create a row that `RunStore.read_results` cannot reconstruct. Require XBRL/PDF for first-party result roles as well as HTML/JSON for vendor roles, and add a negative insert regression.

### Minor

None identified in the assigned surface.

## Checks and preserved boundaries

- Source/surface dimensions extend source-value uniqueness and pair reconstruction; typed CORROBORATION/DIAGNOSTIC pair kinds and VENDOR_CAPTURE selection source are present in Python and SQL.
- Package members remain explicitly first-party XBRL/PDF in the Python contract; SQL membership/alignment checks remain unchanged. First-party extractor iteration is explicitly restricted to `FIRST_PARTY_REPRESENTATIONS` in run configuration.
- Pinned vendor extractors are source/surface qualified and sorted, and requested vendor sides require corresponding extractor/source-authority pins at RunStore publication. Empty optional vendor manifest/pin fields are omitted for old manifest digest compatibility.
- Queue and governance tables have UPDATE/DELETE/TRUNCATE rejection triggers. Runtime has item/proposal writes and read access to finals; receipt/final insert privileges remain withheld. Runtime amount-bearing proposals are refused by an INSERT trigger.
- Protected producer identity and recording time are overwritten from actual `session_user` and `eqos.store_now()`. SET ROLE or caller labels are not treated as authenticated producer identity.
- Python producer requires a privileged connection, verified decision evidence and actual stored subject/proposal digests. Reload verifies protected receipt/evidence linkage, raw-evidence hash, typed decision document and sealed proposal. Finalize reloads rather than trusting the supplied receipt wrapper alone.
- The Python verified wrappers are nominal capabilities, not protection against code with an existing migrator connection constructing arbitrary Python objects or bypassing the trusted authenticator. Security approval must remain bounded to actual SQL role protection and the approved trusted composition boundary.
- There is deliberately no default external decision authenticator or actor/path/hash/owner-flag shortcut. A production positive Task 7 trusted-composition approval path is still required before accepting that later task; a constructed test authenticator cannot establish actual reviewer/owner authority.

## Review boundaries

- Read-only source/diff review performed. No database operations, broad tests, implementation, Git/Beads/network/raw mutations or child agents.
- Entire assigned first pass is complete. S1–S5 are exhaustive for the inspected surface; no other first-pass findings remain pending. Line references describe the pre-fix source read and may move as the implementation fixes land.
- The implementer was still finalizing focused tests at the initial dispatch. Final approval followed the coordinator's freeze and the fresh verification results above.
- All five findings were sent promptly to the coordinator with file/line evidence and concrete regression requirements.

VERDICT: APPROVE — S1–S5 addressed; no new Critical or Important findings. Approval is limited to this shared Task 2 checkpoint. Actual Task 7 trusted-authenticator composition remains parked, and no vendor mapping, frozen manifest, phase or financial-production acceptance is claimed.
