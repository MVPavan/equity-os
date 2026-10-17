---
status: approved
scope: retention-replay
spec: docs/specs/2026-10-12-report-ledger-memory-and-data-lifecycle.md
register: docs/blueprint/funda-blueprint-implementation-decision-register-v2.md
subject_sha256: e7028b7f60e24f5c47fdc29b5f7fa002defc98188ef190d75ecae8d62bca12d8
amendments:
- id: c16-qualified
  scope: retention-replay
  register_clause: C-16:evidence-package-reconstructs-exactly
  change: 'Qualify "evidence package reconstructs exactly": a package whose exchange originals
    expired reconstructs by re-fetch with hash match; one whose vendor material expired keeps only
    outcomes and tombstones.'
- id: c02-qualified
  scope: retention-replay
  register_clause: C-02:original-files-preserved
  change: 'Qualify "original files … preserved": originals of non-covered stocks and all vendor
    material expire under ledger §5; capture records, addresses, hashes and first-seen times are
    preserved forever.'
- id: data-spec-us12
  scope: retention-replay
  data_spec_clause: user-story-12
  change: A past comparison is exactly reproducible from its recorded inputs while its vendor
    readings are retained; otherwise only outcomes remain.
- id: data-spec-4-capture-store
  scope: retention-replay
  data_spec_clause: §4:capture-records-and-blobs
  change: Capture records stay in the snapshot store forever; blobs follow the ledger §5 classes.
- id: data-spec-5-replay
  scope: retention-replay
  data_spec_clause: §5:runs-and-reproducibility
  change: Replay uses only the manifest while the run's vendor readings are retained; otherwise
    it reports ORIGINAL_EXPIRED.
- id: data-spec-6-integrity
  scope: retention-replay
  data_spec_clause: §6:schema-and-integrity
  change: Unchanged for the runtime role; a purge role may delete only vendor payload (leaving
    tombstones), vendor values in result rows (never outcomes), and blobs and links, always with a
    purge record; §4 "immutable" occurrences exclude vendor readings.
- id: data-spec-6-backup
  scope: retention-replay
  data_spec_clause: §6:backup-and-restore
  change: A backup archives every retained blob and lists expired captures with address and
    hash; purge step 5 and restore follow ledger §5.
- id: data-spec-6-restore-test
  scope: retention-replay
  data_spec_clause: §6:restore-test
  change: The restore test resolves every retained capture with a matching hash; every expired
    capture has a purge record.
- id: data-spec-7-shareholding
  scope: retention-replay
  data_spec_clause: §7:prerequisite
  change: The exchange shareholding filing is retained under the ledger §5 classes.
- id: data-spec-8-discovery
  scope: retention-replay
  data_spec_clause: §8:discovery-captures
  change: Discovery captures are retained under the IDENTITY class and holds.
- id: data-spec-stage2-restore
  scope: retention-replay
  data_spec_clause: stage-2:matched-backup-restore
  change: The Stage 2 restore criterion reads as data-spec-6-restore-test, and the replayed run's
    vendor readings must be retained.
- id: data-spec-0-cross-spec
  scope: retention-replay
  data_spec_clause: §0:staged-delivery
  change: data-spec-stage2-restore and data-spec-2-qualification are approved cross-spec
    amendments, not a later stage relaxing an earlier stage's acceptance.
- id: data-spec-5-queue-panel
  scope: retention-replay
  data_spec_clause: §5:analyst-interface-queue
  change: Queue items routed to a human are dispositioned by the approval panel (ACCEPT or REJECT
    of a proposed disposition, amounts from code or the owner); owner dispositions remain and
    outrank; interpretations needing approval are owner-decided until F2 (as amended 2026-10-15).
- id: data-spec-2-qualification
  scope: retention-replay
  data_spec_clause: §2:qualification-scope+stage-1
  change: A demonstrated mapping keeps its recorded measurement after its vendor fixtures expire
    but cannot be re-measured; a rerun over expired vendor fixtures reports ORIGINAL_EXPIRED for
    those rows.
- id: ledger-5-high-incident
  scope: retention-replay
  ledger_clause: §5:purge-step-1+capture-record-states
  change: A failed re-fetch probe or a REFETCH_MISMATCH has no run, key or pair, so instead of a
    queue item it is a severity HIGH row in retention_probes or refetch_attempts, surfaced by the
    view eqos.retention_incidents; a probe incident closes on a later matching probe for that
    source, a mismatch incident when that capture is RESTORED; a command creating one exits 3
    (SUCCESS_WITH_OPEN_HIGH).
