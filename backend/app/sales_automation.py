"""Durable follow-up analyses for a sales report, using the existing worker queue."""
import calendar
import hashlib
import json
import logging
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import defer

from .data_api import dump
from .models import AnalysisRun, MappingVersion, RunEvent
from .quality_schemas import AnalysisParameters

VERSION = 'sales-auto-v1'
DONE = {'ready', 'no_result', 'skipped', 'failed'}
logger = logging.getLogger(__name__)


def initial_state():
    return {'version': VERSION, 'status': 'pending', 'steps': {
        key: {'status': 'pending', 'message': '月报生成后自动开始。'}
        for key in ['association', 'customers']}}


def _set_state(run, params, state):
    run.parameters = dump({**params, 'auto_analysis': state})


def enroll(session, run, retry=False):
    params = json.loads(run.parameters)
    state = params.get('auto_analysis') or initial_state()
    if retry:
        for step in state['steps'].values():
            if step['status'] == 'failed':
                step.update(status='pending', message='正在重新安排分析。', attempt=step.get('attempt', 0) + 1)
                step.pop('run_id', None)
                step.pop('quality_run_id', None)
    if any(s['status'] not in DONE for s in state['steps'].values()):
        state['status'] = 'pending'
    _set_state(run, params, state)
    return state


def _queue(session, parent, kind, key, params, quality=None):
    identity = f'{VERSION}:{parent.id}:{key}'
    old = session.scalar(select(AnalysisRun).where(AnalysisRun.project_id == parent.project_id,
                                                  AnalysisRun.idempotency_key == identity))
    if old:
        return old
    row = AnalysisRun(id=str(uuid4()), project_id=parent.project_id,
                      dataset_version_id=parent.dataset_version_id, mapping_version_id=parent.mapping_version_id,
                      policy_id=parent.policy_id, quality_run_id=quality.id if quality else None,
                      kind=kind, idempotency_key=identity,
                      request_sha256=hashlib.sha256(dump(params).encode()).hexdigest(), parameters=dump(params))
    session.add(row)
    session.flush()
    session.add(RunEvent(run_id=row.id, status='queued', message='已自动加入分析队列。'))
    return row


def _columns(session, parent, sales):
    mappings = []
    for source in sales['sources']:
        row = session.scalar(select(MappingVersion).where(
            MappingVersion.dataset_version_id == source['version_id'],
            MappingVersion.revision == source['mapping_revision']))
        if not row:
            raise ValueError('Frozen mapping no longer available')
        mappings.append(json.loads(row.config))
    return mappings


