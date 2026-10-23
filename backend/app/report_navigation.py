"""Lightweight report navigation and month-scoped pairing lookup."""
import calendar
import json

from sqlalchemy import select
from sqlalchemy.orm import defer

from .data_api import require_project
from .models import AnalysisRun
from .quality_api import run_read
from .task_runner import PUBLISHED


def report_catalog(session, project_id):
    require_project(session, project_id)
    rows = session.execute(select(AnalysisRun, AnalysisRun.result.is_not(None).label('has_result'))
        .options(defer(AnalysisRun.result))
        .where(AnalysisRun.project_id == str(project_id), AnalysisRun.kind == 'sales')
        .order_by(AnalysisRun.created_at.desc(), AnalysisRun.id.desc()))
    items = []
    for row, has_result in rows:
        sales = json.loads(row.parameters).get('sales', {})
        if sales.get('check_only'):
            continue
        item = run_read(row)
        item['parameters'] = {'sales': sales}
        item['has_result'] = bool(has_result and row.status in PUBLISHED)
        items.append(item)
    return {'items': items}


def month_scope(month):
    year, number = map(int, month.split('-'))
    return {'date_start': month + '-01',
            'date_end': f'{month}-{calendar.monthrange(year, number)[1]:02}',
            'countries': [], 'item_ids': [], 'currency': None}


def matches_month(quality, sales, version_id, project_id):
    """Only use the same frozen source, month and duplicate policy."""
    context = quality.get('context') or {}
    source = next((s for s in sales.get('sources', []) if s['version_id'] == version_id), None)
    if not source or context.get('project_id') != str(project_id):
        return False
    if context.get('data_version_id') != version_id or context.get('mapping_revision') != source['mapping_revision']:
        return False
    if quality.get('policy', {}).get('duplicates') != sales.get('duplicates'):
        return False
    scope = quality.get('scope') or {}
    # Unbounded historical analyses may include other months; do not silently reuse them.
    return all(scope.get(k) == value for k, value in month_scope(sales['month']).items())


def month_pairings(session, sales_run, version_id, preferred=None):
    sales = json.loads(sales_run.parameters)['sales']
    valid = any(s['version_id'] == version_id for s in sales['sources'])
    if not valid:
        return {'current': None, 'prepared': None, 'basis': None}
    automatic = json.loads(sales_run.parameters).get('auto_analysis')
    if automatic:
        step = automatic['steps']['association']
        quality = session.get(AnalysisRun, step.get('quality_run_id')) if step.get('quality_run_id') else None
        current = session.get(AnalysisRun, step.get('run_id')) if step.get('run_id') else None
        for row in [quality, current]:
            if row and (row.project_id != sales_run.project_id or
                        json.loads(row.parameters).get('automatic_parent', {}).get('sales_run_id') != sales_run.id):
                raise ValueError('Automatic pairing context mismatch')
        return {'current': run_read(current, True) if current else None,
                'prepared': run_read(quality, True) if quality else None,
                'basis': json.loads(quality.result) if quality and quality.result else None,
                'automatic': True}
    checks = session.scalars(select(AnalysisRun).where(
        AnalysisRun.project_id == sales_run.project_id,
        AnalysisRun.dataset_version_id == version_id,
        AnalysisRun.kind == 'quality', AnalysisRun.status.in_(PUBLISHED),
        AnalysisRun.result.is_not(None))
        .order_by(AnalysisRun.finished_at.desc(), AnalysisRun.created_at.desc(), AnalysisRun.id.desc()))
    matching = {}
    for row in checks:
        result = json.loads(row.result)
        if matches_month(result, sales, version_id, sales_run.project_id):
            matching[row.id] = (row, result)
    ready = next(iter(matching.values()), None)
    selected = None
    if matching:
        rows = list(session.scalars(select(AnalysisRun).where(
            AnalysisRun.project_id == sales_run.project_id,
            AnalysisRun.dataset_version_id == version_id,
            AnalysisRun.kind == 'association', AnalysisRun.status.in_(PUBLISHED),
            AnalysisRun.result.is_not(None), AnalysisRun.quality_run_id.in_(matching))
            .order_by(AnalysisRun.finished_at.desc(), AnalysisRun.created_at.desc(), AnalysisRun.id.desc())))
        for row in rows:
            report = json.loads(row.result)
            context = report.get('context') or {}
            parent_context = matching[row.quality_run_id][1]['context']
            if all(context.get(k) == parent_context.get(k) for k in ('project_id', 'data_version_id', 'mapping_revision')) and context.get('quality_run_id') == row.quality_run_id:
                if selected is None or row.id == preferred:
                    selected = row
                if row.id == preferred:
                    break
    basis = matching[selected.quality_run_id][1] if selected else (ready[1] if ready else None)
    return {'current': run_read(selected, True) if selected else None,
            'prepared': run_read(ready[0], True) if ready else None, 'basis': basis}
