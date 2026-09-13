# Real Siemens S7-400 EAF Commissioning

This project can replace the EAF simulator with a real Siemens S7-400 while LF and CCM remain simulated.

## Architecture

```text
Real Siemens S7-400 EAF
    ISO-on-TCP / S7 classic / TCP 102
                |
                v
Central OPC UA Gateway
    python-snap7, read-only DB reads
                |
                v
Normalized OPC UA namespace
                |
                v
PLC Ingestor -> Historian -> Level 2 API -> Operator UI

LF PLC Simulator ----------------------^
CCM PLC Simulator ---------------------^
```

The gateway never writes process values to the real PLC in this mode. It uses `db_read` only.

## 1. Collect the real PLC connection data

From STEP 7 / HW Config obtain:

- PLC IP address
- Rack number
- Slot number
- reachable TCP port 102
- actual DB numbers and offsets for the signals needed by Level 2
- Siemens data types (`REAL`, `INT`, `DINT`, `BOOL`)

Do not assume the simulator DB addresses match the plant PLC.

## 2. Configure `.env`

Example only:

```env
EAF_PLC_HOST=192.168.10.40
EAF_PLC_PORT=102
EAF_PLC_RACK=0
EAF_PLC_SLOT=2
S7_ADDRESS_MAP_FILE=./backend/plc_simulators/s7_address_map.json
```

Use the actual rack/slot from the PLC hardware configuration.

## 3. Prepare the real DB map

The default file is simulation-only:

```text
backend/plc_simulators/s7_address_map.json
```

Create a reviewed commissioning copy before connecting production data, for example:

```text
config/plc/s7_address_map.plant.json
```

Then set:

```env
S7_ADDRESS_MAP_FILE=./config/plc/s7_address_map.plant.json
```

The JSON must still contain `EAF`, `LF`, and `CCM`. LF and CCM can keep the simulator mappings while EAF is changed to the real plant DB layout.

Example EAF mapping shape:

```json
{
  "EAF": {
    "process_db": 100,
    "diagnostic_db": 110,
    "tags": {
      "EAF.PowerMW": {"address": "DB100.DBD0", "type": "REAL"},
      "EAF.StageCode": {"address": "DB100.DBW26", "type": "INT"},
      "EAF.HeatNumber": {"address": "DB100.DBD28", "type": "DINT"},
      "EAF.Running": {"address": "DB100.DBX32.1", "type": "BOOL"}
    }
  }
}
```

Replace those example addresses with the actual plant DB addresses.

## 4. Build the gateway once

```bash
docker compose --profile plc-multi-test build central-opcua-server
```

## 5. Perform a read-only PLC probe

```bash
make eaf-real-probe
```

The probe:

- connects to the configured S7 endpoint
- performs S7 DB reads only
- does not write any PLC memory
- prints readable DBs and a small decoded sample

Expected shape:

```text
=== READ-ONLY S7 PROBE ===
Controller: EAF
Target:     192.168.10.40:102
Rack/Slot:  0/2
Mode:       DB READ ONLY (no PLC writes)

PASS: DB100 readable (... bytes)
...
PASS: S7 PLC connection and configured DB reads succeeded.
```

If connection succeeds but decoded values are clearly wrong, stop and correct the DB map before using the gateway.

## 6. Run EAF from the real PLC

```bash
make eaf-real-up
```

This uses:

```text
docker-compose.yml
docker-compose.real-eaf.yml
```

The gateway source for EAF becomes the real `EAF_PLC_HOST`. LF and CCM continue to come from their simulators.

The EAF simulator container may still be running, but the gateway does not use it while the real-EAF override is active.

## 7. Verify the gateway

```bash
docker compose -f docker-compose.yml -f docker-compose.real-eaf.yml \
  --profile plc-multi-test logs --tail=100 central-opcua-server
```

Look for:

```text
Connecting to EAF S7 endpoint <real-ip>:102 rack=<rack> slot=<slot>
Connected to EAF S7 PLC
```

## 8. Verify historian data

```bash
docker compose exec historian-db psql -U level2 -d steelmaking_level2 -c "
SELECT DISTINCT ON (pt.tag_name)
  pt.tag_name,
  COALESCE(ps.value_double::text, ps.value_text) AS value,
  ps.quality,
  ps.ts,
  ps.attributes->>'source' AS source
FROM process_samples ps
JOIN process_tags pt ON pt.id = ps.tag_id
WHERE pt.tag_name LIKE 'EAF.%'
ORDER BY pt.tag_name, ps.ts DESC;
"
```

The Level 2 UI, Historian and Production Flow do not need to know whether EAF came from the simulator or the real PLC.

## Rollback to simulation

Stop using the override and start the normal simulator profile again. No database reset is required.

## Safety notes

- Keep commissioning read-only until the PLC team explicitly approves any future writes.
- Do not test unknown DB addresses by writing values.
- Confirm IP, rack, slot and DB offsets against STEP 7 documentation or the PLC program.
- Prefer a dedicated industrial network/VLAN and firewall rules allowing only the required Level 2 host to reach TCP/102.
- A successful TCP connection does not prove that the DB map is correct; validate values with the PLC engineer/operator.
