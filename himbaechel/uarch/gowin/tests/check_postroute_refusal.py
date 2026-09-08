#!/usr/bin/env python3
"""Gate check: `postRoute` refuses an unrouted arc by name.

`NetInfo::wires` holds an entry per wire the router claimed, so a sink whose
arc was left unrouted is simply absent from it.  Reading it back with `at()`
turned a design the router could not route -- "Failed to find a route for arc
0 of net fclk_IBUF_I_O", printed as a warning -- into an uncaught
`std::out_of_range` from `dict::at()`, which aborts the process and hides the
real cause.  Every such lookup in `postRoute` goes through one helper that
names the net, the cell and the port instead.

  test_postroute_takes_no_unchecked_wire
      No `wires.at(` survives in `gowin.cc`.

  test_postroute_refusal_names_the_arc
      The helper exists and its message names the net, the port and the cell.
"""
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
GOWIN_CC = os.path.join(os.path.dirname(_HERE), "gowin.cc")


def _source():
    with open(GOWIN_CC, encoding="utf-8") as fh:
        return fh.read()


def test_postroute_takes_no_unchecked_wire():
    assert "wires.at(" not in _source()


def test_postroute_refusal_names_the_arc():
    text = _source()
    match = re.search(r"PipId sink_driving_pip\(.*?\n\}", text, re.S)
    assert match, "sink_driving_pip helper not found"
    body = match.group(0)
    assert "log_error(" in body
    assert "unrouted" in body


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if not name.startswith("test_"):
            continue
        try:
            fn()
            print("ok   %s" % name)
        except AssertionError as exc:
            failures += 1
            print("FAIL %s: %s" % (name, exc))
    sys.exit(1 if failures else 0)
