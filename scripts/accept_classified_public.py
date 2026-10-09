"""Real XLSX reconciliation and fixed-window evaluation in an isolated deployment."""

import argparse
import csv
import hashlib
import json
import time
import urllib.request
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import openpyxl

parser = argparse.ArgumentParser()
parser.add_argument("--base", required=True)
parser.add_argument("--storage", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
assert args.base == "http://127.0.0.1:18081", "This evidence script refuses production ports"
args.output.mkdir(parents=True, exist_ok=True)
project = "e1711757-601a-4e9a-a05f-037d7e6909e6"
version = "48b9d571-3d7f-43d4-b4f0-19ea931123be"
base = f"/projects/{project}"


def request(path, data=None):
    req = urllib.request.Request(
        args.base + "/api" + path,
        data=json.dumps(data).encode() if data is not None else None,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=120) as response:
        return json.load(response)


def save(name, value):
    (args.output / name).write_text(
        json.dumps(value, ensure_ascii=False, indent=2), encoding="utf8"
    )


source = request(base + f"/sales/sources/{version}")
# Acceptance policy, explicitly a public-data demonstration assumption, not merchant accounting.
special = {
    "POST": "shipping_service",
    "DOT": "shipping_service",
    "C2": "shipping_service",
    "M": "manual_adjustment",
    "m": "manual_adjustment",
    "D": "manual_adjustment",
    "BANK CHARGES": "other",
    "AMAZONFEE": "shipping_service",
    "CRUK": "other",
    "B": "manual_adjustment",
    "S": "other",
    **{f"gift_0001_{n}": "other" for n in [10, 20, 30, 40, 50]},
}
policy = {
    "version_id": version,
    "mapping_revision": source["mapping_revision"],
    "default_kind": "physical_product",
    "default_amount_treatment": "include",
    "confirmed": True,
    "rules": [
        {
            "match_by": "item_id",
            "value": key,
            "kind": kind,
            "amount_treatment": "exclude",
            "basis": "公开数据验收假定：非实物分项排除，非真实商户收入结论",
        }
        for key, kind in special.items()
    ],
}
params = {
    "sources": [{"version_id": version, "mapping_revision": source["mapping_revision"]}],
    "classifications": [policy],
    "month": "2011-10",
    "merge_mode": "append",
    "duplicates": "keep",
    "complete_coverage": True,
    "coverage_start": source["start"],
    "coverage_end": source["end"],
    "closed_dates": [],
}
save(
    "policy.json",
    {
        "parameters": params,
        "limitation": (
            "Default physical, complete coverage, and excluded financial items are "
            "acceptance assumptions; users must choose their own semantics."
        ),
    },
)
workbook = args.storage / "datasets/public/online_retail/source.xlsx"
source_sha = hashlib.sha256(workbook.read_bytes()).hexdigest()
wb = openpyxl.load_workbook(workbook, read_only=True, data_only=True)
ws = wb.worksheets[0]
rows = []
states = {}
conflicts = set()
input_rows = 0
for row in ws.iter_rows(min_row=2, values_only=True):
    invoice, item, name, qty, stamp, price, customer, country = row[:8]
    input_rows += 1
    if not isinstance(stamp, datetime):
        continue
    order = str(invoice).strip() if invoice is not None else None
    item = str(item).strip() if item is not None else None
    when = stamp.isoformat()
    customer = str(customer) if customer is not None else None
    if when[:10] <= "2011-10-31" and order:
        state = states.setdefault(order, [set(), set()])
        state[0].add(when)
        if customer:
            state[1].add(customer)
        if any(len(a) > 1 for a in state):
            conflicts.add(order)
    if when.startswith("2011-10"):
        rows.append((order, item, qty, price, when, name))
wb.close()
quantity = amount = all_quantity = all_amount = Decimal(0)
conflict_quantity = conflict_amount = Decimal(0)
breakdown = defaultdict(lambda: [Decimal(0), Decimal(0), 0])
derived_daily = defaultdict(lambda: [Decimal(0), Decimal(0)])
for order, item, q, p, when, name in rows:
    if not item or (order or "").upper().startswith("C"):
        continue
    try:
        q, p = Decimal(str(q)), Decimal(str(p))
    except Exception:
        continue
    if not q.is_finite() or q <= 0:
        continue
    value = q * p if p.is_finite() and p >= 0 else None
    if order in conflicts:
        conflict_quantity += q
        if value is not None:
            conflict_amount += value
        continue
    all_quantity += q
    if value is not None:
        all_amount += value
    kind = special.get(item, "physical_product")
    b = breakdown[kind]
    b[0] += q
    b[2] += 1
    if value is not None:
        b[1] += value
    if kind == "physical_product":
        quantity += q
        if value is not None:
            amount += value
    derived_daily[when[:10], item, name or item][0] += q
    if value is not None:
        derived_daily[when[:10], item, name or item][1] += value
independent = {
    "source_sha256": source_sha,
    "xlsx_rows": input_rows,
    "legacy_all_record_quantity": float(all_quantity),
    "legacy_all_record_amount": float(all_amount),
    "physical_quantity": float(quantity),
    "selected_amount": float(amount),
    "excluded_conflict_quantity": float(conflict_quantity),
    "excluded_conflict_amount": float(conflict_amount),
    "breakdown": {
        k: {"quantity": float(v[0]), "amount": float(v[1]), "rows": v[2]}
        for k, v in breakdown.items()
    },
}
save("independent_xlsx.json", independent)
print(
    json.dumps({"phase": "independent_xlsx", "values": independent}, ensure_ascii=False), flush=True
)
with (args.output / "derived_daily.csv").open("w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f)
    w.writerow(["date", "item_id", "name", "quantity", "amount"])
    for (day, item, name), (q, a) in sorted(derived_daily.items()):
        w.writerow([day, item, name, str(q), str(a)])
monthly = defaultdict(lambda: [Decimal(0), Decimal(0)])
for (day, item, name), (q, a) in derived_daily.items():
    monthly[item, name][0] += q
    monthly[item, name][1] += a
with (args.output / "derived_monthly.csv").open("w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f)
    w.writerow(["item_id", "name", "quantity", "amount"])
    for (item, name), (q, a) in sorted(monthly.items()):
        w.writerow([item, name, str(q), str(a)])
runs = []
for checking in [True, False]:
    started = time.monotonic()
    run = request(
        base + "/sales/runs", {**params, "check_only": checking, "idempotency_key": str(uuid4())}
    )
    while run["status"] in ["queued", "running", "cancelling"]:
        if time.monotonic() - started > 1250:
            raise TimeoutError("Isolated public run exceeded budget")
        time.sleep(2)
        run = request(base + "/runs/" + run["id"])
    save("check_run.json" if checking else "monthly_run.json", run)
    assert run["result"], run
    report = run["result"]
    assert report["summary"]["quantity"] == float(quantity), (report["summary"], independent)
    assert abs(report["summary"]["amount"] - float(amount)) < 0.01, (report["summary"], independent)
    assert not special.keys() & {p["id"] for p in report["products"]}
    assert (
        abs(
            sum(
                x["amount"]
                for x in report["classification"]["financial_breakdown"]
                if x["month"] == "2011-10"
            )
            - float(all_amount)
        )
        < 0.01
    )
    assert len(report["actions"]) <= 3
    print(
        json.dumps(
            {
                "phase": "check" if checking else "full",
                "run_id": run["id"],
                "seconds": round(time.monotonic() - started, 2),
                "summary": report["summary"],
                "forecast": report["forecast"],
                "anomaly": report["anomaly"],
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    runs.append(run)
run = runs[-1]
for file in [
    "sales_report.json",
    "sales_products.csv",
    "sales_row_audit.csv",
    "sales_classification.csv",
    "sales_business_records.csv",
    "sales_backtests.csv",
    "manifest.json",
]:
    with urllib.request.urlopen(
        args.base + "/api" + base + f"/sales/runs/{run['id']}/files/{file}", timeout=120
    ) as resp:
        (args.output / file).write_bytes(resp.read())
for all_attention, name in [(False, "monthly_summary.html"), (True, "monthly_all_attention.html")]:
    with urllib.request.urlopen(
        args.base
        + "/api"
        + base
        + f"/sales/runs/{run['id']}/report?all_attention={str(all_attention).lower()}",
        timeout=120,
    ) as resp:
        (args.output / name).write_bytes(resp.read())
answer = request(
    base + f"/sales/runs/{run['id']}/ask",
    {"question": "请解释本月销量，并告诉我下次进货前先看什么。"},
)
save("ai_answer.json", answer)
save(
    "acceptance.json",
    {
        "status": "PASS",
        "run_id": run["id"],
        "project_id": project,
        "version_id": version,
        "independent": independent,
        "summary": run["result"]["summary"],
        "ai_used": answer["ai_used"],
        "peak_rss_bytes": run["peak_rss_bytes"],
        "limitations": [
            "Public data acceptance assumptions are not merchant confirmation.",
            "No labels for anomaly accuracy.",
            "Arithmetic/model/artifact API only; browser and legacy tasks are separate.",
        ],
    },
)
print("CLASSIFIED_PUBLIC_PASS", run["id"], "ai_used", answer["ai_used"], flush=True)
