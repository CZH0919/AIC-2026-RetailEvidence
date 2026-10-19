"""Read-only verification against existing reports; does not regenerate stored runs."""
import json
import urllib.request
from app.sales_signals import signal_view

cases=[('e1711757-601a-4e9a-a05f-037d7e6909e6','4d3d48c9-b905-41c0-ade5-16470d2b359b','REGENCY CAKESTAND 3 TIER'),
       ('5ebe626d-d769-45b7-a2b8-e45f41525f6a','330217e8-42f4-45d6-81e2-a8061509cb68','NO SINGING METAL SIGN'),
       ('e1711757-601a-4e9a-a05f-037d7e6909e6','e238dad3-6769-4558-b4c1-b05210fe6c96','RABBIT NIGHT LIGHT')]
for pid,rid,name in cases:
    original=json.load(urllib.request.urlopen(f'http://127.0.0.1:8000/api/projects/{pid}/runs/{rid}',timeout=30))['result']
    report=signal_view(original)
    assert [(p['id'],p['quantity'],p['amount']) for p in original['products']]==[(p['id'],p['quantity'],p['amount']) for p in report['products']]
    p=next(p for p in report['products'] if p['name']==name)
    if name=='REGENCY CAKESTAND 3 TIER':
        assert p['change'] is None and p['comparison']['status']=='missing_records'
    if name=='NO SINGING METAL SIGN':
        assert p['quantity']==4 and p['comparison']['previous_quantity']==1030
        assert p['anomaly_check']['status']=='monthly_summary'
    if name=='RABBIT NIGHT LIGHT':
        assert len(p['anomalies'])==6 and p['anomaly_check']['status']=='detected'
    print(json.dumps({'name':name,'comparison':p['comparison'],'anomaly':p['anomaly_check']},ensure_ascii=False))
print('REAL_REPORTS_PASSED: all product quantities and amounts preserved')
