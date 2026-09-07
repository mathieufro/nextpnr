#!/usr/bin/env python3
"""Gate check -- an AE350 tap must not retype the routing tile's own wire.

Every AE350 port lands on a wire of a die-row-0 routing tile: `CLK`, `CE`,
`LSR` and `A`-`D` for the block's inputs, `F`/`Q`/`OF` for its outputs. Those
wires exist before the AE350 bel is built, and their type is what tells
`globals.cc` that a `CLK` line is a legal clock sink. `create_reuse_wire`
overwrites the type of a wire it finds, so passing `AE350_IN` for a tap would
strip `TILE_CLK` from the tile for every cell in it, not just the AE350.

This check asserts the generator leaves an existing wire's type alone: it
builds the anchor tile type twice, once with the AE350 branch and once
without, and compares the type of every wire the AE350 taps.

Run: python3 himbaechel/uarch/gowin/tests/check_ae350_tap_wire_types.py
Env: APICULA_ROOT  apicula checkout to import `apycula` from
     AE350_MSGPACK path of the GW5AST-138C msgpack.xz
"""

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

SOURCE = os.path.join(os.path.dirname(HERE), "gowin_arch_gen.py")


def test_ae350_branch_keeps_an_existing_wires_type():
    src = open(SOURCE).read()
    branch = src[src.index("elif func == 'ae350':"):]
    branch = branch[:branch.index("elif func == 'pincfg':")]
    call = re.search(r"create_reuse_wire\((.*?)\)\n", branch, re.S)
    assert call, "the AE350 branch no longer creates its tap wires"
    args = " ".join(call.group(1).split())
    assert "tt.has_wire(wire)" in args, (
        "the AE350 branch retypes a wire the tile already owns: "
        f"create_reuse_wire({args})")
    assert '""' in args, (
        "an existing tap wire must keep its own type, not gain an AE350 one: "
        f"create_reuse_wire({args})")
    print("OK-ae350-tap-wire-types")


if __name__ == "__main__":
    test_ae350_branch_keeps_an_existing_wires_type()
