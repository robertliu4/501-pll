"""Can the first divide-by-2 keep up with the VCO's whole range?

The first divider stage has to toggle at the VCO's maximum frequency at every
corner, not just at 300 MHz: if it drops edges near the top of the range during
acquisition, the loop sees a slow divider output, pushes Vctrl further up and
never recovers (divider lock-up).

Compares:
  stdcell: gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 with D = inv_1(Q)  (5 V devices, L = 0.6 um)
  tspc:    custom true-single-phase-clock divide-by-2 on 3.3 V devices
Clock comes from a buf_2 driven by an ideal source, which roughly mimics the VCO
output buffer. Output: results/divider_speed.txt and .png
"""
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import spice

SC = "gf180mcu_fd_sc_mcu7t5v0__"
FREQS = np.array([200, 300, 400, 500, 600, 700, 800, 900, 1000, 1200, 1400]) * 1e6


def dut(kind):
    if kind == "stdcell":
        return f"""
XFF d vdd ck q vdd vdd 0 0 {SC}dffrnq_1
XI q d vdd vdd 0 0 {SC}inv_1
XL q ql vdd vdd 0 0 {SC}inv_1
"""
    # TSPC divide-by-2 (Yuan-Svensson), output of stage 3 fed back to the input
    return """
M1 a q vdd vdd pfet_03v3 W=2u L=0.28u
M2 b ck a vdd pfet_03v3 W=2u L=0.28u
M3 b q 0 0 nfet_03v3 W=1u L=0.28u
M4 c ck vdd vdd pfet_03v3 W=2u L=0.28u
M5 c b e 0 nfet_03v3 W=2u L=0.28u
M6 e ck 0 0 nfet_03v3 W=2u L=0.28u
M7 q c vdd vdd pfet_03v3 W=3u L=0.28u
M8 q ck f 0 nfet_03v3 W=2u L=0.28u
M9 f c 0 0 nfet_03v3 W=2u L=0.28u
XL q ql vdd vdd 0 0 gf180mcu_fd_sc_mcu7t5v0__inv_1
"""


def toggle_ok(kind, ck, f):
    corner, temp, vdd = spice.CORNERS[ck]
    T = 1 / f
    ncyc = 40
    deck = f"""* {kind} {ck} {f/1e6:.0f}MHz
{spice.models(corner, mim=False, res=False, stdcells=True)}
.temp {temp}
VDD vdd 0 {vdd}
VCK cki 0 PULSE(0 {vdd} 0 {0.1*T} {0.1*T} {0.4*T} {T})
XB cki ck vdd vdd 0 0 {SC}buf_2
{dut(kind)}
.control
tran {T/200} {ncyc*T}
meas tran ta WHEN v(q)={vdd/2} RISE=5
meas tran tb WHEN v(q)={vdd/2} RISE=15
meas tran qmax MAX v(q) FROM={ncyc*T/2} TO={ncyc*T}
meas tran qmin MIN v(q) FROM={ncyc*T/2} TO={ncyc*T}
.endc
.end
"""
    log = spice.run(f"div_{kind}_{ck}_{f/1e6:.0f}", deck)
    m = spice.meas(log)
    if "ta" not in m or "tb" not in m:
        return False, np.nan
    fq = 10 / (m["tb"] - m["ta"])
    swing_ok = m.get("qmax", 0) > 0.9 * vdd and m.get("qmin", vdd) < 0.1 * vdd
    return bool(abs(fq - f / 2) / (f / 2) < 0.01 and swing_ok), fq


def main():
    keys = ["tt_27C_3v3", "ss_85C_3v0", "ff_0C_3v6"]
    spice.CORNERS["ss_125C_3v0"] = ("ss", 125, 3.0)
    keys.append("ss_125C_3v0")
    pool = ThreadPoolExecutor(max_workers=10)
    jobs = {(k, c, f): pool.submit(toggle_ok, k, c, f)
            for k in ("stdcell", "tspc") for c in keys for f in FREQS}
    res = {key: j.result() for key, j in jobs.items()}
    lines = ["max input frequency at which the divide-by-2 still toggles cleanly (MHz)"]
    fmax = {}
    for k in ("stdcell", "tspc"):
        for c in keys:
            ok = [f for f in FREQS if res[(k, c, f)][0]]
            # highest frequency below the first failure
            good = 0
            for f in FREQS:
                if res[(k, c, f)][0]:
                    good = f
                else:
                    break
            fmax[(k, c)] = good
            lines.append(f"  {k:8s} {c:12s} {good/1e6:6.0f}   passes at: {[int(x/1e6) for x in ok]}")
    txt = "\n".join(lines)
    print(txt)
    (spice.RESULTS / "divider_speed.txt").write_text(txt + "\n")

    fig, ax = plt.subplots(figsize=(7, 4))
    x = np.arange(len(keys))
    ax.bar(x - 0.18, [fmax[("stdcell", c)] / 1e6 for c in keys], 0.36, label="std-cell dffrnq_1 (5 V devices)")
    ax.bar(x + 0.18, [fmax[("tspc", c)] / 1e6 for c in keys], 0.36, label="custom TSPC (3.3 V devices)")
    ax.axhline(510, color="r", ls="--", lw=1, label="VCO max (typical, from vco sim)")
    ax.set_xticks(x, keys)
    ax.set_ylabel("max toggle input freq (MHz)")
    ax.set_title("First divide-by-2 stage speed")
    ax.legend(fontsize=8)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(spice.RESULTS / "divider_speed.png", dpi=130)


if __name__ == "__main__":
    main()
