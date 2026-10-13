Verdict: REQUEST_CHANGES

# D1a critical whole-phase quality review — Codex session (handoff run)

Review checkpoint: the frozen implementation supplied after R3, inspected independently against `docs/workstreams/data-foundation/plans/D1a.md` and `docs/specs/2026-10-11-canonical-financial-data-and-cross-source-comparison.md`. R2/R3 reports were claims, not evidence. Four Important defects were found; no Critical defect was established. Root began repairing reported defects during this review. The findings below describe the original reviewed checkpoint, and explicitly distinguish the limited subsequent repair evidence.

Strengths: complete capture histories reach selection before cross-key supersession (`src/fundamentals/compare/engine.py:540`; `src/fundamentals/evidence/selection.py:183`); PDF extraction contexts fail closed before current and comparative selection (`src/fundamentals/compare/engine_attempts.py:148`; `src/fundamentals/compare/engine.py:579`); replay loads immutable input ids and recomputes through the same engine (`src/fundamentals/compare/resolve.py:138`; `src/fundamentals/compare/run.py:172`); migration 0005 protects the server clock cache (`migrations/0005_store_clock_cache_and_keyless_dimensions.sql:35`). These repairs close material earlier producer/consumer gaps.

## Issues — Important, ranked by consequence

### CR-1 — Foreign XBRL dimension axes become canonical segment values

- **Quality / correctness / evidence integrity.** `src/fundamentals/extract/xbrl_parser.py:164` keeps a dimension as a lexical QName without resolving its namespace. `src/fundamentals/evidence/xbrl_adapter.py:170` strips the axis to its local name; `src/fundamentals/evidence/mapping.py:407` compares that local name with the configured axis; `src/fundamentals/evidence/interpret.py:532` then resolves the member description under that same local-name key.
- **Trigger:** replace the retained Q2 FY26 segment axis with `foreign:ReportableSegmentsAxis`, binding `foreign` to `urn:foreign-dimensional-semantics`, while keeping the genuine fact namespace, issuer, report nature, period and member description.
- **Observed:** the actual parser and identity verifier accept the modified instance. The actual occurrence adapter and interpreter return `MAPPED`, canonical `segment_revenue`, value **31,001,900,000 INR**, dimensions `segment=conductors` and `elimination_basis=PRE_ELIMINATION`. The native context retains the foreign lexical axis, but the canonical selector sees only `ReportableSegmentsAxis`.
- **Consequence:** an extension/foreign dimension with a different meaning is promoted into a genuine taxonomy segment key. The identity/unit namespace fixes do not cover this dimension boundary. This may produce a false comparable value and pollute the entity's segment evidence.
- **Fix:** resolve dimension axis and member QNames to namespace URI plus local name at the parser boundary; preserve that identity in native evidence; match registered taxonomy axes by that full identity. Reject unsupported/unbound dimensions from canonical mapping while retaining their native evidence. Alternate prefixes bound to the genuine namespace must remain equivalent. Cover explicit and typed axes and conflicting member-description contexts.
- **Proof:** exact in-memory retained parser-to-interpreter probe below, exit 0. No original, configuration or database was changed. Subsequent Area A repair was requested; it is outside this checkpoint verdict.

### CR-2 — Dictionary/formula and mapping hashes can pin bytes different from their parsed semantics

- **Quality / reproducibility.** At the reviewed checkpoint, `src/fundamentals/canon/dictionary.py:399` parses the files, then `:406` / `:408` and `:516` reopen them to hash the dictionary and formula set. `src/fundamentals/evidence/mapping.py:558` / `:576` / `:580` parse mapping members, then `:587` / `:745` reopen them for the mapping hash.
- **Trigger:** a file changes between its parse read and its hash read. This can be an ordinary concurrent edit or deployment; no privileged database mutation is required.
- **Observed:** a pure `Path.read_bytes` probe produced two valid dictionaries with identical dictionary and formula pins, while the execution dictionary's `opm_pct` numerator is `ebitda_excl_other_income` and the settled/replay dictionary's numerator is `other_income`. A separate mapping probe produced an identical mapping pin with revenue sign **+1** on the first load and **−1** on the settled load.
- **Consequence:** content equality no longer establishes semantic equality. Formula replay may compute a different result or fail because its stored trace no longer exists. Ingestion can store/reuse interpretations under a mapping hash that describes different sign semantics. `require_pins` cannot detect this because both hashes are equal (`src/fundamentals/compare/run_config.py:200`). This breaches the manifest reproduction contract (`docs/specs/2026-10-11-canonical-financial-data-and-cross-source-comparison.md:610`).
- **Fix:** read every participating artifact once into an immutable byte bundle, parse those buffers, and hash exactly those buffers, including the separately pinned formula file and mapping index/members. Refuse an inconsistent bundle if the chosen loader design permits concurrent revision changes.
- **Proof:** two no-write loader probes below, each exit 0. Root began a single-buffer repair during review; a source read subsequently showed `dictionary.py:399` / `:408` using a `bodies` bundle. That narrow observation does not constitute the independent fix-round approval or full loader coverage.

