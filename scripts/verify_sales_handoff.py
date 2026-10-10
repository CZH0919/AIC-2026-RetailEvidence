"""Check note persistence against real public evidence, without invented causes."""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import urllib.error
import urllib.request


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    run = '81278059-612c-498b-9dd4-be6377e449de'
    base = f'http://127.0.0.1:8000/api/projects/e1711757-601a-4e9a-a05f-037d7e6909e6/sales/runs/{run}'
    database = Path(__file__).resolve().parents[1] / 'storage/state/retailevidence.sqlite3'

    def report_hash():
        with sqlite3.connect(database) as connection:
            value = connection.execute('SELECT result FROM analysis_runs WHERE id=?', (run,)).fetchone()[0]
        return hashlib.sha256(value.encode()).hexdigest()

    def request(path, payload=None):
        req = urllib.request.Request(base + path, data=json.dumps(payload).encode() if payload else None,
              headers={'Content-Type': 'application/json'}, method='PUT' if payload else 'GET')
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.load(response)

    before = report_hash()
    existing = request('/records')['items']
    record = next((r for r in existing.values() if r['value'].get('source') == 'user_note'
                   and r['value'].get('item_id') == 'M' and r['value'].get('day') == '2011-10-24'), None)
    payload = {'item_id':'M', 'day':'2011-10-24', 'reason':'unknown',
               'note':'公开数据接口核对：尚未向商户确认原因。',
               'expected_revision':record['revision'] if record else 0}
    saved = request('/item-notes', payload)
    try:
        request('/item-notes', payload)
        raise AssertionError('Stale note accepted')
    except urllib.error.HTTPError as issue:
        assert issue.code == 409
    records = request('/records')['items']
    assert any(r['value'] == saved['value'] and r['revision'] == saved['revision'] for r in records.values())
    assert before == report_hash(), 'A note changed the frozen report'
    with urllib.request.urlopen(base + '/report', timeout=30) as response:
        (output / 'monthly_summary_current.html').write_bytes(response.read())
    results = {'run_id':run, 'item_id':'M', 'day':'2011-10-24', 'persisted':True,
               'stale_revision_rejected':True, 'frozen_report_unchanged':True,
               'record':saved, 'limitations':'API verified; final new-note browser flow was interrupted by SSH resets.'}
    (output / 'handoff_api.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(results,ensure_ascii=False))


if __name__ == '__main__':
    main()
