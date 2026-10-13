Verdict: APPROVE

# D1a critical fix-round re-review — Codex session (handoff run)

Review scope: every CR-1–CR-4 finding in `critical-d1a-review.md`, the corresponding repaired producer/consumer paths, and Root's segment fallback correction. The source was frozen for this re-review. This approval covers the reviewed fixes; integrated R4 pytest remains pending and is a separate phase-exit requirement.

Strengths: namespace identities survive from parsing through canonical selection; artifact hashes now describe the exact parsed buffers; taxonomy and dimension semantics enter the extractor content pin; migration execution shares the checksum buffer; ambiguous owner attribution remains fail-closed while unrelated segment sections are not treated as owner ambiguity. Evidence is recorded individually below.

## Finding verdicts — every dispatched finding

| Finding | Verdict | Source evidence and covering verification |
|---|---|---|
| CR-1 — foreign dimension axes become canonical values | **ADDRESSED** | `src/fundamentals/extract/xbrl_dimensions.py:10` preserves lexical dimensions and independently expands axis/member QNames at the declaring element. An unbound/missing axis raises rather than becoming undimensioned (`:19`, `:33`; conversion to `XbrlParseError` at `extract/xbrl_parser.py:187`). The parser carries the resolved identity into raw facts at `xbrl_parser.py:775`; the adapter keeps both lexical and resolved forms at `evidence/xbrl_adapter.py:170` / `:176` and keys descriptions by resolved dimension tuples at `:269`. `evidence/mapping.py:394` requires the genuine taxonomy axis and member namespace and refuses dimensional evidence for a total. `evidence/interpret.py:533` repeats that check for the explicit `as_entry` path, so ambiguity processing cannot bypass it. `tests/fundamentals/test_xbrl_dimension_identity.py:33` covers foreign axis, foreign member and a genuine alternate prefix; `:98` requires UNMAPPED with no canonical key/value, `:124` covers forced entry, `:132` prevents total collapse, and `:142` covers a missing axis. Root supplied **4 passed**. |
| CR-2 — parsed configuration and pinned bytes differ | **ADDRESSED** | `src/fundamentals/canon/dictionary.py:438` captures the participating bytes once. Metadata, templates, applicability and family/formula files are parsed from that bundle at `:445`, `:450`, `:455`, `:459`; dictionary and separate formula hashes consume the same bundle at `:406` / `:408` / `:514`. `canon/applicability.py:106` accepts the captured buffer. `evidence/mapping.py:571` creates a per-load byte cache; `_parse` reads a path only if absent at `:620`, and its parse and hash consume the stored body at `:622` / `:763`. The index, entries, constructions and anchors all use that cache at `:572`, `:579`, `:597`, `:601`. The changing-read regressions assert model equality and exactly one read at `tests/fundamentals/test_file_content_pins.py:18` / `:42`, including separate formula and applicability cases. Root supplied **RED 5 → GREEN 5** for this file, including the migration case below. |
| CR-3 — taxonomy registry omitted from extractor pin | **ADDRESSED** | `src/fundamentals/compare/run_config.py:57` now includes `extract/xbrl_taxonomies.py`; `:58` also includes the new `extract/xbrl_dimensions.py` helper. `extractor_pin` hashes every listed source at `:139`. `tests/fundamentals/test_compare_config_pins.py:44` independently changes each semantic source and requires a changed pin at `:57`. Root supplied **2 passing change-proof tests**. The existing ingest pin path and generation reuse therefore see a different extractor content identity when either source changes (`evidence/first_party_ingest.py:159`; `evidence/first_party_extract.py:229`). |
| CR-4 — executed migration SQL differs from recorded checksum | **ADDRESSED** | `src/fundamentals/pg/migrations.py:116` captures each file once, hashes that body at `:117`, executes that same body at `:129`, and records its matching checksum at `:130`. Applied-file checksum comparison remains at `:118`. The isolated PostgreSQL regression at `tests/fundamentals/test_file_content_pins.py:64` substitutes different bytes on a hypothetical second read, then asserts the original checksum, original table existence, replacement table absence and one read at `:85`–`:93`. This is the fifth case in Root's supplied **5 passed** result. No applied migration SQL edit is needed for this repair. |

Counts: **4 ADDRESSED; 0 NOT ADDRESSED**.

## Root's segment fallback correction

**ADDRESSED; no new blocker established.** `src/fundamentals/evidence/mapping.py:153` adds an explicit opt-in for the unestablished-section fallback. `matches` considers that fallback only when ordinary selection found nothing and only for opted-in entries at `:355` / `:364`. The three shipped owner-attribution entries opt in at `config/mappings/pdf/v1/results_layout.yaml:135`, `:145`, `:155`; segment revenue/assets/liability entries do not. Thus a legitimate segment-results label outside those selectors stays unmatched rather than supplying INVALID candidates for different segment measurements.

Unknown owners still route to every evidenced owner candidate as INVALID without a value (`tests/fundamentals/test_ambiguous_candidate_selection.py:70`, `:77`), and explicit OCI remains stored (`tests/fundamentals/test_evidence_pdf_ingest.py:92`). The actual run/replay case retains INVALID selection for the uncertain owner/OCI cells at `tests/fundamentals/test_compare_integration_boundaries.py:213` / `:219` / `:223`. Retained positive segment behavior is covered by row-aware revenue at `test_evidence_first_party.py:171`, member descriptions at `:358`, filing-specific segment proofs at `:624`, and segment-total child traces at `:687`. Root supplied **11 ambiguity/retained-segment/pin regressions passed** after this correction.

## Remaining issues, ranked by severity

- **Critical:** none established in the dispatched findings or repaired interactions.
- **Important:** none established in the dispatched findings or repaired interactions.
- **Minor:** none established in the dispatched findings or repaired interactions.
- **Out-of-scope observations:** none asserted as additional acceptance blockers.

## Verification and limits

- Independent source review covered the actual parser → raw fact → occurrence → mapping → interpretation path, forced-entry ambiguity path, lexical evidence preservation, total refusal, loader parse/hash caches, extractor dependencies, migration buffer execution and PDF fallback policy. The references above are current source reads, not inherited verdicts from R3 or implementer rationale.
- Current module counts from a fresh read: `evidence/mapping.py` **769**, `canon/dictionary.py` **522**, `extract/xbrl_parser.py` **789**, all below the plan's 800-line limit. No additional structural issue was found at these changed boundaries.
- The covering tests were read for their assertions; Root supplied their recorded pass/red-green results. No test suite, database probe or repeated focused test was run by this reviewer, because the provided runs answer the specific repaired doubts. Root also supplied full Ruff lint/format PASS (**409 formatted files**) and strict mypy PASS (**247 source files**); those commands were not rerun here.
- The last read of `integrated-pytest-r4.log` showed the suite still progressing. No completed integrated pytest result or green phase-exit gate is claimed in this report. Root must consume the final exit status and summary before closing D1a.
- The accepted A2/A9 INVALID policy, B4 AVERAGE-plus-aggregation load rejection and C7 one-entity restriction are preserved. No role or scope exception was inferred from a previous approval.
- The review applied the repository code-review skill's re-review rule to all four findings, including their spec consequences. No children were launched. No Git, Beads, network, secret, real-database, PostgreSQL data-directory or original-source mutation occurred. The requested scratchpad report is this reviewer's only intentionally written artifact.

VERDICT: APPROVE
