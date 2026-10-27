"""Charge-pump PLL loop design: loop-filter values, Bode/phase margin, robustness,
I_cp trade-off and a first phase-noise / jitter budget.

Third-order passive filter: C2 || (R + C1) on Vctrl.
  Z(s) = (1 + s/wz) / (s Ctot (1 + s/wp3)),  Ctot = C1 + C2, wz = 1/(R C1), wp3 = b wz, b = 1 + C1/C2
  open loop G(s) = Icp * Kvco * Z(s) / (N s)     (Kvco in Hz/V; the 2 pi factors cancel)
Placing crossover at the geometric mean of zero and pole gives
  PM = atan((b-1) / (2 sqrt b)),  Ctot = Icp Kvco sqrt(b) / (N wc^2),  R = sqrt(b) / (wc C1)

Run: python model/loop_design.py   -> model/results/*.png, loop_summary.txt
"""
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = Path(__file__).resolve().parent / "results"
K_B = 1.380649e-23
T = 300.0


@dataclass
class Spec:
    f_ref: float = 25e6
    N: int = 12
    i_cp: float = 40e-6          # A, chosen below from the I_cp trade-off
    k_vco: float = 140e6         # Hz/V, from the GF180 ring sim (118-147 MHz/V at the 300 MHz lock point)
    f_c: float = 1.5e6           # crossover, ~f_ref/17
    pm_deg: float = 60.0
    cap_density: float = 3.98e-15 / 1e-12  # F/m^2: cap_nmos_03v3 in inversion (Vctrl >= 1 V). MIM is
                                           # unusable on TT GF: MIM option B needs Metal5, which the tile forbids
    tile_area: float = 711.20e-6 * 325.36e-6  # 2x2 analog tile, m^2
    vdd: float = 3.3
    t_rst: float = 1e-9

    @property
    def f_out(self):
        return self.f_ref * self.N


@dataclass
class Filter:
    R: float
    C1: float
    C2: float
    b: float = field(init=False)

    def __post_init__(self):
        self.b = 1 + self.C1 / self.C2

    @property
    def ctot(self):
        return self.C1 + self.C2

    def Z(self, s):
        wz = 1 / (self.R * self.C1)
        wp = self.b * wz
        return (1 + s / wz) / (s * self.ctot * (1 + s / wp))


def design(sp: Spec) -> Filter:
    pm = np.radians(sp.pm_deg)
    # solve PM = atan((b-1)/(2 sqrt b)) for b: tan(pm) = (b-1)/(2 sqrt b) -> sqrt b = tan + sqrt(tan^2+1)
    t = np.tan(pm)
    sb = t + np.sqrt(t * t + 1)
    b = sb * sb
    wc = 2 * np.pi * sp.f_c
    ctot = sp.i_cp * sp.k_vco * sb / (sp.N * wc ** 2)
    c1 = ctot * (b - 1) / b
    c2 = ctot / b
    r = sb / (wc * c1)
    return Filter(r, c1, c2)


def open_loop(sp: Spec, flt: Filter, f, scale=1.0):
    s = 2j * np.pi * f
    return scale * sp.i_cp * sp.k_vco * flt.Z(s) / (sp.N * s)


def margins(sp, flt, scale=1.0):
    f = np.logspace(3, 9, 20000)
    G = open_loop(sp, flt, f, scale)
    mag = np.abs(G)
    i = np.where(mag < 1)[0][0]
    fc = np.interp(1, mag[i:i - 2:-1], f[i:i - 2:-1]) if i > 0 else f[i]
    ph = np.degrees(np.angle(open_loop(sp, flt, np.array([fc]), scale)))[0]
    return fc, 180 + ph


