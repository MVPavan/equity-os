#!/usr/bin/env python3
"""RESTRUCTURE-1 move map: rule, generation and coverage check.

Writes moves.tsv (kind, old path, new path, flag) and prints the checks. Reads git names and the
AST of Python modules only; never opens a restricted file. Exit 1 on any coverage failure.
Run from the repo root: python3 scratchpad/restructure/rule.py [base-ref] [replay-ref]
"""
import ast
import collections
import pathlib
import re
import subprocess
import sys

BASE = sys.argv[1] if len(sys.argv) > 1 else "HEAD"
REPLAY = sys.argv[2] if len(sys.argv) > 2 else "45d315f9"
OUT = pathlib.Path(__file__).parent / "moves.tsv"
RESTRICTED = ("stage4_holdout.yaml", "stage4_manifest.yaml")

SUB_BUCKETS = """coverage/universe coverage/screens coverage/watchlist companies/onboarding companies/identity
sourcing/transport sourcing/exchange sourcing/documents sourcing/vendors/screener sourcing/vendors/tijori
sourcing/vendors/upstox sourcing/surfaces sourcing/news sourcing/online extraction/packages extraction/xbrl
extraction/results_pdf extraction/vendors/screener extraction/vendors/tijori extraction/vendors/upstox
extraction/surfaces extraction/guidance extraction/model extraction/news normalisation/dictionary
normalisation/mapping normalisation/derivation verification/comparison verification/review_queue
verification/admission verification/diagnostics analysis/calculations analysis/thesis_models
analysis/lenses/risk analysis/lenses/credibility analysis/lenses/thesis_tests analysis/lenses/forward
publication/drafting publication/checking publication/approval publication/revision publication/narration
publication/export storage/raw_files storage/database storage/records storage/facts storage/memory
storage/retention storage/backup storage/search contracts/companies contracts/sourcing contracts/measurement
contracts/verification contracts/publication contracts/storage interface/entry interface/commands/companies
interface/commands/sourcing interface/commands/extraction interface/commands/verification
interface/commands/publication interface/commands/storage interface/workflows""".split()
EMPTY_BY_DESIGN = {"sourcing/online", "storage/search", "coverage/watchlist"}  # README only