approvals:
  c16-qualified:
    reviewer: gpt-6.1-sol
    date: '2026-10-17'
    verdict: APPROVE
    subject_sha256: e7028b7f60e24f5c47fdc29b5f7fa002defc98188ef190d75ecae8d62bca12d8
    report: docs/workstreams/data-foundation/reviews/D9-amendments-review.md
  c02-qualified:
    reviewer: gpt-6.1-sol
    date: '2026-10-17'
    verdict: APPROVE
    subject_sha256: e7028b7f60e24f5c47fdc29b5f7fa002defc98188ef190d75ecae8d62bca12d8
    report: docs/workstreams/data-foundation/reviews/D9-amendments-review.md
  data-spec-us12:
    reviewer: gpt-6.1-sol
    date: '2026-10-17'
    verdict: APPROVE
    subject_sha256: e7028b7f60e24f5c47fdc29b5f7fa002defc98188ef190d75ecae8d62bca12d8
    report: docs/workstreams/data-foundation/reviews/D9-amendments-review.md
  data-spec-4-capture-store:
    reviewer: gpt-6.1-sol
    date: '2026-10-17'
    verdict: APPROVE
    subject_sha256: e7028b7f60e24f5c47fdc29b5f7fa002defc98188ef190d75ecae8d62bca12d8
    report: docs/workstreams/data-foundation/reviews/D9-amendments-review.md
  data-spec-5-replay:
    reviewer: gpt-6.1-sol
    date: '2026-10-17'
    verdict: APPROVE
    subject_sha256: e7028b7f60e24f5c47fdc29b5f7fa002defc98188ef190d75ecae8d62bca12d8
    report: docs/workstreams/data-foundation/reviews/D9-amendments-review.md
  data-spec-6-integrity:
    reviewer: gpt-6.1-sol
    date: '2026-10-17'
    verdict: APPROVE
    subject_sha256: e7028b7f60e24f5c47fdc29b5f7fa002defc98188ef190d75ecae8d62bca12d8
    report: docs/workstreams/data-foundation/reviews/D9-amendments-review.md
  data-spec-6-backup:
    reviewer: gpt-6.1-sol
    date: '2026-10-17'
    verdict: APPROVE
    subject_sha256: e7028b7f60e24f5c47fdc29b5f7fa002defc98188ef190d75ecae8d62bca12d8
    report: docs/workstreams/data-foundation/reviews/D9-amendments-review.md
  data-spec-6-restore-test:
    reviewer: gpt-6.1-sol
    date: '2026-10-17'
    verdict: APPROVE
    subject_sha256: e7028b7f60e24f5c47fdc29b5f7fa002defc98188ef190d75ecae8d62bca12d8
    report: docs/workstreams/data-foundation/reviews/D9-amendments-review.md
  data-spec-7-shareholding:
    reviewer: gpt-6.1-sol
    date: '2026-10-17'
    verdict: APPROVE
    subject_sha256: e7028b7f60e24f5c47fdc29b5f7fa002defc98188ef190d75ecae8d62bca12d8
    report: docs/workstreams/data-foundation/reviews/D9-amendments-review.md
  data-spec-8-discovery:
    reviewer: gpt-6.1-sol
    date: '2026-10-17'
    verdict: APPROVE
    subject_sha256: e7028b7f60e24f5c47fdc29b5f7fa002defc98188ef190d75ecae8d62bca12d8
    report: docs/workstreams/data-foundation/reviews/D9-amendments-review.md
  data-spec-stage2-restore:
    reviewer: gpt-6.1-sol
    date: '2026-10-17'
    verdict: APPROVE
    subject_sha256: e7028b7f60e24f5c47fdc29b5f7fa002defc98188ef190d75ecae8d62bca12d8
    report: docs/workstreams/data-foundation/reviews/D9-amendments-review.md
  data-spec-0-cross-spec:
    reviewer: gpt-6.1-sol
    date: '2026-10-17'
    verdict: APPROVE
    subject_sha256: e7028b7f60e24f5c47fdc29b5f7fa002defc98188ef190d75ecae8d62bca12d8
    report: docs/workstreams/data-foundation/reviews/D9-amendments-review.md
  data-spec-5-queue-panel:
    reviewer: gpt-6.1-sol
    date: '2026-10-17'
    verdict: APPROVE
    subject_sha256: e7028b7f60e24f5c47fdc29b5f7fa002defc98188ef190d75ecae8d62bca12d8
    report: docs/workstreams/data-foundation/reviews/D9-amendments-review.md
  data-spec-2-qualification:
    reviewer: gpt-6.1-sol
    date: '2026-10-17'
    verdict: APPROVE
    subject_sha256: e7028b7f60e24f5c47fdc29b5f7fa002defc98188ef190d75ecae8d62bca12d8
    report: docs/workstreams/data-foundation/reviews/D9-amendments-review.md
  ledger-5-high-incident:
    reviewer: gpt-6.1-sol
    date: '2026-10-17'
    verdict: APPROVE
    subject_sha256: e7028b7f60e24f5c47fdc29b5f7fa002defc98188ef190d75ecae8d62bca12d8
    report: docs/workstreams/data-foundation/reviews/D9-amendments-review.md
