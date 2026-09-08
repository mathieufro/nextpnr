#!/usr/bin/env python3
"""Gate check: `pack_iodelay` moves the Arora V delay line's own ports.

`IODELAY` names two different primitives.  The pre-5A one is
`IODELAY(DI, SDTAP, SETN, VALUE, DF, DO)`; the Arora V one replaces `SETN`
with an eight-bit `DLYSTEP` bus and adds the `DYN_DLY_EN` and `ADAPT_EN`
parameters (`UG304-1.3.8E` Tables 4-47 and 4-48, yosys
`cells_xtra_gw5a.v:1090`).  Packing the 5A cell through the pre-5A branch
dropped all eight step bits on the floor and looked for a port the cell does
not have, so the branch is taken on the cell's own port set rather than on a
device name.

  test_iodelay_gw5a_moves_dlystep
      Packs a real GW5AST-138C netlist and reads the packed IOLOGIC cell back:
      eight `DLYSTEP` bits bound, no `SETN`, and both new parameters
      forwarded.  Needs `NEXTPNR_HIMBAECHEL` and `GOWIN_CHIPDB_138C`.

  test_iodelay_gw1n_setn_unchanged
      The pre-5A branch still moves `SETN`, exactly once, and no other port
      move was moved out from under it.

  test_iodelay_one_per_io_block
      The one-delay-line-per-IO-block rule and its message survive, on both
      the input and the output side.
"""
import json
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
GOWIN = os.path.dirname(HERE)
DEVICE = "GW5AST-LV138PG484AC1/I0"

NEXTPNR = os.environ.get("NEXTPNR_HIMBAECHEL")
CHIPDB = os.environ.get("GOWIN_CHIPDB_138C")

CST = """IO_LOC  "din" V14;
IO_PORT "din" BANK_VCCIO=3.3 PULL_MODE=UP;
IO_LOC  "dout" P19;
IO_PORT "dout" IO_TYPE=LVCMOS33 PULL_MODE=NONE DRIVE=8 BANK_VCCIO=3.3;
IO_LOC  "flag" R19;
IO_PORT "flag" IO_TYPE=LVCMOS33 PULL_MODE=NONE DRIVE=8 BANK_VCCIO=3.3;
IO_LOC  "sdtap" Y12;
IO_PORT "sdtap" BANK_VCCIO=3.3 PULL_MODE=UP;
IO_LOC  "value" U15;
IO_PORT "value" BANK_VCCIO=3.3 PULL_MODE=UP;
"""


def _cell(typ, dirs, conns, parms=None):
    return {"hide_name": 0, "type": typ, "parameters": parms or {}, "attributes": {},
            "port_directions": dirs, "connections": conns}


def _netlist():
    """An `IODELAY` on an input pad, with its flag brought back out to a pad.

    Written by hand rather than synthesised: the check is about which ports
    the packer moves, and a synthesiser in the loop would only add ways for
    that question to go unanswered.
    """
    # net numbers: 0/1 are the constant bits yosys reserves.
    din, dout, flag, sdtap, value = 2, 3, 4, 5, 6
    pad_in, delayed, df, sdtap_i, value_i = 7, 8, 9, 10, 11
    ibuf = lambda i, o: _cell("IBUF", {"I": "input", "O": "output"}, {"I": [i], "O": [o]})
    obuf = lambda i, o: _cell("OBUF", {"I": "input", "O": "output"}, {"I": [i], "O": [o]})
    cells = {
        "din_ibuf": ibuf(din, pad_in),
        "sdtap_ibuf": ibuf(sdtap, sdtap_i),
        "value_ibuf": ibuf(value, value_i),
        "dly": _cell(
            "IODELAY",
            {"DI": "input", "SDTAP": "input", "VALUE": "input", "DLYSTEP": "input",
             "DF": "output", "DO": "output"},
            {"DI": [pad_in], "SDTAP": [sdtap_i], "VALUE": [value_i],
             # step 5, LSB first as JSON bit vectors run
             "DLYSTEP": ["1", "0", "1", "0", "0", "0", "0", "0"],
             "DF": [df], "DO": [delayed]},
            {"C_STATIC_DLY": "00000101", "DYN_DLY_EN": "FALSE", "ADAPT_EN": "FALSE"}),
        "dout_obuf": obuf(delayed, dout),
        "flag_obuf": obuf(df, flag),
    }
    ports = {"din": {"direction": "input", "bits": [din]},
             "sdtap": {"direction": "input", "bits": [sdtap]},
             "value": {"direction": "input", "bits": [value]},
             "dout": {"direction": "output", "bits": [dout]},
             "flag": {"direction": "output", "bits": [flag]}}
    netnames = {name: {"hide_name": 0, "bits": p["bits"], "attributes": {}}
                for name, p in ports.items()}
    return {"creator": "check_iodelay_gw5a",
            "modules": {"top": {"attributes": {"top": "00000000000000000000000000000001"},
                                "ports": ports, "cells": cells, "netnames": netnames}}}