### CR-3 — The XBRL extractor content pin omits its directly used taxonomy registry

- **Quality / version integrity.** `src/fundamentals/compare/run_config.py:53` names the XBRL extractor's hashed source files but omits `src/fundamentals/extract/xbrl_taxonomies.py`. The adapter directly imports that file's `_ALL_TAXONOMIES` at `src/fundamentals/evidence/xbrl_adapter.py:40` and passes it into parsing at `:59`. Registry entries determine supported taxonomy dispatch and the `TaxonomySpec` fields used for basis and declared-period interpretation (`src/fundamentals/extract/xbrl_parser.py:238`; `:310`; `:335`).
- **Trigger:** change a taxonomy registration or its parse/identity semantics without changing the extractor version. The registry bytes change, but the extractor hash does not.
- **Consequence:** the new ingestion content-pin check cannot detect this parser-input drift. `extract_member` can reuse the old generation under the unchanged extractor (`src/fundamentals/evidence/first_party_extract.py:229`; `:250`) while a fresh capture is interpreted using the changed registry. One extractor pin can therefore describe different behavior/provenance.
- **Fix:** add the directly consumed taxonomy registry to the XBRL source pin and audit directly imported extraction/identity dependencies for the same omission. Add a focused content-pin test that changes the registry bytes and requires a different pin/drift rejection.
- **Proof:** the no-write source-read probe below reports `taxonomy_registry_read False` and `extractor_pin_changed False`, exit 0. This is an omission proof, not a claim that a real taxonomy file was edited. The fix changes the extractor content hash, so existing stored pins must be handled by the approved versioning/re-extraction path.

### CR-4 — A migration can execute different SQL from its recorded checksum

- **Quality / migration integrity.** At the reviewed checkpoint, `src/fundamentals/pg/migrations.py:116` computes checksums through `_sha256` / `:158`, but `:128` reopens each pending path for SQL execution, and `:129` records the earlier checksum.
- **Trigger:** a pending migration file is changed/replaced between its checksum read and execution read.
- **Consequence:** SQL B executes while `schema_migrations` records SHA256(A). Restoring A subsequently passes the checksum check although the database executed B, undermining the authority of the applied-migration history. This is the same buffer-integrity principle at a different persistent boundary from CR-2.
- **Fix:** capture every migration's bytes once, hash and execute that same buffer. No applied migration SQL needs editing. A focused runner test should return different bytes on subsequent path reads and prove only the originally captured buffer executes.
- **Evidence / repair status:** independently source-inspected by the delegated PostgreSQL auditor and this reviewer. Root repaired the runner during review: the subsequent source read uses `bodies` at `migrations.py:116` / `:129`. A no-database fake-connection probe then executed `SELECT 1;` and recorded its matching checksum when the fake path would return `SELECT 2;` on a second read. This specific race is **addressed in the newly observed runner**; covering repository tests and the requested independent fix-round verdict remain Root's next verification step. It is retained here so the exhaustive original review ledger omits no finding.

## Boundary checks and evidence limits

