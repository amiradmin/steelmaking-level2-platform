# EAF simulator mode — 2026-11-16

The deployed gateway was already connected to eaf-plc-simulator:102, with PLC_REAL_AREAS unset. The separate physical diagnostics panel was still polling REAL_S7 history and performing physical network probes.

The base Compose API now sets REAL_PLC_ENABLED=0 by default. In this mode:

- The physical latest endpoint returns an authenticated 200 with enabled=false, verified=false, fresh=false, and no values, without querying history.
- Packet diagnostics retain EAF/LF/CCM simulator capture and skip the separate physical probe.
- The map skips physical TCP probing and marks the compatibility node disabled; the new frontend hides it and its flow and skips physical-data polling.
- EAF source metadata correctly labels the source and model as SIMULATOR / S7-400 process simulator.
- Simulator data stays in the existing EAF dashboard and historian paths. It is never marked verified physical data.

The explicit docker-compose.real-eaf.yml override sets REAL_PLC_ENABLED=1, retaining the reviewed physical-source workflow for future use. The current server uses only docker-compose.yml. No database data, retention, or compression changed.

Five isolated SQLite/SimpleTestCase regression tests passed; no production database setup was used. Frontend TypeScript checks and Vite production build passed. API and frontend were recreated; the gateway and EAF simulator continued running.

Live verification: all relevant endpoints returned 200. The disabled physical endpoint took 18 ms (previously a three-second 503); source metadata confirms eaf-plc-simulator:102. Historian returned 27 EAF values with advancing timestamps; EAF dashboard took 53 ms. Packet capture contains EAF, LF, CCM and no REAL entry. Permissions and direct health remained available. API, frontend, Nginx, and OPC UA gateway were healthy.

Refresh the browser to load the new frontend and hide the physical node. Older open clients continue receiving a compatible disabled node and a quick disabled physical-data response.