---

# Retention and replay: C-16, C-02, the data-spec clauses and HIGH incidents

Recorded 2026-10-17 for the approved 2026-10-12 report-ledger spec, Stage 5 (D9 Task 1). Approved by the
independent reviewer on 2026-10-17; see the [approval report](../../workstreams/data-foundation/reviews/D9-amendments-review.md).

This record changes exactly items 2 and 6 of the [report-ledger spec's decision-register amendments](../../specs/2026-10-12-report-ledger-memory-and-data-lifecycle.md#decision-register-amendments-scope-stated-exactly),
the twelve [data spec](../../specs/2026-10-11-canonical-financial-data-and-cross-source-comparison.md)
clauses the ledger spec's §6 lists, and one ledger §5 wording (HIGH items) fixed by the
[D9 plan](../../workstreams/data-foundation/plans/D9.md) ruling R9. The original
[decision register](../funda-blueprint-implementation-decision-register-v2.md) remains the baseline.
The A-05 derived-amounts decision and the tombstone redaction inventory are a separate record,
[A-05 derived amounts](2026-10-12-a05-derived-amounts.md).

## Register C-16 and C-02, verbatim

> | C-02 | Critical | Build immutable document registry and object store | Original files, URLs, timestamps, hashes, parser versions, extraction warnings, and first-seen times are preserved | A-05 | Open |

> | C-16 | Critical | Implement layered reproducibility and artifact approval | Exact-class operators replay exactly; floating-point/optimization outputs meet declared tolerances; stochastic operators store seeds and test distributions; evidence package reconstructs exactly; approved narrative bytes are immutable and bound to content hash | B-03, B-07, C-08 | Open |

## Ledger spec amendments 2 and 6, verbatim (`c16-qualified`, `c02-qualified`)

> 2. **C-16** ("evidence package reconstructs exactly") — qualified: an evidence package whose
>    exchange originals expired reconstructs by re-fetch with hash match; one whose vendor material
>    expired keeps only outcomes and tombstones (§6).

> 6. **C-02** ("original files … preserved"): qualified — originals of non-covered stocks and all
>    vendor material expire under §5; capture records, addresses, hashes and first-seen times are preserved forever.

## Data-spec clauses (ledger §6 items 1–12), verbatim

Each item quotes the ledger spec's amendment, then the data-spec text it amends.

### 1. `data-spec-us12`

> 1. User story 12, "any past comparison exactly reproducible from its recorded inputs": while its
>    vendor readings are retained; otherwise only outcomes remain.

Data spec, user stories:

> 12. any past comparison exactly reproducible from its recorded inputs.

### 2. `data-spec-4-capture-store`

> 2. §4 "Capture records and blobs stay in the existing snapshot store, referenced by the
>    database": capture records stay forever; blobs follow §5 classes.

Data spec §4:

> Capture records and blobs stay in the existing snapshot store, referenced by the database. Only
> complete, **comparison-eligible** (§8) captures are interpreted.

### 3. `data-spec-5-replay`

> 3. §5 "Runs and reproducibility", "Replay uses only the manifest…": while vendor readings are
>    retained; otherwise `ORIGINAL_EXPIRED`.

Data spec §5, **Runs and reproducibility**:

> timestamp, so concurrent default-cutoff reruns over unchanged evidence return one run. Replay
> uses only the manifest, reproducing source states (incl. negative ones) without consulting current
> observations, identity, settings, definitions or queue state.

### 4. `data-spec-6-integrity`

> 4. §6 "Schema and integrity" (immutable evidence, runtime role without DELETE): unchanged for
>    the runtime role; a purge role may delete only vendor payload (leaving tombstones), vendor
>    values in result rows (never outcomes), and blobs and links, always with a purge record. All
>    else is never deleted; §4 "immutable" occurrences exclude vendor readings.

Data spec §6:

> - Evidence tables (occurrences, interpretations, definition sets, run manifests, results, queue
>   records, dispositions, imported legacy facts and selections) are immutable: update and delete are
>   rejected by triggers, and the **runtime role** lacks UPDATE and DELETE on them. A separate
>   **migration role** owns the schema.

### 5. `data-spec-6-backup`

> 5. §6 "Backup and restore (D2)", "an archive of every capture record and blob the database
>    references": every **retained** blob; expired captures listed with address and hash; purge
>    step 5 and restore as §5.

Data spec §6, **Backup and restore (D2)**:

> - A backup is a **matched set** under one backup id: a `pg_dump` custom-format dump; an archive of
>   every capture record and blob the database references, directly or through the legacy evidence
>   binding (§6 import); and a manifest of those capture hashes.

### 6. `data-spec-6-restore-test`

> 6. §6 restore test, "every referenced capture … resolves with a matching hash": every retained
>    capture; every expired one has a purge record.

Data spec §6:

> - A restore test restores the set into a fresh instance, a fresh test database and an empty
>   snapshot-store directory, then checks row counts, referential integrity, that every referenced
>   capture (incl. every bound imported-fact original) resolves with a matching hash, and that
>   replaying one stored run reproduces its results.

### 7. `data-spec-7-shareholding`

> 7. §7 shareholding filing "retained like other filings": under the §5 classes.

Data spec §7:

> **Prerequisite.** Before any capture, the filing is registered in the source catalog with role and
> retention authority, then retained like other filings as the first-party shareholding source.

### 8. `data-spec-8-discovery`

> 8. §8 discovery captures "retained as identity evidence": under the `IDENTITY` class and holds.

Data spec §8:

> **Discovery captures** (instrument master, vendor lookups, filings fetched for identity checks) are
> retained as identity evidence, never interpreted for comparison. A namespace's captures become
> **comparison-eligible** only once it is verified.

### 9. `data-spec-stage2-restore`

> 9. Stage 2 criterion "every referenced capture resolves … one stored run replays identically":
>    as in 6; the replayed run's vendor readings must be retained.

Data spec, Stage 2:

> - A matched backup restores into a fresh instance and empty snapshot-store directory; every
>   referenced capture resolves with a matching hash, and one stored run replays identically.

### 10. `data-spec-0-cross-spec`

> 10. §0 "a later stage never relaxes an earlier stage's acceptance": items 9 and 12 are
>     panel-approved cross-spec amendments, not a later stage relaxing it.

Data spec §0:

> One spec, four stages. Each stage is independently verifiable; a later stage never relaxes an
> earlier stage's acceptance.

### 11. `data-spec-5-queue-panel` (as amended 2026-10-15, F2)

> 11. §5 review queue and analyst interface ("record dispositions"): items routed to a human are
>     dispositioned by the approval panel (§1: `ACCEPT`/`REJECT` of a proposed disposition,
>     amounts from code or the owner); owner dispositions remain and outrank. Interpretations
>     needing approval are owner-decided until F2 adds panel acceptance with deterministic-provenance
>     replay (amended 2026-10-15).

Data spec §5, **Analyst interface**:

> - **Queue:** list by severity and status; record dispositions. **Run:** start with a cutoff.

### 12. `data-spec-2-qualification`

> 12. §2 qualification and Stage 1 acceptance: a demonstrated mapping keeps its recorded
>     measurement after its vendor fixtures expire but cannot be re-measured; a rerun over expired
>     vendor fixtures reports `ORIGINAL_EXPIRED` for those rows.

Data spec §2 and Stage 1:

> **Qualification scope.** A demonstrated mapping records schema versions, surfaces, basis, period
> kinds, any further conditions (e.g. discontinued operations zero), the fixture set (capture ids and
> hashes), exclusions and the sample rule it satisfied (D3; a discriminating case is one where competing
> definitions such as associates, NCI, discontinued operations or exceptional items differ).

> ### Stage 1: dictionary, mappings, comparison (retained captures)

## Ledger §5 HIGH items, verbatim (`ledger-5-high-incident`)

> 1. Before an `EXCHANGE_REFETCHABLE` deletion, a re-fetch probe on a sample per source must
>    hash-match; a failure halts that source's deletions and queues a HIGH item.

> | `EXPIRED` | re-fetch hash differs | stays `EXPIRED`; `REFETCH_MISMATCH` recorded, HIGH item; the new bytes become a new capture through normal intake, never a substitute |

Stage 5:

>   give `REFETCH_MISMATCH`, HIGH, and the expired evidence is not replaced.

A queue item needs a run, a key and a pair (data spec §5 **Review queue**: "an item is keyed by
measurement key, pair (or extraction), outcome and input hash"); a probe failure or a re-fetch
mismatch has none. As with D6's onboarding `IDENTITY_CONFLICT`, the HIGH item is therefore a
severity `HIGH` incident row, not a `queue_items` row. "HIGH" keeps its meaning: it is listed by
the dry-run and makes the creating command exit 3 (`SUCCESS_WITH_OPEN_HIGH`).

## Unchanged

- The runtime role still cannot update or delete evidence; only the purge role, and only through
  the purge path, expires bytes and tombstones vendor payload.
- Invariant 13 (point-in-time capture): non-vendor occurrences and their times are kept forever;
  vendor readings keep their first-seen time in tombstones.
- The data spec's market-wide capture deferral, §H triggers and GBrain deferrals.

Any substantive change to these items requires a new digest and fresh review.
