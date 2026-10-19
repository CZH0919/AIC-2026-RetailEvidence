"""Evidence-backed follow-up lists, computed once from validated order history.

Cluster averages are descriptive, never eligibility rules for individual customers.
No revenue uplift or loss of a customer is inferred from a purchase gap.
"""
import csv
import json
from math import ceil
from pathlib import Path
from statistics import median

import pandas as pd

VERSION = 'customer-followup-v1'
FIELDS = ['customer_id', 'purchase_days', 'usual_gap_days', 'last_purchase', 'days_since_purchase', 'threshold_days']
RULE = '至少在4个不同日期购买；以相邻购买日的间隔中位数作为平时间隔；间隔较稳定，且此次等待已超过平时的1.5倍、并至少多7天。'


def build(frame, report, output):
    output = Path(output)
    reference = pd.Timestamp(report['analysis']['reference_time'])
    if reference.tzinfo is None:
        reference = reference.tz_localize('UTC')
    data = frame[['customer_id', 'order_id', 'event_time']].copy()
    data['day'] = pd.to_datetime(data['event_time'], utc=True, errors='coerce').dt.normalize()
    data = data.dropna(subset=['customer_id', 'order_id', 'day'])
    data = data[data['day'] < reference.normalize()]
    rows = []
    if report.get('summary', {}).get('publishable'):
        for customer, group in data.groupby('customer_id', sort=True):
            days = sorted(group['day'].unique())
            if len(days) < 4:
                continue
            gaps = pd.Series([(b-a).days for a,b in zip(days, days[1:])], dtype=float)
            usual = float(gaps.median())
            if usual < 1 or (gaps.quantile(.75)-gaps.quantile(.25)) > usual*.5 or gaps.max() > usual*2:
                continue
            elapsed = int((reference.normalize()-days[-1]).days)
            threshold = max(usual*1.5, usual+7)
            # Focus on a recent missed interval, not every long-inactive customer.
            if elapsed <= threshold or elapsed > max(90, usual*3):
                continue
            rows.append(dict(customer_id=str(customer), purchase_days=len(days), usual_gap_days=usual,
                             last_purchase=days[-1].date().isoformat(), days_since_purchase=elapsed,
                             threshold_days=threshold))
    rows.sort(key=lambda r: (-r['purchase_days'], r['days_since_purchase']/r['usual_gap_days'], r['customer_id']))
    total = int(report.get('summary', {}).get('customers', 0))
    enough = len(rows) >= max(10, ceil(total*.01))
    result = {'version': VERSION, 'reference_date': reference.date().isoformat(),
              'through_date': (reference-pd.Timedelta(days=1)).date().isoformat(),
              'history_start': data['day'].min().date().isoformat() if len(data) else None,
              'rule': RULE, 'customers_analyzed': total, 'opportunities': []}
    if enough:
        result['opportunities'] = [{'key': VERSION, 'customers': len(rows),
            'purchase_days_median': median(r['purchase_days'] for r in rows),
            'usual_gap_median': median(r['usual_gap_days'] for r in rows),
            'elapsed_median': median(r['days_since_purchase'] for r in rows)}]
    with (output/'customer_followup.csv').open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        if enough:
            writer.writerows(rows)
    (output/'customer_opportunities.json').write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')
    return result


def load(folder):
    path = Path(folder)/'customer_opportunities.json'
    if not path.is_file():
        return None
    result = json.loads(path.read_text(encoding='utf-8'))
    return result if result.get('version') == VERSION else None
