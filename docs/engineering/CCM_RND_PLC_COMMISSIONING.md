# CCM R&D PLC Commissioning Plan

## Purpose and architecture

Build a standalone synthetic CCM process demonstration on the Siemens
S7-400H test CPU. The PLC-native application is authored in Siemens S7-SCL
source under [plc/s7_400h_ccm_rnd](../../plc/s7_400h_ccm_rnd/README.md).

The intended data flow is:

1. OB1 calls FB300 and FB310 cyclically.
2. FB300 generates synthetic CCM process values and is the sole writer of DB300.
3. FB310 updates diagnostic counters and heartbeat and is the sole writer of DB310.
4. The Ubuntu Level-2 S7 gateway reads DB300/DB310 only; it has no PLC write path.
5. The historian and System Map display these values with provenance
   `RND_PLC_TEST`, never `REAL_S7` or actual plant measurements.

The old Ubuntu writer remains available for offline dry-run/packing tests and
read-only DB backup. Its physical write mode is deliberately blocked in the
PLC-native architecture so that there cannot be two competing writers.

## Confirmed hardware and endpoint

| Item | Confirmed value |
|---|---|
| CPU | 1 x Siemens S7-400H CPU 417-4H |
| CPU order number | `6ES7 417-4HT14-0AB0` |
| CPU firmware | `V4.5.5` |
| Ethernet CP | 1 x CP 443-1 |
| CP order number | `6GK7443-1EX20-0XE0` |
| IP endpoint tested | `192.168.1.10:102` |
| Rack / slot used by Snap7 | `0 / 3` |
| Transport | S7 communication over ISO-on-TCP |
| I/O cards | User reports no I/O cards; CPU and communication hardware only |

The CP firmware and hardware revision have not been read from module
diagnostics. The endpoint is reachable by ping and TCP/102 and Snap7 can
establish an S7 connection. This does not prove the CPU is healthy or that
engineering/download services are available.

The CPU previously showed STOP (yellow) and EXTF (red). The CP 443-1 was
reported with INTF (red) and STOP (yellow). Snap7 CPU-info, CPU-state and
protection diagnostics were rejected with service-not-implemented/object-
not-found errors. These faults are unresolved. **Do not attempt MRES, switch
to RUN, change hardware configuration, or download blocks while they remain
unexplained.** A qualified Siemens PLC engineer must inspect the diagnostic
buffer and rack.

The presence of one CPU 417-4H does not establish a complete redundant
S7-400H pair. Do not treat it as a complete H-system without evidence of the
second CPU, synchronization links and complete topology.

## Source block inventory

| Block | Purpose |
|---|---|
| OB1 | Cyclic entry point |
| FB300 / DB301 | Scan-driven synthetic CCM process profile |
| DB300 | 48-byte process data contract |
| FB310 / DB311 | Scan counter and heartbeat diagnostics |
| DB310 | 12-byte diagnostic contract |
| FC300 | Numeric range clamp |

The source order is deliberate: shared DBs and FC300 precede their callers;
OB1 is last. The S7-SCL compiler creates the FB instance DBs for the calls in
OB1. Confirm the generated block list after offline compilation.

## Data contract

The exact proposed standard absolute-address layouts are documented in
[plc/s7_400h_ccm_rnd/DB_LAYOUT.md](../../plc/s7_400h_ccm_rnd/DB_LAYOUT.md).
The layouts are not verified on the physical CPU until the source is compiled,
the resulting DBs are inspected, and the DBs are read back from the CPU.

- DB300: 48 bytes, process values, stage, heat number, status flags and alarm.
- DB310: 12 bytes, scan counter, unmeasured-cycle-time sentinel and status bits.

Do not use the old simulation-only map at
`backend/plc_simulators/s7_address_map.json` as the physical map. A separately
reviewed physical CCM map must match the compiled DBs exactly.

## Synthetic process behavior

