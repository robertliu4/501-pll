"""GF180 3.3 V device characterization (typical, 27 C).

Produces the gm/ID charts used for first-pass sizing of the VCO starve devices,
the V-to-I converter, the charge-pump sources and the buffer OTA.
Outputs: results/devices_gmid.png, results/devices_table.csv
"""
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import spice

W = 10e-6
LS = [0.28e-6, 0.5e-6, 1.0e-6, 2.0e-6]
VDS = [1.6, 1.7]   # two points so gds comes from a finite difference


def sweep(kind, L, vds):
    tag = f"{kind}_L{L*1e6:.2f}_vds{vds:.2f}".replace(".", "p")
    if kind == "n":
        dev = f"M1 d g 0 0 nfet_03v3 W={W} L={L}"
        bias = f"VD d 0 {vds}\nVG g 0 0"
        sweep_cmd = "dc VG 0 3.3 0.005"
        probe = "-i(VD)"
    else:
        dev = f"M1 d g 0 0 pfet_03v3 W={W} L={L}"
        bias = f"VD d 0 {-vds}\nVG g 0 0"
        sweep_cmd = "dc VG 0 -3.3 -0.005"
        probe = "i(VD)"
    deck = f"""* {tag}
{spice.models('typical', mim=False, res=False)}
{bias}
{dev}
.control
{sweep_cmd}
wrdata {tag}.txt {probe}
.endc
.end
"""
    spice.run(tag, deck)
    d = spice.wrdata(f"{tag}.txt")
    return np.abs(d[:, 0]), d[:, 1]


def main():
    fig, ax = plt.subplots(1, 3, figsize=(15, 4.5))
    rows = []
    for kind, ls in (("n", "-"), ("p", "--")):
        for L in LS:
            vgs, i1 = sweep(kind, L, VDS[0])
            _, i2 = sweep(kind, L, VDS[1])
            i = 0.5 * (i1 + i2)
            gm = np.gradient(i, vgs)
            gds = (i2 - i1) / (VDS[1] - VDS[0])
            ok = i > 1e-9
            gmid = np.where(ok, gm / np.maximum(i, 1e-15), np.nan)
            jd = i / W                  # A/m == uA/um
            gain = np.where(ok, gm / np.maximum(gds, 1e-15), np.nan)
            lab = f"{kind}fet L={L*1e6:.2f}u"
            ax[0].semilogy(vgs, jd, ls, label=lab)
            ax[1].semilogx(jd[ok], gmid[ok], ls, label=lab)
            ax[2].semilogx(jd[ok], gain[ok], ls, label=lab)
            # constant-current Vth: ID = 0.1 uA * W/L
            vth = np.interp(0.1e-6 * W / L, i, vgs)
            for target in (8, 10, 15):
                # strong-inversion side: highest current where gm/ID >= target
                idx = np.where(ok & (gmid >= target))[0]
                k = idx[-1] if len(idx) else None
                rows.append(dict(dev=kind, L_um=L * 1e6, vth_cc=vth, gmid=target,
                                 jd_uA_per_um=jd[k] if k is not None else np.nan,
                                 vov_V=(vgs[k] - vth) if k is not None else np.nan,
                                 gm_gds=gain[k] if k is not None else np.nan))
    ax[0].set(xlabel="|VGS| (V)", ylabel="|ID|/W (uA/um)", title="Current density, |VDS|=1.65 V", ylim=(1e-4, 1e3))
    ax[1].set(xlabel="|ID|/W (uA/um)", ylabel="gm/ID (1/V)", title="gm/ID", ylim=(0, 30))
    ax[2].set(xlabel="|ID|/W (uA/um)", ylabel="gm/gds", title="Intrinsic gain", ylim=(1, 1e3), yscale="log")
    for a in ax:
        a.grid(True, which="both", alpha=0.3)
    ax[1].legend(fontsize=7)
    fig.suptitle("GF180MCU nfet_03v3 / pfet_03v3, typical 27 C")
    fig.tight_layout()
    spice.RESULTS.mkdir(exist_ok=True)
    fig.savefig(spice.RESULTS / "devices_gmid.png", dpi=130)

    import csv
    with open(spice.RESULTS / "devices_table.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    for r in rows:
        print("{dev} L={L_um:.2f}u Vth_cc={vth_cc:.3f}  gm/ID={gmid:>2}: J={jd_uA_per_um:7.2f} uA/um "
              "Vov={vov_V:.3f} gm/gds={gm_gds:6.1f}".format(**r))


if __name__ == "__main__":
    main()
