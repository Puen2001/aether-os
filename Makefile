# AETHER OS — thin wrapper for the `make` reflex. The real entrypoint is ./aether.
.PHONY: setup doctor reset help

help:
	@./aether help

setup:
	@./aether init

doctor:
	@./aether doctor

reset:
	@./aether reset
