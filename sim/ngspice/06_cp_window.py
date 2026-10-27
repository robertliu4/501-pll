"""Charge-pump output window: I_up and I_dn vs Vctrl, simple vs cascoded sources.

The CP only matches over a limited Vctrl range; the VCO lock points (1.61-2.28 V
across corners, from 02_ring_vco.py) must sit inside it. Switches are held on,
references are ideal 40 uA sources (the real bias generator is a separate sim),
and the output is swept with an ideal source, so this isolates output-resistance
and headroom effects. Sizes come from the gm/ID table (01_devices.py):
  sources  L = 1 um at gm/ID ~ 8   (nfet ~3.6 uA/um, pfet ~0.88 uA/um)
  cascodes L = 0.5 um at gm/ID ~ 10 (nfet ~4.3 uA/um, pfet ~1.2 uA/um)
Wide-swing cascode bias: a diode device at 1/4 width sets the cascode gate.
Output: results/cp_window.txt, results/cp_window.png
"""
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import spice

ICP = 40e-6
WN, WNC, WP, WPC = 11.0, 9.3, 46.0, 33.0
LS, LC = 1.0, 0.5
WSWN, WSWP = 2.0, 4.0
LOCK = (1.61, 2.28)


def deck(corner_key, cascode):
    corner, temp, vdd = spice.CORNERS[corner_key]
    if cascode:
        nmos = f"""
* NMOS sink, wide-swing cascode mirror
IRN vdd vbn {ICP}
MN3C vbn vcn xn3 0 nfet_03v3 W={WNC}u L={LC}u
MN3 xn3 vbn 0 0 nfet_03v3 W={WN}u L={LS}u
IRNC vdd vcn {ICP}
MN5 vcn vcn 0 0 nfet_03v3 W={WN/4:.2f}u L={LS}u
MN1 xn1 vbn 0 0 nfet_03v3 W={WN}u L={LS}u
MN1C yn vcn xn1 0 nfet_03v3 W={WNC}u L={LC}u
"""
        pmos = f"""
* PMOS source, wide-swing cascode mirror
IRP vbp 0 {ICP}
MP3C vbp vcp xp3 vdd pfet_03v3 W={WPC}u L={LC}u
MP3 xp3 vbp vdd vdd pfet_03v3 W={WP}u L={LS}u
IRPC vcp 0 {ICP}
MP5 vcp vcp vdd vdd pfet_03v3 W={WP/4:.2f}u L={LS}u
MP1 xp1 vbp vdd vdd pfet_03v3 W={WP}u L={LS}u
MP1C yp vcp xp1 vdd pfet_03v3 W={WPC}u L={LC}u
"""
    else:
        nmos = f"""
IRN vdd vbn {ICP}
MN3 vbn vbn 0 0 nfet_03v3 W={WN}u L={LS}u
MN1 yn vbn 0 0 nfet_03v3 W={WN}u L={LS}u
"""
        pmos = f"""
IRP vbp 0 {ICP}
MP3 vbp vbp vdd vdd pfet_03v3 W={WP}u L={LS}u
MP1 yp vbp vdd vdd pfet_03v3 W={WP}u L={LS}u
"""
    tag = f"cp_{'casc' if cascode else 'simple'}_{corner_key}"
    return tag, f"""* {tag}
{spice.models(corner, mim=False, res=False)}
.temp {temp}
VDD vdd 0 {vdd}
{nmos}
{pmos}
* steering switches held on
MSWP yp 0 outp vdd pfet_03v3 W={WSWP}u L=0.28u
MSWN yn vdd outn 0 nfet_03v3 W={WSWN}u L=0.28u
VOP outp vout 0
VON vout outn 0
VOUT vout 0 0
.control
dc VOUT 0 {vdd} 0.01
wrdata {tag}.txt i(VOP) i(VON)
.endc
.end
"""


def run(corner_key, cascode):
    tag, d = deck(corner_key, cascode)
    spice.run(tag, d)
    a = spice.wrdata(f"{tag}.txt")
    v, iup, idn = a[:, 0], a[:, 1], a[:, 3]
    return v, iup, idn


def window(v, iup, idn, tol):
    ok = (np.abs(iup - idn) / ICP < tol) & (iup > (1 - tol) * ICP) & (idn > (1 - tol) * ICP)
    if not ok.any():
        return np.nan, np.nan
    # largest contiguous run
    best, cur, start = (0, 0, 0), 0, 0
    for i, o in enumerate(ok):
        if o:
            if cur == 0:
                start = i
            cur += 1
            if cur > best[0]:
                best = (cur, start, i)
        else:
            cur = 0
    return v[best[1]], v[best[2]]


def main():
    keys = list(spice.CORNERS)
    pool = ThreadPoolExecutor(max_workers=10)
    jobs = {(k, c): pool.submit(run, k, c) for k in keys for c in (False, True)}
    res = {key: j.result() for key, j in jobs.items()}
    lines = [f"Charge pump {ICP*1e6:.0f} uA: Vctrl window where |I_up-I_dn| < tol*I_cp and both within tol of nominal",
             f"(VCO lock points for 300 MHz across corners: {LOCK[0]}-{LOCK[1]} V)"]
    for c in (False, True):
        lines.append(f"\n{'cascoded (wide-swing)' if c else 'simple mirrors'}:")
        for tol in (0.02, 0.05):
            lines.append(f"  tol {tol*100:.0f}%:")
            for k in keys:
                lo, hi = window(*res[(k, c)], tol)
                inside = lo <= LOCK[0] and hi >= LOCK[1]
                lines.append(f"    {k:12s} {lo:5.2f} - {hi:5.2f} V   {'covers lock range' if inside else 'DOES NOT cover lock range'}")
    txt = "\n".join(lines)
    print(txt)
    (spice.RESULTS / "cp_window.txt").write_text(txt + "\n")

    fig, ax = plt.subplots(1, 2, figsize=(12, 4.5), sharey=True)
    for i, c in enumerate((False, True)):
        for k in keys:
            v, iup, idn = res[(k, c)]
            ax[i].plot(v, (iup - idn) / ICP * 100, label=k)
        ax[i].axvspan(*LOCK, color="g", alpha=0.1, label="VCO lock range")
        ax[i].axhspan(-5, 5, color="gray", alpha=0.1)
        ax[i].set(xlabel="Vctrl (V)", title=("cascoded" if c else "simple") + " sources: (I_up - I_dn)/I_cp",
                  ylim=(-30, 30))
        ax[i].grid(alpha=0.3)
    ax[0].set_ylabel("mismatch (%)")
    ax[1].legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(spice.RESULTS / "cp_window.png", dpi=130)


if __name__ == "__main__":
    main()
