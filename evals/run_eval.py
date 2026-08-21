"""Run all 8 eval cases against POST /enrich and print the score."""
import json
import sys
import time
from pathlib import Path

try:
    import requests
except ImportError:
    print("pip install requests  — needed for eval script", file=sys.stderr)
    sys.exit(1)

CASES_PATH = Path(__file__).parent / "cases.json"
BASE_URL = "http://localhost:8000"


def run_eval():
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    passed = 0
    failed = []
    total_duration = 0

    for case in cases:
        case_id = case["id"]
        expected = case["expected_category"]
        inp = case["input"]

        start = time.monotonic()
        try:
            res = requests.post(f"{BASE_URL}/enrich", json=inp, timeout=60)
        except requests.RequestException as exc:
            duration = round((time.monotonic() - start) * 1000)
            failed.append({"id": case_id, "expected": expected, "got": f"HTTP ERROR: {exc}", "duration_ms": duration})
            print(f"  [{case_id}] FAIL — {exc}")
            continue
        duration = round((time.monotonic() - start) * 1000)
        total_duration += duration

        if res.status_code != 200:
            failed.append({"id": case_id, "expected": expected, "got": f"HTTP {res.status_code}: {res.text[:100]}", "duration_ms": duration})
            print(f"  [{case_id}] FAIL — HTTP {res.status_code}")
            continue

        body = res.json()
        got_category = body.get("category", "")
        confidence = body.get("confidence", 0)

        if got_category == expected:
            passed += 1
            print(f"  [{case_id}] PASS — {got_category} (confidence: {confidence}, {duration}ms)")
        else:
            failed.append({"id": case_id, "expected": expected, "got": got_category, "confidence": confidence, "duration_ms": duration})
            print(f"  [{case_id}] FAIL — expected {expected}, got {got_category} (confidence: {confidence})")

    score = f"{passed}/{len(cases)}"
    avg_ms = round(total_duration / len(cases)) if cases else 0
    print(f"\nScore: {score} ({passed/len(cases)*100:.0f}%)")
    print(f"Average response time: {avg_ms}ms")

    if failed:
        print(f"\nFailed cases ({len(failed)}):")
        for f in failed:
            print(f"  [{f['id']}] expected={f['expected']}, got={f['got']}")

    return passed, len(cases), failed


if __name__ == "__main__":
    passed, total, failed = run_eval()
    sys.exit(0 if passed == total else 1)
