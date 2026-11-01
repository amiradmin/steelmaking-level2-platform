# CCM R&D PLC Commissioning Plan

## Purpose and operating boundary

Build a controlled R&D demonstration in which an Ubuntu-hosted synthetic CCM
generator produces continuous-casting values and writes them into two dedicated
data blocks on the physical Siemens S7-400H. The Level-2 gateway reads those
values over S7 communication, exposes them through OPC UA, and the historian
and System Map display them.

These are **Ubuntu-generated R&D test values**, not PLC-generated values or
plant measurements. Their provenance must be stored and displayed as
`RND_PLC_TEST`. They must never be labelled `REAL_S7`, production telemetry,
or actual process measurements.

The PLC is used only as a data-block endpoint. The generator must never write
physical outputs, inputs, markers, timers, counters, or application/control
blocks. The gateway remains read-only. No PLC writes are allowed until the
dedicated DBs have been verified, backed up, reserved, and the explicit write
gate in the integration guide is passed.

## Confirmed hardware and endpoint

| Item | Confirmed value |
|---|---|
| CPU | 1 x Siemens S7-400H CPU 417-4H |
| CPU order number | `6ES7 417-4HT14-0AB0` |
| CPU firmware | `V4.5.5` |
| Ethernet CP | 1 x CP 443-1 |
| CP order number | `6GK7443-1EX20-0XE0` |
| IP endpoint currently tested | `192.168.1.10:102` |
| Rack / slot used by Snap7 | `0 / 3` |
| Transport | S7 communication over ISO-on-TCP |
| I/O cards | User reports no I/O cards; CPU and communication hardware only |

The CP firmware and hardware revision have **not** yet been read from the module
diagnostics. The address `192.168.1.10` is treated as the tested S7 endpoint;
verify that it is the CP interface address before relying on any CP web
diagnostics.

The presence of one CPU 417-4H does not establish a complete redundant S7-400H
pair. Do not configure or commission this as a redundant H-system without
evidence of the second CPU, synchronization links, and the complete H-system
topology.

## Relevant repository findings

- `backend/plc_simulators/ccm_simulator.py` contains the existing correlated
  CCM process profile with PREPARE, START_CAST, STEADY_CAST, and END_CAST stages.
- `backend/plc_simulators/ccm_s7_writer.py` reuses that process model and
  packs its values into the proposed DB300/DB310 byte layout. Its default mode
  is dry-run; PLC writes require an explicit command-line switch and a separate
  DB-layout acknowledgement.
- `backend/plc_simulators/s7_address_map.json` contains a simulation-only
  CCM map. It is **not** a verified physical PLC map and must not be mounted for
  the physical CCM.
- `backend/opcua_gateway/gateway.py` reads absolute S7 DB addresses and
  publishes them to the central OPC UA namespace. It has no write path.
- The CCM R&D Compose overlay redirects only the CCM gateway client to the
  physical endpoint; EAF and LF remain on their existing simulators.
- CCM historian samples must carry `source_kind=RND_PLC_TEST`.

## Proposed S7 data contract (not yet verified on the physical CPU)

The writer expects two existing, dedicated, non-optimized absolute-address
data blocks. These offsets are a proposal for the R&D data contract, not an
assertion that the DBs currently exist or are safe to overwrite.

### DB300 — CCM process data (48 bytes)

| Offset | Tag | S7 type | Unit / meaning |
|---:|---|---|---|
| DBD0 | CastingSpeed | REAL | m/min |
| DBD4 | TundishTemperature | REAL | degC |
| DBD8 | MoldLevelPercent | REAL | % |
| DBD12 | TundishWeightTon | REAL | t |
| DBD16 | MoldCoolingWaterFlowM3h | REAL | m3/h |
| DBD20 | MoldCoolingWaterDeltaC | REAL | degC |
| DBD24 | SecondaryCoolingFlowM3h | REAL | m3/h |
| DBD28 | OscillationFrequencyCpm | REAL | cycles/min |
| DBD32 | StopperPositionPercent | REAL | % |
| DBW36 | StageCode | INT | 0=IDLE, 1=PREPARE, 2=START_CAST, 3=STEADY_CAST, 4=END_CAST |
| DBD40 | HeatNumber | DINT | synthetic heat number |
| DBB44 | StatusFlags | BYTE | bit 0 Ready, 1 Running, 2 Fault, 3 CastingActive, 4 CoolingWaterOK, 5 MoldLevelControlOK, 6 EmergencyStopOK, 7 InterlockOK |
| DBW46 | AlarmCode | INT | 0=none, 301=low cooling water, 302=mold level, 303=E-stop chain, 304=high tundish temperature |

### DB310 — diagnostics (12 bytes)

