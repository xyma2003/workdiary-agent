"""Offline validation for labeled evaluation assets."""

from collections import Counter
import json
from pathlib import Path


def test_template_routing_dataset_is_balanced_and_well_formed():
    path = Path(__file__).resolve().parent.parent / "evals" / "template_routing.json"
    cases = json.loads(path.read_text(encoding="utf-8"))

    assert len(cases) >= 30
    assert len({case["id"] for case in cases}) == len(cases)
    assert all(case["input"].strip() for case in cases)
    counts = Counter(case["expected"] for case in cases)
    assert counts == {"技术型": 10, "业务型": 10, "混合型": 10}
