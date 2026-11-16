# Performance improvements — 2026-11-16

Deployed on ai-server around 14:29–14:30 Tehran time, following the overview outage fix.

## Reports

The existing deployed limit-before-aggregates patch is preserved. Combine sample count, GOOD sample count, and average GOOD EAF power into one lateral scan per selected heat. process_tags.tag_name is unique, so scalar tag lookup preserves join semantics. All other calculations and permission checks remain unchanged.

Use SET LOCAL jit = off inside transaction.atomic for this interactive handler. PostgreSQL compilation overhead was material; the setting automatically reverts when the transaction exits. A direct deployed-handler check confirmed the connection's JIT policy was on before and after the request.

Bounded read-only repeatable-read benchmark, same 24 heats and all result columns identical:

| Query | Seconds |
| --- | ---: |
| Original | 2.246 |
| Combined aggregates | 0.558 |
| Combined, JIT off | 0.120 |
| Original, JIT off | 1.200 |
| Combined, JIT off, repeat | 0.123 |
| Original, repeat | 2.176 |

Authenticated HTTP verification after deployment: Reports 200 in 0.189 seconds; overview concurrently 200 in 0.967 seconds. Repeated permissions and direct health checks remained 200 in 19–31 ms. Anonymous and expired-token Reports requests returned 401. No authorization or data caching was added.

## Frontend transfer

Enable gzip in the gateway's frontend location for HTML/CSS/JavaScript/SVG. API locations remain outside this setting. Main JavaScript: 384,505 bytes uncompressed, 101,443 bytes gzip (73.6% smaller). Decompression produced exactly the original bytes; Vary: Accept-Encoding is present.

Nginx's file bind mount retained the old inode after the source patch, so a reload initially saw the old configuration. The proposed configuration was validated independently inside the container, then only Nginx was recreated to refresh the mount. Final API and gateway health: healthy.

## Scope and remaining work

No retention, compression of database chunks, indexes, schema changes, frontend polling changes, or user/session state changes. The EAF physical-source query still returns its bounded three-second 503 and needs separate optimization. This work improves the measured Reports and frontend-transfer paths; it does not establish a speedup for every endpoint or cold-storage scenario.

Existing server hotfixes and the prior overview fix are preserved. Local Reports now also includes the server's existing heat-selection fix; avoid reverting it when synchronizing branches. See evidence/reports-benchmark.jsonl and evidence/performance-verification.jsonl for timings (gitignored).
