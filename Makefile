# The local gate's single entry point for the nextpnr fork (C12, D94, D95;
# supersedes C8/D75-D78's blocking pre-commit shape). This is a NEW file
# (F88: nextpnr is CMake-only, no root Makefile existed) -- it must not
# shadow or interfere with the out-of-tree `build/` directory P0.T09
# configures and builds from. `.githooks/pre-push` is the only hook:
# task-branch pushes get no gate; a push to main/dev/integration/epic
# spawns this gate detached at GATE_SCOPE=branch.
#
# A human/agent typing `make gate` invokes this same target -- there is
# exactly one definition of "green".

include gate.env

GATE_SCOPE ?= fast

.PHONY: gate _gate-fast _gate-branch _gate-full

gate:
	@case "$(GATE_SCOPE)" in \
	  fast)   $(MAKE) --no-print-directory _gate-fast ;; \
	  branch) $(MAKE) --no-print-directory _gate-branch ;; \
	  full)   $(MAKE) --no-print-directory _gate-full ;; \
	  *) echo "GATE $(GATE_SCOPE): unknown GATE_SCOPE (legal: fast branch full)"; exit 1 ;; \
	esac

# The gowin himbaechel uarch has no C++ unit-test infra (P0.T38 deviation:
# "nextpnr has no test infra here; integration proof used"), so the checks
# it does own are source-level scripts under
# `himbaechel/uarch/gowin/tests/`. They all hang off `_gate-fast`, never a
# second target, so there is exactly one definition of "green". Builds no
# bitstream; does not touch `build/`.
_gate-fast:
	@python3 himbaechel/uarch/gowin/tests/check_hclk_6block.py
	@python3 himbaechel/uarch/gowin/tests/check_arch_gen_deterministic.py
	@$${GATE_PYTHON:-python3} himbaechel/uarch/gowin/tests/check_dcs_spines.py

# branch: fast, plus evidence/criteria tools -- nextpnr owns none of those
# (open-toolchain and the umbrella do); alias for fast (D94: "branch = fast
# + evidence/criteria tools (open-toolchain/umbrella)").
_gate-branch: _gate-fast
	@echo "GATE branch: no evidence/criteria tools owned by nextpnr -- ok, 0 checks"

# full: everything, including heavy checks -- orchestrator-only, run in the
# foreground at phase close / pre-merge, never from a hook. No
# example/golden-netlist checks owned by nextpnr yet.
_gate-full: _gate-branch
	@echo "GATE full: no example/golden-netlist checks owned by nextpnr yet -- ok, 0 checks"
