"""Acceptance against already-imported Online Retail; no manufactured sales or inventory."""

import argparse
import json
import time
import urllib.error
import urllib.request
from decimal import Decimal, InvalidOperation
from pathlib import Path
from uuid import uuid4

import pyarrow.parquet as pq


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', default='http://127.0.0.1:8000')
    parser.add_argument('--project', default='e1711757-601a-4e9a-a05f-037d7e6909e6')
    parser.add_argument('--version', default='48b9d571-3d7f-43d4-b4f0-19ea931123be')
    parser.add_argument('--output', required=True)
    parser.add_argument('--month', default='2011-10')
    args = parser.parse_args()
    root = Path(args.output); root.mkdir(parents=True, exist_ok=True)

    def request(path, method='GET', data=None):
        body = json.dumps(data).encode() if data is not None else None
        req = urllib.request.Request(args.base + '/api' + path, data=body,
                                     headers={'Content-Type': 'application/json'}, method=method)
        with urllib.request.urlopen(req, timeout=120) as response:
            return json.load(response)

    base = f'/projects/{args.project}'
    source = request(base + f'/sales/sources/{args.version}')
    params = {'sources': [{'version_id': args.version, 'mapping_revision': source['mapping_revision']}],
              'month': args.month, 'complete_coverage': True, 'coverage_start': source['start'],
              'coverage_end': source['end'], 'merge_mode': 'append', 'duplicates': 'keep',
              'closed_dates': []}
    runs = []
    for checking in [True, False]:
        started = time.monotonic()
        run = request(base + '/sales/runs', 'POST', {**params, 'check_only': checking, 'idempotency_key': str(uuid4())})
        while run['status'] in ['queued', 'running', 'cancelling']:
            if time.monotonic() - started > 1250:
                raise TimeoutError('Real-data run timed out')
            time.sleep(2)
            run = request(base + '/runs/' + run['id'])
        print(json.dumps({'check_only': checking, 'run_id': run['id'], 'status': run['status'],
                          'message': run['message'], 'seconds': round(time.monotonic() - started, 2)}), flush=True)
        (root / ('check_run.json' if checking else 'monthly_run.json')).write_text(json.dumps(run, ensure_ascii=False, indent=2), encoding='utf-8')
        assert run['result'], run
        runs.append(run)
    run = runs[-1]; report = run['result']
    assert report['quality']['input_rows'] == report['quality']['included_rows'] + report['quality']['excluded_rows']
    assert len(report['highlights']) == min(5, len(report['attention_ids']))
    assert report['summary']['attention_total'] == len(set(report['attention_ids']))
    assert len(report['actions']) <= 3
    for p in report['products']:
        if p['forecast']:
            assert p['forecast']['start'] > args.month + '-31'
    # Independent arithmetic on the ORIGINAL public source, not the sales module.
    raw = Path('storage/datasets/public/online_retail/raw.parquet')
    rows = pq.read_table(raw, columns=['c0', 'c1', 'c3', 'c4', 'c5', 'c6']).to_pylist()
    states, conflicts = {}, set()
    for r in rows:
        order = r['c0']
        if not order: continue
        state = states.setdefault(order, [set(), set()])
        if r['c4']: state[0].add(r['c4'])
        if r['c6']: state[1].add(r['c6'])
        if any(len(s) > 1 for s in state): conflicts.add(order)
    quantity = amount = Decimal(0)
    for r in rows:
        if not str(r['c4']).startswith(args.month) or not (r['c1'] or '').strip(): continue
        if str(r['c0']).upper().startswith('C') or r['c0'] in conflicts: continue
        try:
            q, price = Decimal(r['c3'] or ''), Decimal(r['c5'] or '')
        except InvalidOperation:
            continue
        if q.is_finite() and q > 0:
            quantity += q
            if price.is_finite() and price >= 0: amount += q * price
    assert abs(float(quantity) - report['summary']['quantity']) < .001, (quantity, report['summary'])
    if report['summary']['amount'] is not None:
        assert abs(float(amount) - report['summary']['amount']) < .01, (amount, report['summary'])
    files = ['sales_products.csv', 'sales_backtests.csv', 'sales_row_audit.csv', 'manifest.json']
    for file in files:
        with urllib.request.urlopen(args.base + '/api' + base + f'/sales/runs/{run["id"]}/files/{file}', timeout=120) as response:
            (root / file).write_bytes(response.read())
    for appendix in [False, True]:
        with urllib.request.urlopen(args.base + '/api' + base + f'/sales/runs/{run["id"]}/report?all_attention={str(appendix).lower()}') as response:
            (root / ('monthly_all_attention.html' if appendix else 'monthly_summary.html')).write_bytes(response.read())
    action_checked = False
    if report['actions']:
        aid = urllib.parse.quote(report['actions'][0]['id'], safe='')
        action_path = base + f'/sales/runs/{run["id"]}/actions/{aid}'
        existing = request(base + f'/sales/runs/{run["id"]}/records')['items'].get('action:' + report['actions'][0]['id'])
        revision = existing['revision'] if existing else 0
        payload = {'status': 'pending', 'note': '公开数据验收：备注保存检查，不代表真实经营判断。', 'expected_revision': revision}
        saved = request(action_path, 'PUT', payload)
        assert saved['revision'] == revision + 1
        try:
            request(action_path, 'PUT', payload)
            raise AssertionError('Stale revision accepted')
        except urllib.error.HTTPError as exc:
            assert exc.code == 409
        action_checked = True
    answer = request(base + f'/sales/runs/{run["id"]}/ask', 'POST', {'question': '请解释这份月报，我下次进货前先看什么？'})
    (root / 'ai_answer.json').write_text(json.dumps(answer, ensure_ascii=False, indent=2), encoding='utf-8')
    summary = {'run_id': run['id'], 'project_id': args.project, 'version_id': args.version,
               'source': 'Existing Online Retail, original public rows', 'month': args.month,
               'independent_quantity': float(quantity), 'independent_amount': float(amount),
               'summary': report['summary'], 'forecast': report['forecast'], 'anomaly': report['anomaly'],
               'quality': report['quality'], 'action_revision_checked': action_checked,
               'ai_used': answer['ai_used'], 'peak_rss_bytes': run['peak_rss_bytes'],
               'limitations': ['Public-source coverage confirmation is a demonstration assumption, not independently proven completeness.',
                              'No stock, costs or real merchant causes were invented.']}
    (root / 'acceptance.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
