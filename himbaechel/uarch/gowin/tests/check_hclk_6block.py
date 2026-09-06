#!/usr/bin/env python3
"""Gate check for P1.T10 -- six-block HCLK wire names in the gowin uarch.

Two checks, both source-level: nextpnr has no C++ unit-test infra for the
gowin uarch (P0.T38 deviation), so the contract is asserted against the
sources and the git history instead of a compiled test binary.

  test_constids_appended_only_hclk_6block
      constids.inc is an append-only registry (F55).  Relative to the
      branch base sha -- never an absolute line count, because later
      phases append to the same file -- the file must have exactly the 8
      new HCLK block-4/5 ids added, 0 lines deleted and 0 lines modified.

  test_hclk_fclk_map_covers_six_blocks
      gowin.cc's postRoute() HCLK->FCLK mapping table must cover 24
      distinct id_HCLK<b><w> ids, b in 0..5 and w in 0..3, 6 per
      HCLK_OUT<w> group.

Run: python3 himbaechel/uarch/gowin/tests/check_hclk_6block.py
Base sha override: HCLK_6BLOCK_BASE_SHA=<sha> (default: the
clocking/gw5a-hclk-6block base recorded by P1.T02).
"""

import os
import re
import subprocess
import sys

BASE_SHA_DEFAULT = "e8440c716493f84534220c2c0e2345ec13441e77"
CONSTIDS = "himbaechel/uarch/gowin/constids.inc"
GOWIN_CC = "himbaechel/uarch/gowin/gowin.cc"
NEW_ID_RE = re.compile(r"^X\(HCLK[45][0-3]\)$")

REPO = subprocess.run(
    ["git", "rev-parse", "--show-toplevel"],
    cwd=os.path.dirname(os.path.abspath(__file__)),
    capture_output=True, text=True, check=True).stdout.strip()


def git(*args):
    return subprocess.run(["git", "-C", REPO, *args],
                          capture_output=True, text=True, check=True).stdout


def test_constids_appended_only_hclk_6block():
    base = os.environ.get("HCLK_6BLOCK_BASE_SHA", BASE_SHA_DEFAULT)
    base_text = git("show", f"{base}:{CONSTIDS}")
    n_base = len(base_text.splitlines())
    with open(os.path.join(REPO, CONSTIDS)) as f:
        n_now = len(f.read().splitlines())
    assert n_now == n_base + 8, f"constids.inc: {n_now} lines, expected {n_base} + 8"

    diff = git("diff", "--unified=0", base, "--", CONSTIDS).splitlines()
    removed = [l for l in diff if l.startswith("-") and not l.startswith("---")]
    added = [l[1:] for l in diff if l.startswith("+") and not l.startswith("+++")]
    assert not removed, f"constids.inc: {len(removed)} deleted/modified line(s): {removed}"
    assert len(added) == 8, f"constids.inc: {len(added)} added line(s), expected 8"
    bad = [l for l in added if not NEW_ID_RE.match(l)]
    assert not bad, f"constids.inc: added lines not matching X(HCLK[45][0-3]): {bad}"
    expect = {f"X(HCLK{b}{w})" for b in (4, 5) for w in range(4)}
    assert set(added) == expect, f"constids.inc: added {sorted(added)}, expected {sorted(expect)}"


def test_hclk_fclk_map_covers_six_blocks():
    with open(os.path.join(REPO, GOWIN_CC)) as f:
        src = f.read()
    m = re.search(r"hclk_up_wire\s*\[\s*\]\s*\[\s*4\s*\]\s*=\s*\{(.*?)\n\s*\};", src, re.S)
    assert m, "gowin.cc: HCLK->FCLK mapping table 'hclk_up_wire' not found"
    rows = re.findall(r"\{([^{}]*)\}", m.group(1))
    assert len(rows) == 6, f"gowin.cc: mapping table has {len(rows)} blocks, expected 6"
    ids = []
    for b, row in enumerate(rows):
        entries = [e.strip() for e in row.split(",") if e.strip()]
        assert len(entries) == 4, f"gowin.cc: block {b} has {len(entries)} entries, expected 4"
        for w, entry in enumerate(entries):
            assert entry == f"id_HCLK{b}{w}", \
                f"gowin.cc: block {b} slot {w} is {entry}, expected id_HCLK{b}{w}"
            ids.append(entry)
    assert len(set(ids)) == 24, f"gowin.cc: {len(set(ids))} distinct ids, expected 24"
    for w in range(4):
        group = [i for i in ids if i.endswith(str(w)) and i[len("id_HCLK")] in "012345"
                 and i == f"id_HCLK{i[len('id_HCLK')]}{w}"]
        assert len(group) == 6, f"gowin.cc: HCLK_OUT{w} group has {len(group)} ids, expected 6"
    # every id in the table must exist in the constids registry
    with open(os.path.join(REPO, CONSTIDS)) as f:
        known = set(re.findall(r"^X\((\w+)\)$", f.read(), re.M))
    missing = [i for i in ids if i[len("id_"):] not in known]
    assert not missing, f"gowin.cc: ids absent from constids.inc: {missing}"


def main():
    failures = 0
    for name, fn in sorted((k, v) for k, v in globals().items() if k.startswith("test_")):
        try:
            fn()
        except AssertionError as e:
            failures += 1
            print(f"FAIL {name}: {e}")
        else:
            print(f"ok   {name}")
    print(f"GATE hclk-6block: {2 - failures}/2 checks passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
