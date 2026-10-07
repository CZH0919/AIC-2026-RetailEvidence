"""Reproducible source profiling and faithful Groceries conversion (CPU only)."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
import warnings
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.data_schemas import ParseOptions  # noqa: E402
from app.import_formats import inspect_xlsx  # noqa: E402
from app.import_worker import constrain, parse  # noqa: E402


def digest(path):
    sha = hashlib.sha256()
    with path.open("rb") as f:
        for part in iter(lambda: f.read(1024**2), b""):
            sha.update(part)
    return sha.hexdigest()


def groceries(folder):
    import rdata

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        obj = rdata.read_rda(folder / "Groceries.rda")["Groceries"]
    matrix = obj.data
    assert list(matrix.Dim) == [169, 9835]
    labels = obj.itemInfo["labels"].tolist()
    assert len(labels) == len(set(labels)) == 169
    assert len(matrix.p) == 9836 and matrix.p[0] == 0 and matrix.p[-1] == len(matrix.i)
    output = folder / "groceries.csv"
    partial = output.with_suffix(".csv.part")
    count, empty, repeated = 0, 0, 0
    with partial.open("w", encoding="utf-8", newline="") as out:
        writer = csv.writer(out)
        writer.writerow(["basket_id", "item_id"])
        for basket in range(9835):
            indices = matrix.i[matrix.p[basket] : matrix.p[basket + 1]]
            assert all(0 <= i < 169 for i in indices)
            empty += int(len(indices) == 0)
            repeated += len(indices) - len(set(indices.tolist()))
            for index in indices:
                writer.writerow([str(basket + 1), labels[index]])
                count += 1
    if output.exists() and digest(output) != digest(partial):
        partial.unlink()
        raise RuntimeError("Existing Groceries conversion differs; preserve it and investigate")
    partial.replace(output)
    return {
        "rows": count,
        "baskets": 9835,
        "items": 169,
        "empty_baskets": empty,
        "duplicate_item_occurrences": repeated,
        "columns": ["basket_id", "item_id"],
        "boundary": "Original sparse matrix column index + 1; no fabricated customer/time/money",
        "label_source": "itemInfo.labels indexed by original ngCMatrix.i",
        "csv_sha256": digest(output),
        "package_license": "GPL-3",
        "data_notice": (
            "Groceries.Rd requests citation of Hahsler, Hornik, Reutterer (2006); "
            "no separate data license specified"
        ),
    }


def retail(folder):
    import pyarrow.parquet as pq

    source = folder / "source.xlsx"
    sheets = inspect_xlsx(source)["sheets"]
    options = ParseOptions(sheets=sheets).model_dump()
    output = folder / "raw.parquet"
    preview = parse(source, output.with_suffix(".parquet.part"), options)
    output.with_suffix(".parquet.part").replace(output)
    names = {c["name"]: c["key"] for c in preview["columns"]}
    invoice = names.get("InvoiceNo", names.get("Invoice"))
    time = names["InvoiceDate"]
    counts = Counter()
    minimum, maximum = None, None
    customers, invoices = set(), set()
    customer = names.get("CustomerID", names.get("Customer ID"))
    sheet_counts = Counter()
    for batch in pq.ParquetFile(output).iter_batches(batch_size=10000):
        raw = batch.to_pydict()
        for i, identity in enumerate(raw["source_row_id"]):
            sheet_counts[identity.rsplit(":", 1)[0]] += 1
            order = raw[invoice][i]
            if order:
                invoices.add(order)
                counts["cancellation_rows"] += int(order.upper().startswith("C"))
            person = raw[customer][i]
            if person:
                customers.add(person)
            value = raw[time][i]
            if value:
                minimum = min(minimum, value) if minimum else value
                maximum = max(maximum, value) if maximum else value
            for label, column in [
                ("nonpositive_quantity", "Quantity"),
                ("nonpositive_unit_price", "UnitPrice" if "UnitPrice" in names else "Price"),
            ]:
                value = raw[names[column]][i]
                if value is not None:
                    counts[label] += int(float(value) <= 0)
    return {
        "rows": preview["row_count"],
        "columns": [c["name"] for c in preview["columns"]],
        "missing": {c["name"]: c["missing"] for c in preview["columns"]},
        "sheets": dict(sheet_counts),
        "date_min": minimum,
        "date_max": maximum,
        "unique_order_ids": len(invoices),
        "unique_customer_ids": len(customers),
        **counts,
        "currency": "GBP",
        "cancellation_meaning": "Invoice starts with C",
        "parquet_sha256": digest(output),
        "options": options,
        "overlap_notice": (
            "Online Retail is within Retail II's 2010-2011 period; "
            "never combine as independent samples"
        ),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default="storage/datasets/public")
    args = parser.parse_args()
    root = Path(args.root)
    if not root.is_absolute():
        root = ROOT / root
    constrain()
    for key in ["groceries", "online_retail", "online_retail_ii"]:
        folder = root / key
        manifest_path = folder / "dataset_manifest.json"
        manifest = json.loads(manifest_path.read_text())
        for asset in manifest["assets"]:
            assert digest(folder / asset["file"]) == asset["sha256"]
        profile = groceries(folder) if key == "groceries" else retail(folder)
        manifest.update(
            profile=profile,
            profile_status="complete",
            profiling_script_sha256=digest(Path(__file__)),
        )
        if key == "groceries":
            manifest["source"]["license"] = (
                "arules package GPL-3; Groceries requires citation; "
                "separate data license not specified"
            )
        temp = manifest_path.with_suffix(".json.part")
        temp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temp.replace(manifest_path)
        print(json.dumps({"dataset": key, **profile}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    for key in ["OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"]:
        os.environ[key] = "2"
    main()
