"""Divide-by-4 prescaler from two TSPC divide-by-2 stages on 3.3 V devices, driven
straight from a 5-stage starved ring node through a small inverter (no ideal
edges anywhere). Checks it divides correctly across corners and at both ends of
the VCO range, including a 'slow silicon' case with the ring running 2x slower
(extra load), which the measured TTGF0p2 ring results suggest can happen.
Output: results/prescaler.txt
"""
from concurrent.futures import ThreadPoolExecutor

import numpy as np

import spice

SC = "gf180mcu_fd_sc_mcu7t5v0__"
SZ = dict(WNI=2.0, WPI=5.0, LI=0.28, WNS=10.0, LNS=0.5, WPS=30.0, LPS=0.5)


def tspc(name, ck, q):
    """TSPC divide-by-2: output of stage 3 fed back as D. Internal nodes are prefixed."""
    a, b, c, e, f = (f"{name}_{x}" for x in "abcef")
    return f"""
M{name}1 {a} {q} vdd vdd pfet_03v3 W=2u L=0.28u
M{name}2 {b} {ck} {a} vdd pfet_03v3 W=2u L=0.28u
M{name}3 {b} {q} 0 0 nfet_03v3 W=1u L=0.28u
M{name}4 {c} {ck} vdd vdd pfet_03v3 W=2u L=0.28u
M{name}5 {c} {b} {e} 0 nfet_03v3 W=2u L=0.28u
M{name}6 {e} {ck} 0 0 nfet_03v3 W=2u L=0.28u
M{name}7 {q} {c} vdd vdd pfet_03v3 W=3u L=0.28u
M{name}8 {q} {ck} {f} 0 nfet_03v3 W=2u L=0.28u
M{name}9 {f} {c} 0 0 nfet_03v3 W=2u L=0.28u
"""


def deck(ck_key, iref, extra_cl):
    corner, temp, vdd = spice.CORNERS[ck_key]
    s = SZ
    ring = []
    for k in range(5):
        a, b = f"n{k+1}", f"n{(k+1) % 5 + 1}"
        ring.append(f"MPS{k} xp{k} vbp vdd vdd pfet_03v3 W={s['WPS']}u L={s['LPS']}u")
        ring.append(f"MPI{k} {b} {a} xp{k} vdd pfet_03v3 W={s['WPI']}u L={s['LI']}u")
        ring.append(f"MNI{k} {b} {a} xn{k} 0 nfet_03v3 W={s['WNI']}u L={s['LI']}u")
        ring.append(f"MNS{k} xn{k} vbn 0 0 nfet_03v3 W={s['WNS']}u L={s['LNS']}u")
        ring.append(f"MDP{k} vdd {b} vdd vdd pfet_03v3 W={s['WPI']}u L={s['LI']}u")
        ring.append(f"MDN{k} 0 {b} 0 0 nfet_03v3 W={s['WNI']}u L={s['LI']}u")
        if extra_cl:
            ring.append(f"CX{k} {b} 0 {extra_cl}")
    return f"""* prescaler {ck_key} {iref}
{spice.models(corner, mim=False, res=False, stdcells=True)}
.temp {temp}
VDD vdd 0 {vdd}
IREF vdd vbn {iref}
M4 vbn vbn 0 0 nfet_03v3 W={s['WNS']}u L={s['LNS']}u
M3 vbp vbn 0 0 nfet_03v3 W={s['WNS']}u L={s['LNS']}u
M2 vbp vbp vdd vdd pfet_03v3 W={s['WPS']}u L={s['LPS']}u
{chr(10).join(ring)}
* output buffer: two 3.3 V inverters from ring node n5
MB1P o1 n5 vdd vdd pfet_03v3 W=5u L=0.28u
MB1N o1 n5 0 0 nfet_03v3 W=2u L=0.28u
MB2P ck o1 vdd vdd pfet_03v3 W=10u L=0.28u
MB2N ck o1 0 0 nfet_03v3 W=4u L=0.28u
{tspc('d1', 'ck', 'q1')}
* invert stage-1 output so stage 2 clocks on a clean edge
MI1P q1b q1 vdd vdd pfet_03v3 W=5u L=0.28u
MI1N q1b q1 0 0 nfet_03v3 W=2u L=0.28u
{tspc('d2', 'q1b', 'q2')}
XL q2 q2l vdd vdd 0 0 {SC}inv_1
.ic v(n1)=0 v(n2)={vdd} v(n3)=0 v(n4)={vdd}
.control
tran 10p 600n
meas tran a1 WHEN v(ck)={vdd/2} RISE=8
meas tran a2 WHEN v(ck)={vdd/2} RISE=40
meas tran b1 WHEN v(q2)={vdd/2} RISE=3
meas tran b2 WHEN v(q2)={vdd/2} RISE=11
.endc
.end
"""


def check(ck_key, iref, extra_cl):
    log = spice.run(f"presc_{ck_key}_{iref*1e6:.0f}u_{'slow' if extra_cl else 'nom'}", deck(ck_key, iref, extra_cl))
    m = spice.meas(log)
    try:
        fck = 32 / (m["a2"] - m["a1"])
        fq = 8 / (m["b2"] - m["b1"])
    except KeyError:
        return np.nan, np.nan, False
    return fck, fq, abs(fq * 4 - fck) / fck < 0.01


def main():
    keys = ["tt_27C_3v3", "ss_85C_3v0", "ff_0C_3v6"]
    spice.CORNERS["ss_125C_3v0"] = ("ss", 125, 3.0)
    keys.append("ss_125C_3v0")
    pool = ThreadPoolExecutor(max_workers=10)
    cases = [(k, i, cl) for k in keys for i in (40e-6, 110e-6, 300e-6, 600e-6) for cl in (0, "20f")]
    jobs = {c: pool.submit(check, *c) for c in cases}
    lines = ["TSPC /4 prescaler driven by the real starved ring (VCO freq, /4 output x4, divides correctly?)"]
    for c in cases:
        fck, fq, ok = jobs[c].result()
        lines.append(f"  {c[0]:12s} Iref={c[1]*1e6:4.0f}uA {'slow-silicon (+20 fF/stage)' if c[2] else 'nominal':27s} "
                     f"VCO {fck/1e6:7.1f} MHz  /4*4 = {fq*4/1e6:7.1f} MHz  {'OK' if ok else 'FAIL'}")
    txt = "\n".join(lines)
    print(txt)
    (spice.RESULTS / "prescaler.txt").write_text(txt + "\n")


if __name__ == "__main__":
    main()
