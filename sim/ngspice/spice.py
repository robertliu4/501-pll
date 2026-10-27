"""Tiny helper for running GF180 ngspice decks from Python.

Every deck is written to sim/ngspice/out/<name>.cir and run in batch mode.
Results come back either from .meas lines (parsed from stdout) or from
wrdata files (read with numpy).
"""
import os
import re
import subprocess
from pathlib import Path

import numpy as np

PDK_ROOT = Path(os.environ.get("PDK_ROOT", Path.home() / ".ciel")) / "gf180mcuD"
NGSPICE_DIR = PDK_ROOT / "libs.tech" / "ngspice"
STDCELL_SPICE = (PDK_ROOT / "libs.ref" / "gf180mcu_fd_sc_mcu7t5v0" / "spice"
                 / "gf180mcu_fd_sc_mcu7t5v0.spice")

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
RESULTS = HERE.parent / "results"

# (process corner, temperature C, supply V) triples used throughout
CORNERS = {
    "tt_27C_3v3": ("typical", 27, 3.3),
    "ss_85C_3v0": ("ss", 85, 3.0),
    "ff_0C_3v6": ("ff", 0, 3.6),
    "sf_27C_3v3": ("sf", 27, 3.3),
    "fs_27C_3v3": ("fs", 27, 3.3),
}


def models(corner="typical", mim=True, res=True, stdcells=False):
    lines = [f".include {NGSPICE_DIR / 'design.ngspice'}",
             f".lib {NGSPICE_DIR / 'sm141064.ngspice'} {corner}"]
    if res:
        res_corner = {"typical": "res_typical", "ss": "res_ss", "ff": "res_ff"}.get(corner, "res_typical")
        lines.append(f".lib {NGSPICE_DIR / 'sm141064.ngspice'} {res_corner}")
    if mim:
        lines.append(f".lib {NGSPICE_DIR / 'sm141064.ngspice'} mimcap_typical")
    if stdcells:
        lines.append(f".include {STDCELL_SPICE}")
    return "\n".join(lines)


def run(name, deck, timeout=3600):
    OUT.mkdir(exist_ok=True)
    cir = OUT / f"{name}.cir"
    cir.write_text(deck)
    proc = subprocess.run(["ngspice", "-b", cir.name], cwd=OUT, capture_output=True,
                          text=True, timeout=timeout)
    log = proc.stdout + proc.stderr
    (OUT / f"{name}.log").write_text(log)
    return log


def meas(log):
    """Parse 'name = value' lines that .meas / print produce."""
    vals = {}
    for m in re.finditer(r"^\s*([A-Za-z_][\w]*)\s*=\s*([-+0-9.eE]+)", log, re.M):
        try:
            vals[m.group(1).lower()] = float(m.group(2))
        except ValueError:
            pass
    return vals


def wrdata(path):
    """Read an ngspice wrdata file into an (n, k) array (x/y pairs per vector)."""
    return np.loadtxt(OUT / path)
