"""Explain selected spikes using included source rows, cached once per report."""
import csv
import hashlib
import json
import logging
import math
import os
import tempfile
import threading
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from .amounts import money
from .sales_actions import _fmt

VERSION = "order-focus-v1"
_lock = threading.Lock()
logger = logging.getLogger(__name__)


def _read_orders(output, sources, events):
    """Join the immutable row audit to canonical data; never count excluded rows."""
    wanted = {(e['id'], e['date']) for e in events}
    included = defaultdict(dict)
    with (output / 'sales_row_audit.csv').open(encoding='utf-8-sig', newline='') as stream:
        for row in csv.DictReader(stream):
            event = (row['item_id'], row['date'])
            if event in wanted and row['reason'] == 'included':
                included[row['version_id']][row['source_row_id']] = event
    totals, orders, invalid, counts = defaultdict(Decimal), defaultdict(lambda: defaultdict(Decimal)), set(), defaultdict(int)
    storage, project = output.parents[2], output.parent.name
    for source in sources:
        rows = included.pop(source['version_id'], {})
        if not rows:
            continue
        folder = storage / 'datasets/projects' / project / source['version_id'] / 'mappings' / str(source['mapping_revision'])
        config = json.loads((folder / 'mapping.json').read_text())['config']
        supported = config.get('record_kind', 'transactions') == 'transactions' and config.get('order_boundary') in {'order_id', 'basket_id'}
        path = folder / 'canonical.parquet'
        expected = source.get('canonical_sha256')
        if expected:
            with path.open('rb') as stream:
                actual_hash = hashlib.file_digest(stream, 'sha256').hexdigest()
            if actual_hash != expected:
                raise ValueError('Source has changed since report publication')
        table = pq.read_table(path, columns=['source_row_id', 'quantity', 'order_id'],
                              filters=[('source_row_id', 'in', list(rows))])
        for row in table.to_pylist():
            event = rows.pop(row['source_row_id'])
            quantity = money(row['quantity'])
            order = (row.get('order_id') or '').strip()
            if quantity is None or quantity < 0:
                invalid.add(event)
                continue
            totals[event] += quantity
            counts[event] += 1
            if not supported or not order:
                invalid.add(event)
            else:
                # Distinct source namespaces avoid merging unrelated order numbers.
                orders[event][(source['version_id'], order)] += quantity
        invalid.update(rows.values())
    if included:
        raise ValueError('Report source not available')
    result = {}
    for event in events:
        key = (event['id'], event['date'])
        if key in invalid or not math.isclose(float(totals[key]), event['actual'], rel_tol=1e-9, abs_tol=1e-8):
            continue
        quantities = sorted((float(q) for q in orders[key].values() if q > 0), reverse=True)
        if not quantities or totals[key] <= 0:
            continue
        result[event['id']] = {'date': event['date'], 'actual': event['actual'],
                               'top_quantities': quantities[:2], 'orders': len(quantities), 'rows': counts[key]}
    return result


def _cached_orders(output, sources, events):
    key = hashlib.sha256(json.dumps([VERSION, sources, events], sort_keys=True).encode()).hexdigest()
    path = output / '.sales-focus-orders-v1.json'
    with _lock:
        if path.is_file():
            saved = json.loads(path.read_text())
            if saved.get('key') == key:
                return saved['items']
        items = _read_orders(output, sources, events)
        fd, temporary = tempfile.mkstemp(prefix='.sales-focus-orders-', dir=output)
        try:
            with os.fdopen(fd, 'w') as stream:
                json.dump({'key': key, 'items': items}, stream)
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        return items


def order_focus(report, output):
    if report.get('order_focus_version') == VERSION:
        return report
    events = [{'id': p['id'], 'date': p['focus']['evidence']['date'],
               'actual': p['focus']['evidence']['actual']}
              for p in report['products'] if (p.get('focus') or {}).get('category') == 'anomaly']
    output = Path(output)
    if not events or not report.get('sources') or not (output / 'sales_row_audit.csv').is_file():
        return report
    try:
        items = _cached_orders(output, report['sources'], sorted(events, key=lambda e: e['id']))
    except (OSError, ValueError, KeyError, pa.ArrowException):
        logger.warning('Unable to verify focus order evidence for report %s', output.name, exc_info=True)
        return report
    products = []
    for product in report['products']:
        item = items.get(product['id'])
        p = product
        if item:
            # Explain concentration only when one or two sizable orders account
            # for at least 80% of the day's actual sales; do not infer from totals.
            top, actual = item['top_quantities'], item['actual']
            chosen = top[:1] if top[0] / actual >= .8 else top[:2]
            if all(q >= 3 for q in chosen) and sum(chosen) / actual >= .8:
                if len(chosen) == 1:
                    detail = f'其中一笔订单购买 {_fmt(chosen[0])}'
                elif chosen[0] == chosen[1]:
                    detail = f'其中两笔订单各购买 {_fmt(chosen[0])}'
                else:
                    detail = f'其中两笔订单分别购买 {_fmt(chosen[0])} 和 {_fmt(chosen[1])}'
                reason = f"{item['date'][5:]} 售出 {_fmt(actual)}，{detail}。"
                focus = {**p['focus'], 'label': '大批量订单带动', 'reason': reason,
                         'note': '当天销量主要来自少数大单，进货时还需参考其他日期的销量。',
                         'order_evidence': item}
                p = {**p, 'focus': focus, 'focus_reason': reason}
        products.append(p)
    return {**report, 'products': products, 'order_focus_version': VERSION}
