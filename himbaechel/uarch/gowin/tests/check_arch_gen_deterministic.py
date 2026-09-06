#!/usr/bin/env python3
"""Gate check for D101 -- gowin_arch_gen.py must be a pure function of the chipdb.

`gowin_arch_gen.py` was non-deterministic: two runs over the *same*
`apycula/<device>.msgpack.xz` produced different `.bba` files (and, in the
worst case, wildly different tile-shape dedup counts -- 19825 vs 19832 vs
2849), so the installed `<device>.bin` was not reproducible and no sha256
of it meant anything.  Root cause: sets of strings reaching the generator's
output order -- `db.nodes`' member set, `db.io2hclk`/`db.hclk_div2`'s member
sets, and ~20 `for x in {'A', 'B'}` set literals whose iteration order is
PYTHONHASHSEED-dependent and which fix the wire-creation order inside a
tile type.

This check runs the generator twice, in two fresh interpreters with two
*different* PYTHONHASHSEEDs (a single seed would pass even on the broken
generator), and asserts the two `.bba` files are byte-identical.

Run: python3 himbaechel/uarch/gowin/tests/check_arch_gen_deterministic.py
Env: ARCH_GEN_DET_DEVICE  device to build (default GW5AST-138C)
     APICULA_ROOT         apicula checkout to import `apycula` from, when it
                          is not already importable
     GATE_PYTHON          interpreter that has apicula's deps (msgpack, numpy)
                          installed; default: the one running this script
"""

import hashlib
import os
import subprocess
import sys
import tempfile

REPO = os.path.abspath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                 os.pardir, os.pardir, os.pardir, os.pardir))
GEN = os.path.join(REPO, "himbaechel", "uarch", "gowin", "gowin_arch_gen.py")
DEVICE = os.environ.get("ARCH_GEN_DET_DEVICE", "GW5AST-138C")


def _apicula_root():
    """Where `apycula` (and its built <device>.msgpack.xz) can be imported from."""
    root = os.environ.get("APICULA_ROOT")
    if root:
        return root
    try:
        import apycula  # noqa: F401
        return None  # already importable, nothing to add to PYTHONPATH
    except ImportError:
        pass
    for cand in (os.path.join(os.path.dirname(REPO), "apicula"),
                 os.path.join(os.path.dirname(REPO), "apicula-wt", "integ")):
        if os.path.isfile(os.path.join(cand, "apycula", "chipdb.py")):
            return cand
    return None


def _run(out_path, seed, env_extra):
    env = dict(os.environ)
    env.update(env_extra)
    env["PYTHONHASHSEED"] = seed
    python = os.environ.get("GATE_PYTHON", sys.executable)
    subprocess.run([python, GEN, "-d", DEVICE, "-o", out_path],
                   env=env, check=True, capture_output=True)
    with open(out_path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def test_bba_is_reproducible_from_one_msgpack():
    root = _apicula_root()
    env_extra = {}
    if root:
        env_extra["PYTHONPATH"] = root + os.pathsep + os.environ.get("PYTHONPATH", "")
        msgpack = os.path.join(root, "apycula", f"{DEVICE}.msgpack.xz")
    else:
        import apycula
        msgpack = os.path.join(os.path.dirname(apycula.__file__),
                               f"{DEVICE}.msgpack.xz")
    assert os.path.isfile(msgpack), (
        f"{msgpack} not built -- `make apycula/{DEVICE}.msgpack.xz` in apicula first")
    msgpack_sha = hashlib.sha256(open(msgpack, "rb").read()).hexdigest()

    with tempfile.TemporaryDirectory() as td:
        a = _run(os.path.join(td, "a.bba"), "1", env_extra)
        b = _run(os.path.join(td, "b.bba"), "12345", env_extra)

    assert a == b, (
        f"gowin_arch_gen.py is non-deterministic for {DEVICE}: two runs over "
        f"the same chipdb (sha256 {msgpack_sha[:16]}) gave .bba sha256 "
        f"{a[:16]} and {b[:16]} (D101)")
    print(f"OK-arch-gen-deterministic {DEVICE} bba={a[:16]} chipdb={msgpack_sha[:16]}")


if __name__ == "__main__":
    test_bba_is_reproducible_from_one_msgpack()