def noise_budget(sp: Spec, flt: Filter, fom_dbc=-157.0, p_vco=0.36e-3, f3_corner=500e3,
                 ref_floor_dbc=-130.0, cp_gm_over_id=8.0, gamma=1.0):
    """Single-sideband phase noise at the VCO output, per source, in dBc/Hz.
    All inputs are ASSUMPTIONS to refine with simulation; see the PLAN."""
    f = np.logspace(3, np.log10(sp.f_ref / 2), 600)
    s = 2j * np.pi * f
    G = open_loop(sp, flt, f)
    H_lp = G / (1 + G)           # reference / CP path (times N for reference)
    H_hp = 1 / (1 + G)           # VCO path
    # VCO free running: FOM = L + 10log(P/1mW) - 20log(f0/df)
    L_vco = fom_dbc + 20 * np.log10(sp.f_out / f) - 10 * np.log10(p_vco / 1e-3)
    L_vco = L_vco + 10 * np.log10(1 + f3_corner / f)          # crude 1/f^3 region
    S_vco = 2 * 10 ** (L_vco / 10)                             # rad^2/Hz (two-sided -> S_phi = 2 L)
    out = {"VCO": S_vco * np.abs(H_hp) ** 2}
    # reference: flat floor at f_ref, multiplied by N^2 in band
    S_ref = 2 * 10 ** (ref_floor_dbc / 10) * np.ones_like(f)
    out["Reference"] = S_ref * sp.N ** 2 * np.abs(H_lp) ** 2
    # charge pump: two sources, thermal drain noise 4kT gamma gm, on for t_rst out of each period
    gm = cp_gm_over_id * sp.i_cp
    i_n2 = 2 * 4 * K_B * T * gamma * gm * (sp.t_rst * sp.f_ref)
    out["Charge pump"] = i_n2 * (2 * np.pi * sp.N / sp.i_cp) ** 2 * np.abs(H_lp) ** 2
    # loop-filter resistor: its voltage noise reaches Vctrl through the C1/C2 divider seen from the loop
    v_n2 = 4 * K_B * T * flt.R
    # Vctrl / v_R transfer with the loop closed: K_vco/s * 2pi * (C1 branch shaping) * H_hp
    zr = 1 / (1 + s * flt.R * flt.C1 * flt.C2 / flt.ctot) * (flt.C1 / flt.ctot)
    out["Loop-filter R"] = v_n2 * np.abs(2 * np.pi * sp.k_vco / s * zr) ** 2 * np.abs(H_hp) ** 2
    total = sum(out.values())
    out["Total"] = total
    L = {k: 10 * np.log10(v / 2) for k, v in out.items()}
    jit = {}
    for k, v in out.items():
        rad2 = np.trapezoid(v, f)
        jit[k] = np.sqrt(rad2) / (2 * np.pi * sp.f_out)
    return f, L, jit


