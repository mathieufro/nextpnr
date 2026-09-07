#!/usr/bin/env python3
"""Gate check: the IO / IOLOGIC timing arcs `create_timing_info` installs.

`P3.T33`. Apicula publishes no `io` and no `iregoreg` timing group for the
GW5A family -- by measurement, not by omission (`P3.T32`,
`apicula/doc/timing-io-iologic.md`): both `.tm` blocks are inherited GW2A
bytes and the vendor's own GW5AST-138C SDF contradicts them. So this check
asserts the honest pair of facts:

  test_arch_gen_io_arcs_present_or_nodata
      either the chipdb carries the groups and nextpnr installs at least one
      IO/IOLOGIC arc from them, or the no-data marker is recorded in the
      generator and the branch that would consume them exists.

  test_arch_gen_no_wire_delay_assertion
      the emitter runs to completion over the real chipdb timing with no
      `AssertionError` -- the `db.wire_delay` assertions still hold, because
      the branch adds no wire.

  test_arch_gen_lut4_arc_count_unchanged
      the LUT4 cell keeps exactly its four comb arcs per speed grade; the new
      branch touched nothing the CFU classes depend on.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
GOWIN = os.path.dirname(HERE)
DEVICE = "GW5AST-138C"
LUT4_ARCS_PER_GRADE = 4

sys.path.insert(0, GOWIN)


def _source():
    with open(os.path.join(GOWIN, "gowin_arch_gen.py")) as handle:
        return handle.read()


def _timing():
    """`db.timing` for this device, or `None` when apicula is not installed."""
    try:
        import importlib.resources as ir

        from apycula.chipdb import load_chipdb
    except ImportError:
        return None
    try:
        return load_chipdb(str(ir.files("apycula") / f"{DEVICE}.msgpack.xz")).timing
    except (FileNotFoundError, OSError):
        return None


class _Cell:
    def __init__(self, name, sink):
        self.name, self.sink = name, sink

    def add_comb_arc(self, frm, to, delay):
        self.sink.append((self.name, frm, to))

    def add_clock_out(self, clock, pin, edge, delay):
        self.sink.append((self.name, clock, pin))

    def add_setup_hold(self, clock, pin, edge, setup, hold):
        pass


class _Tmg:
    def __init__(self):
        self.arcs = {}

    def add_cell_variant(self, speed, name):
        return _Cell(name, self.arcs.setdefault(speed, []))

    def set_pip_class(self, speed, name, delay, *args, **kwargs):
        pass


class _Chip:
    def __init__(self):
        self.tmg = _Tmg()

    def set_speed_grades(self, grades):
        return self.tmg


class _Db:
    def __init__(self, timing):
        self.timing = timing


def _emit(timing):
    import gowin_arch_gen

    chip = _Chip()
    gowin_arch_gen.create_timing_info(chip, _Db(timing))
    return chip.tmg.arcs


def test_arch_gen_io_arcs_present_or_nodata():
    timing = _timing()
    if timing is None:
        print("skip: apicula is not installed in this environment")
        return
    groups = {g for grade in timing.values() for g in grade}
    arcs = _emit(timing)
    io_arcs = [a for per_grade in arcs.values() for a in per_grade
               if a[0].startswith(("IBUF", "OBUF", "TBUF", "IOBUF",
                                   "IDDR", "ODDR", "OSER", "IDES"))]
    if groups & {"io", "iregoreg"}:
        assert io_arcs, "chipdb carries an io/iregoreg group but nextpnr installs no arc"
        return
    # no-data path: the marker must be recorded, and the branch must exist.
    src = _source()
    assert re.search(r'group == "io"', src), "no `io` branch in create_timing_info"
    assert re.search(r'group == "iregoreg"', src), "no `iregoreg` branch"
    assert "timing-io-iologic.md" in src, "the no-data marker is not recorded"
    assert not io_arcs, "IO arcs emitted from a chipdb that carries no IO group"


def test_arch_gen_no_wire_delay_assertion():
    timing = _timing()
    if timing is None:
        print("skip: apicula is not installed in this environment")
        return
    _emit(timing)   # an AssertionError here fails the check


def test_arch_gen_lut4_arc_count_unchanged():
    timing = _timing()
    if timing is None:
        print("skip: apicula is not installed in this environment")
        return
    arcs = _emit(timing)
    assert arcs, "no timing arcs at all"
    for speed, per_grade in arcs.items():
        lut4 = [a for a in per_grade if a[0] == "LUT4"]
        assert len(lut4) == LUT4_ARCS_PER_GRADE, (speed, len(lut4))


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if not name.startswith("test_"):
            continue
        try:
            fn()
        except AssertionError as exc:
            failures += 1
            print(f"FAIL {name}: {exc}")
        else:
            print(f"ok   {name}")
    sys.exit(1 if failures else 0)
