.PHONY: full-heat full-heat-fast full-heat-60 full-heat-real full-heat-detached eaf-real-probe eaf-real-up

full-heat:
	./scripts/full_heat_demo.sh --speed 120

full-heat-fast:
	./scripts/full_heat_demo.sh --speed 120 --skip-build

full-heat-60:
	./scripts/full_heat_demo.sh --speed 60

full-heat-real:
	./scripts/full_heat_demo.sh --speed 1

full-heat-detached:
	./scripts/full_heat_demo.sh --speed 120 --detach

# Build the gateway image and perform read-only S7 DB reads from the configured
# real EAF PLC. Requires EAF_PLC_HOST in .env. No PLC write operation is used.
eaf-real-probe:
	docker compose --profile plc-multi-test build central-opcua-server
	docker compose -f docker-compose.yml -f docker-compose.real-eaf.yml --profile plc-multi-test run --rm --no-deps central-opcua-server \
		python s7_probe.py --controller EAF

# Use the real S7-400 for EAF while LF and CCM continue using their simulators.
# Recreate Level 2 API as well so Production Flow reports REAL PLC immediately.
eaf-real-up:
	docker compose -f docker-compose.yml -f docker-compose.real-eaf.yml --profile plc-multi-test up -d \
		level2-api central-opcua-server plc-ingestor-central-test
	docker compose restart nginx
