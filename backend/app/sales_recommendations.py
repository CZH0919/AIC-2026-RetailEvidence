"""Combine saved sales, basket and customer evidence into distinct next steps.

Scores compare historical reach and strength, never predicted revenue uplift.
No training, source-file scans or customer identifiers are needed on page load.
"""
import calendar
import hashlib
import json
import os
import tempfile
from datetime import date, timedelta

from .sales_actions import _eligible, _fmt
from .sales_views import encode

VERSION = "recommendations-v1"
CACHE_VERSION = "recommendations-customers-v3"


def _id(kind, run_id, key):
    digest = hashlib.sha256((run_id + "|" + key).encode()).hexdigest()[:24]
    return f"{VERSION}:{kind}:{digest}"


def compatible(inputs, row, report, quality):
    """Use the same frozen source/mapping and no observations after this month."""
    automatic = (quality or {}).get('automatic_parent')
    if automatic:
        expected = inputs.get('parameters', {}).get('sources', [])
        signature = lambda entries: sorted((s['version_id'], s['mapping_revision']) for s in entries)
        if automatic.get('sales_run_id') != inputs.get('context', {}).get('run_id') or signature(automatic.get('sources', [])) != signature(expected):
            return False
    sources = {s['version_id']: s['mapping_revision'] for s in inputs.get('sources') or []}
    context = report.get('context') or {}
    if context.get('data_version_id') not in sources or sources[context['data_version_id']] != context.get('mapping_revision'):
        return False
    if not report.get('summary', {}).get('publishable') or not quality:
        return False
    if context.get('project_id') != inputs.get('context', {}).get('project_id'):
        return False
    qcontext = quality.get('context') or {}
    if any(qcontext.get(k) != context.get(k) for k in ['project_id', 'data_version_id', 'mapping_revision']):
        return False
    if qcontext.get('run_id') != row.quality_run_id:
        return False
    scope = quality.get('scope') or {}
    params = inputs.get('parameters') or {}
    if scope.get('countries') or scope.get('item_ids') or scope.get('currency'):
        return False
    if quality.get('policy', {}).get('duplicates') != params.get('duplicates'):
        return False
    month = inputs['month']
    last = f"{month}-{calendar.monthrange(int(month[:4]), int(month[5:]))[1]:02}"
    observed = scope.get('date_end') or quality.get('summary', {}).get('latest_valid_order_time')
    if not observed or observed[:7] < month or observed[:10] > last:
        return False
    actual_latest = quality.get('summary', {}).get('latest_valid_order_time')
    if actual_latest and actual_latest[:10] > last:
        return False
    # Clustering's reference date is the day AFTER the last observed day.
    reference = report.get('analysis', {}).get('reference_time')
    if reference and reference[:10] > (date.fromisoformat(last) + timedelta(days=1)).isoformat():
        return False
    if params.get('coverage_start') and (not scope.get('date_start') or scope['date_start'] < params['coverage_start']):
        return False
    return True


