# D1b Task 13 publication repair plan

> **Superseded 2026-10-14** by [D1b-cleanup.md](D1b-cleanup.md): the design this plan describes was deleted or simplified; kept as history.

Status: approved-for-implementation, r3, 2026-10-13. Fresh independent Codex session (handoff run) R3 APPROVE. Actual release authority and evidence remain pending.

## Owned patch files

- `src/fundamentals/evidence/vendor_config.py`
- `src/fundamentals/compare/run_config.py`
- `src/fundamentals/contracts/evidence.py`
- `src/fundamentals/compare/run_store.py`
- `migrations/0007_vendor_publication_pin.sql`
- new publication regression and migration-compatibility tests
- `scratchpad/execution/data-foundation-resume-2026-10-13/publication-fix-report.md`

The coordinator assigned this implementer the minimal `evidence/repository.py` and
`evidence/repository_rows.py` guarded-pin API. No other repository behavior is in scope. The
Task 11 worker owns its first-party producer call; root owns or delegates the not-yet-built Task 6
vendor persistence call. No first-party ingest, native, mapping, or shared config file is part of
this patch.

## Release and review receipt

The lifecycle has three distinct commits:

1. Candidate artifact commit **A** contains the selected publication, mapping index/members,
   dictionary/formula files, normalisation policy, source-authority artifact, source/rights
   evidence, and extractor code members. A non-authoritative candidate validator may inspect A,
   but every runtime load, pin, and generation write still refuses it.
2. A fresh independent review examines exactly those selected blobs at A. Coordinator receipt
   commit **C** then adds the fixed receipt and the exact review result; A is an ancestor of C.
3. Current commit **H** may include unrelated later work. C is an ancestor of H. The selected
   release bytes at H must still equal A, and the receipt/review-result bytes at H must still equal
   C. Unrelated later commits therefore neither invalidate nor silently widen the release.

The fixed receipt location is `config/vendor_publication/<version>.review.yaml`. Its private,
runtime-only schema is: publication version and SHA-256; reviewed candidate commit A; canonical
selected-member-manifest SHA-256; review-result `ContentMember`; verdict exactly `APPROVE`; and an
aware coordinator-recorded timestamp. The selected-member manifest hashes sorted canonical
repository-relative paths plus their content hashes, including source/rights evidence at A.
Review-result evidence is introduced at C and is not confused with those rights records.

Runtime callers cannot pass, construct, deserialize, or select a trusted receipt, path, reviewer,
or decision. The loader reads only that fixed committed sidecar, verifies A -> C -> H ancestry,
the two exact byte sets, the canonical subject digest, the review-result hash and `APPROVE`, then
returns `PublishedVendorConfig`. `ReleaseReviewReceipt` stays private. A receipt field, state,
path, hash, account, flag, or fixture is not represented as external reviewer approval; actual
reviewer identity is the operational fact established by root's fresh review and coordinator
commit. This Task 13 receipt is independent of Task 7 `ApprovalReceipt` and migration 0006, so it
creates no Task 13 -> Task 6 -> Task 7 -> Task 13 cycle. Synthetic fixtures never supply release
authority.

`C` is derived without naming itself: use the first-parent history from A (exclusive) to H
(inclusive) and find the unique first commit whose tree introduces both the exact current fixed
receipt blob and exact current review-result blob while its first parent contains neither path.
That commit is C. A must be on H's first-parent history. Zero or multiple introduction commits,
either path already present in C's parent, a later delete/re-add, or current bytes differing from C
all refuse. This deterministic transition permits unrelated commits after C and rejects ambiguous
or replaced receipt histories without a circular hash.

## Generation guard API

`require_published_generation(config: LoadedConfig, *, config_root: Path) ->
PublishedVendorConfig` refuses `vendor_config is None`, re-runs `load_run_config` from the fixed
committed root for `RELEASED` (or the explicit isolated root for `SYNTHETIC`), repeats receipt/Git
verification, and requires the freshly loaded object and every pin to equal the supplied config.
Public Pydantic models, their serialization, mutually consistent caller pins, and raw guard models
are never proof of loader provenance. `pin_published_generation(config, *, config_root,
repository)` always performs that fresh proof before writing the joined set; it does not accept a
prebuilt verifier result. The synthetic branch is loader-validated mechanics only and may write
solely after its database-name check in the same `eqos_test_*` repository connection and
transaction. `PublishedVendorConfig.published_config_sha256` is a read-only alias of its verified
`content_sha256` for producer handoffs.

The mandatory authoritative seams and order are:

