"""Dummy tile layout to prove the Tiny Tapeout GF flow end to end (PLAN.md §5, W1 item 3).

Builds gds/<top>.gds and lef/<top>.lef for the 2x2 analog tile:
  - PR_bndry over the whole 711.20 x 325.36 um tile
  - all 51 template pins from tt_analog_2x2.def on Metal4 (drawing + label + text)
  - VDPWR / VGND power stripes on Metal4, 2 um wide, y = 5 ... 320.36 um
  - one std-cell inverter (filltie | inv_1 | filltie from gf180mcu_fd_sc_mcu7t5v0)
    with ua[0] -> I and ZN -> ua[1], rails tied to the stripes through via stacks
This mirrors what magic_init_project.tcl from tt-support-tools draws, plus the
inverter, without needing Magic. The real PLL layout replaces all of it.

Rules used (gf180mcuD techlef / via.rb): via 0.26 um square, 0.36 um apart in
arrays, Mx >= 0.28 um wide (M1 0.23); every coordinate is on the 5 nm grid.
Run:  ../.venv/bin/python make_dummy_gds.py
"""
import os
import re
from pathlib import Path

import gdstk

TOP = "tt_um_robertliu4_pll"
HERE = Path(__file__).resolve().parent
REPO = HERE.parent
DEF = HERE / "tt_analog_2x2.def"
PDK_ROOT = Path(os.environ.get("PDK_ROOT", Path.home() / ".ciel")) / "gf180mcuD"
SC_GDS = (PDK_ROOT / "libs.ref" / "gf180mcu_fd_sc_mcu7t5v0" / "gds"
          / "gf180mcu_fd_sc_mcu7t5v0.gds")
SC = "gf180mcu_fd_sc_mcu7t5v0__"

# GDS layer/datatype (gf180mcu.lyp)
PR_BNDRY = (0, 0)
M1, V1, M2, V2, M3, V3, M4 = (34, 0), (35, 0), (36, 0), (38, 0), (42, 0), (40, 0), (46, 0)
M4_LABEL = (46, 10)

STRIPE_W = 2.0
STRIPES = {"VDPWR": 268.0, "VGND": 344.0}   # left edge x, um
STRIPE_Y = (5.0, 320.36)
X0, Y0 = 300.0, 20.0                          # lower-left of the cell row
CELL_H = 3.92


def parse_def(path):
    """Die size and pin rectangles (um) from a template DEF."""
    text = path.read_text()
    dbu = int(re.search(r"UNITS DISTANCE MICRONS (\d+) ;", text).group(1))
    die = [int(v) / dbu for v in re.search(r"DIEAREA \( (\S+) (\S+) \) \( (\S+) (\S+) \) ;", text).groups()]
    pins = {}
    pin_re = re.compile(r"- (\S+) \+ NET \S+ \+ DIRECTION (\S+) \+ USE (\S+)\s+\+ PORT\s+"
                        r"\+ LAYER (\S+) \( (\S+) (\S+) \) \( (\S+) (\S+) \)\s+\+ PLACED \( (\S+) (\S+) \) N ;")
    for m in pin_re.finditer(text):
        name, direction, use, layer = m.group(1, 2, 3, 4)
        lx, by, rx, ty, ox, oy = (int(v) / dbu for v in m.group(5, 6, 7, 8, 9, 10))
        pins[name] = dict(direction=direction, use=use, layer=layer,
                          rect=(ox + lx, oy + by, ox + rx, oy + ty))
    return die[2], die[3], pins


def rect(cell, layer, x1, y1, x2, y2):
    cell.add(gdstk.rectangle((x1, y1), (x2, y2), layer=layer[0], datatype=layer[1]))


def via_stack(cell, cx, cy, n, top_layer, pad, m1_pad=True):
    """n x n cuts of Via1..Via(top) centred on (cx, cy), with square pads on the metals above M1.
    m1_pad=False lands Via1 on existing Metal1 (a std-cell pin) without adding any."""
    pitch = 0.26 + 0.36
    span = n * 0.26 + (n - 1) * 0.36
    vias = [V1, V2, V3]
    metals = [M1, M2, M3, M4]
    for i, via in enumerate(vias[:top_layer - 1]):
        for a in range(n):
            for b in range(n):
                x = cx - span / 2 + a * pitch
                y = cy - span / 2 + b * pitch
                rect(cell, via, x, y, x + 0.26, y + 0.26)
        for metal in metals[i:i + 2] if (i or m1_pad) else metals[1:2]:
            rect(cell, metal, cx - pad / 2, cy - pad / 2, cx + pad / 2, cy + pad / 2)


def pin(cell, name, x1, y1, x2, y2):
    rect(cell, M4, x1, y1, x2, y2)
    rect(cell, M4_LABEL, x1, y1, x2, y2)
    cell.add(gdstk.Label(name, ((x1 + x2) / 2, (y1 + y2) / 2), layer=M4_LABEL[0], texttype=M4_LABEL[1]))