def _pairings(inputs, analysis):
    report, run_id = analysis['report'], analysis['id']
    products = {p['id']: p for p in inputs['products'] if _eligible(p)}
    total = sum(p.get('amount') or 0 for p in products.values())
    total_quantity = sum(p['quantity'] for p in products.values())
    output = []
    for rule in report.get('top_rules', []):
        a = rule['antecedents'].split(' | ')
        b = rule['consequents'].split(' | ')
        ids = sorted(set(a + b))
        identity = '|'.join(ids)
        if not all(key in products for key in ids):
            continue
        n, na, nb, nab = (rule.get(k, 0) for k in ['denominator', 'n_a', 'n_b', 'n_ab'])
        vn, va, vb, vab = (rule.get(k, 0) for k in ['validation_denominator', 'validation_n_a', 'validation_n_b', 'validation_n_ab'])
        lower = rule.get('confidence_lower', 0)
        if not (n >= na >= nab >= max(20, report.get('analysis', {}).get('min_count', 20))
                and n >= nb >= nab and vn >= va >= vab >= 3 and vn >= vb >= vab
                and na > nab and rule.get('lift', 0) > 1 and rule.get('validation_lift', 0) > 1):
            continue
        baseline, validation_baseline = nb / n, vb / vn
        if lower <= baseline or vab / va <= validation_baseline:
            continue
        reach = sum(products[k].get('amount') or 0 for k in ids) / total if total else sum(products[k]['quantity'] for k in ids) / max(total_quantity, 1)
        if reach < .002:
            continue
        strength = min((lower - baseline) / max(1 - baseline, .001),
                       (vab / va - validation_baseline) / max(1 - validation_baseline, .001))
        score = reach * strength * min(vab / 20, 1)
        names = [products[k]['name'] for k in ids]
        target = {'kind': 'pairing', 'version_id': report['context']['data_version_id'], 'run_id': run_id}
        reason = (f"买过{'、'.join(products[k]['name'] for k in a)}的 {_fmt(na)} 笔订单中，"
                  f"{_fmt(nab)} 笔也买了{'、'.join(products[k]['name'] for k in b)}；"
                  f"另一批订单中也出现了 {_fmt(vab)} 次共同购买。")
        output.append({'id': _id('pairing', run_id, identity), 'item_id': '', 'item_name': '＋'.join(names),
                       'category': '商品搭配', 'strategy': 'pairing', 'title': '把这组商品放在一起试卖',
                       'text': '将' + '、'.join(names) + '相邻摆放，或一起展示；先观察共同购买次数是否增加。',
                       'reason': reason, 'review': '试摆放后，比较共同购买次数和组合销售额。',
                       'related_items': ids, 'target': target, 'button_label': '查看商品搭配',
                       'source_run_id': run_id, 'score': score,
                       'selection': {'reach': reach, 'strength': strength, 'basis': 'historical_reach_and_validation'}})
    # Reciprocal rules describe the same arrangement. Keep the stronger tested
    # direction rather than whichever happened to appear first in a report.
    unique = {}
    for action in sorted(output, key=lambda a: (-a['score'], a['reason'])):
        unique.setdefault(action['id'], action)
    return list(unique.values())


def _customers(inputs, analysis):
    report, run_id = analysis['report'], analysis['id']
    evidence = report.get('customer_opportunities') or {}
    opportunities = evidence.get('opportunities', [])
    total = evidence.get('customers_analyzed', 0)
    output = []
    for opportunity in opportunities:
        count = opportunity['customers']
        if count < max(10, total * .01) or not total:
            continue
        reason = (f"从 {total:,} 位客户中找到 {count:,} 位：每人至少在4个不同日期购买过，"
                  "过去购买间隔较稳定；截至本月底，本次间隔均已超过各自平时的1.5倍，并至少多7天。")
        output.append({'id': _id('customer', run_id, opportunity['key']),
            'item_id': '', 'category': '客户回访', 'strategy': 'customer-followup',
            'title': f'回访这 {count:,} 位购买间隔变长的老客户',
            'text': '按名单联系客户，询问这次是否还有采购需求；有需要再根据对方要买的商品准备报价。',
            'reason': reason, 'review': '记录客户是否回应、是否再次下单，再决定是否继续回访。',
            'related_items': [], 'target': {'kind': 'customer', 'run_id': run_id, 'opportunity': opportunity['key']},
            'source_run_id': run_id, 'button_label': '查看回访名单与依据',
            'score': count / total * .25,
            'details': [{'label': '针对哪些客户', 'value': evidence['rule']},
                {'label': '这批客户的中间水平', 'value': f"购买过 {_fmt(opportunity['purchase_days_median'])} 个不同日期；平时间隔 {_fmt(opportunity['usual_gap_median'])} 天，本次距上次购买 {_fmt(opportunity['elapsed_median'])} 天。这些是名单的中位数，每人按自己的间隔筛选。"},
                {'label': '使用的销售记录', 'value': f"{evidence.get('history_start') or '已上传历史'} 至 {evidence['through_date']}"},
                {'label': '名单包含', 'value': '客户编号、购买日期数、平时间隔、上次购买日期、本次间隔和筛选门槛。请通过店铺已有联系方式联系客户。'},
                {'label': '如何使用', 'value': '这是表格中暂未再次购买的客户，先询问需求，不代表客户已流失。'}],
            'selection': {'reach': count/total, 'strength': 1, 'basis': 'individual_regular_purchase_gaps'}})
    return output


