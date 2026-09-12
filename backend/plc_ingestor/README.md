# PLC OPC UA Ingestor

This service is the production-facing Level 1 telemetry adapter. It reads configured OPC UA nodes and writes them into the existing `process_samples` historian table so the Django API and realtime WebSocket dashboard can keep using the same data contract.

## Safety / rollout

The service is behind the Docker Compose `plc` profile and is not started by the normal `docker compose up -d` command. Keep `level1-simulator` running while developing. When the real PLC mapping is verified, stop the simulator before enabling PLC ingestion so both sources do not compete for the same logical tags.

## Required configuration

Set these values in `.env`:

```env
PLC_OPCUA_ENDPOINT=opc.tcp://192.168.1.10:4840
PLC_OPCUA_USERNAME=
PLC_OPCUA_PASSWORD=
PLC_POLL_INTERVAL_SECONDS=1
PLC_RECONNECT_DELAY_SECONDS=5
PLC_LOG_LEVEL=INFO
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

## Start and inspect

```bash
docker compose --profile plc build plc-ingestor
docker compose --profile plc up -d plc-ingestor
docker compose logs -f plc-ingestor
```

After the real PLC feed is confirmed, stop the simulator:

```bash
docker compose stop level1-simulator
```

The dashboard continues to consume `/ws/v1/telemetry`; no frontend endpoint change is required.
