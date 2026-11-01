# CCM R&D PLC — isolated Level 2 integration

## Purpose

This opt-in profile connects only the CCM S7 client in the central OPC UA gateway
to the dedicated Siemens S7-400H R&D PLC. EAF and LF remain connected to their
existing simulators. The gateway performs read-only S7 DB reads; it does not
write to the PLC.

CCM samples are explicitly stored with
`attributes.source_kind = "RND_PLC_TEST"`. They must not be represented as
`REAL_S7` or production measurements.

## Preconditions — do not skip

1. The PLC application and its data blocks must be created and reviewed in a
   compatible, licensed STEP 7 Classic environment.
2. Back up the existing CPU/station project before any download.
3. Verify the physical CCM DB layout against the actual STEP 7 project and the
   PLC's online DBs. The repository's
   `backend/plc_simulators/s7_address_map.json` is simulation-only.
4. Create a separate full gateway map file. Keep the EAF and LF sections for
   their simulators; replace every CCM address/type with the verified physical
   mapping. It must contain the complete logical CCM tag set consumed by the
   central ingestor.
5. Run the read-only probe successfully before starting the integration profile.

The proposed DB300/DB310 layout in
`docs/engineering/CCM_RND_PLC_COMMISSIONING.md` is a proposal, not an uploaded
PLC program or verified address map. Do not use it as a real map until the
application has been reviewed, downloaded under an approved maintenance window,
and read back successfully.

## Configuration

Add these values to the local, uncommitted `.env` file:

```dotenv
CCM_RND_PLC_HOST=192.168.1.10
CCM_RND_PLC_PORT=102
CCM_RND_PLC_RACK=0
CCM_RND_PLC_SLOT=3
CCM_RND_S7_ADDRESS_MAP_FILE=/absolute/path/to/your/verified-full-s7-map.json
```

The map path must be absolute and readable by Docker. Do not commit the actual
site-specific map if it contains sensitive plant information.

Validate the merged Compose configuration:

```bash
docker compose -f docker-compose.yml -f docker-compose.ccm-rnd.yml config --quiet
```

After the STEP 7 project and physical DBs are verified, run the read-only probe
using the same map mounted into the gateway:

```bash
docker compose -f docker-compose.yml -f docker-compose.ccm-rnd.yml run --rm --no-deps central-opcua-server \
  python s7_probe.py --controller CCM --host 192.168.1.10 --port 102 \
  --rack 0 --slot 3 --map /app/s7_address_map.ccm-rnd.json --limit 40
```

Only after every required DB read and decoded tag has been checked against the
STEP 7 project should the live profile be started:

```bash
docker compose -f docker-compose.yml -f docker-compose.ccm-rnd.yml up -d --build \
  central-opcua-server plc-ingestor-central-test level2-api
```

## Verification

Check the central gateway and ingestor logs:

```bash
docker compose -f docker-compose.yml -f docker-compose.ccm-rnd.yml logs --tail=100 central-opcua-server plc-ingestor-central-test
```

Check the System Map at `http://127.0.0.1/#/system-map`. The CCM R&D PLC node
must not show verified/online telemetry merely because TCP/102 is reachable.
It is considered active only when the latest CCM sample is fresh, has
`source_kind=RND_PLC_TEST`, and has GOOD OPC UA quality.

Inspect provenance in TimescaleDB:

```bash
docker compose exec historian-db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "
SELECT pt.tag_name, ps.ts, ps.quality, ps.attributes->>'source_kind' AS source_kind,
       ps.attributes->>'source_endpoint' AS source_endpoint
FROM process_samples ps
JOIN process_tags pt ON pt.id = ps.tag_id
WHERE pt.tag_name LIKE 'CCM.%'
ORDER BY ps.ts DESC
LIMIT 30;"
```

## Roll back to the normal simulator profile

Recreate the affected services using the base Compose file only:

```bash
docker compose -f docker-compose.yml up -d --force-recreate \
  central-opcua-server plc-ingestor-central-test level2-api
```

This restores the normal CCM simulator host, base S7 map, and default sample
provenance. It does not delete historian data or change the PLC.

## Safety boundary

- This profile is opt-in; the normal Compose stack is unchanged.
- Do not combine this overlay with `docker-compose.real-eaf.yml` unless a
  separately reviewed combined profile is designed.
- No PLC writes, forces, output changes, start/stop commands, or downloads are
  performed by this integration.
- Never point the physical CCM at the simulation-only DB map.
- A successful TCP connection is not proof that the application DBs are
  readable, valid, or producing fresh synthetic process data.