def combine(inputs, analyses):
    pool = []
    summary = inputs.get('summary') or {}
    monetary = all(p.get('amount') is not None for p in inputs.get('products', []))
    total = summary.get('amount' if monetary else 'quantity') or 1
    for saved in inputs.get('candidates', []):
        a = dict(saved)
        kind = a.get('item_type')
        strategy = ('procurement-' if kind == 'physical' else 'sales-') + a['signal']
        a.update(category='进货安排' if kind == 'physical' else '销售安排', strategy=strategy,
                 target={'kind': 'product', 'item_id': a['item_id']}, button_label='查看 ' + a['item_name'])
        normalized = a['selection']['impact'] * (4 if a['selection']['comparison'] == 'daily' else 1) / total
        a['score'] = min(normalized, 1) * (.8 if a['selection']['comparison'] == 'monthly' else 1)
        pool.append(a)
    for analysis in analyses:
        pool.extend(_pairings(inputs, analysis) if analysis['kind'] == 'association' else _customers(inputs, analysis))
    selected, strategies, covered = [], set(), set()
    while len(selected) < 3:
        available = [a for a in pool if a['strategy'] not in strategies]
        if not available:
            break
        def priority(a):
            items = set(a.get('related_items', []))
            overlap = len(items & covered) / len(items) if items else 0
            return (-a['score'] * (1 - .6 * overlap), a['id'])
        best = min(available, key=priority)
        selected.append(best)
        strategies.add(best['strategy'])
        covered.update(best.get('related_items', []))
    # Keep identities and notes for formerly displayed recommendations. The UI
    # only exposes these when an actual saved note/status exists.
    history = {a['id']: a for a in inputs.get('previous_actions', []) + inputs.get('candidates', []) + pool}
    for a in selected:
        history.pop(a['id'], None)
    return {'actions': selected, 'previous_actions': list(history.values()), 'recommendation_version': VERSION}


def recommendations(session, run, directory):
    from sqlalchemy import select
    from sqlalchemy.orm import defer
    from .models import AnalysisRun
    from .task_runner import PUBLISHED
    inputs = json.loads((directory / 'action-input.json').read_bytes())
    sources = {s['version_id'] for s in inputs.get('sources') or []}
    rows = session.scalars(select(AnalysisRun).options(defer(AnalysisRun.result))
        .where(AnalysisRun.project_id == run.project_id, AnalysisRun.dataset_version_id.in_(sources),
               AnalysisRun.kind.in_(['association', 'clustering']), AnalysisRun.status.in_(PUBLISHED))
        .order_by(AnalysisRun.created_at.desc()).limit(50)).all() if sources else []
    fingerprint = hashlib.sha256(encode([CACHE_VERSION, [(r.id, r.finished_at) for r in rows]])).hexdigest()[:24]
    target = directory / ('recommendations-' + fingerprint + '.json')
    if target.is_file():
        return json.loads(target.read_bytes())
    analyses, seen = [], set()
    for row in rows:
        key = row.dataset_version_id, row.kind
        if key in seen:
            continue
        quality_row = session.get(AnalysisRun, row.quality_run_id) if row.quality_run_id else None
        if not quality_row or quality_row.project_id != run.project_id or quality_row.kind != 'quality' or quality_row.status not in PUBLISHED:
            continue
        report, quality = json.loads(row.result or '{}'), json.loads(quality_row.result or '{}')
        if row.kind == 'clustering':
            from .customer_opportunities import load
            from .settings import configured_path
            evidence = load(configured_path('AIC_STORAGE_DIR', 'storage') / 'runs' / row.project_id / row.id)
            if evidence is not None:
                report['customer_opportunities'] = evidence
        if compatible(inputs, row, report, quality):
            seen.add(key)
            analyses.append({'id': row.id, 'kind': row.kind, 'report': report})
    result = combine(inputs, analyses)
    current = {a['id'] for a in result['actions']}
    history = {a['id']: a for a in result['previous_actions']}
    for previous in directory.glob('recommendations-*.json'):
        for a in json.loads(previous.read_bytes()).get('actions', []):
            if a['id'] not in current:
                history[a['id']] = a
    result['previous_actions'] = list(history.values())
    fd, temporary = tempfile.mkstemp(prefix='.recommendations-', dir=directory)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(encode(result))
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return result
