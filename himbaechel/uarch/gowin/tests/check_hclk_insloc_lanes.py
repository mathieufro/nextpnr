#!/usr/bin/env python3
"""Gate check: `INS_LOC "<cell>" <SIDE>[0~7]` reaches every HCLK lane.

The vendor pins a CLKDIV to one lane of one HCLK block with
`INS_LOC "div0" BOTTOMSIDE[4];` (SUG1018-1.7E Table 2-2, measured over 24
positions in `P1.T08d`).  The reader accepted `[0|1]` only -- a two-section
side, which is the pre-Arora-V shape -- so on a device with two blocks per
side and four lanes per block the vendor's own line fell through to the
placement-macro branch and aborted the run.  A serialiser row cannot pin the
HCLK lane its `FCLK` lands on without it (`D107`).

  test_hclk_insloc_regex_takes_eight_indices
      The index class is 0~7, not the old `[0,1]`.

  test_hclk_insloc_splits_index_into_block_and_lane
      The index is read as `block * lanes_per_block + lane`, with four lanes
      per block on an Arora V HCLK and two sections otherwise.

  test_hclk_insloc_orders_blocks_along_the_side
      The block ordinal indexes candidates sorted by their position along the
      side, so `BOTTOMSIDE[4]` is the second bottom block and not whichever
      bel the bucket happened to yield first.
"""
import os
import re

_HERE = os.path.dirname(os.path.abspath(__file__))
CST_CC = os.path.join(os.path.dirname(_HERE), "cst.cc")


def _source():
    with open(CST_CC, encoding="utf-8") as fh:
        return fh.read()


def _hclk_bel_fn():
    text = _source()
    match = re.search(r"BelId getConstrainedHCLKBel\(.*?\n    \}", text, re.S)
    assert match, "getConstrainedHCLKBel not found"
    return match.group(0)


def test_hclk_insloc_regex_takes_eight_indices():
    text = _source()
    match = re.search(r"TOP\|RIGHT\|BOTTOM\|LEFT\)SIDE.*?\]", text)
    assert match, "the SIDE[] INS_LOC regex is gone"
    assert "0-7" in match.group(0), match.group(0)
    assert "0,1" not in match.group(0), match.group(0)


def test_hclk_insloc_splits_index_into_block_and_lane():
    body = _hclk_bel_fn()
    assert "has_5A_HCLK()" in body
    assert re.search(r"lanes_per_block\s*=\s*hclk_5A\s*\?\s*4\s*:\s*2", body), body
    assert re.search(r"block_ordinal\s*=\s*idx\s*/\s*lanes_per_block", body), body
    assert re.search(r"lane\s*=\s*idx\s*%\s*lanes_per_block", body), body


def test_hclk_insloc_orders_blocks_along_the_side():
    body = _hclk_bel_fn()
    assert "std::sort(" in body, body
    assert "blocks.at(block_ordinal)" in body, body
    # a side with fewer blocks than the index asks for is a refusal, not a
    # silent wrap onto another block
    assert re.search(r"block_ordinal\s*>=\s*int\(blocks\.size\(\)\)", body), body
