# EAF S7-400H Level 2 test program

This handoff package is for the isolated laboratory PLC:

- CPU: Siemens S7-400H CPU 417-4H
- Order number: `6ES7 417-4HT14-0AB0`
- Firmware: `V4.5.5`
- Ethernet CP: CP 443-1, `6GK7 443-1EX20-0XE0`, firmware `V2.1`
- Endpoint: `192.168.1.10:102`, rack `0`, slot `3`

## What the program does

`EAF_LEVEL2_TEST.awl` creates `DB100`, `DB110`, and `OB1`. It generates a repeating 65-second EAF test cycle with stages CHARGE, MELTING, REFINING, SUPERHEAT, and TAPPING. The Heat Number increments after every cycle. A heartbeat toggles approximately once per second.

The program never accesses input, output, peripheral input, or peripheral output addresses. It does not contain `I`, `Q`, `PI`, or `PQ` process control logic. All generated values remain in `DB100` and `DB110` and are intended to be read by the Level 2 gateway.

## Required backup

Before compiling or downloading anything:

1. Open STEP 7 Classic / SIMATIC Manager.
2. Set the PG/PC interface to the Ethernet adapter connected to `192.168.1.0/24`.
3. Use `PLC > Upload Station to PG` and save the uploaded station as a separate backup.
4. Save the CPU and CP diagnostic buffers.
5. Do not use MRES.

An earlier read-only inspection reported no user OB, FB, FC, or DB blocks, but the online backup is still mandatory.

## Import and compile

1. Open the uploaded project or create an S7 project for the test rack.
2. Under the S7 Program, select `Sources`.
3. Use `Insert New Object > External Source` and select `EAF_LEVEL2_TEST.awl`.
4. Open the imported source and run `File > Compile`.
5. Confirm that the compiler creates `OB1`, `DB100`, and `DB110` without errors.
6. Verify the compiled DB offsets against `EAF_LEVEL2_TAG_MAP.csv`.

If any of `OB1`, `DB100`, or `DB110` already exists online, stop and compare it with the backup before overwriting it.

## Download scope

Put the CPU in STOP and download only these three blocks:

- `OB1`
- `DB100`
- `DB110`

Do not download HW Config, NetPro, or System Data as part of this test. Keeping the existing CP configuration preserves the known IP address.

After download, monitor `DB100` and `DB110` online. If the values are correct, put the CPU in RUN. If the CPU does not remain in RUN, return it to STOP and inspect the Diagnostic Buffer; do not perform MRES.

Expected online behavior:

- `DB110.DBD0` increases every OB1 scan.
- `DB110.DBX8.2` toggles approximately every second.
- `DB100.DBW26` cycles through stage codes 1 to 5.
- `DB100.DBD12` changes with the simulated stage.
- `DB100.DBD28` increments after each 65-second cycle.

## Level 2 gateway configuration

Set the following values in the repository `.env` file:

```dotenv
EAF_PLC_HOST=192.168.1.10
EAF_PLC_PORT=102
EAF_PLC_RACK=0
EAF_PLC_SLOT=3
S7_ADDRESS_MAP_FILE=./backend/plc_simulators/s7_address_map.json
```

Run the read-only probe first:

```bash
make eaf-real-probe
```

Only after the probe reads DB100 and DB110 successfully, switch the EAF gateway to the real PLC:

```bash
make eaf-real-up
```

The gateway performs S7 read requests only. No custom application-level request frame or PLC write is required for this test program.

## Rollback

1. Put the CPU in STOP.
2. Restore the uploaded backup if restoration is required by the lab owner.
3. On the Level 2 host, start the normal Compose stack without `docker-compose.real-eaf.yml` to return EAF to its simulator.
