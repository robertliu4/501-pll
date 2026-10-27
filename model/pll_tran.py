"""Time-domain behavioural CP-PLL: PFD state machine, charge pump with mismatch and
reset delay, the passive loop filter, and the VCO tuning curves simulated in ngspice
(sim/results/vco_summary.txt). Edges are timed to sub-step precision so the
charge per pulse is exact.

Checks: lock from a cold start (Vctrl = 0) at every corner, lock time, the static
phase offset from current mismatch, Vctrl ripple at lock and the resulting
reference-spur estimate. Output: model/results/pll_lock.png, pll_tran_summary.txt
"""
import re
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from loop_design import Spec, design

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent / "results"


def load_vco_curves():
    txt = (ROOT / "sim" / "results" / "vco_summary.txt").read_text()
    block = txt.split("C) full VCO")[1].split("lock point")[0]
    header = None
    rows = []
    for ln in block.splitlines():
        if ln.strip().startswith("Vctrl"):
            header = ln.split()[1:]
        elif re.match(r"^\s+\d", ln):
            rows.append([float(x) for x in ln.split()])
    a = np.array(rows)
    return {h: (a[:, 0], a[:, i + 1] * 1e6) for i, h in enumerate(header)}


def simulate(sp, flt, vco, t_end=12e-6, dt=20e-12, mismatch=0.0, leak=0.0, v0=0.0, ref_jitter=0.0, seed=1):
    """Fixed-step integration with exact edge timing inside each step.
    mismatch: I_dn = I_up * (1 + mismatch). leak: constant current out of Vctrl (A)."""
    rng = np.random.default_rng(seed)
    vtab, ftab = vco
    i_up = sp.i_cp
    i_dn = sp.i_cp * (1 + mismatch)
    R, C1, C2 = flt.R, flt.C1, flt.C2
    v1 = v2 = v0                       # C1 voltage, Vctrl (= C2 voltage)
    phase = 0.0                        # VCO phase in cycles
    next_div = sp.N                    # VCO phase at which the next DIV edge happens
    T_ref = 1 / sp.f_ref
    next_ref = T_ref + (rng.normal(0, ref_jitter) if ref_jitter else 0.0)
    up = dn = False
    t_reset = np.inf
    t_up_on = t_dn_on = 0.0
    n = int(t_end / dt)
    dec = 25
    log_t, log_v, log_f = [], [], []
    ref_edges, div_edges = [], []
    t = 0.0
    for k in range(n):
        t_next = t + dt
        # collect events inside (t, t_next]
        q = 0.0                         # charge into Vctrl this step
        tau = t
        f = np.interp(v2, vtab, ftab)
        # VCO phase over the step (frequency frozen within the 20 ps step)
        ph_next = phase + f * dt
        events = []
        if next_ref <= t_next:
            events.append((next_ref, "ref"))
        if ph_next >= next_div:
            events.append((t + (next_div - phase) / f, "div"))
        if t_reset <= t_next:
            events.append((t_reset, "rst"))
        events.sort()
        for te, kind in events:
            q += (i_up * up - i_dn * dn) * (te - tau)
            tau = te
            if kind == "ref":
                up = True
                ref_edges.append(te)
                next_ref += T_ref + (rng.normal(0, ref_jitter) if ref_jitter else 0.0)
            elif kind == "div":
                dn = True
                div_edges.append(te)
                next_div += sp.N
            else:
                up = dn = False
                t_reset = np.inf
            if up and dn and t_reset == np.inf:
                t_reset = te + sp.t_rst
        q += (i_up * up - i_dn * dn) * (t_next - tau)
        q -= leak * dt
        # loop filter: charge lands on C2, then C2 and C1 exchange through R
        v2 += q / C2
        ir = (v2 - v1) / R
        v2 -= ir * dt / C2
        v1 += ir * dt / C1
        phase = ph_next
        t = t_next
        if k % dec == 0:
            log_t.append(t)
            log_v.append(v2)
            log_f.append(f)
    return (np.array(log_t), np.array(log_v), np.array(log_f),
            np.array(ref_edges), np.array(div_edges))