def build_gds(width, height, pins):
    lib = gdstk.Library(unit=1e-6, precision=1e-9)
    sc = {c.name: c for c in gdstk.read_gds(str(SC_GDS)).cells}
    tie, inv = sc[SC + "filltie"], sc[SC + "inv_1"]
    lib.add(tie, inv)
    top = lib.new_cell(TOP)
    rect(top, PR_BNDRY, 0, 0, width, height)

    for name, p in pins.items():
        pin(top, name, *p["rect"])
    for name, x in STRIPES.items():
        pin(top, name, x, STRIPE_Y[0], x + STRIPE_W, STRIPE_Y[1])

    # filltie | inv_1 | filltie: the fillties are the well/substrate taps inv_1 lacks
    xi = X0 + 1.12
    top.add(gdstk.Reference(tie, (X0, Y0)), gdstk.Reference(inv, (xi, Y0)),
            gdstk.Reference(tie, (xi + 2.24, Y0)))
    x_end = xi + 2.24 + 1.12

    # rails: VDD (top, y = 3.62..4.22) left to VDPWR, VSS (bottom, -0.3..0.3) right to VGND
    vdd_x = STRIPES["VDPWR"] + STRIPE_W / 2
    vss_x = STRIPES["VGND"] + STRIPE_W / 2
    rect(top, M1, vdd_x - 0.6, Y0 + 3.62, X0, Y0 + 4.22)
    rect(top, M1, x_end, Y0 - 0.3, vss_x + 0.6, Y0 + 0.3)
    via_stack(top, vdd_x, Y0 + CELL_H, 2, 4, 1.2)
    via_stack(top, vss_x, Y0, 2, 4, 1.2)

    # signal stacks on the inv_1 pins (I: x 0.710-1.035, ZN: x 1.265-1.595), staggered in y
    # so the 0.5 um pads stay 1 um apart; the pins are < 0.34 um wide, so the cut keeps
    # >= 0.06 um from their line ends
    i_cx, i_cy = xi + 0.875, Y0 + 1.45
    z_cx, z_cy = xi + 1.43, Y0 + 2.95
    via_stack(top, i_cx, i_cy, 1, 4, 0.5, m1_pad=False)
    via_stack(top, z_cx, z_cy, 1, 4, 0.5, m1_pad=False)

    # Metal4: ua[0] -> I (route right, then down), ZN -> ua[1] (route left, then down)
    ua0, ua1 = pins["ua[0]"]["rect"], pins["ua[1]"]["rect"]
    ua0_cx, ua1_cx = (ua0[0] + ua0[2]) / 2, (ua1[0] + ua1[2]) / 2
    rect(top, M4, i_cx - 0.25, i_cy - 0.25, ua0_cx + 0.5, i_cy + 0.25)
    rect(top, M4, ua0_cx - 0.5, 0, ua0_cx + 0.5, i_cy + 0.25)
    rect(top, M4, ua1_cx - 0.5, z_cy - 0.25, z_cx + 0.25, z_cy + 0.25)
    rect(top, M4, ua1_cx - 0.5, 0, ua1_cx + 0.5, z_cy + 0.25)
    return lib


def write_lef(path, width, height, pins):
    out = ["VERSION 5.7 ;", '  NOWIREEXTENSIONATPIN ON ;', '  DIVIDERCHAR "/" ;', '  BUSBITCHARS "[]" ;',
           f"MACRO {TOP}", "  CLASS BLOCK ;", f"  FOREIGN {TOP} ;", "  ORIGIN 0.000 0.000 ;",
           f"  SIZE {width:.3f} BY {height:.3f} ;"]

    def lef_pin(name, direction, use, r):
        out.extend([f"  PIN {name}", f"    DIRECTION {direction} ;", f"    USE {use} ;", "    PORT",
                    "      LAYER Metal4 ;", "        RECT {:.3f} {:.3f} {:.3f} {:.3f} ;".format(*r),
                    "    END", f"  END {name}"])

    for name, p in pins.items():
        lef_pin(name, p["direction"], p["use"], p["rect"])
    for name, x in STRIPES.items():
        lef_pin(name, "INOUT", "GROUND" if name == "VGND" else "POWER",
                (x, STRIPE_Y[0], x + STRIPE_W, STRIPE_Y[1]))

    # black box: M1-M3 fully blocked, M4 blocked except the stripes and the pin bands
    out.extend(["  OBS"] + [f"      LAYER {m} ;\n        RECT 0.000 0.000 {width:.3f} {height:.3f} ;"
                            for m in ("Metal1", "Metal2", "Metal3")] + ["      LAYER Metal4 ;"])
    edges = [0.0] + [v for x in sorted(STRIPES.values()) for v in (x - 0.3, x + STRIPE_W + 0.3)] + [width]
    for x1, x2 in zip(edges[::2], edges[1::2]):
        out.append(f"        RECT {x1:.3f} 1.500 {x2:.3f} {height - 1.5:.3f} ;")
    out.extend(["  END", f"END {TOP}", "END LIBRARY", ""])
    path.write_text("\n".join(out))


def main():
    width, height, pins = parse_def(DEF)
    assert len(pins) == 51, len(pins)
    (REPO / "gds").mkdir(exist_ok=True)
    (REPO / "lef").mkdir(exist_ok=True)
    build_gds(width, height, pins).write_gds(str(REPO / "gds" / f"{TOP}.gds"))
    write_lef(REPO / "lef" / f"{TOP}.lef", width, height, pins)
    print(f"wrote gds/{TOP}.gds and lef/{TOP}.lef ({width} x {height} um, {len(pins)} pins + 2 stripes)")


if __name__ == "__main__":
    main()
