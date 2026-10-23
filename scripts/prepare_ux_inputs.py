"""Public UX fixtures with explicit classification assumptions."""

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

parser = argparse.ArgumentParser(description="Derive auditable public Online Retail UX fixtures.")
parser.add_argument("--source", type=Path, required=True)
parser.add_argument("--root", type=Path, required=True)
args = parser.parse_args()
src = args.source.resolve()
u = args.root.resolve()
if str(u).lower().startswith("c:"):
    raise ValueError("C drive output prohibited")
if (u / "inputs").exists():
    raise ValueError("Choose an independent empty output root; never replace frozen test inputs")
(u / "inputs").mkdir(parents=True)

d = pd.read_parquet(src).rename(
    columns={
        "c0": "InvoiceNo",
        "c1": "StockCode",
        "c2": "Description",
        "c3": "Quantity",
        "c4": "InvoiceDate",
        "c5": "UnitPrice",
        "c6": "CustomerID",
        "c7": "Country",
    }
)
q = pd.to_numeric(d.Quantity, errors="coerce")
price = pd.to_numeric(d.UnitPrice, errors="coerce")
dates = pd.to_datetime(d.InvoiceDate, errors="coerce")
mask = (
    q.gt(0)
    & price.ge(0)
    & dates.notna()
    & ~d.InvoiceNo.fillna("").str.startswith("C")
    & d.StockCode.notna()
    & d.Description.notna()
)
x = d.loc[mask].copy()
x["quantity"] = q[mask]
x["amount"] = q[mask] * price[mask]
x["date"] = dates[mask].dt.strftime("%Y-%m-%d")
x["month"] = dates[mask].dt.strftime("%Y-%m")
kinds = {
    "POST": "shipping_service",
    "DOT": "shipping_service",
    "M": "manual_adjustment",
    "D": "manual_adjustment",
    "C2": "shipping_service",
    "BANK CHARGES": "manual_adjustment",
    "S": "manual_adjustment",
    "CRUK": "other",
}
x["record_type"] = x.StockCode.map(kinds).fillna("physical_product")
paths = []
for month in ["2011-09", "2011-10"]:
    part = x[x.month.eq(month)]
    monthly = (
        part.groupby(["StockCode", "Description", "record_type"], dropna=False)[
            ["quantity", "amount"]
        ]
        .sum()
        .reset_index()
        .rename(columns={"StockCode": "item_id", "Description": "name"})
    )
    p = u / "inputs" / ("monthly_" + month + ".csv")
    monthly[["item_id", "name", "quantity", "amount", "record_type"]].to_csv(
        p, index=False, encoding="utf-8-sig"
    )
    paths.append(p)
raw = d[dates.between("2011-09-01", "2011-10-31 23:59:59")].head(5000)[
    [
        "InvoiceNo",
        "StockCode",
        "Description",
        "Quantity",
        "InvoiceDate",
        "UnitPrice",
        "CustomerID",
        "Country",
    ]
]
p = u / "inputs/public_detail_sample.xlsx"
with pd.ExcelWriter(p, engine="openpyxl") as w:
    raw.iloc[:2500].to_excel(w, index=False, sheet_name="销售明细A")
    raw.iloc[2500:].to_excel(w, index=False, sheet_name="销售明细B")
    pd.DataFrame({"说明": ["不是销售数据"], "备注": ["请选销售明细"]}).to_excel(
        w, index=False, sheet_name="填写说明"
    )
paths.append(p)
rows = (
    x[x.month.eq("2011-10") & x.record_type.eq("physical_product")]
    .groupby("StockCode")
    .quantity.sum()
    .nlargest(5)
    .index
)
daily = (
    x[x.StockCode.isin(rows) & x.date.between("2011-06-01", "2011-10-31")]
    .groupby(["date", "StockCode", "Description"])[["quantity", "amount"]]
    .sum()
    .reset_index()
    .rename(columns={"StockCode": "item_id", "Description": "name"})
)
p = u / "inputs/daily_public.csv"
daily[["date", "item_id", "name", "quantity", "amount"]].to_csv(
    p, index=False, encoding="utf-8-sig"
)
paths.append(p)
(u / "inputs/chinese_gbk.csv").write_bytes(
    "商品编号,商品名称,数量,金额\nA001,红茶,2,20\nA002,杯子,3,18\n".encode("gb18030")
)
paths.append(u / "inputs/chinese_gbk.csv")
(u / "inputs/missing_fields.csv").write_text(
    "item_id,name,quantity\nA001,红茶,2\nA002,杯子,3\n", encoding="utf-8-sig"
)
paths.append(u / "inputs/missing_fields.csv")
manifest = {
    "source": str(src),
    "source_sha256": hashlib.sha256(src.read_bytes()).hexdigest(),
    "original_xlsx_sha256": "43465a06f2ccf7c8b5bd2892bc7defb52f97487934fe93b16ae4c3936424676d",
    "derived": [
        {
            "file": str(p),
            "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
            "bytes": p.stat().st_size,
        }
        for p in paths
    ],
    "classification": "explicit public test assumptions, not merchant facts",
    "edge_samples": ["chinese_gbk.csv", "missing_fields.csv"],
}
(u / "inputs/manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
print(json.dumps(manifest, ensure_ascii=False))