def main():
    OUT.mkdir(exist_ok=True)
    lines = []
    sp = Spec()

    # --- I_cp trade-off at fixed crossover / PM
    lines.append("I_cp trade-off (f_c = 1.5 MHz, PM = 60 deg, K_vco = 140 MHz/V, N = 12)")
    lines.append("  I_cp   Ctot     C1      C2      R       area@4fF/um2  I*R step   R noise")
    for icp in (10e-6, 20e-6, 40e-6, 80e-6):
        s2 = Spec(i_cp=icp)
        fl = design(s2)
        area = fl.ctot / s2.cap_density * 1e12
        lines.append(f"  {icp*1e6:4.0f}u {fl.ctot*1e12:6.1f}p {fl.C1*1e12:6.2f}p {fl.C2*1e12:6.2f}p "
                     f"{fl.R/1e3:6.1f}k  {area:8.0f} um2  {icp*fl.R:6.2f} V   "
                     f"{np.sqrt(4*K_B*T*fl.R)*1e9:5.1f} nV/rtHz")

    flt = design(sp)
    lines.append(f"\nChosen: I_cp = {sp.i_cp*1e6:.0f} uA -> R = {flt.R/1e3:.1f} kOhm, C1 = {flt.C1*1e12:.2f} pF, "
                 f"C2 = {flt.C2*1e12:.2f} pF (b = {flt.b:.1f})")
    lines.append(f"  zero {1/(2*np.pi*flt.R*flt.C1)/1e3:.0f} kHz, pole {flt.b/(2*np.pi*flt.R*flt.C1)/1e6:.2f} MHz, "
                 f"area {flt.ctot/sp.cap_density*1e12:.0f} um2 of MOS cap "
                 f"({flt.ctot/sp.cap_density/sp.tile_area*100:.1f}% of a 2x2 tile, 711x325 um)")
    lines.append("\nRobustness (I_cp*K_vco product scaled):")
    for sc in (0.5, 0.7, 1.0, 1.4, 2.0):
        fc, pm = margins(sp, flt, sc)
        lines.append(f"  x{sc:<4} f_c = {fc/1e6:5.2f} MHz (f_ref/{sp.f_ref/fc:4.1f})  PM = {pm:5.1f} deg")

    # --- Bode plot
    f = np.logspace(3, 8.5, 2000)
    fig, ax = plt.subplots(2, 1, figsize=(7, 6), sharex=True)
    for sc, c in ((0.5, "C1"), (1.0, "k"), (2.0, "C3")):
        G = open_loop(sp, flt, f, sc)
        ax[0].semilogx(f, 20 * np.log10(np.abs(G)), color=c, label=f"I_cp*K_vco x{sc}")
        ax[1].semilogx(f, np.degrees(np.angle(G)), color=c)
    ax[0].axhline(0, color="gray", lw=0.8)
    ax[0].axvline(sp.f_ref / 10, color="r", ls=":", lw=1, label="f_ref/10")
    ax[1].axvline(sp.f_ref / 10, color="r", ls=":", lw=1)
    ax[1].axhline(-180, color="gray", lw=0.8)
    ax[0].set(ylabel="|G| (dB)", ylim=(-60, 100), title=f"Open loop: R={flt.R/1e3:.1f}k C1={flt.C1*1e12:.1f}p C2={flt.C2*1e12:.2f}p")
    ax[1].set(xlabel="f (Hz)", ylabel="phase (deg)", ylim=(-200, -60))
    ax[0].legend(fontsize=8)
    for a in ax:
        a.grid(True, which="both", alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUT / "loop_bode.png", dpi=130)

    # --- noise budget
    fn, L, jit = noise_budget(sp, flt)
    fig, ax = plt.subplots(figsize=(7, 4.5))
    for k, v in L.items():
        ax.semilogx(fn, v, lw=2.2 if k == "Total" else 1.2, color="k" if k == "Total" else None,
                    label=f"{k}: {jit[k]*1e12:.1f} ps rms")
    ax.set(xlabel="offset (Hz)", ylabel="L(f) (dBc/Hz)", ylim=(-150, -60),
           title=f"Phase-noise budget at {sp.f_out/1e6:.0f} MHz (ASSUMED source levels)")
    ax.grid(True, which="both", alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "noise_budget.png", dpi=130)
    lines.append("\nJitter budget (integrated 1 kHz .. f_ref/2), assumptions: ring FOM -157 dBc/Hz, 0.36 mW, "
                 "1/f^3 corner 500 kHz, reference floor -130 dBc/Hz, CP gm/ID = 8")
    for k, v in jit.items():
        lines.append(f"  {k:14s} {v*1e12:6.2f} ps rms")
    i1 = np.argmin(abs(fn - 1e6))
    lines.append(f"  total L(1 MHz) = {L['Total'][i1]:.1f} dBc/Hz; free-running VCO alone at 1 MHz = "
                 f"{-157 + 20*np.log10(sp.f_out/1e6) - 10*np.log10(0.36) + 10*np.log10(1.5):.1f} dBc/Hz")

    txt = "\n".join(lines)
    print(txt)
    (OUT / "loop_summary.txt").write_text(txt + "\n")


if __name__ == "__main__":
    main()