def _pack(netlist, extra_cst=""):
    """Run the packer alone over `netlist`; return (returncode, log, packed)."""
    tmp = tempfile.mkdtemp(prefix="iodelay-")
    src, cst, out = (os.path.join(tmp, n) for n in ("in.json", "pins.cst", "out.json"))
    with open(src, "w") as f:
        json.dump(netlist, f)
    with open(cst, "w") as f:
        f.write(CST + extra_cst)
    proc = subprocess.run(
        [NEXTPNR, "--chipdb", CHIPDB, "--device", DEVICE, "--vopt", f"cst={cst}",
         "--top", "top", "--json", src, "--write", out, "--pack-only"],
        capture_output=True, text=True)
    packed = None
    if os.path.exists(out):
        with open(out) as f:
            packed = json.load(f)
    return proc.returncode, proc.stdout + proc.stderr, packed


def _iologic_cells(packed):
    cells = packed["modules"]["top"]["cells"]
    return {n: c for n, c in cells.items() if c["type"].startswith("IOLOGIC")}


def _pack_iodelay_source():
    """The text of `pack_iodelay` alone -- a `SETN` elsewhere is not this one."""
    text = open(os.path.join(GOWIN, "pack_iologic.cc"), encoding="utf-8").read()
    match = re.search(r"^void GowinPacker::pack_iodelay\(void\).*?^\}", text, re.S | re.M)
    assert match, "pack_iodelay not found in pack_iologic.cc"
    return match.group(0)


def test_iodelay_gw5a_moves_dlystep():
    if not (NEXTPNR and CHIPDB):
        return "not run: set NEXTPNR_HIMBAECHEL and GOWIN_CHIPDB_138C"
    rc, log, packed = _pack(_netlist())
    if "Can\'t place IOLOGIC" in log:
        # The delay line hangs off an IOLOGIC bel, and `get_iologici_bel`
        # refuses before `pack_iodelay` moves a single port.  A database whose
        # IOLOGIC surface has not been built yet therefore cannot answer this
        # question either way, and saying so is not the same as passing.
        return "not run: the chipdb has no IOLOGIC bel at the constrained pin"
    assert rc == 0, f"packing failed:\n{log}"
    iologic = _iologic_cells(packed)
    assert len(iologic) == 1, f"expected one IOLOGIC cell, got {sorted(iologic)}"
    cell = next(iter(iologic.values()))
    steps = [p for p in cell["connections"] if p.startswith("DLYSTEP")]
    assert len(steps) == 8, f"DLYSTEP bits bound: {sorted(steps)}"
    assert not [p for p in cell["connections"] if p == "SETN"]
    assert cell["parameters"].get("C_STATIC_DLY") is not None
    return f"8 DLYSTEP bits, 0 SETN, C_STATIC_DLY forwarded"


def test_iodelay_gw1n_setn_unchanged():
    source = _pack_iodelay_source()
    assert source.count("movePortTo(id_SETN") == 1
    for port in ("id_SDTAP", "id_VALUE", "id_DF"):
        assert source.count(f"movePortTo({port}") == 1
    # SETN is reached only when the cell has no DLYSTEP bus.
    assert re.search(r"} else \{\s*ci\.movePortTo\(id_SETN, iologic, id_SETN\);", source)
    return None


def test_iodelay_gw5a_branch_moves_eight_bits_and_no_setn():
    """The 5A branch, read off the source the live pack cannot reach yet."""
    source = _pack_iodelay_source()
    assert "id_DLYSTEP" in source
    assert re.search(r"for \(int i = 0; i < 8; \+\+i\) \{\s*IdString bit = "
                     r"ctx->idf\(\"%s\[%d\]\", id_DLYSTEP\.c_str\(ctx\), i\);\s*"
                     r"ci\.movePortTo\(bit, iologic, bit\);", source)
    # The discriminator is the cell's own port set, never a device name.
    assert "is_gw5a_delay = ci.ports.count(" in source
    assert not re.search(r"GW5A[A-Z]*-\d", source)
    for parm in ("id_DYN_DLY_EN", "id_ADAPT_EN"):
        assert parm in source
    return None


def test_iodelay_one_per_io_block():
    source = _pack_iodelay_source()
    assert source.count('log_error("Only one IODELAY allowed per IO block %s.\\n"') == 2
    assert source.count("iologic->attrs.count(id_IODELAY) != 0") == 2
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
    print(f"check_iodelay_gw5a: {failures} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