def _advance(session, parent):
    from .task_runner import PUBLISHED, TERMINAL
    params = json.loads(parent.parameters)
    state, sales = params['auto_analysis'], params['sales']
    if parent.status not in PUBLISHED:
        if parent.status in TERMINAL:
            for step in state['steps'].values():
                step.update(status='skipped', message='月报未生成成功，未启动后续分析。')
            state['status'] = 'complete'
            _set_state(parent, params, state)
        return
    mappings = _columns(session, parent, sales)
    end = f"{sales['month']}-{calendar.monthrange(*map(int, sales['month'].split('-')))[1]:02}"
    metadata = {'sales_run_id': parent.id, 'sources': sales['sources']}
    for purpose, step in state['steps'].items():
        if step['status'] in DONE:
            continue
        base_missing = any(m.get('record_kind', 'transactions') != 'transactions' or
                           m.get('order_boundary') not in {'order_id', 'basket_id'} or
                           not m['columns'].get('order_id') for m in mappings)
        if sales.get('check_only') or base_missing:
            step.update(status='skipped', message='需要带订单编号的销售明细；当前表格无法用于这项分析。')
            continue
        if purpose == 'customers' and not any(m['columns'].get('customer_id') for m in mappings):
            step.update(status='skipped', message='表格没有客户编号，未进行客户分群。')
            continue
        if not any(m['columns'].get('event_time') for m in mappings):
            step.update(status='skipped', message='缺少购买日期，未进行这项分析。')
            continue
        attempt = step.get('attempt', 0)
        if step['status'] == 'pending':
            scope = {'date_start': sales['month'] + '-01' if purpose == 'association' else sales.get('coverage_start'),
                     'date_end': end, 'countries': [], 'item_ids': [], 'currency': None}
            # The same input/scope can be shared when the uploaded history is one month.
            scope_key = hashlib.sha256(dump(scope).encode()).hexdigest()[:12]
            quality = _queue(session, parent, 'quality', f'q:{scope_key}:{attempt}',
                             {'scope': scope, 'timeout_seconds': 1200, 'memory_mb': 8192,
                              'automatic_parent': metadata})
            step.update(status='preparing', message='正在整理可用订单。', quality_run_id=quality.id)
        quality = session.get(AnalysisRun, step['quality_run_id'])
        if quality.status not in PUBLISHED:
            if quality.status in TERMINAL:
                step.update(status='failed', message='订单整理未完成，可以重试。')
            continue
        q = json.loads(quality.result or '{}')
        kind = 'association' if purpose == 'association' else 'rfm' if q['capabilities']['rfm']['allowed'] else 'rf'
        capability = q['capabilities'][kind]
        if not capability['allowed']:
            if purpose == 'customers':
                count = q['summary']['rf_customers']
                message = f'可用客户只有 {count} 位，至少需要50位。' if count < 50 else '客户购买记录太少，或购买情况差异不足，暂未分组。'
            else:
                count = q['summary']['complete_baskets']
                message = f'可用订单只有 {count} 笔，至少需要200笔。' if count < 200 else '当前订单或商品规模不适合这项分析。' if capability.get('state') == 'resource_limited' else '完整订单或商品种类不足，暂未分析搭配。'
            step.update(status='skipped', message=message)
            continue
        if not step.get('run_id'):
            child = _queue(session, parent, 'association' if purpose == 'association' else 'clustering',
                           f'{purpose}:{attempt}', {'analysis': AnalysisParameters(kind=kind).model_dump(),
                           'timeout_seconds': 1200, 'memory_mb': 8192, 'automatic_parent': metadata}, quality)
            step.update(status='running', message='正在查找常见商品搭配。' if purpose == 'association' else '正在分析客户购买情况。', run_id=child.id)
        child = session.get(AnalysisRun, step['run_id'])
        if child.status in PUBLISHED:
            result = json.loads(child.result or '{}')
            useful = result.get('summary', {}).get('publishable')
            if purpose == 'association':
                useful = useful and any(r.get('lift', 0) > 1 for r in result.get('top_rules', []))
            step.update(status='ready' if useful else 'no_result',
                        message='已完成，已加入搭配建议。' if useful and purpose == 'association' else
                                '已完成，可查看客户分组。' if useful else
                                '已分析，暂未发现明确的商品搭配。' if purpose == 'association' else
                                '已分析，客户购买情况暂未形成清晰分组。')
        elif child.status in TERMINAL:
            step.update(status='failed', message='本次分析未完成，可以重试。')
    state['status'] = 'complete' if all(s['status'] in DONE for s in state['steps'].values()) else 'running'
    _set_state(parent, params, state)


def advance(sessions):
    """Recover queue dependencies from persisted state, without a browser session."""
    with sessions() as session:
        session.connection().exec_driver_sql('BEGIN IMMEDIATE')
        rows = session.scalars(select(AnalysisRun).options(defer(AnalysisRun.result)).where(
            AnalysisRun.kind == 'sales',
            func.json_extract(AnalysisRun.parameters, '$.auto_analysis.status').in_(['pending', 'running']))
            .order_by(AnalysisRun.created_at).limit(50)).all()
        for parent in rows:
            try:
                with session.begin_nested():
                    _advance(session, parent)
            except Exception:
                logger.exception('Automatic analyses could not advance for report %s', parent.id)
                params = json.loads(parent.parameters)
                state = params['auto_analysis']
                for step in state['steps'].values():
                    if step['status'] not in DONE:
                        step.update(status='failed', message='暂时无法安排分析，可以重试。')
                state['status'] = 'complete'
                _set_state(parent, params, state)
        session.commit()


def read_state(session, run):
    state = json.loads(run.parameters).get('auto_analysis')
    if not state:
        return {'status': 'not_started', 'steps': {}}
    result = json.loads(json.dumps(state))
    step = result['steps']['customers']
    if step['status'] == 'ready' and step.get('run_id'):
        row = session.get(AnalysisRun, step['run_id'])
        if row and row.project_id == run.project_id:
            report = json.loads(row.result or '{}')
            result['customer_groups'] = report.get('clusters', [])
            result['customer_mode'] = report.get('analysis', {}).get('mode')
            from .customer_opportunities import load
            from .settings import configured_path
            evidence = load(configured_path('AIC_STORAGE_DIR', 'storage') / 'runs' / row.project_id / row.id)
            result['customer_evidence'] = evidence or report.get('customer_opportunities')
    return result
