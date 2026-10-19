import json
import time
import urllib.request
import os
from pathlib import Path
from app.sales_signals import signal_view
from app.sales_focus import focus_view

pid='e1711757-601a-4e9a-a05f-037d7e6909e6'
rid='e238dad3-6769-4558-b4c1-b05210fe6c96'
r=json.load(urllib.request.urlopen(f'http://127.0.0.1:8000/api/projects/{pid}/runs/{rid}'))['result']
output=Path('/home/ubuntu/AIC_Project')/os.environ.get('AIC_STORAGE_DIR','storage')/'runs'/pid/rid
before=[(p['id'],p['quantity'],p['amount']) for p in r['products']]
start=time.monotonic();view=focus_view(signal_view(r),output)
print('first_read_seconds',round(time.monotonic()-start,3))
assert [(p['id'],p['quantity'],p['amount']) for p in view['products']]==before
assert view['highlights']==focus_view(signal_view(r))['highlights']
for key,text in [('23084','一笔订单购买 2,400'),('22273','两笔订单各购买 720')]:
    p=next(p for p in view['products'] if p['id']==key)
    assert p['focus']['label']=='大批量订单带动'
    assert text in p['focus_reason']
    print(p['name'],p['focus_reason'])
start=time.monotonic();assert focus_view(signal_view(r),output)==view
print('cached_read_seconds',round(time.monotonic()-start,3))
print('REAL_ORDER_FOCUS_PASSED')
