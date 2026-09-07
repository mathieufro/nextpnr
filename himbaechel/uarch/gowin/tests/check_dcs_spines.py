#!/usr/bin/env python3
"""Gate check: the DCS spine permission set is derived, not named.

`global_DCS_pip_filter` used to name eight spine ids -- the pre-5A CLKOUT
spines -- as the only ones a DCS-managed net may travel on.  On a die whose
clock plane is fed through a bridge, a DCS output reaches ordinary spines of
each quadrant instead, so that list left every such net unroutable.  The set
now comes from the database, and these checks assert the two properties that
makes it safe:

  test_derived_set_reproduces_the_named_set_on_pre5a
      On GW5A-25A the derivation returns exactly the eight spines the filter
      used to name, so no pre-5A device changes behaviour.

  test_bridged_die_reaches_the_quadrant_spines
      On GW5AST-138C it additionally returns spines 4 and 5 of every quadrant
      -- the ones the bridge cell's multiplexer drives from a DCS output --
      and the DCS output wire names include the CBRIDGEOUT nodes.

  test_filter_reads_the_database
      Source-level: the filter asks `GowinUtils`, and no longer carries a
      hardcoded spine-id list.

  test_dcs_clock_inputs_are_reachable
      The output side is only half a DCS.  On GW5AST-138C every DCS clock
      input multiplexer must offer at least one source that carries a fabric
      clock wire in its node -- otherwise the router reaches the DCS output
      and then dead-ends one hop short of the clock source, which is exactly
      what the die did while the clock plane knew only one logic-to-clock
      gate.

Run: python3 himbaechel/uarch/gowin/tests/check_dcs_spines.py
"""

import importlib.resources as ir
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
GOWIN = os.path.abspath(os.path.join(HERE, os.pardir))
REPO = os.path.abspath(os.path.join(GOWIN, os.pardir, os.pardir, os.pardir))

#: The ids `global_DCS_pip_filter` used to name.
PRE5A_SPINES = {"SPINE6", "SPINE7", "SPINE14", "SPINE15",
                "SPINE22", "SPINE23", "SPINE30", "SPINE31"}

#: MEASURED on the GW5AST-138C (`P1.T31` follow-up): the bridge cell's
#: multiplexer drives spines 4 and 5 of each quadrant from a DCS output.
BRIDGED_EXTRA = {"SPINE4", "SPINE5", "SPINE12", "SPINE13",
                 "SPINE20", "SPINE21", "SPINE28", "SPINE29"}


def load_arch_gen():
    spec = importlib.util.spec_from_file_location(
        "gowin_arch_gen", os.path.join(GOWIN, "gowin_arch_gen.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_db(device):
    from apycula.chipdb import load_chipdb
    return load_chipdb(str(ir.files("apycula") / f"{device}.msgpack.xz"))


def test_derived_set_reproduces_the_named_set_on_pre5a(arch_gen):
    spines, clkouts = arch_gen.dcs_spines_and_clkouts(load_db("GW5A-25A"))
    assert set(spines) == PRE5A_SPINES, spines
    assert set(clkouts) == PRE5A_SPINES, clkouts


def test_bridged_die_reaches_the_quadrant_spines(arch_gen):
    spines, clkouts = arch_gen.dcs_spines_and_clkouts(load_db("GW5AST-138C"))
    spines = set(spines)
    assert {"SPINE14", "SPINE15", "SPINE22", "SPINE23"} <= spines, spines
    assert BRIDGED_EXTRA <= spines, spines
    assert {"CBRIDGEOUT_TOP6", "CBRIDGEOUT_TOP7",
            "CBRIDGEOUT_BOTTOM6", "CBRIDGEOUT_BOTTOM7"} <= set(clkouts), clkouts


#: MEASURED (`P1.F2`, batch `p1f2-dcsin`): the two clock-bridge cells that
#: host a DCS, and the fabric clock wires their input multiplexers reach.
DCS_INPUT_CELLS = {(54, 93), (54, 88)}


def test_dcs_clock_inputs_are_reachable(_arch_gen=None):
    db = load_db("GW5AST-138C")
    fabric_clock = {}
    for _name, (_kind, members) in db.nodes.items():
        reach = {m for m in members
                 if m[2].startswith("CLK") and m[2][3:].isdigit()}
        if reach:
            for member in members:
                fabric_clock.setdefault(member, set()).update(reach)
    for row, col in sorted(DCS_INPUT_CELLS):
        tile = db[row, col]
        inputs = {dest: srcs for dest, srcs in tile.clock_pips.items()
                  if dest[0] == "P" and dest[1:3].isdigit()}
        assert inputs, f"({row}, {col}) hosts no DCS input multiplexer"
        for dest, srcs in sorted(inputs.items()):
            fed = set()
            for src in srcs:
                fed |= {m for m in fabric_clock.get((row, col, src), ())
                        if (m[0], m[1]) != (row, col)}
            assert fed, f"({row}, {col}) {dest} has no source with a driver"


def test_filter_reads_the_database(_arch_gen=None):
    source = open(os.path.join(GOWIN, "globals.cc")).read()
    start = source.index("bool global_DCS_pip_filter")
    body = source[start:source.index("\n    }\n", start)]
    assert "gwu.is_dcs_spine(src_name)" in body
    assert "id_SPINE6" not in body, "the spine list is still hardcoded"


def main():
    arch_gen = load_arch_gen()
    failures = 0
    for name, fn in sorted(globals().items()):
        if not name.startswith("test_"):
            continue
        try:
            fn(arch_gen)
            print(f"ok   {name}")
        except AssertionError as exc:
            failures += 1
            print(f"FAIL {name}: {exc}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
