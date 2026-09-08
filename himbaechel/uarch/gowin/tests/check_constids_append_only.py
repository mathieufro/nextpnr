#!/usr/bin/env python3
"""Gate check: `constids.inc` grows only at its end.

Every identifier in `constids.inc` is numbered by its position, and a
`chipdb-*.bin` stores those numbers, not the names.  Inserting or reordering a
line therefore silently renumbers every identifier below it and makes every
previously generated database decode as a different design.  Appending cannot
do that, which is why the file is append-only and why the Arora V IODELAY
identifiers went at the bottom.

  test_constids_appended_only
      The file the IODELAY work started from is pinned by the sha256 of its
      first `PRE_EDIT_LINES` lines; those lines must still hash to it, and the
      first names after them must still be the IODELAY three. Later work
      appends after those, which is what append-only means.

  test_constids_has_dlystep
      `X(DLYSTEP)` is declared exactly once -- a duplicate `X()` compiles but
      gives the same name two ids.
"""
import hashlib
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CONSTIDS = os.path.join(os.path.dirname(HERE), "constids.inc")

# State of the file before the IODELAY identifiers were appended.
PRE_EDIT_LINES = 1470
PRE_EDIT_SHA256 = "e9f5985d6f91d049ca96f27a4316f47f422242b013af3e2a23f9c1ee8525f0fe"

# Appended by this work, in order.
APPENDED = ["DLYSTEP", "DYN_DLY_EN", "ADAPT_EN"]


def _text():
    with open(CONSTIDS, "rb") as f:
        return f.read()


def _names():
    return re.findall(rb"^X\((\w+)\)", _text(), re.MULTILINE)


def test_constids_appended_only():
    """The pinned prefix is unchanged and the first append follows it.

    Anchoring on the *last* names instead would make every later append look
    like a reordering: the ADC identifiers were appended after these, and the
    file is expected to keep growing. What must not move is the prefix, and
    where the first append starts.
    """
    lines = _text().splitlines(keepends=True)
    assert len(lines) > PRE_EDIT_LINES
    prefix = b"".join(lines[:PRE_EDIT_LINES])
    assert hashlib.sha256(prefix).hexdigest() == PRE_EDIT_SHA256, \
        "the pinned prefix changed: every chipdb built before this renumbers"
    pinned = len(re.findall(rb"^X\(\w+\)", prefix, re.MULTILINE))
    names = [n.decode() for n in _names()]
    assert names[pinned:pinned + len(APPENDED)] == APPENDED, \
        f"the first appended identifiers are {names[pinned:pinned + len(APPENDED)]}"
    return f"{pinned} pinned, {len(names) - pinned} appended"


def test_constids_has_dlystep():
    names = [n.decode() for n in _names()]
    assert names.count("DLYSTEP") == 1
    assert len(names) == len(set(names))
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
    print(f"check_constids_append_only: {failures} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
