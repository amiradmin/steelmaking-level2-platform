# Central OPC UA Gateway

This service provides the single OPC UA endpoint consumed by the Steelmaking Level 2 platform.

For the integration-test architecture it connects to the three S7-400-style simulators over classic S7/TCP:

- EAF simulator — S7 TCP/102
- LF simulator — S7 TCP/102
- CCM simulator — S7 TCP/102

It reads the project-defined S7 data-block map, decodes the values, and republishes them under one OPC UA namespace.

## Test flow

```text
EAF S7 simulator ----\
LF S7 simulator ------> Central OPC UA Server -> PLC Ingestor -> Historian
CCM S7 simulator ----/
```

## OPC UA endpoint

Inside Docker:

```text
opc.tcp://central-opcua-server:4840/steelmaking/
```

From the host by default:

```text
opc.tcp://localhost:4845/steelmaking/
```

## S7 connection defaults

The gateway uses the classic S7 client with rack `0`, slot `2`, and TCP port `102` for each simulated S7-400 domain. All settings can be overridden with environment variables.

## Data quality

When a PLC connection is healthy, values are published with OPC UA `Good` quality and current source timestamps.

If an S7 connection fails, the last known values are retained but published with `BadNoCommunication`. The gateway keeps retrying the PLC connection independently, so one failed controller does not stop the other two domains.

## Address map

The gateway consumes the same simulation address map as the PLC simulators:

```text
backend/plc_simulators/s7_address_map.json
```

The current DB addresses are simulation-only. When the real plant DB map is available, the tag-to-address map can be replaced without changing the logical Level 2 tag names.
