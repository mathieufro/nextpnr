#!/usr/bin/env python3
"""Gate check: the HCLK -> IOLOGIC-FCLK edge on GW5AST-138C.

A board input clock reaching an IOLOGIC's fast clock is what makes RGMII RX
and TDM IO buildable on this part, so the two things that decide whether the
router can even try are checked here rather than discovered in a run:

  test_has_5a_hclk_is_set_for_138c
      `gowin_utils.cc`'s `chip_flags & HAS_5A_HCLK` gate opens for this device.
      Without the flag the six-block HCLK model is not consulted at all.

  test_the_hclk_to_fclk_edge_is_modelled_for_every_block
      MEASURED: `P3.T07` found `dev.io2hclk == {}` and this check first
      asserted that absence; `P3.T13` then measured the vendor driving
      `OSER`/`IDES` `FCLK` from `HCLK` and built the table, and the gearbox
      rows close at `E1` over it.  So the check now asserts the edge is
      present on all six blocks.

  test_a_partly_routed_global_network_names_the_sinks_it_missed
      The reporting half, which stands either way: `route_direct_net` counts
      reached and missed sinks independently (the fold it replaced lost a
      first-sink failure whenever a later sink succeeded), and
      `report_unreachable_sinks` names the pin.

  test_arch_gen_names_the_fclk_wire_class
      `GowinUtils::is_iologic_fclk_wire` is what turns a failed global route
      into a message about the database, so it must exist and be called from
      the reporting path.

The edge itself is not a nextpnr change: it lives in `apycula/chipdb.py`'s
`gw5_create_hclk_iol_pip`, which `D106` lets Phase 3 build for this device.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
GOWIN = os.path.dirname(HERE)
DEVICE = "GW5AST-138C"


def _read(name):
    with open(os.path.join(GOWIN, name)) as handle:
        return handle.read()


def _chipdb():
    """The apicula chipdb for this device, loaded the way the other checks
    load it, or `None` when apicula is not installed in this environment."""
    try:
        import importlib.resources as ir

        from apycula.chipdb import load_chipdb
    except ImportError:
        return None
    try:
        return load_chipdb(str(ir.files("apycula") / f"{DEVICE}.msgpack.xz"))
    except (FileNotFoundError, OSError):
        return None


def test_has_5a_hclk_is_set_for_138c():
    source = _read("gowin_utils.cc")
    assert "HAS_5A_HCLK" in source, "gowin_utils no longer gates on HAS_5A_HCLK"
    db = _chipdb()
    if db is None:
        return "skipped (no chipdb reachable from this checkout)"
    assert "HAS_5A_HCLK" in db.chip_flags, \
        f"{DEVICE} chip_flags lack HAS_5A_HCLK: {db.chip_flags}"
    return None


def test_a_partly_routed_global_network_names_the_sinks_it_missed():
    """The reporting half, which stands whether or not the edge exists.

    `route_direct_net` counts reached and missed sinks independently -- the
    fold it replaced lost a first-sink failure whenever a later sink
    succeeded -- so a clock that reaches three of four IOLOGIC cells is
    reported as a routing failure naming the fourth, not as a success.
    """
    globals_cc = _read("globals.cc")
    assert "int reached = 0, missed = 0;" in globals_cc, \
        "route_direct_net no longer counts sinks independently"
    assert re.search(r"routed\s*=\s*reached == 0 \? NOT_ROUTED", globals_cc), \
        "route_direct_net's result is not derived from the two counts"
    assert "report_unreachable_sinks" in globals_cc, \
        "a partly routed global network no longer names the sinks it missed"
    return None


def test_the_hclk_to_fclk_edge_is_modelled_for_every_block():
    """The edge exists, on all six HCLK blocks.

    This check was written when it did not: `P3.T07` measured `io2hclk == {}`
    and the router message existed to say so rather than let a clock stop at
    an IOLOGIC fast-clock pin unremarked. `P3.T13` then measured the vendor
    driving `OSER`/`IDES` `FCLK` from `HCLK` (`FCLKSEL1`/`2` = `HCLK2`) and
    built the table, and the gearbox rows close at `E1` over it. What this
    check asserts is therefore the opposite of what it first asserted, and
    saying so here is the point: a guard that keeps asserting an absence after
    the absence is filled is a guard that has stopped measuring anything.
    """
    db = _chipdb()
    if db is None:
        return "skipped (no chipdb reachable from this checkout)"
    assert db.io2hclk, (
        f"{DEVICE} carries no IO-to-HCLK edge: an IOLOGIC fast clock has no "
        "source and the gearbox rows cannot close")
    assert len(db.io2hclk) == 6, (
        f"expected one entry per HCLK block, got {sorted(db.io2hclk)}")
    for block, cells in sorted(db.io2hclk.items()):
        assert cells, f"HCLK block {block} reaches no IO cell"
    return f"6 blocks, {sum(len(v) for v in db.io2hclk.values())} IO cells"


def test_arch_gen_names_the_fclk_wire_class():
    assert "is_iologic_fclk_wire" in _read("gowin_utils.h")
    assert "is_iologic_fclk_wire" in _read("gowin_utils.cc")
    assert "is_iologic_fclk_wire" in _read("globals.cc")
    return None


def main():
    failures = 0
    for name, test in sorted(globals().items()):
        if not name.startswith("test_"):
            continue
        try:
            note = test()
        except AssertionError as exc:
            print(f"FAIL {name}: {exc}")
            failures += 1
        else:
            print(f"ok   {name}" + (f" -- {note}" if note else ""))
    print(f"check_hclk_to_fclk_138c: {failures} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
