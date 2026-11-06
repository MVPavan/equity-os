"""Bounded evaluation; draft keys require separate Sol review before real scoring."""

import argparse
import hashlib
import json
import os
from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, SecretStr

from equity_os.extraction.model.vendor_surface_claims import SYSTEM as SPAN_SYSTEM
from equity_os.extraction.model.vendor_surface_claims import validate_spans
from equity_os.extraction.model.vendor_surface_labels import SYSTEM as LABEL_SYSTEM
from equity_os.extraction.model.vendor_surface_labels import accept
from equity_os.extraction.model.vendor_surface_model import ChatCompletionsModel, LabelModel
from equity_os.extraction.surfaces.vendor_surface_cells import LabelSample, label_samples
from equity_os.extraction.surfaces.vendor_surface_parse import PARSERS, Body, ParseContext
from equity_os.extraction.surfaces.vendor_text_readers import read_text
from equity_os.extraction.vendors.screener.screener_session_models import Basis
from equity_os.normalisation.dictionary.dictionary import load_dictionary
from equity_os.sourcing.surfaces.vendor_surface_fetch import Site


class LabelScore(BaseModel):
    """Accuracy is measured only on positive key rows."""

    model_config = ConfigDict(frozen=True)
    accuracy: float
    false_mappings: int
    abstentions: int


def score_labels(answers: Sequence[str | None], key: Sequence[str | None]) -> LabelScore:
    """Count wrong accepted mappings and positive-label abstentions separately."""
    pairs = list(zip(answers, key, strict=True))
    positives = sum(expected is not None for _, expected in pairs)
    return LabelScore(
        accuracy=sum(answer == expected and expected is not None for answer, expected in pairs)
        / max(positives, 1),
        false_mappings=sum(answer is not None and answer != expected for answer, expected in pairs),
        abstentions=sum(answer is None and expected is not None for answer, expected in pairs),
    )


class SpanScore(BaseModel):
    """Exact matches are scoped by capture and claim kind."""

    model_config = ConfigDict(frozen=True)
    precision: float
    recall: float


SpanKey = tuple[str, str, int, int]


def score_spans(accepted: set[SpanKey], key: set[SpanKey]) -> SpanScore:
    """Compute micro precision and recall; empty denominators score zero."""
    matches = len(accepted & key)
    return SpanScore(
        precision=matches / len(accepted) if accepted else 0.0,
        recall=matches / len(key) if key else 0.0,
    )


Passage = tuple[str, int, str]


def inputs() -> tuple[list[dict[str, Any]], list[LabelSample], list[Passage], set[SpanKey]]:
    """Read hash-verified references; build label evidence as cell_labels does, without a
    database, and cut each keyed region out of its normalised source."""
    keys = yaml.safe_load(Path("config/sourcing/vendor_surface/label_key.yaml").read_text())
    regions = yaml.safe_load(Path("config/sourcing/vendor_surface/span_key.yaml").read_text())
    captures = {r["capture"] for r in regions}
    index = []
    for name in ("kinds-index.json", "snapshots-index.json"):
        index += json.loads((Path("docs/research/vendor-surface") / name).read_text())
    parents = {
        "section-insights": "company-page",
        "company-compare": "company-compare",
        "benchmarking-benchmarking-financial": "company-benchmarking",
        "benchmarking-benchmarking-business": "company-benchmarking",
    }
    cells: dict[tuple[str, str], list[tuple[str, str | None, bool]]] = {}
    texts = {}
    for row in index:
        surfaces = {
            r["surface"]
            for r in keys
            if r["site"] == row["site"] and parents[r["surface"]] == row["id"]
        }
        if not surfaces and row["sha256"] not in captures:
            continue
        raw = Path(row["path"]).read_bytes()
        if hashlib.sha256(raw).hexdigest() != row["sha256"]:
            raise ValueError("reference body hash mismatch")
        site = Site.SCREENER if row["site"] == "screener" else Site.TIJORI
        if row["sha256"] in captures:
            texts[row["sha256"]] = read_text(site, row["id"], raw, row["url"]).text
        # These readers use only basis; the inert clock is never persisted.
        context = ParseContext(
            ids=None,
            basis=Basis(row["basis"])
            if row.get("basis") in {"standalone", "consolidated"}
            else None,
            url=row["url"],
            retrieved_at=datetime.min.replace(tzinfo=UTC),
            body_sha256=row["sha256"],
            capture_id=row["sha256"],
        )
        body = Body(raw=raw)
        for surface in surfaces:
            cells.setdefault((row["site"], surface), []).extend(
                (c.row_label, c.unit, c.expected_numeric)
                for c in PARSERS[site, surface].parse(body, context)
            )
    found = {
        (site, surface, sample.label): sample
        for (site, surface), group in cells.items()
        for sample in label_samples(group)
    }
    samples = [found[r["site"], r["surface"], r["label"]] for r in keys]
    passages, expected = [], set()
    for region in regions:
        offset, end = region["region"]
        passage = texts[region["capture"]][offset:end]
        accepted, rejected = validate_spans(
            passage,
            json.dumps(
                [
                    s | {"start": s["start"] - offset, "end": s["end"] - offset}
                    for s in region["spans"]
                ]
            ),
        )
        if rejected or len(accepted) != len(region["spans"]):
            raise ValueError("invalid span key")
        passages.append((region["capture"], offset, passage))
        expected |= {(region["capture"], s["kind"], s["start"], s["end"]) for s in region["spans"]}
    return keys, samples, passages, expected


