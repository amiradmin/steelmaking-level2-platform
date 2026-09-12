# PLC OPC UA Ingestor

This service is the production-facing Level 1 telemetry adapter. It reads configured OPC UA nodes and writes them into the existing `process_samples` historian table so the Django API and realtime WebSocket dashboard can keep using the same data contract.

## Runtime model

`plc-ingestor` is an independent Docker Compose service. The Python process owns OPC UA connectivity, reconnect logic, tag mapping, data-quality conversion, heat association and Historian writes. Docker owns process lifecycle and container health monitoring.

The current implementation uses polling. Each read stores the OPC UA source/server timestamp when available and maps the OPC UA `StatusCode` to the Historian quality values `GOOD`, `UNCERTAIN`, `BAD` or `UNKNOWN`.

## Safety / rollout

The service is behind the Docker Compose `plc` profile and is not started by the normal `docker compose up -d` command. Keep `level1-simulator` running while developing. When the real PLC mapping is verified, stop the simulator before enabling PLC ingestion so both sources do not compete for the same logical tags.

## Required configuration

Copy the required values from `.env.plc.example` into the project's local `.env` file. Do not commit real PLC credentials.

```env
PLC_OPCUA_ENDPOINT=opc.tcp://192.168.1.10:4840
PLC_OPCUA_USERNAME=
PLC_OPCUA_PASSWORD=
PLC_POLL_INTERVAL_SECONDS=1
PLC_RECONNECT_DELAY_SECONDS=5
PLC_LOG_LEVEL=INFO
PLC_HEALTH_STALE_AFTER_SECONDS=15
PLC_NODE_MAP_JSON={"EAF.PowerMW":"ns=2;s=EAF.PowerMW","EAF.CurrentKA":"ns=2;s=EAF.CurrentKA"}
```

`PLC_NODE_MAP_JSON` maps existing Level 2 `process_tags.tag_name` values to real OPC UA Node IDs. The currently seeded logical tags are:

- `EAF.PowerMW`
- `EAF.CurrentKA`
- `EAF.OxygenFlow`
- `EAF.SteelTemperature`
- `LF.SteelTemperature`
- `LF.ArgonFlow`
- `CCM.CastingSpeed`
- `CCM.TundishTemperature`

## Build

```bash
docker compose --profile plc config --quiet
docker compose --profile plc build plc-ingestor
```

## Start and inspect

Only start the production adapter after the endpoint and node mapping have been configured:

```bash
docker compose --profile plc up -d plc-ingestor
docker compose ps plc-ingestor
docker compose logs -f plc-ingestor
```

A healthy container means a successful OPC UA read has occurred recently, not merely that the Python process is still running.

After the real PLC feed is confirmed, stop the simulator:

```bash
docker compose stop level1-simulator
```

The dashboard continues to consume `/ws/v1/telemetry`; no frontend endpoint change is required.

## Historian verification

Use the existing API/dashboard or inspect the latest samples in PostgreSQL. Values written by this adapter have `attributes.source = OPCUA` and include the configured OPC UA Node ID and StatusCode.

## Next production hardening

When the factory endpoint details are known, add the site's required OPC UA security policy/certificates and decide whether the PLC server supports subscriptions/change-of-value well enough to replace polling for high-rate tags.