# (old-module regex, sub-bucket, judgement call?) — first match wins.
CMD = "interface/commands/"
SCR, TIJ, UPX = "vendors/screener", "vendors/tijori", "vendors/upstox"
R = [
    # interface
    (r"api/(cli|cli_parser|operator_cli|config|env_credentials)", "interface/entry", 0),
    (r"api/(pipeline|pipeline_steps|goal_runner|report_builder|comparatives|run_comparatives)", "interface/workflows", 0),
    (r"api/(onboard_cli|entity_map_cli)", CMD + "companies", 0),
    (r"api/evidence_cli", CMD + "extraction", 0),
    (r"api/(compare_cli|three_source_cli|upstox_crosscheck_cli|upstox_sensitivity_cli|validate_cli)", CMD + "verification", 0),
    (r"api/screener_watchlist_corroborate_cli", CMD + "verification", 1),
    (r"api/(ledger_cli|report_cli|review_cli)", CMD + "publication", 0),
    (r"api/(thesis_cli|adjudication_cli)", CMD + "publication", 1),
    (r"api/(db_cli|legacy_cli|retention_cli)", CMD + "storage", 0),
    (r"api/(coverage_cli|artifact_writer)", CMD + "sourcing", 1),
    (r"api/(watchlist_config|wave_selection)", "interface/entry", 1),  # composition config stays with api/config
    (r"api/(source_admission|source_intake)", CMD + "sourcing", 1),
    (r"api/.*", CMD + "sourcing", 0),
    # normalisation
    (r"canon/(dictionary|dictionary_validation|applicability|role_translation)", "normalisation/dictionary", 0),
    (r"canon/.*", "normalisation/derivation", 0),
    # verification
    (r"compare/(queue|routing|triage)", "verification/review_queue", 0),
    (r"compare/trust", "verification/review_queue", 1),
    (r"compare/.*", "verification/comparison", 0),
    (r"evidence/admission", "verification/admission", 0),
    (r"evidence/selection", "verification/comparison", 1),
    (r"reconcile/report", "verification/diagnostics", 1),
    (r"reconcile/gold_file", "verification/diagnostics", 0),
    (r"reconcile/.*", "verification/comparison", 1),
    (r"verify/quote_anchor", "publication/checking", 0),  # owner decision
    (r"verify/thesis_predicates", "analysis/lenses/thesis_tests", 1),
    (r"verify/(laneb_.*|three_source.*)", "verification/diagnostics", 0),
    (r"verify/.*", "verification/comparison", 1),
    # contracts
    (r"contracts/(entity_identity|onboarding|basis_status)", "contracts/companies", 0),
    (r"contracts/(acquisition_outcome|snapshot|source_catalog|source_registration|news)", "contracts/sourcing", 0),
    (r"contracts/(comparison|comparative|review_queue)", "contracts/verification", 0),
    (r"contracts/(config_versions|versioning)", "contracts/verification", 1),
    (r"contracts/(ledger|forward_book)", "contracts/publication", 0),
    (r"contracts/(memory|retention|retention_purge)", "contracts/storage", 0),
    (r"contracts/(evidence|qualification|guidance_claim)", "contracts/measurement", 1),
    (r"contracts/.*", "contracts/measurement", 0),
    # coverage and companies
    (r"coverage/registry", "coverage/universe", 0),
    (r"coverage/.*", "coverage/screens", 0),
    (r"ingest/(screen_export|tijori_screen_fetch)", "coverage/screens", 1),
    (r"entity/(discovery|discovery_origins|verification|derived_settings)", "companies/onboarding", 0),
    (r"entity/.*", "companies/identity", 0),
    (r"evidence/discovery_gate", "companies/onboarding", 1),
    (r"pg/identity_seed", "companies/identity", 1),
    # extraction, first party
    (r"evidence/(capture_intake|first_party_extract|first_party_ingest|member_identity|presence|shareholding_ingest)", "extraction/packages", 0),
    (r"evidence/(xbrl_adapter|shareholding_filing)", "extraction/xbrl", 0),
    (r"evidence/pdf_adapter", "extraction/results_pdf", 0),
    (r"evidence/vendor_screener", "extraction/" + SCR, 0),
    (r"evidence/vendor_tijori", "extraction/" + TIJ, 0),
    (r"evidence/vendor_upstox", "extraction/" + UPX, 0),
    (r"evidence/(vendor_ingest|vendor_shareholding)", "extraction/surfaces", 1),
    (r"extract/guidance_extractor", "extraction/guidance", 0),
    (r"extract/pdf_.*", "extraction/results_pdf", 0),
    (r"extract/.*", "extraction/xbrl", 0),
    (r"ingest/(pdf_source|ocr_engine)", "extraction/results_pdf", 1),
    (r"ingest/xbrl_identity", "extraction/xbrl", 0),
    # normalisation from evidence
    (r"evidence/(mapping|mapping_models|interpret)", "normalisation/mapping", 0),
    (r"evidence/(alignment|capture_interpretation)", "normalisation/mapping", 1),
    (r"evidence/derived", "normalisation/derivation", 0),
    # storage from evidence
    (r"evidence/capture_retention", "storage/raw_files", 0),
    (r"evidence/repository.*", "storage/records", 0),
    # sourcing, first party and news
    (r"ingest/http_session", "sourcing/transport", 0),
    (r"ingest/(bse_pdf_source|bse_source|nse_filings|shareholding_filing|xbrl_source|comparator_cache)", "sourcing/exchange", 0),
    (r"ingest/sec_source", "sourcing/exchange", 1),
    (r"ingest/(first_party_documents|screener_documents|tijori_documents)", "sourcing/documents", 0),
    (r"ingest/news_.*", "sourcing/news", 0),
    (r"news/store", "storage/records", 1),  # persistence; renamed below
    (r"news/health", "sourcing/news", 1),
    (r"news/.*", "extraction/news", 0),
    # Lane B and cross-source diagnostics
    (r"ingest/(screener_crosscheck|screener_watchlist_crosscheck|screener_watchlist_corroborate|upstox_crosscheck)", "verification/diagnostics", 1),
    # screener: fetch and orchestration vs reading
    (r"ingest/screener_(session|company|company_sweep|company_parts|financials|source|watchlist)", "sourcing/" + SCR, 0),
    (r"ingest/screener_watchlist_models", "sourcing/" + SCR, 1),
    (r"ingest/screener_.*", "extraction/" + SCR, 0),
    # tijori
    (r"ingest/tijori_(source|capture|retention)", "sourcing/" + TIJ, 0),
    (r"ingest/tijori_overview", "sourcing/" + TIJ, 1),
    (r"ingest/tijori_.*", "extraction/" + TIJ, 0),
    # upstox
    (r"ingest/upstox_statements", "extraction/" + UPX, 0),
    (r"ingest/(upstox_source|upstox_retention)", "sourcing/" + UPX, 0),
    (r"ingest/(upstox_instruments|upstox_candle_retention)", "sourcing/" + UPX, 1),
    # vendor surfaces
    (r"ingest/vendor_surface_(model|labels|claims)", "extraction/model", 0),
    (r"ingest/vendor_surface_(parse|readers|tables|cells|series)", "extraction/surfaces", 0),
    (r"ingest/vendor_surface_topology", "extraction/surfaces", 1),
    (r"ingest/vendor_surface_(capture|fetch|expand|market|due|specs)", "sourcing/surfaces", 0),
    (r"ingest/vendor_surface_canary", "sourcing/surfaces", 1),
    # publication and lenses
    (r"ledger/(citations|claim_check|numeral_scan)", "publication/checking", 0),
    (r"ledger/(lifecycle|panel|recorded_reviewer|review)", "publication/approval", 0),
    (r"ledger/rework", "publication/revision", 0),
    (r"ledger/(importer|import_mapping)", "publication/revision", 1),
    (r"ledger/(narrate|narrate_checks|evidence_bundle)", "publication/narration", 0),
    (r"ledger/export", "publication/export", 0),
    (r"ledger/(run_draft|run_sources)", "publication/drafting", 0),
    (r"ledger/display", "publication/drafting", 1),
    (r"output/.*", "publication/drafting", 1),
    (r"ledger/(risk_probe|probe_operands)", "analysis/lenses/risk", 0),
    (r"ledger/credibility", "analysis/lenses/credibility", 0),
    (r"ledger/guidance_targets", "analysis/lenses/credibility", 1),
    (r"ledger/falsifier_status", "analysis/lenses/thesis_tests", 0),
    (r"ledger/forward.*", "analysis/lenses/forward", 0),
    (r"ledger/run_traces", "analysis/calculations", 1),
    (r"ledger/store", "storage/records", 1),
    (r"thesis/.*", "analysis/thesis_models", 0),
    # storage
    (r"memory/.*", "storage/memory", 0),
    (r"pg/(backup|restore_check)", "storage/backup", 0),
    (r"pg/retention_io", "storage/retention", 0),
    (r"pg/document_intake", "storage/records", 1),
    (r"pg/legacy_import|pg/cutover", "storage/facts", 1),
    (r"pg/approvals", "storage/database", 1),
    (r"pg/.*", "storage/database", 0),
    (r"retention/.*", "storage/retention", 0),
    (r"store/(fact_store|pg_fact_store)", "storage/facts", 0),
    (r"store/vendor_values_store", "storage/records", 1),
    (r"store/.*", "storage/raw_files", 0),
]
# The only rename: same basename as ledger/store in storage/records.
RENAMED = {"news/store": "news_store"}
# A test that imports another test relatively stays beside it, so the relative import still resolves.
BESIDE = {"test_compare_diagnostic": "verification/comparison"}
# Old package __init__.py: only thesis keeps content (62 importers use its re-exports). The rest
# were either docstring-only or re-export no importer uses; contracts' 13 used names are resolved
# to their defining modules by the rewriter.
INIT_FATE = {"thesis": "equity_os/analysis/thesis_models/__init__.py"}
CONFIG = [
    (r"config/(aparinds-.*\.yaml)", r"config/runs/\1", 0),
    (r"config/(dictionary|mappings|normalisation_policy|rounding_policy)/(.*)", r"config/normalisation/\1/\2", 0),
    (r"config/(comparison_policy|definition_sets)/(.*)", r"config/verification/\1/\2", 0),
    (r"config/(watchlist|screens)\.yaml", r"config/coverage/\1.yaml", 0),
    (r"config/identity/(.*)", r"config/companies/identity/\1", 0),
    (r"config/vendor_surface/(.*)", r"config/sourcing/vendor_surface/\1", 0),
    (r"config/fundamentals\.yaml", r"config/sourcing/fundamentals.yaml", 0),
    (r"config/(narrate|ledger_import)\.yaml", r"config/publication/\1.yaml", 1),
    (r"config/laneb_triage\.yaml", r"config/verification/laneb_triage.yaml", 0),
    (r"config/legacy_import_manifest\.yaml", r"config/storage/legacy_import_manifest.yaml", 1),
    (r"config/retention/(.*)", r"config/storage/retention/\1", 0),
    (r"config/guidance_targets/(.*)", r"config/analysis/guidance_targets/\1", 1),
]
SUPPORT = re.compile(r"(_support|_fixtures|_check|_checks|_cases|_filings|_provenance|_markup|_locators)$")