def evaluate(candidates: Sequence[tuple[LabelModel, Decimal, Decimal]]) -> str:
    """Score accepted answers and aggregate token costs in currency per million tokens."""
    keys, samples, passages, expected = inputs()
    dictionary = load_dictionary(Path("config/normalisation/dictionary"), "v3")
    fields = {r.canonical_id: r.value_kind for r in dictionary.rows}
    key = [r["field"] for r in keys]
    baseline = score_labels([None] * len(key), key)
    rows = [("always-unmapped", baseline, score_spans(set(), expected), Decimal(0))]
    for model, input_price, output_price in candidates:
        answers, accepted, cost = [], set[SpanKey](), Decimal(0)
        for sample in samples:
            reply = model.complete(
                LABEL_SYSTEM, json.dumps(sample.model_dump(mode="json") | {"fields": dict(fields)})
            )
            answers.append(accept(sample, reply.text, fields)[0])
            cost += reply.input_tokens * input_price + reply.output_tokens * output_price
        for capture, offset, text in passages:
            reply = model.complete(SPAN_SYSTEM, text)
            spans, _ = validate_spans(text, reply.text)
            accepted.update((capture, s.kind, s.start + offset, s.end + offset) for s in spans)
            cost += reply.input_tokens * input_price + reply.output_tokens * output_price
        labels = score_labels(answers, key)
        spans_score = score_spans(accepted, expected)
        rows.append((model.model_id, labels, spans_score, cost / Decimal(1_000_000)))
    table = [
        "# Vendor surface bake-off",
        "",
        "Key: model-drafted; model-checked by GPT-6.1 Sol (high), 2026-10-29; not human-checked. "
        "Dictionary: v3.",
        "Costs use configured input/output prices per million tokens.",
        "",
        "| Candidate | Positive accuracy | False mappings | Abstentions | "
        "Span precision | Span recall | Cost |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    if not candidates:
        table.insert(4, "Candidate rows are pending the owner's candidate list and API key.")
    for name, labels, spans_score, cost in rows:
        name = name.replace("|", "\\|").replace("\n", " ")
        table.append(
            f"| {name} | {labels.accuracy:.3f} | {labels.false_mappings} | "
            f"{labels.abstentions} | {spans_score.precision:.3f} | "
            f"{spans_score.recall:.3f} | {cost:.6f} |"
        )
    return "\n".join(table) + "\n"


def write_report(table: str, directory: Path) -> Path:
    """Write only the dated research report; runtime model selection stays separate."""
    path = directory / f"bakeoff-{datetime.now(UTC).date()}.md"
    path.write_text(table)
    return path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--candidates",
        type=Path,
        required=True,
        help="YAML list: model_id, base_url, key_file, input_price, output_price (per million)",
    )
    config = yaml.safe_load(parser.parse_args().candidates.read_text())
    secrets = Path(os.environ.get("EQOS_SECRETS_DIR", "~/.secrets")).expanduser()
    candidates = [
        (
            ChatCompletionsModel(
                r["model_id"],
                r["base_url"],
                SecretStr((secrets / r["key_file"]).read_text().strip()),
            ),
            Decimal(str(r["input_price"])),
            Decimal(str(r["output_price"])),
        )
        for r in config
    ]
    write_report(evaluate(candidates), Path("docs/research/vendor-surface"))
