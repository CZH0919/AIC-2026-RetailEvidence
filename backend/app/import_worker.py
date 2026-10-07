"""Isolated import worker. Its job files are generated internally, never by browser input."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from .import_formats import DataIssue, inspect_xlsx, iter_csv, iter_xlsx
from .mapping import suggestions
from .settings import MAX_ROWS, PREVIEW_ROWS


def constrain():
    if hasattr(os, "sched_setaffinity"):
        os.sched_setaffinity(0, sorted(os.sched_getaffinity(0))[:2])
    if sys.platform == "linux":
        import resource

        resource.setrlimit(resource.RLIMIT_AS, (8 * 1024**3, 8 * 1024**3))


def parse(source: Path, output: Path, options: dict) -> dict:
    import pyarrow as pa
    import pyarrow.parquet as pq

    reader = iter_xlsx(source, options) if source.suffix == ".xlsx" else iter_csv(source, options)
    names = None
    writer = None
    batch, size = [], 0
    count, blanks = 0, 0
    columns, samples = [], []
    basket_index = None
    try:
        for kind, value in reader:
            if kind == "headers":
                original = value
                if options["shape"] == "basket_list":
                    if options["basket_column"] not in original:
                        raise DataIssue("请填写存放商品列表的表头名称。")
                    basket_index = original.index(options["basket_column"])
                    names = ["basket_id", "item_id"]
                else:
                    names = original
                columns = [
                    {"key": f"c{i}", "name": name, "missing": 0, "examples": []}
                    for i, name in enumerate(names)
                ]
                schema = pa.schema(
                    [("source_row_id", pa.string())] + [(c["key"], pa.string()) for c in columns]
                )
                writer = pq.ParquetWriter(output, schema, compression="zstd")
            elif kind == "blank":
                blanks += 1
            else:
                sheet, number, values = value
                source_id = f"{sheet}:{number}"
                if basket_index is not None:
                    raw = values[basket_index]
                    if not raw:
                        raise DataIssue(f"第 {number} 行购物篮为空，请明确处理后再导入。")
                    items = [v.strip() for v in raw.split(options["item_separator"])]
                    if any(not item for item in items):
                        raise DataIssue(f"第 {number} 行购物篮有空商品，请检查商品分隔符。")
                    records = [
                        (f"{source_id}:{i + 1}", [source_id, item]) for i, item in enumerate(items)
                    ]
                else:
                    records = [(source_id, values)]
                for identity, row in records:
                    count += 1
                    if count > MAX_ROWS:
                        raise DataIssue("展开后超过 150 万行，请缩小文件。", "row_limit", 413)
                    record = {"source_row_id": identity}
                    for col, cell in zip(columns, row, strict=True):
                        record[col["key"]] = cell
                        if cell is None:
                            col["missing"] += 1
                        elif len(col["examples"]) < 3 and cell[:120] not in col["examples"]:
                            col["examples"].append(cell[:120])
                        size += len(cell or "")
                    batch.append(record)
                    if len(samples) < PREVIEW_ROWS:
                        samples.append(
                            {k: v[:500] if isinstance(v, str) else v for k, v in record.items()}
                        )
                    if len(batch) >= 1000 or size >= 2 * 1024**2:
                        writer.write_table(pa.Table.from_pylist(batch, schema=schema))
                        batch, size = [], 0
        if not count:
            raise DataIssue("文件只有表头或空行，请选择含数据的文件。")
        if batch:
            writer.write_table(pa.Table.from_pylist(batch, schema=schema))
    finally:
        if hasattr(reader, "close"):
            reader.close()
        if writer:
            writer.close()
    return {
        "row_count": count,
        "blank_rows_skipped": blanks,
        "columns": columns,
        "rows": samples,
        "suggestions": suggestions(columns),
        "preview_truncated_at": 500,
        "source_shape": options["shape"],
        "raw_values_preserved": True,
    }


def canonical(source: Path, output: Path, mapping: dict):
    import pyarrow as pa
    import pyarrow.parquet as pq

    from .amounts import OrderAmounts
    from .data_schemas import FIELDS

    amounts = OrderAmounts(mapping["amount_mode"])
    schema = pa.schema([("source_row_id", pa.string())] + [(name, pa.string()) for name in FIELDS])
    count = 0
    with pq.ParquetWriter(output, schema, compression="zstd") as writer:
        for batch in pq.ParquetFile(source).iter_batches(batch_size=1000):
            raw = batch.to_pydict()
            empty = [None] * batch.num_rows
            data = {"source_row_id": raw["source_row_id"]}
            for field in FIELDS:
                key = mapping["columns"].get(field)
                data[field] = raw[key] if key else empty
            if mapping.get("currency_constant"):
                data["currency"] = [mapping["currency_constant"]] * batch.num_rows
            writer.write_table(pa.Table.from_pydict(data, schema=schema))
            for i in range(batch.num_rows):
                amounts.add({field: data[field][i] for field in FIELDS})
            count += batch.num_rows
    order_schema = pa.schema(
        [
            ("order_id", pa.string()),
            ("source_rows", pa.int64()),
            ("amount_candidate", pa.string()),
            ("currency", pa.string()),
            ("issues", pa.string()),
            ("quality_gate", pa.string()),
        ]
    )
    buffer, orders, conflicts = [], 0, 0
    with pq.ParquetWriter(
        output.with_name("order_amounts.parquet"), order_schema, compression="zstd"
    ) as writer:
        for row in amounts.records():
            buffer.append(row)
            orders += 1
            conflicts += int(bool(row["issues"]))
            if len(buffer) >= 1000:
                writer.write_table(pa.Table.from_pylist(buffer, schema=order_schema))
                buffer = []
        if buffer:
            writer.write_table(pa.Table.from_pylist(buffer, schema=order_schema))
    return {
        "rows": count,
        "storage_types": "nullable_utf8",
        "normalization": "names_only",
        "order_amount_view": "order_amounts.parquet",
        "unique_orders": orders,
        "amount_orders_with_issues": conflicts,
        "quality_gate": "pending",
    }


def main():
    job = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    constrain()
    try:
        if job["action"] == "inspect":
            result = inspect_xlsx(Path(job["source"]))
        elif job["action"] == "parse":
            result = parse(Path(job["source"]), Path(job["output"]), job["options"])
        else:
            result = canonical(Path(job["source"]), Path(job["output"]), job["mapping"])
        response = {"result": result}
    except DataIssue as exc:
        response = {"error": {"message": exc.message, "code": exc.code, "status": exc.status}}
    except MemoryError:
        response = {
            "error": {
                "message": "处理超出内存预算，请缩小文件。",
                "code": "memory_limit",
                "status": 413,
            }
        }
    except Exception:
        response = {
            "error": {
                "message": "无法处理文件，请检查文件完整性和格式。",
                "code": "parse_failed",
                "status": 422,
            }
        }
    Path(job["response"]).write_text(json.dumps(response, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
