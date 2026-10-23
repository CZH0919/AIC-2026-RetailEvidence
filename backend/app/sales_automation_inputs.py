"""Reuse quality processing on the exact sources and exclusions of a sales report."""
import csv
import json
from collections import defaultdict
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from .data_api import write_json
from .import_formats import DataIssue
from .quality import normalize, process_quality
from .data_schemas import FIELDS


def prepare(job, progress):
    output = Path(job['output'])
    parent = job['automatic_input']
    allowed = defaultdict(dict)
    with Path(parent['audit']).open(encoding='utf-8-sig', newline='') as stream:
        for row in csv.DictReader(stream):
            # Retain malformed order members so quality processing can detect
            # incomplete baskets. Reuse sales decisions on overlap and duplicates.
            if row['reason'] not in {'outside_scope', 'replaced_range', 'duplicate_removed'}:
                allowed[row['version_id']][row['source_row_id']] = row['reason']
    columns = {k: k if any(s['mapping']['columns'].get(k) for s in parent['sources']) else None for k in FIELDS}
    columns['record_status'] = 'record_status'
    mapping = {**job['mapping'], 'columns': columns, 'time_format': 'iso8601', 'status_rule': 'status_column',
               'status_values': {k: k for k in ['forward', 'cancelled', 'return', 'unknown']}}
    # The extra raw identity prevents a second, different deduplication pass:
    # duplicate retention/removal was already frozen in sales_row_audit.csv.
    schema = pa.schema([('source_row_id', pa.string())] + [(k, pa.string()) for k in FIELDS] + [('_sales_source_row', pa.string())])
    source = output / '.automatic-input.parquet'
    writer = pq.ParquetWriter(source, schema, compression='zstd')
    try:
        for s in parent['sources']:
            if parent['hashes'].get(s['version_id']) != s['canonical_sha256']:
                raise DataIssue('销售表已变化，请重新生成月报。', 'artifact_mismatch')
            keep = allowed[s['version_id']]
            for batch in pq.ParquetFile(s['path']).iter_batches(batch_size=2000):
                rows = []
                for raw in batch.to_pylist():
                    if raw['source_row_id'] not in keep:
                        continue
                    row = normalize(raw, s['mapping'], job['policy'])
                    if keep[raw['source_row_id']] == 'order_conflict':
                        row['record_status'] = 'unknown'
                    identity = s['version_id'] + ':' + raw['source_row_id']
                    rows.append({'source_row_id': identity, **{k: row.get(k) for k in FIELDS}, '_sales_source_row': identity})
                if rows:
                    writer.write_table(pa.Table.from_pylist(rows, schema=schema))
    finally:
        writer.close()
    try:
        result = process_quality(source, source, output, mapping, job['policy'], job['scope'], job['context'], progress)
        result['automatic_parent'] = parent['metadata']
        result['warnings'].append('重复记录和文件重叠沿用对应销售月报的处理结果。')
        write_json(output / 'quality_report.json', result)
        return result
    finally:
        source.unlink(missing_ok=True)
