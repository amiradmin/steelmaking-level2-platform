.PHONY: full-heat full-heat-60 full-heat-real full-heat-detached

full-heat:
	./scripts/full_heat_demo.sh --speed 120

full-heat-60:
	./scripts/full_heat_demo.sh --speed 60

full-heat-real:
	./scripts/full_heat_demo.sh --speed 1

full-heat-detached:
	./scripts/full_heat_demo.sh --speed 120 --detach
