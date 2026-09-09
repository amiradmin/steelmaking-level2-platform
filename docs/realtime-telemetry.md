# Realtime Level 1 Telemetry Path

The dashboard realtime path is intentionally decoupled from the physical PLC protocol.

```text
PLC / SCADA / Level 1
        |
        | OPC UA / industrial gateway (future plant-specific adapter)
        v
TimescaleDB historian
  - process_tags
  - process_samples
  - latest_process_values
        |
        v
Django Level 2 API (ASGI / Daphne)
        |
        | JWT-authenticated WebSocket
        | /ws/v1/telemetry
        v
React Level 2 dashboard
```

## Why the dashboard reads the historian

The existing `level1-simulator` writes the same historian schema that a real PLC gateway will use. The frontend therefore does not need to know whether a value came from the simulator, OPC UA, PROFINET middleware, or another Level 1 source.

This also gives the Level 2 application one consistent place to enforce data quality, freshness, heat association, and auditability.

## WebSocket authentication

The browser sends the JWT access token as a WebSocket subprotocol:

```text
Sec-WebSocket-Protocol: level2.jwt, <access-token>
```

The token is not placed in the WebSocket URL, which avoids exposing it in ordinary reverse-proxy URL logs.

## Current realtime tags

The simulator currently produces these historian tags:

- `EAF.PowerMW`
- `EAF.CurrentKA`
- `EAF.OxygenFlow`
- `EAF.SteelTemperature`
- `LF.SteelTemperature`
- `LF.ArgonFlow`
- `CCM.CastingSpeed`
- `CCM.TundishTemperature`

The dashboard consumes the applicable tags directly from the realtime snapshot.

## Freshness policy

`TELEMETRY_STALE_AFTER_SECONDS` defines when the Level 1 link is shown as degraded. The default is 5 seconds.

`TELEMETRY_PUSH_INTERVAL_SECONDS` defines the dashboard push interval. The default is 1 second.

## Next plant-integration phase

The next phase is a dedicated OPC UA gateway. It should:

1. connect to the plant OPC UA server using read-only credentials for the first commissioning stage;
2. map PLC node IDs to `process_tags.tag_name` values through configuration rather than hard-coded application code;
3. preserve source timestamp, server timestamp, engineering unit, and OPC quality/status code;
4. write normalized values to the existing historian schema;
5. implement reconnect/backoff, stale detection, heartbeat, and per-tag diagnostics;
6. keep control/write commands disabled until a separate safety review and interlock design is approved.

The React dashboard and WebSocket contract do not need to change when that gateway replaces the simulator.
