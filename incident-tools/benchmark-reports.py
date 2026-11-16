# Stage the saved deployed baseline at /tmp/reports-before.py and candidate at /tmp/reports-proposed.py inside the API container.
import ast,json,time,os
os.environ.setdefault('DJANGO_SETTINGS_MODULE','level2_project.settings')
import django
django.setup()
from django.db import connection,transaction

def query(path):
 tree=ast.parse(open(path).read()); f=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='reports_dashboard')
 return sorted((n for n in ast.walk(f) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='execute' and n.args and isinstance(n.args[0],ast.Constant) and 'process_samples' in str(n.args[0].value)),key=lambda n:n.lineno)[0].args[0].value
old=query('/tmp/reports-before.py');new=query('/tmp/reports-proposed.py')
with transaction.atomic(),connection.cursor() as c:
 c.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
 c.execute("SET LOCAL statement_timeout='10s'")
 expected=None
 for name,sql,jit in [('old',old,True),('new',new,True),('new-no-jit',new,False),('old-no-jit',old,False),('new-no-jit-repeat',new,False),('old-repeat',old,True)]:
  c.execute('SET LOCAL jit = '+('on' if jit else 'off'))
  t=time.monotonic();c.execute(sql,[24]); rows=c.fetchall();elapsed=time.monotonic()-t
  # The limited heat ordering has ties: compare by heat ID, preserving every calculated value.
  values=sorted(rows,key=lambda r:r[0]);expected=values if expected is None else expected
  assert values==expected, 'Report calculations differ'
  print(json.dumps({'variant':name,'seconds':round(elapsed,3),'heats':len(rows),'identical':True}),flush=True)
