"""Read-only review of highlight selection on published reports."""
import json
import time
import urllib.request
from app.sales_signals import signal_view
from app.sales_focus import focus_view, merchandise

cases=[('e1711757-601a-4e9a-a05f-037d7e6909e6','e238dad3-6769-4558-b4c1-b05210fe6c96'),
       ('5ebe626d-d769-45b7-a2b8-e45f41525f6a','330217e8-42f4-45d6-81e2-a8061509cb68'),
       ('e1711757-601a-4e9a-a05f-037d7e6909e6','4d3d48c9-b905-41c0-ade5-16470d2b359b')]
for pid,rid in cases:
    original=json.load(urllib.request.urlopen(f'http://127.0.0.1:8000/api/projects/{pid}/runs/{rid}',timeout=30))['result']
    normalized=signal_view(original)
    start=time.monotonic();view=focus_view(normalized);elapsed=time.monotonic()-start
    assert len(view['highlights'])<=5 and len(set(view['highlights']))==len(view['highlights'])
    assert [(p['id'],p['quantity'],p['amount']) for p in original['products']]==[(p['id'],p['quantity'],p['amount']) for p in view['products']]
    assert view['summary']==normalized['summary'] and view['actions']==normalized['actions']
    products={p['id']:p for p in view['products']}
    assert all(merchandise(products[k]) for k in view['highlights'])
    print(json.dumps({'run':rid,'month':view['month'],'selection_seconds':round(elapsed,3),'highlights':[
        {'id':k,'name':products[k]['name'],'amount':products[k]['amount'],'label':products[k]['focus']['label'],'reason':products[k]['focus_reason']}
        for k in view['highlights']]},ensure_ascii=False))
print('REAL_HIGHLIGHTS_PASSED')
