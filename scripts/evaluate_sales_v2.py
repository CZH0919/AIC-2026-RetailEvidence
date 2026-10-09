"""Development experiment; output paths supplied explicitly, no production DB writes."""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.sales_mining import anomaly_series, calendar, forecast_series  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source")
    parser.add_argument("output")
    args = parser.parse_args()
    sums = defaultdict(float)
    # Public preparation preserves source columns as stable c0..c7 keys.
    rows = pq.read_table(args.source, columns=["c4", "c1", "c3", "c0"]).rename_columns(
        ["InvoiceDate", "StockCode", "Quantity", "InvoiceNo"]
    )
    for row in rows.to_pylist():
        day = str(row["InvoiceDate"])[:10]
        if "2010-12-01" <= day <= "2011-10-31" and not str(row["InvoiceNo"]).upper().startswith(
            "C"
        ):
            try:
                q = float(row["Quantity"])
            except (ValueError, TypeError):
                continue
            if q > 0:
                sums[day, str(row["StockCode"])] += q
    totals = defaultdict(float)
    for (_, key), quantity in sums.items():
        totals[key] += quantity
    keys = sorted(totals, key=lambda k: (-totals[k], k))[:300]
    dates = calendar("2010-12-01", "2011-10-31")
    series = {k: [sums.get((d.isoformat(), k), 0) for d in dates] for k in keys}
    forecast = forecast_series(series, dates)
    anomaly = anomaly_series(series, dates, "2011-10")
    Path(args.output).write_text(
        json.dumps(
            {
                "forecast": forecast,
                "anomaly": anomaly,
                "limitations": [
                    "Online Retail is online gift retail with wholesale orders; not a convenience store.",
                    "Observed sales do not identify stockouts or unmet demand.",
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "metrics": forecast["metrics"],
                "method": forecast.get("selected_method"),
                "published_items": forecast.get("published_items"),
                "anomaly_flags": anomaly.get("flagged_samples"),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