- Selection, cutoff, package scope and negative outcomes were traced at `evidence/selection.py:59`, `:152`, `:236`, `compare/resolve_loader.py:155`, `:182`, `compare/engine_attempts.py:122`, and `compare/engine.py:448`. Complete-capture supersession and incompatible PDF-context refusal were source verified; no new defect was established in those repaired edges.
- Nested derivation, qualifications, dimension binding, period aggregation and comparison adjustments were traced at `evidence/derived.py:189`, `:219`, `:255`, `compare/engine_formula.py:205`, `canon/period_aggregation.py:78`, and `compare/tables.py:266`. The approved B4 loader refusal remains intact at `canon/dictionary_validation.py:261`. No unsupported numeric composition is claimed.
- Run input closure, publication, CLI failure handling and report provenance were checked at `compare/resolve.py:182`, `compare/run_store.py:248`, `api/compare_cli.py:107`, and `compare/report.py:119` / `:198`. PostgreSQL parent-created branches gate the reviewed public child writes at `evidence/repository.py:309`, `:421`, `:598`; speculative direct SQL child appends and arbitrary timestamp INSERTs were not graded as public-API defects.
- The owner rulings are preserved: A2/A9 ambiguous PDF attribution and unclear blank rows remain INVALID; C7 remains one entity per run; B4 remains loader rejection. Their policies were not relitigated. The current consumer paths were checked at `evidence/interpret.py:152`, `:547`, `compare/run_models.py:127`, and `canon/dictionary_validation.py:261`.
- The security lens covered raw XML/PDF input, configuration hashes, migration integrity and runtime privilege boundaries. No new web authentication/session, network acquisition or LLM-output boundary exists in the reviewed D1a surface; those checklist sections do not apply to this task.
- Fresh focused evidence consists of in-memory parser/interpreter, loader and content-pin probes using `PYTHONDONTWRITEBYTECODE=1`, task-local `UV_CACHE_DIR`, and `uv run --no-sync`. A first formula-race probe changing the percentage literal to 200 was correctly rejected by UNIT_ALGEBRA; the valid numerator-substitution probe then reproduced CR-2. That setup refusal is not a test-suite failure.
- No broad suite was rerun, no network/secret/real-database/data-directory access was performed, and no production/test/configuration/document/Beads/Git mutation was made by this reviewer. The delegated auditor used source-only inspection and wrote nothing. This scratchpad report is the only intentionally written artifact. Read-only `git status --short` showed the shared implementation changes; this reviewer did not stage or modify them.
- Root supplied Ruff lint, Ruff formatting (406 files) and strict mypy (246 files) PASS claims. Root subsequently reported eight failures from its integrated suite, mostly stale fixtures and still under investigation. This reviewer did not independently rerun that suite and does not claim a green phase-exit gate or conclude that all eight failures are harmless.
- This is a quality review. The new findings are correctness/integrity defects in implemented boundaries, with spec consequences identified where applicable; the earlier 34-finding spec matrix is not re-litigated. The requested whole-phase risks were inspected, but this report does not claim exhaustive security assurance or a line-by-line re-review of every unchanged module.

## Exact CR-1 reproduction

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --no-sync python - <<'PY'
from pathlib import Path
from datetime import datetime, UTC
from lxml import etree
from fundamentals.canon.dictionary import load_dictionary
from fundamentals.evidence.mapping import load_mapping_set, load_normalisation_policy
from fundamentals.evidence.xbrl_adapter import parse_instance, occurrences_from_instance
from fundamentals.evidence.member_identity import IssuerIdentifiers, verify_xbrl_identity
from fundamentals.evidence.interpret import interpret
from fundamentals.contracts.evidence import CaptureReference, PackageMember, KnowledgeTimeStatus
from fundamentals.contracts.canonical import Representation, Basis, PeriodKind
from fundamentals.contracts.observation import AccountingFramework
from fundamentals.contracts.qualification import QualificationContext
now = datetime.now(UTC)
dictionary = load_dictionary(Path('config/dictionary'), 'v1')
mappings = load_mapping_set(Path('config/mappings'), 'v1', dictionary=dictionary)
policy = load_normalisation_policy(Path('config/normalisation_policy/v1.yaml'))
body = Path('data/raw/watchlist/aparinds/nse/INTEGRATED_FILING_INDAS_1560713_29102025085858_WEB.xml').read_bytes()
root = etree.fromstring(body)
ns = 'http://xbrl.org/2006/xbrldi'
changed = 0
for node in root.findall('.//{' + ns + '}explicitMember'):
    if node.get('dimension', '').endswith(':ReportableSegmentsAxis'):
        new = etree.Element(node.tag, nsmap={'foreign': 'urn:foreign-dimensional-semantics'})
        new.attrib.update(node.attrib)
        new.set('dimension', 'foreign:ReportableSegmentsAxis')
        new.text = node.text
        node.getparent().replace(node, new)
        changed += 1
instance = parse_instance(etree.tostring(root), mapping_set=mappings)
identifiers = IssuerIdentifiers(entity_id=1, isin='INE372A01015', nse_symbol='APARINDS', bse_scrip='532259', evidence_input_id=1)
print('foreign_axes', changed, 'identity_verified', verify_xbrl_identity(instance, identifiers, basis=Basis.CONSOLIDATED).verified)
capture = CaptureReference(capture_ref_id=1, source_id='nse', surface='NSE_XBRL_INSTANCE', request_key='probe', capture_id='probe', blob_sha256='0'*64, record_sha256='0'*64, registered_at=now, first_seen_at=now)
member = PackageMember(representation=Representation.XBRL, capture=capture, knowledge_time=now, knowledge_time_raw=now.isoformat(), knowledge_time_status=KnowledgeTimeStatus.KNOWN)
occurrences = occurrences_from_instance(instance, capture=capture, member=member, mapping_set=mappings)
selected = [o for o in occurrences if o.native_context.get('context_ref') == 'OneReportable1D' and o.native_context.get('local_name') == 'SegmentRevenue']
print('selected', len(selected))
for occurrence in selected:
    occurrence = occurrence.model_copy(update={'occurrence_id': 1})
    print('native_dimensions', occurrence.native_context['dimensions'])
    print('selector_axes', occurrence.native_context['dimension_axes'])
    qualification = QualificationContext(schema_identity=instance.schema_identity, surface=capture.surface, basis=Basis.CONSOLIDATED, period_kind=PeriodKind.QUARTER, proven={})
    result = interpret(occurrence, entity_id=1, basis=Basis.CONSOLIDATED, framework=AccountingFramework.IND_AS, mapping_set=mappings, policy=policy, dictionary=dictionary, fiscal_year_end_month=3, qualification=qualification, recorded_at=now)
    print('interpretation', result.status.value, 'canonical', result.canonical_id, 'value', result.value, 'dimensions', None if result.key is None else result.key.dimensions.pairs)
