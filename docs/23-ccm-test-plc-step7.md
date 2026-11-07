# CCM test PLC — STEP 7 Classic commissioning

## Target identity

| Parameter | Configured value |
|---|---|
| Process role | CCM test controller |
| PLC family | Siemens S7-400H |
| Firmware reported | V4.5.5 |
| Test PLC IP | 192.168.1.10 |
| S7 communication | ISO-on-TCP, TCP/102 |
| Rack | 0 |
| S7 rack/slot endpoint | 0/3 |
| Communication processor | Siemens CP 443-1 EX20 |
| CP order number | 6GK7 443-1EX20-0XE0 |

The rack/slot pair above is the S7 connection endpoint supplied for this target. Confirm the CPU and CP physical positions in the actual STEP 7 HW Config before connecting. The CP's physical module slot must not be inferred from the S7 endpoint slot.

## Intended engineering approach

Use Siemens STEP 7 Classic (and the compatible S7-SCL package) as the engineering environment. The Git repository stores source, interface definitions and commissioning records; it does not program the PLC by itself.

The existing source in `plc/s7_400h_ccm_rnd/` is a **synthetic R&D demonstration**, not a plant CCM control application. It contains no validated I/O mapping, actuator logic, real process interlocks, safety functions, or approved H-system configuration. Do not present its synthetic permissive/status bits as real signals.

## Network preparation

1. Confirm the engineering PC Ethernet interface is connected to the isolated test PLC network.
2. Assign the PC a free address in the `192.168.1.0/24` subnet (for example `192.168.1.20/24`), after checking that the address is unused. Do not assign `192.168.1.10` to the PC.
3. In STEP 7, select the correct PG/PC interface and Ethernet adapter.
4. Use **Accessible Nodes** to confirm that the expected station is visible.
5. Verify TCP/102 reachability from the engineering host. A successful TCP connection alone does not validate the CPU identity, S7 endpoint, DB map, or safety of a download.

## Mandatory backup and diagnosis gate

Before any programming or download:

- Photograph and record CPU, CP, power-supply and rack/module labels.
- Read the CPU and CP diagnostic buffers and resolve all STOP, EXTF, INTF or other diagnostic indications.
- Upload the complete accessible STEP 7 station and archive the original project, hardware configuration, symbols and blocks. Preserve an untouched copy outside the working project.
- Record the current CPU operating mode and confirm the test PLC is physically isolated from plant actuators and production networks.
- Confirm the STEP 7 and S7-SCL versions support the exact CPU order number and firmware.
- Have the responsible Siemens PLC engineer approve the download plan and recovery procedure.

**Do not perform MRES, change the H-system hardware configuration, force RUN, overwrite blocks, or download while diagnostics are unresolved or a verified backup/recovery plan is unavailable.**

## STEP 7 project workflow

1. Open the archived station in STEP 7 Classic; do not start by creating a replacement station and downloading it.
2. Inspect the actual HW Config. Confirm CPU order number, firmware, rack, slot, CP order number, CP slot, network interface and configured IP.
3. Compare the configured IP with `192.168.1.10`; confirm the CP's Ethernet interface is the interface intended for S7 communication.
4. Inspect the existing block list and cross-references. Determine which blocks own the CCM process data.
5. Import `plc/s7_400h_ccm_rnd/CCM_RND.scl` only into a separate offline copy for the synthetic R&D exercise. Compile offline and review every diagnostic.
6. Verify DB300 and DB310 against `DB_LAYOUT.md` after compilation. Do not assume the declared layout is the physical PLC layout.
7. Do not merge synthetic demonstration blocks into an existing controller application until the responsible PLC engineer has reviewed block numbers, data ownership, scan-time impact, H-system implications and recovery.
8. Download only the explicitly approved blocks in a controlled test session. Keep the controller isolated from real machinery and use an approved safe operating state.
9. Read back the blocks and DBs, verify values/offsets, and record the resulting project version and test evidence.

## Level-2 integration boundary

The Level-2 S7 gateway is **read-only** for this commissioning phase. It may read only documented DBs after their compiled layout and sample values have been independently verified. It must not write process DBs, outputs, markers, control words, setpoints or commands.

The current CCM R&D interface proposes DB300 (48-byte synthetic process data) and DB310 (12-byte diagnostics). These are not confirmed to exist on the physical test PLC until the source is compiled, approved, downloaded and read back. Keep data provenance marked as `RND_PLC_TEST`; do not classify synthetic values as production measurements.

## Connection reference

```env
# Reference values for the CCM test PLC.
# These are documentation values; the current application does not
# automatically consume this file as a live connection configuration.
CCM_TEST_PLC_HOST=192.168.1.10
CCM_TEST_PLC_PORT=102
CCM_TEST_PLC_RACK=0
CCM_TEST_PLC_SLOT=3
CCM_TEST_PLC_FAMILY=S7-400H
CCM_TEST_PLC_FIRMWARE=V4.5.5
CCM_TEST_PLC_CP=6GK7 443-1EX20-0XE0
CCM_TEST_PLC_ACCESS=READ_ONLY
```

## Acceptance checklist

- [ ] Test PLC physically isolated from production equipment/network
- [ ] CPU and CP identity verified from labels and STEP 7 HW Config
- [ ] CPU/CP diagnostic buffers reviewed; no unresolved faults
- [ ] Complete original station uploaded and archived
- [ ] PG/PC interface and IP connectivity verified
- [ ] TCP/102 reachable
- [ ] STEP 7/S7-SCL compatibility confirmed
- [ ] Offline compile completed without errors
- [ ] DB layouts and block ownership independently verified
- [ ] Download approved by responsible PLC engineer
- [ ] Read-back and Level-2 read-only validation completed

## Scope limitation

This commit documents the target and safe engineering workflow. It does not connect to the PLC, upload its current project, compile SCL, generate Siemens loadable blocks, or download/program the controller. Those operations must be performed on the engineering workstation using the compatible Siemens STEP 7 toolchain and on-site authorization.
