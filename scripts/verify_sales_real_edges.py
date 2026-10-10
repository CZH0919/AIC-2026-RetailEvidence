"""Additional checks using the existing public files, including real-data aggregates."""

import argparse
import csv
import json
import time
import urllib.error
import urllib.request
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path
from uuid import uuid4

import pyarrow.parquet as pq


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    root = Path(args.output); root.mkdir(parents=True, exist_ok=True)
    base = 'http://127.0.0.1:8000/api'
    pid = 'e1711757-601a-4e9a-a05f-037d7e6909e6'
    version = '48b9d571-3d7f-43d4-b4f0-19ea931123be'

    def request(url, data=None, method=None, raw=False):
        body = data if raw else json.dumps(data).encode() if data is not None else None
        req = urllib.request.Request(base + url, data=body,
              headers={'Content-Type': 'application/octet-stream' if raw else 'application/json'},
              method=method or ('POST' if data is not None else 'GET'))
        with urllib.request.urlopen(req, timeout=120) as response:
            return json.load(response)

    project = request('/projects/' + pid)
    metadata = request(f'/projects/{pid}/versions/{version}')
    revision = metadata['mapping']['revision']
    results = {}

    def wait_report(project_id, sources, month, complete=False,
                    coverage_start='2010-12-01', coverage_end='2011-12-09'):
        run = request(f'/projects/{project_id}/sales/runs', {
            'sources': sources, 'month': month, 'complete_coverage': complete,
            'coverage_start': coverage_start if complete else None,
            'coverage_end': coverage_end if complete else None,
            'idempotency_key': str(uuid4())})
        start = time.monotonic()
        while run['status'] in ['queued', 'running', 'cancelling']:
            if time.monotonic() - start > 1250: raise TimeoutError()
            time.sleep(2)
            run = request(f'/projects/{project_id}/runs/{run["id"]}')
        assert run['result'], run
        return run

    sources = [{'version_id': version, 'mapping_revision': revision}]
    first = wait_report(pid, sources, '2010-12', True)
    assert first['result']['summary']['quantity'] > 0
    assert first['result']['forecast']['status'] == 'unavailable'
    assert first['result']['anomaly']['status'] == 'unavailable'
    assert first['result']['summary']['previous'] is None
    results['first_month'] = {'run_id': first['id'], 'summary': first['result']['summary'],
                             'forecast': first['result']['forecast'], 'anomaly': first['result']['anomaly']}
    uncertain = wait_report(pid, sources, '2011-10', False)
    assert not uncertain['result']['summary']['complete_month']
    assert uncertain['result']['forecast']['status'] == 'unavailable'
    assert any(p['quantity'] is None for p in uncertain['result']['chart'])
    results['unknown_coverage'] = {'run_id': uncertain['id'], 'summary': uncertain['result']['summary']}
    try:
        request(f'/projects/{pid}/sales/runs', {'sources': [{'version_id': 'e4e9bd38-43a5-4158-bb19-36092f446d03', 'mapping_revision': 1}],
                  'month': '2011-10', 'idempotency_key': str(uuid4())})
        raise AssertionError('Undated basket data accepted')
    except urllib.error.HTTPError as exc:
        assert exc.code == 422
        results['groceries_refusal'] = json.load(exc)
    # Derive monthly totals ONLY from actual downloaded rows. Never invent dates, amounts or sales.
    monthly = defaultdict(lambda: [Decimal(0), Decimal(0), ''])
    rows = pq.read_table('storage/datasets/public/online_retail/raw.parquet', columns=['c0','c1','c2','c3','c4','c5']).to_pylist()
    for r in rows:
        month = str(r['c4'])[:7]
        if month not in ['2011-09', '2011-10'] or not (r['c1'] or '').strip() or str(r['c0']).upper().startswith('C'): continue
        try:
            qty, price = Decimal(r['c3'] or ''), Decimal(r['c5'] or '')
        except InvalidOperation:
            continue
        if not qty.is_finite() or not price.is_finite() or qty <= 0 or price < 0: continue
        aggregate = monthly[month, r['c1'].strip()]
        aggregate[0] += qty; aggregate[1] += qty * price
        aggregate[2] = aggregate[2] or r['c2'] or r['c1']
    derived_project = request('/projects', {'name': 'Online Retail 月汇总格式验收 ' + str(uuid4())[:8],
              'description': '由已下载真实明细按月汇总；保留全部正向有效数量/价格，不排除同单冲突。不是商户原始月表。', 'color': 'teal'})
    derived_id = derived_project['id']; imported = []
    for month in ['2011-09', '2011-10']:
        path = root / f'online_retail_monthly_{month}.csv'
        with path.open('w', encoding='utf-8-sig', newline='') as stream:
            writer = csv.writer(stream); writer.writerow(['StockCode', 'Description', 'Quantity', '销售额'])
            writer.writerows([key, values[2], str(values[0]), str(values[1])] for (m, key), values in sorted(monthly.items()) if m == month)
        draft = request(f'/projects/{derived_id}/imports?filename={path.name}', path.read_bytes(), raw=True)
        draft = request(f'/projects/{derived_id}/imports/{draft["id"]}/preview', {
            'encoding': 'utf-8-sig', 'delimiter': ',', 'sheets': [], 'shape': 'transactions', 'basket_column': None, 'item_separator': '|'})
        mapping = {'columns': draft['preview']['suggestions']['columns'], 'record_kind': 'monthly_summary',
                   'summary_month': month, 'order_boundary': 'unavailable', 'amount_mode': 'line_amount',
                   'currency_constant': 'GBP', 'quantity_unit': '原始商品单位', 'time_format': None,
                   'timezone': None, 'status_rule': 'all_forward', 'status_values': {}, 'confirmed': True}
        saved = request(f'/projects/{derived_id}/imports/{draft["id"]}/confirm', {'preview_token': draft['preview_token'], 'mapping': mapping})
        imported.append({'version_id': saved['id'], 'mapping_revision': saved['mapping']['revision']})
    summary = wait_report(derived_id, imported, '2011-10', True,
                          coverage_start='2011-09-01', coverage_end='2011-10-31')
    report = summary['result']
    assert not report['chart'] and not report['products'][0]['daily']
    assert report['forecast']['status'] == 'unavailable'
    assert report['summary']['orders'] is None and report['summary']['average_order'] is None
    assert report['summary']['previous'] is not None
    expected = sum(v[0] for (m,_),v in monthly.items() if m == '2011-10')
    assert report['summary']['quantity'] == float(expected)
    assert report['summary']['attention_total'] > 5
    results['monthly_aggregates'] = {'project_id': derived_id, 'run_id': summary['id'],
                'summary': report['summary'], 'provenance': 'Monthly aggregation of original Online Retail rows; no generated observations.'}
    (root / 'real_edges.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(results, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
