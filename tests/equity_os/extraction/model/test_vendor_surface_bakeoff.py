"""Bake-off scores use positive labels and exact, capture-scoped spans."""

import runpy


def test_positive_accuracy_false_mappings_and_baseline():
    bakeoff = runpy.run_path("scripts/vendor_surface_bakeoff.py")
    score = bakeoff["score_labels"](["a", "wrong", None, "a", None], ["a", "b", "c", None, None])
    assert (score.accuracy, score.false_mappings, score.abstentions) == (1 / 3, 2, 1)
    baseline = bakeoff["score_labels"]([None] * 5, ["a", "b", "c", None, None])
    assert (baseline.accuracy, baseline.false_mappings, baseline.abstentions) == (0, 0, 3)


def test_spans_require_capture_kind_and_exact_offsets():
    score = runpy.run_path("scripts/vendor_surface_bakeoff.py")["score_spans"]
    key = {("a", "NAME", 0, 4), ("a", "CLAIM", 5, 10)}
    accepted = {("a", "NAME", 0, 4), ("b", "CLAIM", 5, 10), ("a", "NAME", 5, 10)}
    result = score(accepted, key)
    assert (result.precision, result.recall) == (1 / 3, 0.5)
    assert score(set(), set()).model_dump() == {"precision": 0, "recall": 0}


def test_two_fake_models_write_expected_table_without_selecting_runtime_model(tmp_path):
    import json
    from decimal import Decimal
    from pathlib import Path

    from equity_os.extraction.model.vendor_surface_model import ModelReply

    class Fake:
        def __init__(self, model_id):
            self.model_id = model_id

        def complete(self, system, user):
            if user.startswith("{"):
                sample = json.loads(user)
                assert "why" not in sample and "field" not in sample
                answer = {"label": sample["label"], "field": None}
                if self.model_id == "greedy":
                    answer["field"] = "opm_pct"
            else:
                end = 4 if user.startswith("Apar,") else 17 if user.startswith("HDFC Bank") else 27
                answer = [{"kind": "NAME", "start": 0, "end": end}]
                if self.model_id == "greedy":
                    answer += [
                        {"kind": "CLAIM", "start": 0, "end": 1},
                        {"kind": "NAME", "start": 0, "end": len(user) + 1},
                    ]
            return ModelReply(text=json.dumps(answer), input_tokens=10, output_tokens=2)

    bakeoff = runpy.run_path("scripts/vendor_surface_bakeoff.py")
    runtime = Path("config/sourcing/vendor_surface/model.yaml")
    before = runtime.read_bytes()
    table = bakeoff["evaluate"](
        [(Fake(name), Decimal(1), Decimal(2)) for name in ("safe", "greedy")]
    )
    assert "| always-unmapped | 0.000 | 0 | 4 | 0.000 | 0.000 | 0.000000 |" in table
    assert "| safe | 0.000 | 0 | 4 | 1.000 | 0.375 | 0.000266 |" in table
    assert "| greedy | 0.250 | 8 | 0 | 0.500 | 0.375 | 0.000266 |" in table
    report = bakeoff["write_report"](table, tmp_path)
    assert report.name.startswith("bakeoff-") and report.read_text() == table
    assert runtime.read_bytes() == before


def test_oracle_model_scores_full_accuracy_on_the_keys():
    import json
    from decimal import Decimal

    import yaml

    from equity_os.extraction.model.vendor_surface_model import ModelReply

    bakeoff = runpy.run_path("scripts/vendor_surface_bakeoff.py")
    fields = {
        r["label"]: r["field"]
        for r in yaml.safe_load(open("config/sourcing/vendor_surface/label_key.yaml"))
    }
    _, _, passages, expected = bakeoff["inputs"]()
    spans = {
        text: [
            {"kind": kind, "start": start - offset, "end": end - offset}
            for key, kind, start, end in expected
            if key == capture
        ]
        for capture, offset, text in passages
    }

    class Oracle:
        model_id = "oracle"

        def complete(self, system, user):
            if user.startswith("{"):
                label = json.loads(user)["label"]
                answer = {"label": label, "field": fields[label]}
            else:
                answer = spans[user]
            return ModelReply(text=json.dumps(answer), input_tokens=0, output_tokens=0)

    table = bakeoff["evaluate"]([(Oracle(), Decimal(0), Decimal(0))])
    assert "| oracle | 1.000 | 0 | 0 | 1.000 | 1.000 | 0.000000 |" in table


def test_span_prompt_carries_the_annotation_policy():
    from decimal import Decimal

    from equity_os.extraction.model.vendor_surface_model import ModelReply

    seen = set()

    class Recorder:
        model_id = "recorder"

        def complete(self, system, user):
            if not user.startswith("{"):
                seen.add(system)
            return ModelReply(text="[]", input_tokens=0, output_tokens=0)

    runpy.run_path("scripts/vendor_surface_bakeoff.py")["evaluate"](
        [(Recorder(), Decimal(0), Decimal(0))]
    )
    (system,) = seen
    assert "NAME: every organisation or person name" in system
    assert "CLAIM: each whole sentence asserting a fact about the company" in system