PY
```

Observed at the reviewed checkpoint:

```text
foreign_axes 8 identity_verified True
selected 1
native_dimensions [['foreign:ReportableSegmentsAxis', 'in-capmkt:ReportableSegments1Member']]
selector_axes ['ReportableSegmentsAxis']
interpretation MAPPED canonical segment_revenue value 31001900000 dimensions (('elimination_basis', 'PRE_ELIMINATION'), ('segment', 'conductors'))
```

## CR-2 loader-race reproduction

The mapping and dictionary probes were executed separately, using only patched reads and no filesystem writes. This equivalent consolidated command reproduces both probes. A fixed single-buffer loader should make the first and settled pins differ instead.

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --no-sync python - <<'PY'
from pathlib import Path
from unittest.mock import patch
from fundamentals.canon.dictionary import load_dictionary
from fundamentals.evidence.mapping import load_mapping_set
original = Path.read_bytes
for kind in ('dictionary', 'mapping'):
    root = Path('config/dictionary' if kind == 'dictionary' else 'config/mappings')
    target = root / ('v1/derived.yaml' if kind == 'dictionary' else 'xbrl/v1/in_capmkt.yaml')
    a = original(target)
    if kind == 'dictionary':
        b = a.replace(b'    - name: ebitda\n      canonical_id: ebitda_excl_other_income\n', b'    - name: ebitda\n      canonical_id: other_income\n', 1)
        load = lambda: load_dictionary(root, 'v1')
    else:
        b = a.replace(b'    canonical_id: revenue_from_operations\n', b'    canonical_id: revenue_from_operations\n    sign: -1\n', 1)
        dictionary = load_dictionary(Path('config/dictionary'), 'v1')
        load = lambda: load_mapping_set(root, 'v1', dictionary=dictionary)
    assert a != b
    count = [0]
    def racing(path):
        if path == target:
            count[0] += 1
            return a if count[0] == 1 else b
        return original(path)
    with patch.object(Path, 'read_bytes', racing):
        first = load()
    with patch.object(Path, 'read_bytes', lambda path: b if path == target else original(path)):
        settled = load()
    print(kind, 'same_pin', first.content_sha256 == settled.content_sha256)
    if kind == 'dictionary':
        print('same_formula_pin', first.formula_set_sha256 == settled.formula_set_sha256)
        print('numerators', first.row('opm_pct').formula.operands[0].canonical_id, settled.row('opm_pct').formula.operands[0].canonical_id)
    else:
        print('signs', first.entry('capmkt.revenue_from_operations').sign, settled.entry('capmkt.revenue_from_operations').sign)
PY
```

Separate successful probe outputs at the reviewed checkpoint:

```text
same_dictionary_pin True
same_formula_pin True
execute_opm_numerator ebitda_excl_other_income
replay_opm_numerator other_income
target_reads_during_first_load 2

same_mapping_pin True
execute_revenue_sign 1
replay_revenue_sign -1
target_reads_during_first_load 2
```

## Exact CR-3 omitted-registry proof

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --no-sync python - <<'PY'
from pathlib import Path
from unittest.mock import patch
from fundamentals.compare.run_config import extractor_pin
from fundamentals.contracts.canonical import Representation
original = Path.read_bytes
before = extractor_pin(Representation.XBRL)
reads = []
def changed(path):
    reads.append(path.as_posix())
    data = original(path)
    return data + b'\n# changed taxonomy registry\n' if path.name == 'xbrl_taxonomies.py' else data
with patch.object(Path, 'read_bytes', changed):
    after = extractor_pin(Representation.XBRL)
print('taxonomy_registry_read', any(name.endswith('/xbrl_taxonomies.py') for name in reads))
print('extractor_pin_changed', before != after)
PY
```

Observed: `taxonomy_registry_read False`; `extractor_pin_changed False`; exit 0.

VERDICT: REQUEST_CHANGES

Portability note: host-local uv cache overrides were omitted from the recorded commands.
