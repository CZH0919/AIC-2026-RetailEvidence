"""Independent weekly benchmark; never fabricate dates or consume full-series normalization."""

import argparse
import csv
import hashlib
import io
import json
import urllib.request
import zipfile
from pathlib import Path

import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor

from app.sales_mining import score


def feature(values, origin):
    past = values[:origin]
    scale = max(float(past[-4:].mean()), 0.1)
    return [
        float(past[-1]) / scale,
        float(past[-2]) / scale,
        float(past[-8:].mean()) / scale,
        float(past[-4:].std()) / scale,
        float(np.count_nonzero(past[-8:])) / 8,
    ], scale


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--data-dir", default="storage/datasets/public/sales_weekly")
    args = parser.parse_args()
    root = Path(args.data_dir)
    root.mkdir(parents=True, exist_ok=True)
    archive = root / "source.zip"
    url = (
        "https://archive.ics.uci.edu/static/public/396/sales%2Btransactions%2Bdataset%2Bweekly.zip"
    )
    if not archive.exists():
        with urllib.request.urlopen(url, timeout=60) as response:
            archive.write_bytes(response.read())
    with zipfile.ZipFile(archive) as zipped:
        name = next(n for n in zipped.namelist() if n.endswith(".csv"))
        raw = zipped.read(name)
    (root / "source.csv").write_bytes(raw)
    series = {
        r["Product_Code"]: np.array([float(r[f"W{i}"]) for i in range(52)])
        for r in csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    }
    manifest = {
        "source_url": url,
        "doi": "10.24432/C5XS4Q",
        "license": "CC BY 4.0",
        "sha256": hashlib.sha256(raw).hexdigest(),
        "products": len(series),
        "notice": "Weekly quantities W0..W51 only. No known calendar dates or amounts. Normalised columns excluded.",
    }
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    records = []
    # Windows are frozen before this independent dataset is run.
    for origin in range(36, 52):
        x, y, test_x, scales = [], [], [], []
        for values in series.values():
            for t in range(8, origin):
                f, scale = feature(values, t)
                x.append(f)
                y.append(values[t] / scale)
            f, scale = feature(values, origin)
            test_x.append(f)
            scales.append(scale)
        model = HistGradientBoostingRegressor(
            max_iter=80,
            max_leaf_nodes=15,
            min_samples_leaf=15,
            l2_regularization=2,
            random_state=42,
            early_stopping=False,
        ).fit(x, y)
        predictions = np.maximum(0, model.predict(test_x)) * np.array(scales)
        for j, (key, values) in enumerate(series.items()):
            records.append(
                {
                    "item_id": key,
                    "origin_week": origin,
                    "training_end_week": origin - 1,
                    "split": "validation" if origin < 44 else "test",
                    "actual": float(values[origin]),
                    "gradient_boosting": float(predictions[j]),
                    "last_week": float(values[origin - 1]),
                    "four_week_mean": float(values[origin - 4 : origin].mean()),
                }
            )
    metrics = []
    for split in ["validation", "test"]:
        rows = [r for r in records if r["split"] == split]
        for method in ["gradient_boosting", "last_week", "four_week_mean"]:
            metrics.append(
                {
                    "split": split,
                    "method": method,
                    **score([r["actual"] for r in rows], [r[method] for r in rows]),
                }
            )
    chosen = min([m for m in metrics if m["split"] == "validation"], key=lambda m: m["mae"])[
        "method"
    ]
    output = {
        "source": manifest,
        "metrics": metrics,
        "selected_method": chosen,
        "records": records,
        "limitations": [
            "Weekly benchmark is not the daily production model.",
            "Unlabelled store/product context; cannot prove benefits for small shops.",
        ],
    }
    Path(args.output).write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(json.dumps({"metrics": metrics, "selected_method": chosen}))


if __name__ == "__main__":
    main()