def lock_metrics(sp, t, v, f, ref, div):
    target = sp.f_out
    ok = np.abs(f - target) / target < 0.001
    # lock = last time the frequency left the 0.1% band
    if not ok[-1]:
        return np.nan, np.nan, np.nan
    bad = np.where(~ok)[0]
    t_lock = t[bad[-1]] if len(bad) else t[0]
    # pair each late DIV edge with its nearest REF edge (acquisition slips cycles, so
    # index-by-index pairing would be off by whole periods)
    tail_div = div[int(0.8 * len(div)):]
    j = np.clip(np.searchsorted(ref, tail_div), 1, len(ref) - 1)
    nearest = np.where(abs(ref[j] - tail_div) < abs(ref[j - 1] - tail_div), ref[j], ref[j - 1])
    tail = tail_div - nearest
    late = t > t[-1] - 2e-6
    ripple = v[late].max() - v[late].min()
    return t_lock, np.median(tail), ripple


def main():
    OUT.mkdir(exist_ok=True)
    sp = Spec()
    flt = design(sp)
    curves = load_vco_curves()
    lines = [f"Loop: I_cp={sp.i_cp*1e6:.0f}uA R={flt.R/1e3:.1f}k C1={flt.C1*1e12:.2f}p C2={flt.C2*1e12:.2f}p "
             f"t_rst={sp.t_rst*1e9:.1f}ns, cold start Vctrl=0"]
    fig, ax = plt.subplots(2, 1, figsize=(8, 6.5), sharex=True)
    for name, vco in curves.items():
        t, v, f, ref, div = simulate(sp, flt, vco, t_end=12e-6)
        t_lock, pe, rip = lock_metrics(sp, t, v, f, ref, div)
        lines.append(f"  {name:12s} lock time {t_lock*1e6:5.2f} us, final Vctrl {v[-1]:.3f} V, "
                     f"static phase error {pe*1e12:6.1f} ps")
        ax[0].plot(t * 1e6, v, lw=1, label=name)
        ax[1].plot(t * 1e6, f / 1e6, lw=1, label=name)
    ax[0].axhspan(1.0, 2.7, color="g", alpha=0.06)
    ax[0].set(ylabel="Vctrl (V)", title="Behavioural lock from cold start, GF180 VCO curves per corner")
    ax[1].axhline(sp.f_out / 1e6, color="k", ls=":", lw=1)
    ax[1].set(xlabel="time (us)", ylabel="VCO freq (MHz)")
    for a in ax:
        a.grid(alpha=0.3)
        a.legend(fontsize=7, ncol=3)
    fig.tight_layout()
    fig.savefig(OUT / "pll_lock.png", dpi=130)

    # non-idealities at typical: mismatch -> static offset and ripple -> reference spur estimate
    lines.append("\nNon-idealities at tt (starting already near lock):")
    tt = curves["tt_27C_3v3"]
    v_lock = float(np.interp(sp.f_out, tt[1], tt[0]))
    for mm, lk in ((0.0, 0.0), (0.05, 0.0), (0.10, 0.0), (0.0, 1e-9), (0.0, 10e-9)):
        t, v, f, ref, div = simulate(sp, flt, tt, t_end=8e-6, mismatch=mm, leak=lk, v0=v_lock)
        _, pe, _ = lock_metrics(sp, t, v, f, ref, div)
        # fine-resolution ripple over the last few reference periods
        t2, v2, *_ = simulate(sp, flt, tt, t_end=8e-6, dt=10e-12, mismatch=mm, leak=lk, v0=v_lock)
        late = t2 > 7e-6
        vv = v2[late] - v2[late].mean()
        tt_ = t2[late]
        # fundamental of the ripple at f_ref -> FM sidebands: spur(dBc) = 20log(Kvco*A/(2 f_ref))
        a1 = 2 * abs(np.mean(vv * np.exp(-2j * np.pi * sp.f_ref * tt_)))
        spur = 20 * np.log10(max(sp.k_vco * a1 / (2 * sp.f_ref), 1e-12))
        lines.append(f"  mismatch {mm*100:4.1f}%  leak {lk*1e9:5.1f} nA: static offset {pe*1e12:7.1f} ps "
                     f"(predicted dI/I*t_rst = {mm*sp.t_rst*1e12:5.1f} ps), ripple@f_ref {a1*1e3:6.3f} mV "
                     f"-> ref spur ~ {spur:6.1f} dBc at the VCO, {spur-20*np.log10(16):6.1f} dBc after /16")
    txt = "\n".join(lines)
    print(txt)
    (OUT / "pll_tran_summary.txt").write_text(txt + "\n")


if __name__ == "__main__":
    main()
