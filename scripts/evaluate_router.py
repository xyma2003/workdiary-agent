#!/usr/bin/env python3
"""Run the labeled template-routing evaluation against a configured provider."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import sys
from time import perf_counter

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from workdiary_agent.router.agent import TemplateRouterAgent
from workdiary_agent.utils import validate_llm_configuration


DEFAULT_CASES = PROJECT_ROOT / "evals" / "template_routing.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--threshold", type=float, default=0.8)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    load_dotenv(PROJECT_ROOT / ".env", override=False)
    provider = validate_llm_configuration()
    cases = json.loads(args.cases.read_text(encoding="utf-8"))
    if args.limit is not None:
        cases = cases[: args.limit]
    if not cases:
        raise ValueError("No evaluation cases selected")

    router = TemplateRouterAgent()
    results = []
    confusion: dict[str, Counter] = defaultdict(Counter)
    started = perf_counter()

    for case in cases:
        case_started = perf_counter()
        predicted = router.classify(case["input"])
        latency = perf_counter() - case_started
        correct = predicted == case["expected"]
        confusion[case["expected"]][predicted] += 1
        results.append({**case, "predicted": predicted, "correct": correct, "latency_seconds": round(latency, 3)})
        print(f"{'PASS' if correct else 'FAIL'} {case['id']}: {case['expected']} -> {predicted} ({latency:.2f}s)")

    correct_count = sum(result["correct"] for result in results)
    accuracy = correct_count / len(results)
    summary = {
        "provider": provider,
        "cases": len(results),
        "correct": correct_count,
        "accuracy": round(accuracy, 4),
        "elapsed_seconds": round(perf_counter() - started, 3),
        "confusion": {expected: dict(counts) for expected, counts in confusion.items()},
        "results": results,
    }
    print(json.dumps({key: value for key, value in summary.items() if key != "results"}, ensure_ascii=False, indent=2))

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if accuracy >= args.threshold else 1


if __name__ == "__main__":
    raise SystemExit(main())