| Offset | Tag | S7 type | Meaning |
|---:|---|---|---|
| DBD0 | ScanCounter | DINT | incrementing Ubuntu generator counter |
| DBD4 | CycleTimeMs | REAL | measured generator cycle time |
| DBX8.0 | WatchdogOK | BOOL | generator loop within its cycle budget |
| DBX8.1 | CommsOK | BOOL | writer is in PLC-write mode |
| DBX8.2 | Heartbeat | BOOL | toggles every five generator cycles |

The proposed DB layout intentionally differs from the older simulation-only
map. The physical gateway map must be created separately and must match the
verified DB layout exactly.

## Synthetic process behavior

The generator runs on Ubuntu and reuses the project's CCM process model:

1. IDLE: casting speed and oscillation are zero.
2. PREPARE: initialize the synthetic heat and simulated permissives.
3. START_CAST: ramp speed, oscillation, stopper position, and water flows.
4. STEADY_CAST: hold casting speed near target with bounded oscillations;
   tundish weight decreases with time; mold level remains controlled.
5. END_CAST: ramp down speed and oscillation and reduce tundish weight.
6. Return to IDLE and increment the synthetic heat number.

Fault injection is disabled by default and restricted to explicit R&D test
modes. Simulated faults only affect test values and alarms. They never drive
physical outputs.

## Commissioning gates

### Gate 0 — read-only identification

- Confirm the CP interface IP and TCP/102 reachability.
- Read CPU/CP identification, firmware, hardware revision, diagnostic buffer,
  and protection/access settings using available read-only diagnostics.
- Do not infer that successful TCP connection means DB read/write access is
  enabled.

### Gate 1 — read-only DB verification and backup

- Confirm DB300 and DB310 are intended for this R&D test and are not used by
  an existing application.
- Run the writer's `--backup-only` mode. It reads only DB300 bytes 0–47 and
  DB310 bytes 0–11 and saves the raw data, hex, and SHA-256 hashes on Ubuntu.
- Verify the actual DB sizes, offsets, data types, and reservation independently.
  The backup is only a byte-range backup, not a complete STEP 7 project or
  station backup.
- If either DB is missing, inaccessible, protected, or not dedicated to this
  R&D test, stop. Snap7 cannot create Siemens DB blocks or compile PLC code.
  Provisioning missing DBs requires a suitable Siemens engineering tool or
  another verified engineering process.

### Gate 2 — offline generator validation

- Run the writer in its default dry-run mode. It must not connect to the PLC.
- Verify the generated DB300 and DB310 byte layouts against this document and
  the planned physical gateway map.
- Confirm all values are finite, within expected engineering ranges, and
  internally consistent.
- Keep fault injection disabled for initial commissioning.

### Gate 3 — explicitly approved DB writes

- Confirm the DB backup exists on the Ubuntu host.
- Confirm DB300 and DB310 are dedicated, correct, and safe to overwrite.
- Set the exact DB-layout acknowledgement and invoke the writer with
  `--enable-plc-writes`.
- The writer repeats the read-only preflight and saves another pre-write backup
  before writing.
- Write only DB300 bytes 0–47 and DB310 bytes 0–11. Never write to any other
  PLC area.
- Start with a one-shot write, verify via an independent read-only probe, and
  only then consider continuous generation.

### Gate 4 — isolated Level-2 integration

- Use the dedicated CCM R&D Compose overlay; do not modify normal startup or
  EAF/LF simulator configuration.
- Keep EAF and LF on their existing simulators.
- Configure only the CCM S7 client to use the physical endpoint, rack 0,
  slot 3, and a separately reviewed full address map.
- Store CCM samples with `RND_PLC_TEST` provenance, never `REAL_S7`.
- Mark the CCM R&D node active only after all 25 logical CCM tags have fresh,
  GOOD-quality historian samples with the expected provenance.
- Preserve immediate rollback by returning to the base simulator Compose file.

## Immediate next actions

1. Run the Ubuntu writer in dry-run mode to validate the synthetic model and
   byte packing without connecting to the PLC.
2. Run `--backup-only` to test read access to DB300/DB310 and preserve their
   current byte ranges.
3. Verify that both DBs are dedicated to this R&D purpose and that the
   proposed offsets match the physical data blocks.
4. Do not enable writes until those checks are complete and the operator
   explicitly approves the write stage.

## Siemens references

- [S7-400H System Manual](https://cache.industry.siemens.com/dl/files/523/1186523/att_42086/v1/s7_400h_de_de-DE.pdf) — CPU 417-4H family and engineering context.
- [CP 443-1 EX20 Manual](https://cache.industry.siemens.com/dl/files/386/27013386/att_63884/v1/GH_CP443-1-EX20_76.pdf) — order number, firmware variants, and engineering compatibility.
- [Siemens S7 CPs for Industrial Ethernet reference](https://support.industry.siemens.com/cs/attachments/56699406/hy_S7-CPs-IE_76.pdf) — CP 443-1 EX20 module characteristics.