FB300 cycles through:

1. IDLE
2. PREPARE
3. START_CAST
4. STEADY_CAST
5. END_CAST
6. Return to IDLE and increment the synthetic heat number.

The sequence is scan-count based. Wall-clock stage duration depends on the
actual OB1 scan time and is not a real-time guarantee. The source does not
claim a measured OB1 cycle time; DB310.CycleTimeMs remains zero to mean
"not measured".

The status/permissive bits are synthetic demonstration values only. In
particular, EmergencyStopOK and InterlockOK are not connected to physical
safety circuits and must never be used as real safety indications.

## Mandatory commissioning gates

### Gate 0 — resolve hardware faults and preserve the station

- Have a qualified Siemens PLC engineer inspect the CPU and CP diagnostic
  buffers, power supply, rack, CP configuration and actual hardware topology.
- Resolve the CPU STOP/EXTF and CP INTF indications before programming.
- Confirm the exact STEP 7 / S7-SCL engineering version supports the CPU
  order number and firmware.
- Obtain a complete upload/backup of the existing STEP 7 station and all
  accessible blocks. A Snap7 byte-range DB backup is not a station backup.
- Do not MRES, erase memory, force RUN or download until a recovery plan and
  the existing station backup are confirmed.

### Gate 1 — offline compile only

- Import `plc/s7_400h_ccm_rnd/CCM_RND.scl` into an S7-SCL source folder in a
  compatible STEP 7 Classic project.
- Compile offline. Resolve every compiler diagnostic; do not assume that
  source text is compiled just because it is committed to GitHub.
- Confirm that the compiler generated OB1, FB300, FB310, FC300, DB300, DB310,
  and instance DB301/DB311.
- Inspect DB300 and DB310 byte offsets, lengths, data types and standard
  (non-optimized) access against DB_LAYOUT.md.
- Review the hardware configuration and complete block set with the
  responsible PLC engineer.

### Gate 2 — controlled download and read-back

- Proceed only after Gate 0 and Gate 1 are formally complete and explicitly
  approved by the responsible PLC engineer.
- Download only the reviewed application blocks during a controlled R&D
  maintenance session with a verified recovery path.
- Do not overwrite the hardware configuration or erase the CPU as a shortcut.
- Keep the CPU in the engineer-approved operating state.
- Read DB300 and DB310 back with Snap7; verify exact lengths, offsets and
  plausible synthetic values before enabling the Level-2 reader.

### Gate 3 — isolated Level-2 integration

- Use the dedicated CCM R&D Compose overlay; normal startup remains unchanged.
- Redirect only the CCM S7 gateway client to the verified physical endpoint
  and the separately reviewed full address map.
- Keep EAF and LF on their existing simulators.
- Keep the gateway read-only.
- Store CCM historian samples with `source_kind=RND_PLC_TEST`.
- Mark the CCM R&D node active only after all 25 logical CCM tags have fresh,
  GOOD-quality samples with the expected provenance.
- Preserve immediate rollback by returning to the base simulator Compose
  configuration.

## Current status

- Dry-run Python CCM process generator: passed.
- TCP/102 reachability and Snap7 connection: passed.
- DB300 and DB310 read: failed because the blocks do not exist.
- Snap7 block inventory: OB=0, FB=0, FC=0, DB=0; system blocks reported.
- CPU STOP/EXTF and CP INTF indications: unresolved.
- Siemens SCL source: committed as source only; not compiled or downloaded.
- Physical DB layout: not yet verified.
- Level-2 physical CCM gateway activation: not authorized yet.

## Siemens language reference

The source follows the S7-SCL language structure for S7-300/S7-400 documented
in the Siemens SIMATIC S7-SCL V5.3 manual, including DB declarations, FB
instances, FCs, OB declarations and SCL block-call syntax:
https://cache.industry.siemens.com/dl/files/793/5581793/att_66783/v1/SCL_e.pdf
