"""Compare frozen business fields without normalizing values or changing reports."""

import argparse
import csv
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

BUSINESS_FIELDS = (
    "month", "summary", "chart", "previous_chart", "products", "attention_ids",
    "highlights", "actions", "forecast", "anomaly", "quality", "notices",
)


def source_info(path: Path) -> dict:
    return {"path": str(path.resolve()), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def load_run(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict) or not isinstance(payload.get("result"), dict):
        raise ValueError(f"Expected a saved run JSON containing result: {path}")
    return payload["result"]


def load_csv(path: Path) -> dict:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        return {"headers": reader.fieldnames, "rows": list(reader)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--baseline-products", type=Path)
    parser.add_argument("--candidate-products", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if bool(args.baseline_products) != bool(args.candidate_products):
        parser.error("Provide both product CSV paths or neither.")
    receipt = {
        "executed_at": datetime.now(UTC).isoformat(),
        "status": "FAIL",
        "comparison": (
            "Fixed business-field allowlist; no value normalization. Run IDs, source IDs "
            "and application version outside these fields are not compared. CSV headers, "
            "values and row order are compared exactly after parsing."
        ),
        "inputs": {},
        "checks": [],
    }
    try:
        baseline, candidate = load_run(args.baseline), load_run(args.candidate)
        receipt["inputs"] = {
            "baseline": source_info(args.baseline), "candidate": source_info(args.candidate)
        }
        for field in BUSINESS_FIELDS:
            present = field in baseline and field in candidate
            equal = present and baseline[field] == candidate[field]
            check = {"field": field, "status": "PASS" if equal else "FAIL"}
            if not equal:
                check["reason"] = (
                    "Business value differs" if present else "Required business field is missing"
                )
            receipt["checks"].append(check)
        if args.baseline_products:
            receipt["inputs"].update({
                "baseline_products": source_info(args.baseline_products),
                "candidate_products": source_info(args.candidate_products),
            })
            equal = load_csv(args.baseline_products) == load_csv(args.candidate_products)
            receipt["checks"].append({
                "field": "parsed_products_csv", "status": "PASS" if equal else "FAIL"
            })
        passed = all(check["status"] == "PASS" for check in receipt["checks"])
        receipt["status"] = "PASS" if passed else "FAIL"
    except (OSError, ValueError, csv.Error) as exc:
        receipt["error"] = str(exc)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "status": receipt["status"], "checks": len(receipt["checks"]), "receipt": str(args.output)
    }, ensure_ascii=False))
    return 0 if receipt["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
