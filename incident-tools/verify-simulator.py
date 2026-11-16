import os,json,time,datetime,urllib.request
os.environ.setdefault('DJANGO_SETTINGS_MODULE','level2_project.settings')
import django
django.setup()
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import AccessToken
from django.db import connection
u=get_user_model().objects.get(username=os.environ.get('DJANGO_BOOTSTRAP_USERNAME','OP-4109'))
headers={'Authorization':'Bearer '+str(AccessToken.for_user(u))}
def get(path):
 t=time.monotonic()
 with urllib.request.urlopen(urllib.request.Request('http://nginx'+path,headers=headers),timeout=6) as r:
  data=json.loads(r.read()); print(path,r.status,round(time.monotonic()-t,3),'seconds',flush=True);return data
source=get('/api/v1/plc-sources')['sources']['EAF'];assert source['source']=='simulator';print(json.dumps(source))
physical=get('/api/v1/real-plc/latest?area=EAF');assert physical['enabled'] is False and not physical['verified'];print(json.dumps(physical))
mapdata=get('/api/v1/system-map');node=next(n for n in mapdata['nodes'] if n['id']=='real-plc');assert node['enabled'] is False;assert not any(f['from']=='real-plc' for f in mapdata['flows'])
packets=get('/api/v1/plc-packets?limit=2');assert 'REAL' not in packets['controllers'];assert 'EAF' in packets['controllers'];print('packet sources:',list(packets['controllers']))
for i in range(2):
 values=get('/api/v1/historian/latest?area=EAF');assert values;print('EAF values:',len(values),'newest:',max(v['ts'] for v in values if v.get('ts')))
 get('/api/v1/auth/me')
 with urllib.request.urlopen('http://127.0.0.1:8080/health',timeout=3) as r:assert r.status==200
 if i==0:time.sleep(2)
get('/api/v1/eaf/dashboard')
with connection.cursor() as c:
 c.execute("SELECT ps.ts, ps.quality::text, ps.attributes->>'source_kind', ps.attributes->>'source_endpoint' FROM process_tags pt CROSS JOIN LATERAL (SELECT ts,quality,attributes FROM process_samples WHERE tag_id=pt.id ORDER BY ts DESC LIMIT 1) ps WHERE pt.tag_name='EAF.PowerMW'")
 print('latest EAF.PowerMW provenance:',c.fetchone())
