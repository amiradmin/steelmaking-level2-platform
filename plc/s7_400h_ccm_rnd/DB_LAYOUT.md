# CCM R&D S7 data-block layout

These are the required **standard absolute-address** layouts for the S7-400H
R&D interface. They are not verified physical DB layouts until the S7-SCL
source is compiled and the resulting blocks are inspected/read back.

## DB300 — process values (48 bytes)

| Byte offset | Address | Field | Siemens type | Meaning |
|---:|---|---|---|---|
| 0 | DBD0 | CastingSpeed | REAL | m/min |
| 4 | DBD4 | TundishTemperature | REAL | degC |
| 8 | DBD8 | MoldLevelPercent | REAL | % |
| 12 | DBD12 | TundishWeightTon | REAL | t |
| 16 | DBD16 | MoldCoolingWaterFlowM3h | REAL | m3/h |
| 20 | DBD20 | MoldCoolingWaterDeltaC | REAL | degC |
| 24 | DBD24 | SecondaryCoolingFlowM3h | REAL | m3/h |
| 28 | DBD28 | OscillationFrequencyCpm | REAL | cycles/min |
| 32 | DBD32 | StopperPositionPercent | REAL | % |
| 36 | DBW36 | StageCode | INT | 0 IDLE, 1 PREPARE, 2 START_CAST, 3 STEADY_CAST, 4 END_CAST |
| 38 | DBW38 | ReservedWord38 | WORD | Reserved; preserves DINT alignment |
| 40 | DBD40 | HeatNumber | DINT | Synthetic heat sequence |
| 44 | DBB44 | StatusFlags | BYTE | Bit field below |
| 45 | DBB45 | ReservedByte45 | BYTE | Reserved |
| 46 | DBW46 | AlarmCode | INT | 0 in this initial no-fault profile |

StatusFlags bits:

| Bit | Meaning |
|---:|---|
| 0 | Ready (synthetic) |
| 1 | Running (synthetic) |
| 2 | Fault (synthetic; currently false) |
| 3 | CastingActive (synthetic) |
| 4 | CoolingWaterOK (synthetic) |
| 5 | MoldLevelControlOK (synthetic) |
| 6 | EmergencyStopOK (synthetic; not a physical E-stop input) |
| 7 | InterlockOK (synthetic; not a physical interlock) |

The initial source writes F1 hex during IDLE/PREPARE and FA hex during casting.
These values are demonstration status only, not safety signals.

## DB310 — diagnostics (12 bytes)

| Byte offset | Address | Field | Siemens type | Meaning |
|---:|---|---|---|---|
| 0 | DBD0 | ScanCounter | DINT | FB310 scan counter |
| 4 | DBD4 | CycleTimeMs | REAL | 0 means not measured |
| 8 | DBX8.0 | StatusBits bit 0 | BOOL | FB310 diagnostic task executed |
| 8 | DBX8.1 | StatusBits bit 1 | BOOL | External communications status; remains false/not measured |
| 8 | DBX8.2 | StatusBits bit 2 | BOOL | Heartbeat |
| 9–11 | DBB9–DBB11 | ReservedBytes | BYTE[3] | Reserved |

## Verification required after compilation

Do not assume the SCL declaration order guarantees these offsets. In the
compiled STEP 7 project and on the target CPU, independently verify:

- DB300 is exactly 48 bytes and all offsets/types match the table.
- DB310 is exactly 12 bytes and all offsets/types match the table.
- DB300 and DB310 are standard (non-optimized) DBs.
- DB301 and DB311 are the instance DBs generated for FB300 and FB310.
- No other application block writes DB300 or DB310.

Only after these checks may the read-only Level-2 gateway use this map.
