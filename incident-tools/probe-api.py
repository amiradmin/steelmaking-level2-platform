import os, json, time, datetime, threading, urllib.request, urllib.error
os.environ.setdefault('DJANGO_SETTINGS_MODULE','level2_project.settings')
import django
django.setup()
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import AccessToken
user=get_user_model().objects.get(username=os.environ.get('DJANGO_BOOTSTRAP_USERNAME','OP-4109'))
assert user.is_active
headers={'Authorization':'Bearer '+str(AccessToken.for_user(user))}
def probe(name,path,base='http://127.0.0.1:8080',timeout=6):
    start=time.monotonic(); stamp=datetime.datetime.now(datetime.timezone.utc).isoformat()
    try:
        r=urllib.request.urlopen(urllib.request.Request(base+path,headers=headers),timeout=timeout)
        body=json.loads(r.read()); result={'status':r.status}
        if name.startswith('auth'): result['permissions']=body.get('permissions')
        elif name=='reports': result.update(summary=body.get('summary'),heat_count=len(body.get('heats',[])))
        elif name=='eaf': result['body']=body
    except urllib.error.HTTPError as e: result={'status':e.code,'body':e.read().decode()[:2000]}
    except Exception as e: result={'error':str(e)}
    print(json.dumps({'at':stamp,'name':name,'seconds':round(time.monotonic()-start,3),**result}),flush=True)
probe('auth-before','/api/v1/auth/me',base='http://nginx')
probe('health-before','/health')
if os.environ.get('PROBE_REPORTS')=='1':
    t=threading.Thread(target=probe,args=('reports','/api/v1/reports/dashboard?limit=24','http://nginx',30)); t.start()
    overview=threading.Thread(target=probe,args=('overview','/api/v1/overview-live','http://nginx',20)); overview.start()
    for i in range(5):
        time.sleep(2)
        a=threading.Thread(target=probe,args=(f'auth-{i}','/api/v1/auth/me','http://nginx'))
        h=threading.Thread(target=probe,args=(f'health-{i}','/health'))
        a.start(); h.start(); a.join(); h.join()
    t.join(); overview.join()
probe('eaf','/api/v1/real-plc/latest?area=EAF','http://nginx')
