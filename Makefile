# The local blocking gate's single entry point for the nextpnr fork (C8,
# D77, P0.T41-T42). This is a NEW file (F88: nextpnr is CMake-only, no root
# Makefile existed) -- it must not shadow or interfere with the out-of-tree
# `build/` directory P0.T09 configures and builds from.
#
# `pre-commit`, `pre-push` and a human/agent typing `make gate` all invoke
# this same target -- there is exactly one definition of "green".

include gate.env

GATE_SCOPE ?= fast

.PHONY: gate _gate-fast _gate-full _gate-all

gate:
	@case "$(GATE_SCOPE)" in \
	  fast) $(MAKE) --no-print-directory _gate-fast ;; \
	  full) $(MAKE) --no-print-directory _gate-full ;; \
	  all)  $(MAKE) --no-print-directory _gate-all ;; \
	  *) echo "GATE $(GATE_SCOPE): unknown GATE_SCOPE (legal: fast full all)"; exit 1 ;; \
	esac

# The gowin himbaechel uarch has no unit-test infra yet (P0.T38 deviation:
# "nextpnr has no test infra here; integration proof used"). Until a phase
# adds one, the fast/full/all scopes are a documented no-op that still
# enforces the single-entry-point contract and the GATE_SCOPE validation --
# the moment tests exist here they are added to `_gate-fast`/`_gate-full`,
# never to a second target. Builds no bitstream; does not touch `build/`.
_gate-fast:
	@echo "GATE fast: no unit-test infra in nextpnr yet (P0.T38 deviation) -- ok, 0 checks"

_gate-full: _gate-fast
	@echo "GATE full: no example/golden-netlist checks owned by nextpnr yet -- ok, 0 checks"

_gate-all: _gate-full
	@echo "GATE all: ok, 0 checks"
