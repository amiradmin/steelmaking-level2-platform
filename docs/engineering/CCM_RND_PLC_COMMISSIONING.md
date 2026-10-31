# CCM R&D PLC Commissioning Plan

## Purpose and operating boundary

Build a controlled R&D demonstration in which the physical Siemens PLC generates synthetic continuous-casting values in its own data blocks. The Level-2 gateway reads those values over S7 communication, exposes them through OPC UA, and the historian and System Map display them.

These are **PLC-generated test values**, not plant measurements. Their provenance must be stored and displayed as `RND_PLC_TEST`. They must never be labelled `REAL_S7`, production telemetry, or actual process measurements.

This plan is read-only until the explicit programming gate below is passed. No PLC writes, force operations, memory resets, STOP/RUN transitions, firmware changes, or program downloads are authorized by this document.

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

The CP firmware and hardware revision have **not** yet been read from the module diagnostics. The address `192.168.1.10` is treated as the tested S7 endpoint; verify that it is the CP interface address before relying on any CP web diagnostics.

The presence of one CPU 417-4H does not establish a complete redundant S7-400H pair. Do not configure or commission this as a redundant H-system without evidence of the second CPU, synchronization links, and the complete H-system topology.

## Relevant repository findings

- `backend/plc_simulators/ccm_simulator.py` already contains a correlated CCM profile with PREPARE, START_CAST, STEADY_CAST, and END_CAST stages.
- `backend/plc_simulators/s7_address_map.json` contains a CCM DB300/DB310 layout, but the file explicitly identifies itself as simulation-only. It is **not** a verified physical PLC map and must not be mounted as a real-PLC map.
- `backend/opcua_gateway/gateway.py` can read absolute S7 DB addresses and publish them to the central OPC UA namespace. Its default topology expects EAF, LF, and CCM controllers.
- `docker-compose.real-eaf.yml` demonstrates the existing hybrid real-PLC pattern, but it marks the selected area as `REAL_S7`; that provenance is inappropriate for this R&D simulator.
- `backend/level2_api/api/system_map.py` currently shows the physical CPU as a separate read-only node while the CCM logical node still points to the CCM simulator.
- `backend/level2_api/api/ccm_dashboard.py` already queries the core CCM tags and can display values once the historian receives them.

## Proposed PLC data contract (not yet loaded)

Use a dedicated, non-optimized absolute-address data block for a first commissioning implementation, subject to confirmation in the STEP 7 project and gateway parser. The following layout is a proposal for the new R&D application, not an assertion about existing PLC memory.

### DB300 — CCM process data

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

### DB310 — diagnostics

| Offset | Tag | S7 type | Meaning |
|---:|---|---|---|
| DBD0 | ScanCounter | DINT | incrementing simulation scan counter |
| DBD4 | CycleTimeMs | REAL | measured or nominal simulation cycle time |
| DBX8.0 | WatchdogOK | BOOL | simulation task healthy |
| DBX8.1 | CommsOK | BOOL | reserved for communication diagnostic |
| DBX8.2 | Heartbeat | BOOL | toggles on each simulation tick |

The aligned HeatNumber and status-byte offsets above deliberately differ from the old simulator-only map. The gateway map must be created from this approved contract only after the PLC program is compiled and checked.

## Synthetic process behavior

Generate coherent, bounded values inside the PLC program. Suggested sequence:

1. IDLE: casting speed and oscillation are zero.
2. PREPARE: validate simulated permissives and initialize the heat.
3. START_CAST: ramp speed, oscillation, stopper position, and water flows.
4. STEADY_CAST: hold casting speed near the target with small bounded oscillations; tundish weight decreases with time; mold level remains controlled.
5. END_CAST: ramp down speed and oscillation and reduce tundish weight.
6. Return to IDLE and increment the synthetic heat number.

Fault injection must be disabled by default and restricted to explicit R&D test modes. A simulated fault may set an alarm and a simulated process state, but must not drive physical outputs. There are no I/O cards in this test setup, and the program must not reference physical outputs.

## Engineering and commissioning gates

### Gate 0 — read-only identification (current stage)

- Confirm the CP interface IP and TCP/102 reachability.
- Read CPU and CP identification, firmware, hardware revision, diagnostic buffer, and protection/access settings using supported diagnostic tools.
- Preserve the results in the commissioning record.
- Do not infer that a successful TCP connection means DB read access is enabled.

### Gate 1 — engineering environment and backup

- Obtain a licensed, compatible Siemens STEP 7 Classic engineering environment and the matching hardware catalog/HSP.
- Siemens documentation for this CPU family identifies STEP 7 V5.3 SP2 with the relevant hardware update as a baseline for the CPU; CP 443-1 EX20 documentation identifies STEP 7 V5.4 SP3 or later for H-connection functionality. Select the installed STEP 7 release only after checking the exact CPU/CP firmware and project requirements.
- Upload and archive the existing station configuration and blocks before any modification. If upload/backup is not possible, stop and resolve the access/ownership issue before proceeding.
- Record a recoverable backup and a rollback plan.

### Gate 2 — offline application preparation

- Create a separate STEP 7 project for this R&D device.
- Verify rack/slot configuration, CP network interface, CPU operating mode, memory/protection settings, and the existing block inventory.
- Add only the required data blocks and simulation logic in the offline project.
- Compile and inspect all blocks; verify there are no references to physical I/O.
- Validate the absolute DB layout against the gateway parser and a generated address-map test.

### Gate 3 — approved download and validation

No download is allowed until the user explicitly approves a documented maintenance window and confirms the backup. Download only the reviewed application/configuration. Confirm CPU state and diagnostics before and after the operation. Validate DB values locally using STEP 7 before enabling gateway reads.

### Gate 4 — isolated Level-2 integration

- Add a dedicated CCM R&D compose overlay; do not modify normal startup or EAF/LF simulator configuration.
- Keep EAF and LF on their existing simulators.
- Configure only the CCM S7 client to use the physical endpoint, rack 0, slot 3, and the reviewed CCM DB map.
- Add a distinct provenance value `RND_PLC_TEST` in the ingestor; do not reuse the current `PLC_REAL_AREAS` mechanism, which labels samples `REAL_S7`.
- Change the System Map CCM flow from the CCM simulator to the physical R&D PLC only after successful GOOD-quality DB reads and fresh historian samples with `RND_PLC_TEST` provenance.
- Preserve an immediate rollback path by omitting the dedicated overlay.

## Immediate next actions

1. Run read-only network checks for TCP/102 and optional HTTP/HTTPS diagnostics on the confirmed endpoint.
2. Read the CP firmware/hardware revision using STEP 7 module diagnostics or the CP web diagnostics if enabled.
3. Confirm the STEP 7 engineering workstation/license availability.
4. Complete Gate 0 and Gate 1 before generating the final importable PLC source or downloading any block.

## Siemens references

- [S7-400H System Manual](https://cache.industry.siemens.com/dl/files/523/1186523/att_42086/v1/s7_400h_de_de-DE.pdf) — CPU 417-4H family and STEP 7 engineering context.
- [CP 443-1 EX20 Manual](https://cache.industry.siemens.com/dl/files/386/27013386/att_63884/v1/GH_CP443-1-EX20_76.pdf) — order number, firmware variants, and STEP 7 compatibility.
- [Siemens S7 CPs for Industrial Ethernet reference](https://support.industry.siemens.com/cs/attachments/56699406/hy_S7-CPs-IE_76.pdf) — CP 443-1 EX20 module characteristics.
