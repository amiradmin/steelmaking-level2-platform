# CCM R&D PLC — Ubuntu generator and isolated Level 2 integration

## Architecture

The synthetic process model runs on Ubuntu in the optional
`ccm-rnd-s7-writer` service. It uses Snap7 to write only the dedicated R&D data
blocks DB300 and DB310. The central OPC UA gateway remains read-only and reads
the physical S7 DBs; the ingestor stores CCM samples with
`attributes.source_kind = "RND_PLC_TEST"`.

The writer is disabled by default, is not part of the normal Compose startup,
and defaults to dry-run mode. It never writes outputs, markers, timers, inputs,
or any DB other than DB300 and DB310.

## Hard preconditions

1. Confirm that DB300 and DB310 are dedicated to this R&D test and contain no
   application or production data that must be preserved.
2. Confirm DB300 is at least 48 bytes and DB310 at least 12 bytes.
3. Verify every offset and data type against the actual CPU DB layout. The
   proposed layout is documented in
   `docs/engineering/CCM_RND_PLC_COMMISSIONING.md`; it is not evidence that
   either DB currently exists.
4. Back up the existing PLC data/application before enabling writes.
5. If either DB is missing, inaccessible, protected, or not reserved, STOP.
   Snap7 can write bytes into an existing accessible DB; it cannot create a
   Siemens DB block or compile a PLC program.
6. Keep a separately reviewed full gateway map file. The repository's
   `backend/plc_simulators/s7_address_map.json` is simulation-only and must
   never be used for the physical CCM.

The writer requires both the command-line switch `--enable-plc-writes` and
the exact environment acknowledgement
`CCM_RND_DB_LAYOUT_ACK=DB300_48_DB310_12_VERIFIED_AND_RESERVED`. These are
fail-closed operator guards, not substitutes for inspecting the real DBs.

## Connection settings

Add to the local, uncommitted `.env` file:

```dotenv
CCM_RND_PLC_HOST=192.168.1.10
CCM_RND_PLC_PORT=102
CCM_RND_PLC_RACK=0
CCM_RND_PLC_SLOT=3
CCM_RND_SCAN_SECONDS=1.0
CCM_RND_S7_ADDRESS_MAP_FILE=/absolute/path/to/your/verified-full-s7-map.json
```

Do not set the DB acknowledgement until the DBs have been independently
verified and reserved.

## Stage 1 — dry-run on Ubuntu (no PLC connection, no writes)

Build and run one synthetic sample:

```bash
docker compose -f docker-compose.yml -f docker-compose.ccm-rnd.yml \
  --profile ccm-rnd-writer build ccm-rnd-s7-writer

docker compose -f docker-compose.yml -f docker-compose.ccm-rnd.yml \
  --profile ccm-rnd-writer run --rm ccm-rnd-s7-writer \
  python ccm_s7_writer.py --once
```

This imports the existing CCM process model and packs DB300/DB310 bytes, but
does not connect to the PLC. Review the output before moving to the next stage.

## Stage 2 — explicit write enable (only after DB verification)

First perform a read-only DB probe using the verified map. Confirm that the
actual online DB300 and DB310 match the documented offsets, sizes, and data
types, and that both are dedicated to this R&D writer. Preserve the backup.

Only after those checks and explicit operator approval, set this local
`.env` value:

```dotenv
CCM_RND_DB_LAYOUT_ACK=DB300_48_DB310_12_VERIFIED_AND_RESERVED
```

Then run the writer with the explicit write switch:

```bash
docker compose -f docker-compose.yml -f docker-compose.ccm-rnd.yml \
  --profile ccm-rnd-writer run --rm ccm-rnd-s7-writer \
  python ccm_s7_writer.py --enable-plc-writes --once
```

The writer first reads DB300 (48 bytes) and DB310 (12 bytes), then writes only
those two ranges. A successful one-shot write must be verified with an
independent read-only probe before starting continuous generation.

For continuous generation, omit `--once` but retain
`--enable-plc-writes`. Stop it with Ctrl+C. The writer container has no
automatic restart policy.

## Stage 3 — Level-2 read-only integration

Create a full map file whose CCM entries match the verified physical layout.
Keep EAF and LF entries pointed at their existing simulators. Then validate
the merged Compose configuration:

```bash
docker compose -f docker-compose.yml -f docker-compose.ccm-rnd.yml config --quiet
```

Run the read-only probe:

```bash
docker compose -f docker-compose.yml -f docker-compose.ccm-rnd.yml run --rm --no-deps central-opcua-server \
  python s7_probe.py --controller CCM --host 192.168.1.10 --port 102 \
  --rack 0 --slot 3 --map /app/s7_address_map.ccm-rnd.json --limit 40
```

Only after all mapped values decode correctly, start the Level-2 integration:

```bash
docker compose -f docker-compose.yml -f docker-compose.ccm-rnd.yml up -d --build \
  central-opcua-server plc-ingestor-central-test level2-api
```

Check the System Map at `http://127.0.0.1/#/system-map`. CCM R&D is active
only when all 25 mapped logical CCM tags have fresh GOOD-quality samples with
`source_kind=RND_PLC_TEST`.

## Rollback

Stop the writer first (Ctrl+C if running). Restore the normal simulator-based
Level-2 services using the base Compose file only:

```bash
docker compose -f docker-compose.yml up -d --force-recreate \
  central-opcua-server plc-ingestor-central-test level2-api
```

This does not delete historian data or modify the PLC DB contents.

## Safety boundary

- The standard Compose startup is unchanged.
- The gateway remains read-only.
- The writer's default mode performs no PLC connection or write.
- The writer can access only DB300 and DB310; it has no output/IO write path.
- Do not enable writes unless the DBs are verified, backed up, and reserved.
- Never use the simulation-only address map for the physical PLC.
- Never represent these samples as `REAL_S7` or production measurements.