- Task 11 owner: its new
  `evidence/first_party_generation.py::append_first_party_generation(..., config: LoadedConfig,
  repository: EvidenceRepository, ...) -> FirstPartyGenerationHandoff` receives the real
  `LoadedConfig` plus the config root needed for re-verification, accepts no free-standing
  artifact/digest or separate pool, and calls `pin_published_generation` before existing
  `ingest_first_party` can reach
  `EvidenceRepository.put_generation`, `put_attempts`, or `put_interpretations`, and binds the
  returned publication digest into `FirstPartyGenerationHandoff`. Missing/mismatched proof must
  yield zero generation-table mutation. Existing `ingest_first_party` remains the explicit legacy
  v1/draft entry point and is not edited here.
- Task 6 owner (root or its delegated worker): the new vendor persistence composition calls the
  same guard before any `put_generation`, `put_attempts`, or `put_interpretations`, and requires
  `VendorGeneration.published_config_sha256` to equal the returned digest. The current pure
  `vendor_offline`/adapter builders remain draft-only and do not authorize storage.

Both handoff owners must add public-seam no-write tests. This implementer supplies the guard and
single-repository transaction; it does not edit their producer files.

## Stored run compatibility

`PinnedVersions.vendor_publication: VersionPin | None = None` is omitted from legacy JSON just
like the existing optional authority pin. `RunStore` writes/reads the scalar
`vendor_publication` row. Migration `0007` only widens the immutable `run_versions.pin` check to
that value; migrations `0001` through `0006` remain byte-for-byte unchanged. Replay compares the
publication digest, including ledger-only changes.

## Fail-closed boundaries

- Every version is one canonical filename component.
- Release/config/evidence members are descriptor-read regular files; symlinked roots,
  directories, and members are refused.
- Only source-generic mappings or declared first-party sources on the two filing surfaces may
  use the legacy boundary. Unknown or derived sources always require publication.
- Released authority evidence references resolve to actual repository-relative regular files
  and their hashes are checked. Recognized projections are closed, not free-form:
  `A05-DECISION-005` at
  `docs/evidence/phase-0a/a-05-rights-decision-005-subscriber-scraping.md` authorizes only
  Screener/Tijori subscriber surfaces for private, personal, non-commercial internal retention,
  processing, and derived facts; those sources remain derived and the publication carries that
  use boundary. The 2026-09-03 canonical data-spec decision may classify Upstox only as
  derived/diagnostic-only and can never produce a `SurfaceAuthority`. The loader checks exact
  decision/record identity, applicable source, role, declared surface/use boundary, evidence hash,
  and canonical projection digest. Unknown evidence types, unrelated valid files, broader/public/
  commercial declarations, and any Upstox authority or reconcilable role fail closed.
- Extractor bundles name their exact supported schema identities; every mapping and construction
  must join the matching source, surface, and schema.

## RED and acceptance ruling

The original sealed acceptance file stays unchanged. New regressions must reach existing public
behavior; missing imports/keywords and infrastructure errors are recorded separately and never
counted as feature RED. Synthetic Git/review fixtures prove mechanics only and are never evidence
of actual independent approval.

| Finding | Required public-seam acceptance |
| --- | --- |
| 1 | candidate A without receipt refuses; A outside first-parent history refuses; zero/multiple/parent-preexisting C transitions and deleted/re-added or replaced receipt histories refuse; dirty/untracked selected member, authority, rights evidence, extractor code, receipt or review-result drift refuses; unrelated later H accepts; forged/caller-selected receipt is impossible/refused |
| 2 | manually constructed/deserialized mutually consistent `LoadedConfig`/`PublishedVendorConfig` without the fixed receipt refuses with zero pins/rows; Task 11 first-party v2 and Task 6 vendor persistence each refuse absent/mismatched proof with zero generation mutation, pin before their first write, and bind the exact publication digest; explicit v1/draft paths remain separate |
| 3 | derived and unknown sources using first-party-looking surfaces still require publication and cannot enter the first-party exception |
| 4 | exact A05 private-use projection accepts only its Screener/Tijori scope; unrelated/unknown/broader evidence refuses; Upstox reconcilable promotion and every Upstox `SurfaceAuthority` refuse; diagnostic values never vote |
| 5 | formula-only and ledger-only drift refuse; migration fresh install and 0006->0007 upgrade pass; `RunStore` round-trips the optional publication pin; same-root v2->v3 keeps old-manifest replay pinned to v2; v1 JSON omits the field |
| 6 | synthetic pinning succeeds only through one `eqos_test_*` repository connection; non-test and pool/repository mismatch attempts leave no partial pins |
| 7 | every version traversal/multi-component value, symlinked root/directory/member, nonregular member, and changed-during-read identity refuses |
| 8 | source/surface/schema mismatch and unsupported schema refuse against the exact extractor bundle |
| 9 | actual public ingest/run/replay/refusal paths cover the above; root adds the exact committed real-release load/coverage assertion only after accepted shared artifacts and fresh review/receipt commits exist |

Root owns PostgreSQL RED/green, resealing, candidate/review/receipt commits, final release creation,
and the eventual exact real-release test after all shared artifacts freeze.
