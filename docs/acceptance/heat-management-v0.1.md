# Heat Management Core v0.1 - Acceptance Checklist

## Deliverable scope

- [x] Dockerized Heat Management API service
- [x] Database health endpoint
- [x] Heat listing and active-heat query
- [x] Heat detail endpoint
- [x] Heat stage/event timeline endpoint
- [x] Latest live values per heat
- [x] Heat creation against steel-grade master
- [x] Validated lifecycle transition endpoint
- [x] Transition audit event generation
- [x] OpenAPI/Swagger documentation
- [x] Local automated smoke-test script

## Local acceptance commands

```bash
git pull origin main
docker compose up -d --build
docker compose ps
python3 scripts/heat_management_smoke_test.py
```

## Acceptance criterion

The milestone is technically accepted for the local/pre-server environment when:

1. `historian-db` is healthy.
2. `level1-simulator` is running.
3. `heat-management` is healthy.
4. `scripts/heat_management_smoke_test.py` reports `PASS`.
5. `http://localhost:8000/docs` opens successfully.

Plant integration acceptance is separate and requires actual Level 1/Level 3 interfaces and site infrastructure.
