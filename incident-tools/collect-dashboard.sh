#!/usr/bin/env bash
# Read-only collection. Run on ai-server through SSH; no restarts or DDL.
set -u
cd "$HOME/Documents/projects/steelmaking-level2-platform" || exit 1
umask 077
out=$(mktemp -d /tmp/level2-incident.XXXXXX)
exec > >(tee "$out/collection.log") 2>&1
stamp() { date -u +%FT%TZ; }
db() { timeout 15s docker compose exec -T historian-db sh -c 'PGOPTIONS="-c statement_timeout=10000 -c lock_timeout=2000 -c default_transaction_read_only=on" psql -X -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' ; }
activity() {
  stamp
  db <<'SQL'
SELECT clock_timestamp(),pid,application_name,state,query_start,clock_timestamp()-query_start AS age,wait_event_type,wait_event,pg_blocking_pids(pid),left(query,12000) AS query
FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid() AND state IS DISTINCT FROM 'idle' ORDER BY query_start;
SQL
}
stamp
git status --short
git log -5 --oneline
git diff --stat
sha256sum backend/level2_api/api/reports_dashboard.py
docker compose ps -a
docker stats --no-stream
for service in level2-api historian-db nginx frontend; do
  id=$(docker compose ps -q "$service")
  [ -z "$id" ] || docker inspect --format '{{.Name}} {{json .State}}' "$id"
done
activity
docker compose logs --timestamps --since 30m --tail 1500 nginx level2-api > "$out/logs-before.txt" 2>&1
docker compose exec -T level2-api cat /app/api/reports_dashboard.py </dev/null > "$out/deployed-reports.py"
sha256sum "$out/deployed-reports.py"
db > "$out/indexes.txt" <<'SQL'
SELECT schemaname,tablename,indexname,indexdef FROM pg_indexes
WHERE tablename='process_samples' OR schemaname='_timescaledb_internal' ORDER BY schemaname,tablename,indexname;
SELECT n.nspname,c.relname,i.indisvalid,i.indisready,pg_get_indexdef(i.indexrelid)
FROM pg_index i JOIN pg_class c ON c.oid=i.indrelid JOIN pg_namespace n ON n.oid=c.relnamespace
WHERE c.relname='process_samples' OR (n.nspname='_timescaledb_internal' AND c.relname LIKE '%chunk');
SELECT * FROM timescaledb_information.chunks WHERE hypertable_name='process_samples';
SQL
# Extract the actual SQL without importing or invoking the deployed handler.
python3 - "$out/deployed-reports.py" > "$out/explain.sql" <<'PY'
import ast,sys
tree=ast.parse(open(sys.argv[1]).read())
handler=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='reports_dashboard')
calls=sorted((n for n in ast.walk(handler) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='execute'),key=lambda n:n.lineno)
sql=next(n.args[0].value for n in calls if n.args and isinstance(n.args[0],ast.Constant) and isinstance(n.args[0].value,str) and 'process_samples' in n.args[0].value)
assert sql.count('%s')==1, 'Unexpected deployed SQL placeholders; inspect manually'
assert sql.lstrip().upper().startswith(('SELECT','WITH')), 'Expected SELECT'
print('EXPLAIN (VERBOSE, COSTS, SETTINGS) '+sql.replace('%s','24')+';')
PY
if [ -s "$out/explain.sql" ]; then db < "$out/explain.sql" > "$out/explain.txt"; fi
token=''
if (: </dev/tty) 2>/dev/null; then
  printf '\nPaste a valid dashboard ACCESS token (hidden; Enter skips authenticated probes): ' > /dev/tty
  IFS= read -rs token < /dev/tty
  printf '\n' > /dev/tty
fi
# Keep the token out of argv, logs, and the collected directory.
authfile=$(mktemp /tmp/level2-auth.XXXXXX)
trap 'rm -f "$authfile"' EXIT
printf 'Authorization: Bearer %s\n' "$token" > "$authfile"
probe() {
  local name=$1 path=$2 seconds=$3
  stamp
  curl -sS --connect-timeout 3 --max-time "$seconds" -H @"$authfile" -o "$out/$name.body" -w "$name status=%{http_code} total=%{time_total} first_byte=%{time_starttransfer}\n" "http://127.0.0.1$path"
  stamp
}
health() {
  stamp
  timeout 8s docker compose exec -T level2-api python3 -c 'import urllib.request,time,datetime; t=time.monotonic(); print(datetime.datetime.now(datetime.timezone.utc).isoformat(),flush=True); r=urllib.request.urlopen("http://127.0.0.1:8080/health",timeout=5); print(r.status,round(time.monotonic()-t,3),r.read().decode())'
  stamp
}
health
if [ -n "$token" ]; then
  probe auth-before /api/v1/auth/me 7
  # Exactly one Reports request; activity capture starts before the request.
  probe reports '/api/v1/reports/dashboard?limit=24' 25 & report_pid=$!
  for i in 1 2 3; do
    activity > "$out/activity-$i.txt" & activity_pid=$!
    probe "auth-during-$i" /api/v1/auth/me 7 & auth_pid=$!
    health & health_pid=$!
    wait "$activity_pid" "$auth_pid" "$health_pid"
    sleep 2
  done
  wait "$report_pid" 2>/dev/null || true
  probe auth-after /api/v1/auth/me 7
  probe real-eaf '/api/v1/real-plc/latest?area=EAF' 7
else
  printf 'Authenticated probes SKIPPED; no token supplied.\n'
fi
activity > "$out/activity-after.txt"
docker compose logs --timestamps --since 10m --tail 1500 nginx level2-api > "$out/logs-after.txt" 2>&1
docker compose ps -a
stamp
printf 'Evidence saved on ai-server: %s\n' "$out"
printf 'Reports may continue in PostgreSQL after the client timeout; see activity-after.txt. No queries were cancelled.\n'
