#!/usr/bin/env python3
"""Gate check: the HCLK -> IOLOGIC-FCLK edge on GW5AST-138C.

A board input clock reaching an IOLOGIC's fast clock is what makes RGMII RX
and TDM IO buildable on this part, so the two things that decide whether the
router can even try are checked here rather than discovered in a run:

  test_has_5a_hclk_is_set_for_138c
      `gowin_utils.cc`'s `chip_flags & HAS_5A_HCLK` gate opens for this device.
      Without the flag the six-block HCLK model is not consulted at all.

  test_the_hclk_to_fclk_edge_is_absent_and_the_router_says_so
      MEASURED, `P3.T07`: the 138C database carries **no** IO-to-HCLK edge
      (`dev.io2hclk == {}`; `chipdb.gw5_create_hclk_iol_pip` returns `False`
      for this device), and neither does the vendor -- twelve vendor
      bitstreams decode zero pips into any `FCLK*` wire.  So a DHCE-gated
      clock reaching a `CLKDIV` and stopping at an IOLOGIC fast-clock pin is
      a missing model edge, not a placement the router could have found.
      This check asserts the two halves of that being *reported* rather than
      silently mis-routed: `route_direct_net` counts reached and missed sinks
      independently (the fold it replaced lost a first-sink failure whenever a
      later sink succeeded), and `report_unreachable_sinks` names the pin.

  test_arch_gen_names_the_fclk_wire_class
      `GowinUtils::is_iologic_fclk_wire` is what turns a failed global route
      into a message about the database, so it must exist and be called from
      the reporting path.

Adding the edge itself is not a nextpnr change: it needs
`apycula/chipdb.py`'s `gw5_create_hclk_iol_pip`, which Phase 3 does not own.
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


def test_the_hclk_to_fclk_edge_is_absent_and_the_router_says_so():
    globals_cc = _read("globals.cc")
    assert "int reached = 0, missed = 0;" in globals_cc, \
        "route_direct_net no longer counts sinks independently"
    assert re.search(r"routed\s*=\s*reached == 0 \? NOT_ROUTED", globals_cc), \
        "route_direct_net's result is not derived from the two counts"
    assert "report_unreachable_sinks" in globals_cc, \
        "a partly routed global network no longer names the sinks it missed"
    db = _chipdb()
    if db is None:
        return "skipped (no chipdb reachable from this checkout)"
    assert db.io2hclk == {}, (
        "io2hclk is no longer empty for this device -- if the HCLK -> FCLK "
        "edge has landed, this check and the router message must be revisited")
    return None


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
