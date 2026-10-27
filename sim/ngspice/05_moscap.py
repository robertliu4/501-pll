"""MOS capacitor density vs bias (loop-filter C1/C2 and supply decap).

MIM is out on TT GF (MIM option B needs Metal5, which the tile forbids), so the
loop filter uses MOS caps. Output: results/moscap.txt
"""
import spice

KINDS = ["cap_nmos_03v3", "cap_nmos_03v3_b", "cap_pmos_03v3"]
SIDE = 10e-6


def main():
    lines = ["small-signal C density (fF/um^2) at 1 MHz, 10x10 um device, typical"]
    lines.append("  Vbias  " + "  ".join(f"{k:>16s}" for k in KINDS))
    for v in (0.0, 0.5, 0.75, 1.0, 1.5, 2.0, 2.5, 3.0, 3.3):
        row = []
        for k in KINDS:
            # pmos cap is drawn with its gate at the low terminal, so flip the bias for it
            nodes = "g 0" if "nmos" in k else "0 g"
            deck = f"""* {k} {v}
{spice.models('typical', mim=False, res=False)}
.lib {spice.NGSPICE_DIR / 'sm141064.ngspice'} moscap_typical
VG g 0 DC {v} AC 1
XC {nodes} {k} c_width={SIDE} c_length={SIDE}
.control
ac lin 1 1meg 1meg
let c = abs(imag(i(VG)))/(2*pi*1e6)
print c
.endc
.end
"""
            m = spice.meas(spice.run(f"moscap_{k}_{v}", deck))
            row.append(m["c"] / (SIDE * SIDE) * 1e3)   # F/m^2 -> fF/um^2
        lines.append(f"  {v:5.2f}  " + "  ".join(f"{c:16.3f}" for c in row))
    txt = "\n".join(lines)
    print(txt)
    (spice.RESULTS / "moscap.txt").write_text(txt + "\n")


if __name__ == "__main__":
    main()
