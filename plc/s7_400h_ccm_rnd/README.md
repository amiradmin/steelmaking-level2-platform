# S7-400H CCM R&D application

This folder contains Siemens S7-SCL source for a **standalone synthetic CCM
process demonstration**. It is source code only. It has not been compiled for,
or downloaded to, the physical S7-400H CPU.

## Blocks in the source

| Block | Role |
|---|---|
| OB1 | Cyclic entry point; calls the two R&D function blocks |
| FB300 / generated instance DB301 | Scan-driven synthetic CCM process model; sole writer of DB300 |
| DB300 | 48-byte process-data interface for the Level-2 S7 reader |
| FB310 / generated instance DB311 | Scan counter and heartbeat diagnostics; sole writer of DB310 |
| DB310 | 12-byte diagnostic interface |
| FC300 | Numeric range clamp used by FB300 |

The source is ordered so that shared DBs and FC300 precede the FBs that use them,
and OB1 is last. The S7-SCL V5.x compiler creates the instance DBs when compiling
the calls in OB1.

## Data ownership

When this PLC-native source is used, **the PLC owns DB300 and DB310**. Do not run
ccm_s7_writer.py with --enable-plc-writes at the same time. That would create
two writers and produce nondeterministic values. The Python simulator/writer
remains useful for offline model tests, but its physical write mode is not part
of this PLC-native architecture.

The Level-2 S7 gateway must remain read-only and must use the physical map only
after the compiled DB offsets have been verified on the CPU.

## Synthetic-only semantics

- No physical input/output, marker, timer, counter, motor, drive or actuator
  addresses are referenced by this source.
- No process-control or safety function is implemented.
- The StatusFlags permissive bits are synthetic demonstration states only;
  they do not represent a real emergency-stop chain or real plant interlocks.
- DB310.CycleTimeMs = 0.0 means cycle time is not measured by this source.
- The stage sequence is scan-count based. Its wall-clock duration depends on
  the actual OB1 scan time and is not a real-time guarantee.
- All generated values must be classified in Level-2 as RND_PLC_TEST, never
  as real plant measurements.

## Required commissioning gates — do not skip

The physical CPU has previously shown **STOP (yellow) and EXTF (red)**. The CP
443-1 was also reported with **INTF (red)** and STOP (yellow). The diagnostic
services tested through Snap7 were rejected. These faults are unresolved.

1. Do not attempt a download, MRES, RUN transition, memory reset or hardware
   configuration change while these indications remain unexplained.
2. Have a qualified Siemens PLC engineer identify the CPU and CP diagnostic
   buffer entries and verify the actual rack, power supply, CP configuration,
   firmware compatibility and hardware configuration.
3. Obtain and preserve a complete upload/backup of the existing STEP 7 station
   and all accessible blocks before any change. A Snap7 byte-range backup is
   not a station backup.
4. Confirm the exact STEP 7 / S7-SCL engineering version supports the CPU
   order number and firmware.
5. Import this source into an S7-SCL source folder in a compatible STEP 7
   Classic project. Compile offline first. Resolve every compiler diagnostic.
6. Inspect the compiled block list and generated instance DBs. Verify the
   standard (non-optimized) DB300 and DB310 layouts against DB_LAYOUT.md.
7. Review the resulting hardware configuration and block set with the
   responsible PLC engineer. This source is not a replacement for the
   hardware configuration or a validated H-system project.
8. Only after explicit approval, download the required blocks in a controlled
   maintenance session with a recovery path. Do not overwrite or erase the
   existing station blindly.
9. After download, keep the CPU in the engineer-approved state, read DB300 and
   DB310 back with Snap7, verify byte offsets and sample values, and only then
   connect the read-only Level-2 gateway.

## Important limitation

Python-Snap7 is not the compiler or engineering downloader for this source.
It can read/write accessible DBs, but it does not compile SCL into Siemens
native blocks. A compatible Siemens engineering toolchain is still required.