def names(ref, *paths):
    return subprocess.check_output(["git", "ls-tree", "-r", "--name-only", ref, "--", *paths], text=True).split()


def show(ref, path):
    return subprocess.check_output(["git", "show", f"{ref}:{path}"], text=True)


def place(old):
    for pattern, target, judged in R:
        if re.fullmatch(pattern, old):
            return target, judged
    raise SystemExit(f"UNASSIGNED {old}")


def imported(ref, path, modules):
    """Old module names this Python file imports, with submodule-of-package imports resolved."""
    found = []
    for node in ast.walk(ast.parse(show(ref, path))):
        if isinstance(node, ast.Import):
            found += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            for alias in node.names:
                sub = f"{node.module}.{alias.name}"
                found.append(sub if sub in modules else node.module)
    return [m for m in found if m in modules]


def main():
    fail = []
    src = sorted(set(names(BASE, "src/fundamentals")) | set(names(REPLAY, "src/fundamentals")))
    head = set(names(BASE, "src/fundamentals"))
    rows, modules, flags = [], {}, collections.Counter()
    for path in src:
        rel = path.removeprefix("src/fundamentals/").removesuffix(".py")
        only = "" if path in head else "replay-only"
        if rel == "__init__" or rel.endswith("/__init__"):
            package = rel.removesuffix("__init__").rstrip("/")
            rows.append(("init", path, INIT_FATE.get(package, "(docstring goes to the new README)"), only))
            modules["fundamentals" + ("." + package.replace("/", ".") if package else "")] = None
            continue
        target, judged = place(rel)
        new = f"equity_os/{target}/{RENAMED.get(rel, pathlib.PurePath(rel).name)}.py"
        rows.append(("module", path, new, ",".join(x for x in ("judgement" if judged else "", only) if x)))
        modules["fundamentals." + rel.replace("/", ".")] = target
    config = [p for p in names(BASE, "config")]
    for path in config:
        for pattern, new, judged in CONFIG:
            if re.fullmatch(pattern, path):
                rows.append(("config", path, re.sub(pattern, new, path), "judgement" if judged else ""))
                break
        else:
            fail.append(f"config unassigned: {path}")
    # Tests: conftest and support to the shared folder; the rest by the plurality of the
    # sub-buckets they import; e2e files to interface/workflows. Fixtures do not move.
    tests = [p for p in sorted(set(names(BASE, "tests/fundamentals")) | set(names(REPLAY, "tests/fundamentals")))
             if p.endswith(".py") and "/fixtures/" not in p]
    base_tests = set(names(BASE, "tests/fundamentals"))
    thin = 0
    for path in tests:
        stem = pathlib.PurePath(path).stem
        ref = BASE if path in base_tests else REPLAY
        only = "" if path in base_tests else "replay-only"
        if stem == "conftest":
            new, tag = "tests/equity_os/conftest.py", ""
        elif not stem.startswith("test_") and SUPPORT.search(stem):
            new, tag = f"tests/equity_os/support/{stem}.py", ""
        elif stem in BESIDE:
            new, tag = f"tests/equity_os/{BESIDE[stem]}/{stem}.py", ""
        elif stem.endswith("_e2e"):
            new, tag = f"tests/equity_os/interface/workflows/{stem}.py", ""
        else:
            counts = collections.Counter(modules[m] for m in imported(ref, path, modules) if modules.get(m))
            real = {k: v for k, v in counts.items() if not k.startswith("contracts/")} or counts
            if real:
                top = sorted(real.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
                tag = "judgement" if sum(v == real[top] for v in real.values()) > 1 else ""
            else:
                top, tag, thin = "interface/workflows", "judgement", thin + 1
            new = f"tests/equity_os/{top}/{stem}.py"
        rows.append(("test", path, new, ",".join(x for x in (tag, only) if x)))
    # Coverage checks
    assert not any(any(r in row[1] for r in RESTRICTED) for row in rows)
    olds = collections.Counter(row[1] for row in rows)
    fail += [f"assigned twice: {p}" for p, n in olds.items() if n > 1]
    missing = (set(src) | set(config) | set(tests)) - set(olds)
    fail += [f"unassigned: {p}" for p in sorted(missing)]
    news = collections.Counter(row[2] for row in rows if not row[2].startswith("("))
    fail += [f"collision at {p}" for p, n in news.items() if n > 1]
    used = {m for m in modules.values() if m}
    unknown = used - set(SUB_BUCKETS)
    fail += [f"target not a sub-bucket: {u}" for u in sorted(unknown)]
    empties = sorted(set(SUB_BUCKETS) - used)
    fail += [f"empty sub-bucket not declared: {e}" for e in empties if e not in EMPTY_BY_DESIGN]
    OUT.write_text("kind\told\tnew\tflag\n" + "".join("\t".join(r) + "\n" for r in rows))
    by = collections.Counter(r[0] for r in rows)
    head_mod = sum(1 for r in rows if r[0] == "module" and "replay-only" not in r[3])
    head_init = sum(1 for r in rows if r[0] == "init" and "replay-only" not in r[3])
    print("rows", dict(by), "| head modules", head_mod, "head __init__", head_init)
    print("sub-buckets listed", len(SUB_BUCKETS), "used", len(used), "empty", empties)
    print("judgement rows", dict(collections.Counter(r[0] for r in rows if "judgement" in r[3])), "tests with no product import", thin)
    print("per sub-bucket", sorted(collections.Counter(m for m in modules.values() if m).items()))
    # backward imports under the bucket order
    order = ["contracts", "storage", "coverage", "companies", "sourcing", "extraction", "normalisation",
             "verification", "analysis", "publication", "interface"]
    rank = {b: i for i, b in enumerate(order)}
    back = set()
    for path in sorted(head):
        rel = path.removeprefix("src/fundamentals/").removesuffix(".py")
        if rel.endswith("__init__"):
            continue
        me = modules["fundamentals." + rel.replace("/", ".")]
        for dep in imported(BASE, path, modules):
            target = modules.get(dep)
            if target and rank[target.split("/")[0]] > rank[me.split("/")[0]]:
                back.add((path, dep))
    print("backward import edges (file, module) under the order", len(back), order)
    edge = collections.Counter(f"{modules['fundamentals.' + a.removeprefix('src/fundamentals/').removesuffix('.py').replace('/', '.')].split('/')[0]}->{modules[b].split('/')[0]}" for a, b in back)
    print(edge.most_common(30))
    if fail:
        print("\n".join(fail))
        raise SystemExit(1)
    print("COVERAGE OK")


main()
