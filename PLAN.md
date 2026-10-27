# GF180 integer-N PLL — tapeout plan

Tiny Tapeout **TTGF26c**, closes **Mon Dec 7 2026, 20:00 UTC (12:00 PST)**. Solo. Presentation required (pre-silicon: chips are due back around May–June 2027).

Written overnight on Oct 26–27 from the design discussion in the "Mos" chat, three research passes (Tiny Tapeout GF rules, the GF180 PDK and tools, open-source prior art), and the first ngspice/Python simulations in this repo. Anything marked **[A#]** is an assumption I made so I could keep going. They're collected in [§11](#11-assumptions-to-review) for you to check.

---

## 0. Where things stand

**Done tonight**

- Git repo with the TT GF analog template merged in (`info.yaml`, `src/project.v`, `docs/info.md`, GitHub Actions), plus `sim/` and `model/`. Pushed to <https://github.com/robertliu4/501-pll> (public), where the TT Actions run on every push.
- Local tools: ngspice 47 (Homebrew), the gf180mcuD PDK via `ciel` (open_pdks 792ef67) and a Python venv.
- Simulations on real GF180 models, with results in `sim/results/` and `model/results/`:
  - 3.3 V device characterization: Vth and gm/ID charts.
  - Ring VCO: speed headroom, tuning curves across 5 corners, K_VCO, supply pushing.
  - First divider stage: standard-cell DFF against a custom TSPC stage.
  - TSPC ÷4 prescaler driven by the real ring, including a "silicon 2× slow" case.
  - MOS-cap density, for the loop filter.
  - Charge-pump up/down matching window vs Vctrl, simple vs cascoded sources.
  - Beta-multiplier bias reference spread across corners, temperature and supply.
  - Loop design with the real K_VCO: R/C values, phase margin, I_cp trade-off and a jitter budget.
  - Behavioural closed-loop lock from a cold start at all 5 corners, using the simulated VCO curves.
- **The dummy tile passes the full TT precheck in CI (Oct 27).** `layout/make_dummy_gds.py` draws the template pins, the VDPWR/VGND stripes and one std-cell inverter wired `ua[0]` → I, ZN → `ua[1]`. All 12 checks are green, including GF180MCU DRC and antenna ([run 40534489155](https://github.com/robertliu4/501-pll/actions/runs/40534489155)). GitHub Pages is on, and the 3D layout viewer is at <https://robertliu4.github.io/501-pll/>.

**Findings that changed the earlier plan**

| # | Finding | Evidence | Change |
|---|---|---|---|
| 1 | **MIM caps can't be used in a TT GF tile.** MIM option B needs Via4/Metal5, and the precheck forbids Metal5. | TT precheck `tech_data.py`; GF `mim_b.drc` | The loop filter uses **MOS caps**, which are 4.0 fF/µm² for Vctrl ≥ 1 V, twice MIM's density. C1 + C2 come to about 4,900 µm², roughly 2% of the tile. |
| 2 | **Standard-cell flip-flops are too slow for the first divider stage.** The 7-track cells use 5 V devices (L = 0.6 µm). `dffrnq_1` min_period at ss/125 °C/3.0 V is 3.58 ns (about 280 MHz). My toggle simulation reached 600 MHz at ss, but measured GF silicon has come back 2–3× slower than simulation. | Liberty files; `sim/results/divider_speed.txt`; TTGF0p2 feedback | Use a **custom TSPC ÷4 prescaler** on 3.3 V devices; it works past 1.1 GHz at every corner, including with 2× slow silicon. Standard cells only run at ≤ 130 MHz. |
| 3 | **K_VCO is about 140 MHz/V, not 200–250.** The ring's lock point for 300 MHz sits at 1.6–2.3 V across corners. | `sim/results/vco_summary.txt` | Loop filter redesigned for K_VCO = 140 MHz/V and **I_cp = 40 µA**. |
| 4 | **Supply pushing is −167 MHz/V (−56 %/V)**, about twice the estimate. 10 mV of supply noise shifts the VCO by 1.7 MHz. | `vco_summary.txt` (D) | The VCO and V-to-I converter get an **on-chip RC-filtered supply**, which also needs decap area. |
| 5 | **The GF breakout board may not route analog pins at all.** The only published GF board, a chip-on-board DIP breakout, appears to leave the analog pads unconnected. | breakout-pcb repo | `ua[0]` can't be the only way to test the VCO. Add digital-only test paths (§6). **Ask on Discord.** |
| 6 | **Measured GF silicon has been 2–3× slower than simulated.** A TTGF0p2 9-stage standard-cell ring measured 17 kHz against 51 kHz in simulation. | TT silicon feedback | Keep at least 2× speed margin over the post-layout simulation. Add a VCO band bit and N select so the operating point can move after silicon. |
| 7 | The precheck runs **KLayout DRC only (no LVS)**, plus antenna and structural checks. Metal fill is added after precheck. | `tt-support-tools/precheck` | Magic/KLayout disagreements don't matter for passing precheck, but you must run LVS yourself with netgen. Add fill-block layers over the VCO and loop filter. |

**What I need from you in the morning:** see §11 and §12.

---

## 1. Hard constraints

| Item | Value | Source |
|---|---|---|
| Shuttle / deadline | TTGF26c (wafer.space Run #3), **2026-12-07 20:00 UTC**. 143 of 160 tiles were still free on Oct 26. | TT API, verified |
| Template | `TinyTapeout/ttgf-analog-template` @ `ttgf26c`, gf180mcuD, merged into this repo | verified |
| Tile | **2×2 = 711.20 × 325.36 µm** (0.231 mm²) | `tt-support-tools/tech/gf180mcuD/def/analog`, verified |
| Supply | VDPWR = **3.3 V**. Optional VAPWR has an undocumented voltage; **we don't use it** [A1]. | template, verified |
| Metal | M1–M4 only (**Metal5 forbidden**). Pins on M4. Power stripes are vertical M4, ≥ 0.8 µm wide, running within 10 µm of the top and bottom edges. | precheck, verified |
| Analog pins | `ua[0..5]` usable; currently **free on GF** (confirm at checkout). GF R/C isn't published; the SKY figure is < 500 Ω, < 5 pF. The demo board puts a **10 kΩ pulldown** on analog pins (jumper). | verified / [A2] |
| Digital I/O | GF limits unpublished; SKY is 33 MHz out and 66 MHz in. Our outputs are ≤ 31 MHz. | [A3] |
| Cost | €70 per tile → **2×2 = €280**; analog pins €0 right now; PCB extra | TT app config, verified |
| Precheck | KLayout `gf180mcu.drc` (all except density and antenna), a separate antenna check, the `PR_bndry` box must exactly match the template, pins must match the DEF, LEF power pins `USE POWER/GROUND`, Yosys syntax on `src/project.v`. **No LVS.** | verified |
| Precheck PDK | open_pdks **e8daeda** (2026-06-11), KLayout 0.30.8 (Nix, `tt-support-tools` main; `tool-versions.json` still says 0.30.4). Local install is 792ef67; run the final DRC against e8daeda (`ciel enable … e8daeda…`). | verified |
| Files | `info.yaml`, `LICENSE`, `docs/info.md` (images < 512 kB each, < 1 MB total), `gds/<top>.gds`, `lef/<top>.lef`, `src/project.v`; top module `tt_um_*` | verified |

---

## 2. Architecture (v1 spec, frozen unless a §11 assumption breaks)

```
            ui[6] REF_SEL
 clk ──┐       │
 ui[7]─┴─[mux]─┴─ REF ─────────────┐                            ┌─────────── uo[3] REF_OUT
                                   ▼                            │
                              ┌────────┐ UP/UPb  ┌────────────┐ │    Vctrl   ┌──────────────┐
                              │  PFD   │────────▶│ Charge pump│─┼──────●─────▶│ V-to-I + bias│
                              │ (std   │ DN/DNb  │ steering + │ │      │      │ (filtered    │
                         ┌───▶│ cells) │────────▶│ A1 buffer  │ │   ┌──┴──┐   │  VDD_VCO)    │
                         │    └────────┘         └────────────┘ │   │ R   │   └──────┬───────┘
                         │                         OPEN_LOOP ───┘   │ C1  │ C2       │ Vbp/Vbn
                         │                         (CP off,         └─────┘          ▼
                         │                          TG to ua[0])        ua[0]   ┌──────────┐
                         │                                        VCTRL_EXT     │ 5-stage  │
                         │  ┌────────────┐   ┌─────────────┐   ┌───────────┐    │ starved  │
                         └──│ ÷2/÷3/÷4   │◀──│ TSPC ÷4     │◀──│ out buffer│◀───│ ring VCO │
          uo[2] FB_DIV ◀────│ (std cells)│   │ (3.3 V dev) │   └───────────┘    └──────────┘
                            └────────────┘   └──────┬──────┘
                                 N = 4·{2,3,4} = 8/12/16    └──▶ ÷4 ──▶ uo[0] VCO/16 ──▶ ÷4 ──▶ uo[1] VCO/64
```

| Parameter | Value | Basis |
|---|---|---|
| f_ref | 25 MHz (the demo board can make it exactly) | earlier chat; board firmware |
| N | 8 / 12 / **16 selectable**; nominal **12** | |
| f_out | **300 MHz** nominal (200 and 400 MHz best effort) | |
| VCO | 5-stage current-starved ring. Switches nfet 2/0.28 µm and pfet 5/0.28 µm; starve devices nfet 10/0.5 and pfet 30/0.5. **C_L ≈ 20 fF/stage, about 108 µA (0.36 mW) at 300 MHz.** | `02_ring_vco.py` |
| Tuning (tt) | about 150–505 MHz over Vctrl 0–3.3 V; lock at 300 MHz needs **Vctrl 1.61–2.28 V** across corners | `vco_summary.txt` |
| K_VCO | **118–147 MHz/V** at the lock point (design value 140) | |
| Speed headroom | Starve devices fully on: 1.36 GHz tt, **0.92 GHz ss/85 °C/3.0 V**, which is more than 2× above 455 MHz | |
| Prescaler | 2 × TSPC ÷2 (3.3 V devices), driven from the ring through 2 inverters | `04_prescaler.py` |
| PFD | std-cell `dffrnq_1` ×2, `buf_2` ×2, `nand2`, `dly*` reset chain; t_rst ≈ 1 ns (set by the dead-zone sim); U5 inverter + U6 TG for UP/DN matching | chat |
| Charge pump | current-steering with unity-gain buffer A1 (architecture d), cascoded sources, **I_cp = 40 µA**; ≤ 2 % mismatch over 0.44–2.57 V (worst corner) | chat + `loop_design.py` + `06_cp_window.py` |
| Bias | beta multiplier, 10 µA (×4 → I_cp), R ≈ 7.9 kΩ `ppolyf_u_1k`; −12 / +29 % over PVT | `07_bias.py` |
| Loop filter | **R = 21.8 kΩ** (`ppolyf_u_1k`, about 22 squares), **C1 = 18.2 pF**, **C2 = 1.41 pF** (MOS caps); f_c = 1.5 MHz (f_ref/17), PM 60° (55.6° at ×0.5 and ×2) | `loop_design.py` |
| Lock time | 2.0–2.8 µs from a cold start, all corners (behavioural) | `pll_tran.py` |
| Jitter budget | about 9 ps rms (VCO 7.3, reference 5.1, R 1.4, CP 0.9) from **assumed** source levels [A4] | `noise_budget.png` |
| Area | about 0.05 mm² of active circuitry plus decap. The 2×2 (0.231 mm²) leaves room for decap and the supply filter. | estimate |

---

## 3. Block-by-block decisions and trade-offs

Each block lists the decision, why, what was rejected, and the fallback.

### 3.1 VCO: 5-stage current-starved ring (keep)
- **Why:** a wide, linear tuning range absorbs process shifts, full-rail outputs drive the divider directly, and it's simple. An LC isn't viable at these frequencies with no inductor model and no Metal5. A supply-regulated ring rejects supply noise better but needs a regulator, a level shifter and a nonlinear K_VCO.
- **New from tonight:** supply pushing is −56 %/V, so the VCO needs its own filtered rail (§3.6). The ring is fast enough: ≥ 2× headroom even at ss.
- **To decide:**
  - Mirror ratio: 1:1 now, so the bias branch costs 2× the core current. Going to 1:4 saves about 150 µA.
  - Starve-device L: 0.5 µm now. Longer L improves I_up/I_dn matching and duty cycle, at the cost of a little headroom.
- **Fallback:** none needed. This is the core.

### 3.2 V-to-I converter and bias
- **Now:** NMOS M1 (20/1 µm) with degeneration R_s = 15.2 kΩ, plus a floor current I0 = 59 µA so the VCO always starts. Both are still ideal in simulation.
- **Missing piece the chat never covered: where the bias currents come from.** I_cp, I0 and the A1 tail all need a reference.
  - **Recommendation:** a constant-gm (beta-multiplier) reference with a startup circuit, built from `ppolyf_u_1k`. Its ±20–30 % spread is fine because the loop tolerates 0.5–2× changes in I_cp·K_VCO.
  - **Simulated** (`07_bias.py`, `sim/results/bias.txt`):
    - Sizing: M1 10/2 µm, K = 4, R ≈ 7.9 squares of `ppolyf_u_1k` (2 × 15.8 µm). That gives **10.0 µA** at tt.
    - Spread: −1.5 % at ss/85 °C, **+22 %** at ff/0 °C, −12 % at 0 °C, **+29 %** at 85 °C, and ±2 % from 3.0 to 3.6 V.
    - Still to check in W2: the ff/85 °C combination, and the startup circuit with a VDD ramp.
    - I_cp ∝ 1/R² from the bias and the loop-filter R are the same poly, so the crossover moves roughly as 1/R². That's 0.7–1.6× over the ±20 % sheet-resistance range, inside the tolerance.
  - **Rejected:** an off-chip resistor or current on an analog pin. Analog-pin access is uncertain (finding 5).
- **Silicon insurance (Tier 2):** a VCO_BAND bit that adds about +50 % to I0, and an ICP_SEL[1:0] trim (×0.5, ×1, ×1.5, ×2). Both are a few switched mirror legs.

### 3.3 Dividers
- **Decision:** a TSPC ÷4 prescaler on 3.3 V devices, followed by a standard-cell programmable ÷2/3/4 at ≤ 130 MHz, giving N = 8/12/16. A separate ÷4 → ÷4 chain produces VCO/16 and VCO/64.
- **Why not standard cells first:** finding 2.
  - **Divider lock-up rule:** the prescaler must work up to the **VCO's maximum frequency** at every corner, not just 300 MHz. If it drops edges near the top of the range during acquisition, the loop pushes Vctrl further up and never recovers.
  - The TSPC passes at 1.13 GHz, which is above the VCO maximum, so this holds.
- **TSPC caveat:** it's dynamic logic. Leakage sets a minimum frequency, but that's far below the VCO's ~110 MHz floor, and the clock never stops while powered. When the VCO is off, the TSPC output is undefined, which is harmless.
- **Odd ÷3 duty cycle:** the PFD only uses rising edges, so duty cycle doesn't matter for DIV.

### 3.4 PFD (as designed in the chat; the easiest block)
- Standard cells: two `dffrnq_1` with D tied high, `buf_2` after each, `nand2` reset, and a `dly*` chain for t_rst. Then U5 (inverter → UPb) and U6 (always-on TG → DN), sized for matched effective pulse width at the switch gates.
- Set t_rst from the dead-zone sweep with the real CP at the worst corner, then add 1.5–2× margin. The `dlya` cell is about 0.53 ns at tt 3.3 V.
- The steering CP needs four phases (UP, UPb, DN, DNb). Generate each pair with an inverter and a TG in parallel.

### 3.5 Charge pump: current-steering + unity-gain buffer A1 (keep, but timeboxed)
- **Why:** no charge sharing at any Vctrl and fast switching. That gives the strongest presentation story, with before/after charge sharing already simulated in the chat.
- **Tonight's numbers that make it easier:**
  - The lock window is only **1.6–2.3 V** (N = 12, all corners).
  - A1 only needs an input/output range of about 1.2–2.8 V, so a **plain NMOS-input 5-transistor OTA follower** is enough; no rail-to-rail needed.
  - The bottom of the range is naturally limited by the NMOS V-to-I converter anyway.
- **Simulated output window** (`06_cp_window.py`, `sim/results/cp_window.png`). Setup: 40 µA, sources L = 1 µm at gm/ID ≈ 8, cascodes L = 0.5 µm, wide-swing cascode bias, switches on.
  - **Cascoded:** |I_up − I_dn| < 2 % over **0.44–2.57 V at the worst corner (ss)**, and about 0.35–2.9 V elsewhere. That covers the 1.61–2.28 V lock range with margin.
  - **Simple long-L mirrors:** only < 5 %. At 2 % the window is 0.7–2.0 V, which misses the lock range.
  - So **keep the cascodes**, and A1 needs about 1.2–2.6 V of range.
  - This was with ideal, identical up/down references. The real PMOS reference comes from an NMOS mirror leg, and that ratio error adds a constant offset (Monte Carlo in W3).
- **Behavioural check:**
  - 5 % up/down mismatch gives a 50 ps static offset (matches ΔI/I·t_rst exactly), 0.03 mV of ripple at f_ref, and about −81 dBc spurs at the VCO (−105 dBc after ÷16).
  - 10 nA of leakage gives about −72 dBc.
  - Spurs won't be measurable through the pads anyway, so don't over-optimize.
- **Timebox:** 3 days for A1. **Fallback (c):** remove A1 and hold the dummy node at about 1.9 V (mid lock window) with a resistive divider and a decap. **Fallback (b):** source-switched CP with t_rst = 2–3 ns and heavy bias decoupling.

### 3.6 Supply, decap and the "VCO rail"
- **Decision:** feed the VCO, V-to-I and bias from VDPWR through an RC low-pass: poly R of about 300–500 Ω and about 50–100 pF of MOS decap. That's roughly 12,500–25,000 µm², 5–11 % of the tile.
  - It drops about 40–60 mV at about 120 µA, which shifts the tuning curve slightly but is fine.
- **Trade-off:** the loop suppresses supply noise below about 1.5 MHz, and the RC filters above its corner (about 3–10 MHz). The gap between them is partly exposed.
- **Tier 2:** an NMOS source-follower or LDO regulator for the VCO rail, if pushing simulations against a realistic supply-noise estimate show it's needed.
- **Fill the leftover area with decap** on the digital rail too. The PFD and dividers switch hard; keep their supply separate from the VCO/CP bias where you can.

### 3.7 Loop filter
- **Topology:** passive third order without R3/C3, at R = 21.8 kΩ, C1 = 18.2 pF, C2 = 1.41 pF.
- **I_cp = 40 µA, chosen over 20 µA:**
  - It gives smaller R (less thermal noise: 19 vs 27 nV/√Hz) and less CP noise relative to signal.
  - The area is still tiny with MOS caps.
  - The I·R step is the same 0.87 V either way (I·R is fixed by f_c and PM).
- **C1:** `cap_nmos_03v3` (inversion). It's flat at 3.98 fF/µm² for V ≥ 1 V and collapses below about 0.7 V. That only affects the first few hundred ns of a cold start, when Vctrl < 0.7 V; the loop is then faster but still converges. Re-check this in the transistor-level lock simulation.
  - Alternative: `cap_nmos_03v3_b` holds 3.2–4.0 fF/µm² down to 0 V, so it's more linear at low Vctrl. **Prefer `_b` for C1 if its layout is just as easy.**
- **C2:** also a MOS cap; it includes the VCO's M1 gate capacitance, A1's input and wiring, so subtract those.
- **R:** `ppolyf_u_1k`, about 22 squares (for example 2 µm wide × 44 µm long). It's the only high-resistance poly in this variant.
- **Re-run** `model/loop_design.py` with post-layout K_VCO and I_cp. The phase margin is flat (55–60°) over 0.5–2× variation.

### 3.8 Test, observability and control (digital pins are the safe path)
- **The insurance principle:** in OPEN_LOOP mode the CP is disabled and disconnected. Even if the loop blocks are broken, the VCO, prescaler and outputs remain a working test chip ("guaranteed core").
- **Digital-only characterization, which works even if analog pins aren't reachable:**
  - Lock range: sweep f_ref (the board can make many frequencies) × N ∈ {8, 12, 16}, and watch FB_DIV against REF_OUT on a scope.
  - That maps the VCO's lockable range as 8–16 × f_ref.
  - Lock is visible as FB_DIV phase-aligned with REF_OUT.
- **With analog pins (if the board brings them out):** `ua[0]` forces Vctrl in open-loop mode to measure the true f–Vctrl curve and K_VCO.
- **Stretch:** a 3-bit on-chip Vctrl DAC (an R-string from the filtered rail, plus TGs) selected by `uio[2:0]`. It gives the f–Vctrl curve through digital pins only.
- **Lock detect (Tier 2):** UP/DN pulse wider than t_rst + Δ → reset a counter; LOCK goes high after 64 clean cycles.

**Draft pin map** (also in `info.yaml`):

| Pin | Function |
|---|---|
| `clk` | 25 MHz reference (from the board) |
| `ui[1:0]` | N_SEL: 00 → 8, 01 → 12, 10 → 16, 11 → 12 |
| `ui[2]` | OPEN_LOOP: 1 = CP off, Vctrl connected to `ua[0]` |
| `ui[4:3]` | ICP_SEL (Tier 2) |
| `ui[5]` | VCO_BAND (Tier 2) |
| `ui[6]` | REF_SEL: 0 = `clk`, 1 = `ui[7]` |
| `ui[7]` | EXT_REF, a clean generator input |
| `rst_n` | low = dividers and PFD held in reset, CP off |
| `uo[0]` | VCO/16 (≤ 31 MHz at the top of the range) |
| `uo[1]` | VCO/64 (always slow enough for any I/O) |
| `uo[2]` | FB_DIV |
| `uo[3]` | REF_OUT (the selected reference, for a phase comparison on the scope) |
| `uo[4]` | LOCK (Tier 2) |
| `uo[7:5]`, `uio_*` | tied 0 / inputs (`uio[2:0]` reserved for the Vctrl DAC) |
| `ua[0]` | VCTRL_EXT, through a TG enabled by OPEN_LOOP |
| `ua[1]` | VCTRL_MON, a buffered Vctrl copy behind a TG (Tier 2) |

Keep pad loading off the loop-filter node. `ua[0]` reaches Vctrl only through the TG when the loop is open, and a monitor must be buffered. Another TT project's op-amp oscillated driving the pad's R and C.

---

## 4. Scope tiers and cut-lines

| Tier | Contents | Must be done by |
|---|---|---|
| **0: guaranteed core** | VCO + V-to-I + bias + filtered rail, TSPC ÷4, output ÷4/÷4 (VCO/16, VCO/64), OPEN_LOOP TG to `ua[0]`, minimal control logic | Ships no matter what |
| **1: closed loop** | PFD, steering CP + A1, loop filter, ÷2/3/4 N select, FB_DIV and REF_OUT outputs, REF_SEL | Schematic locks at all corners by **Sun Nov 15** |
| **2: stretch** | ICP_SEL, VCO_BAND, lock detect, VCTRL_MON buffer, Vctrl DAC, VCO regulator | Only if Tier 1 layout is LVS-clean by **Sun Nov 22** |

Cut decisions:
- **Nov 15:** if the transistor-level loop doesn't lock at all 5 corners, drop A1 (fallback c) and fix N = 12.
- **Nov 22:** if Tier 1 layout isn't LVS-clean, drop all of Tier 2.
- **Nov 29:** if top-level DRC/LVS isn't clean, tape out Tier 0 plus whatever of Tier 1 is clean, with the loop blocks disconnected by OPEN_LOOP tied high internally.

---

## 5. Schedule (41 days)

Weeks run Monday to Sunday. Exams in early December (from the chat) are why everything aims at **submitting on Fri Dec 4** and keeping the weekend as buffer.

| Week | Dates | Work | Exit criterion |
|---|---|---|---|
| **W1** | Tue Oct 27 – Sun Nov 1 | 1) Install Docker (or OrbStack) and **IIC-OSIC-TOOLS 2026.10** (has xschem, magic, klayout, netgen and gf180mcuD).<br>2) ~~Push this repo to GitHub and confirm the Actions run.~~ Done Oct 27.<br>3) ~~**Put a dummy layout (one inverter plus the template box, pins and power stripes) through the GitHub precheck.**~~ **Done Oct 27: all 12 checks green.**<br>4) Ask on TT Discord (§12).<br>5) Redraw tonight's VCO in xschem from the ngspice netlist; reproduce the tt tuning curve.<br>6) Lay out **one VCO stage** in Magic or KLayout to learn the GF180 rules. | Precheck green on a dummy GDS; xschem VCO matches `vco_summary.txt` |
| **W2** | Nov 2 – Nov 8 | VCO + V-to-I + **real bias generator** + filtered rail; corners, supply pushing, startup (Vctrl = 0, slow VDD ramp). TSPC prescaler + output buffers. Standard-cell ÷2/3/4, N select and output dividers. Control logic. | Tier 0 schematic frozen (Sat Nov 7); VCO layout started |
| **W3** | Nov 9 – Nov 15 | PFD (dead-zone sweep, t_rst, U5/TG). Steering CP with cascodes: mismatch vs Vctrl, charge-sharing check. A1 (**3-day timebox**). Loop filter with MOS caps and poly R. **Transistor-level closed-loop lock at 5 corners** (about 5 µs transients). | **CHECKPOINT Sun Nov 15**: lock at all corners → Tier 1 is go |
| **W4** | Nov 16 – Nov 22 | Layout: VCO (finish), prescaler, output buffers, PFD and dividers (hand-placed standard cells), CP + A1, bias. **DRC and LVS clean per block** (KLayout DRC, netgen LVS). | **Sun Nov 22**: all Tier 1 blocks LVS-clean → Tier 2 go/no-go |
| **W5** | Nov 23 – Nov 29 | Loop-filter caps/R, decap, floorplan, top-level routing on M1–M4, power stripes, pins on M4 per the template DEF, fill-block layers. Top-level DRC/LVS. Write the LEF (`lef write -pinonly`, don't flatten), export the GDS, fill `src/project.v`. **Precheck green on the real design.** | **Sun Nov 29**: real GDS passes precheck |
| **W6** | Nov 30 – Fri Dec 4 | Extraction (Magic `ext2spice` with C, plus R on critical nets) → post-layout VCO curve, prescaler speed, lock at tt/ss/ff. Fix and re-run the precheck. Write `docs/info.md`. **Submit Fri Dec 4.** | Submitted |
| buffer | Sat Dec 5 – Mon Dec 7 noon PST | Only things that move the precheck. Deadline 20:00 UTC Mon. | |

**Presentation:** build figures as you go. Tonight's plots are already slide-ready: `vco_tuning.png`, `loop_bode.png`, `pll_lock.png`, `noise_budget.png`, `divider_speed.png`. The deck itself is a W6 task, or after Dec 7 if the presentation is later [A5].

---

## 6. Verification plan

Run every row at tt_27C_3v3, ss_85C_3v0, ff_0C_3v6, sf and fs (and ss_125C_3v0 for divider timing), unless the row says otherwise.

| Block | Simulation | Pass criterion |
|---|---|---|
| VCO | f vs Vctrl, K_VCO, I_supply | 300 MHz reachable with Vctrl inside the CP window at every corner |
| VCO | Supply pushing; startup at Vctrl = 0 and with a slow VDD ramp | Always oscillates. Pushing re-checked with the RC rail filter. |
| VCO | Transient-noise period jitter | Sanity check against the −157 dBc/Hz FOM assumption |
| Prescaler | ÷4 driven from the real ring, f_min to f_max | Divides correctly at every corner, post-layout as well |
| Dividers | N = 8/12/16 at ss_125C | Correct counts at 130 MHz input with timing margin |
| PFD + CP | Dead-zone sweep (average current vs Δt) | Linear through zero at the worst corner |
| PFD + CP | Identical-edges offset test (from the chat) | ≤ 50 ps equivalent offset, all corners |
| CP | I_up/I_dn vs Vctrl, 1.2–2.8 V | ≤ 5 % mismatch in the window |
| A1 | Stability driving C_D; range | PM > 60°, follows Vctrl over 1.2–2.8 V |
| Loop | Transistor-level cold-start lock, N = 12, 5 corners | Locks in < 10 µs |
| Loop | Mixed-level (XSPICE/behavioural VCO + real CP) for long runs | Spur and ripple trends match `pll_tran.py` |
| Mismatch | Monte Carlo on CP up/down, PFD paths, starve mirrors (`sw_stat_mismatch=1`) | Offset spread within budget |
| Post-layout | VCO curve, prescaler f_max, lock at tt/ss/ff | ≥ 2× speed margin retained |

**Monte Carlo note:** the mismatch wrappers are subcircuits. Check whether your netlist instantiates `nfet_03v3` as `M…` (binned model, **no mismatch**) or `X…` (the wrapper with mismatch). I used `M` tonight.

---

## 7. Layout plan

- **Floorplan:** analog pins `ua[]` are on the bottom edge (M4, 43.68 µm pitch, `ua[0]` at x ≈ 327 µm); digital pins are on the top edge.
  - Put the **digital section (PFD, dividers, control) along the top**, near the digital pins.
  - Put the **VCO in the middle**, away from the digital section, with dummy stages at its ends.
  - Put the **loop filter and CP near the bottom**, next to `ua[0]`.
  - Use the remaining area for decap.
- **VCO:** identical stages, common orientation, dummy loads on every stage so each node sees the same capacitance as the buffered one. Keep the starve-to-switch nodes small.
- **CP:** common-centroid or interdigitated up/down current mirrors, with long L.
- **Loop filter:** guard rings, and keep C1/C2 under fill-block layers.
- **Standard cells:** hand-place them (there's no automatic place-and-route in the analog template). Use the 7-track `gf180mcu_fd_sc_mcu7t5v0` cells, which is what TT GF uses.
- **Verify:** KLayout DRC with the PDK deck, matching precheck, at the e8daeda PDK version. Netgen LVS per block and top-level. Magic extraction for post-layout.
- **Precheck rules learned from the dummy** (`tt-support-tools/precheck`):
  - The LEF must list all 51 template pins with exactly the DEF rectangles (one rect each). It also needs VDPWR and VGND on Metal4, at least 0.8 µm wide, reaching within 10 µm of the top and bottom edges.
  - Every LEF port needs a `Metal4_Label` (46/10) polygon covering it, drawn in the **top cell** (shapes in subcells don't count).
  - Analog pin check: each used `ua` pin (`analog_pins: 2` means `ua[0]` and `ua[1]`) needs Metal4 or Via3 touching the 0.1–0.5 µm ring around the pin. Unused pins must have nothing there.
  - `inv_1` and most logic cells have no well taps. Put a `filltie` in every row.
  - Via1 can land on a 0.33 µm std-cell pin (0.03–0.035 µm side enclosure is legal when the line-end enclosure is ≥ 0.06 µm). Don't add an M1 pad there, because it breaks M1 spacing to the neighbouring pin.
- **Known trap from TTGF0p3:** a project was disabled because its LEF didn't match its GDS (a missing VAPWR stripe). Generate the LEF from the final GDS every time.

---

## 8. Silicon test plan (for the presentation)

1. Power up with OPEN_LOOP = 1. With `ua[0]` driven, if analog pins are accessible: sweep Vctrl, read VCO/64 on a frequency counter → tuning curve and K_VCO, compared against the corner simulations.
2. Close the loop with OPEN_LOOP = 0 and N = 12 at 25 MHz: check that FB_DIV phase-locks to REF_OUT on a 2-channel scope, and that VCO/16 reads 18.75 MHz.
3. Lock range: sweep f_ref and N → lockable VCO range.
4. Jitter: scope TIE/period jitter on VCO/16. The I/O path and the reference will dominate, so compare the RP2350 reference with an external generator on `ui[7]`.
5. With Tier 2: ICP_SEL sweep → lock-transient speed vs I_cp (shows the loop dynamics), and VCO_BAND.

---

## 9. Presentation outline

1. The problem and the spec (why a PLL, why these numbers).
2. Architecture and the "guaranteed core" insurance.
3. GF180 constraints that drove the design, i.e. the findings table: no MIM, slow 5 V cells, slow silicon, pin access.
4. VCO: tuning curves across corners, and supply pushing.
5. Dividers: the standard-cell vs TSPC speed plot.
6. PFD/CP: dead zone, U5/TG matching, the charge-sharing before/after.
7. Loop: Bode at 0.5/1/2×, and the lock transient at 5 corners.
8. Noise/jitter budget.
9. Layout and the pre- vs post-layout table.
10. Silicon test plan.

---

## 10. Risk register

| Risk | L | I | Mitigation |
|---|---|---|---|
| Tool setup or precheck flow eats a week | M | H | Do it first (W1); use IIC-OSIC-TOOLS; dummy-GDS precheck by Nov 1 |
| Layout of everything solo in about 2.5 weeks | H | H | Pipeline the VCO layout from W2; standard cells for digital; scope tiers and cut-lines; relaxed GF rules plus your layout background |
| Silicon 2–3× slower than simulation | M | M | ≥ 2× speed headroom; post-layout sims; N select; VCO_BAND; f_ref sweep |
| Analog pins not reachable on the GF board | M | M | Digital-only test path (§3.8); ask on Discord |
| Supply noise from the shared TT supply | M | M | RC-filtered VCO rail plus decap; only one project is active at a time on TT, which helps [A6] |
| A1 instability or range problems | M | L | 3-day timebox; fallback (c) or (b) |
| Divider lock-up at the top of the VCO range | L | H | TSPC prescaler verified past the VCO's maximum frequency; re-check post-layout |
| Metal fill near sensitive nodes | M | L | Fill-block layers over the VCO and loop filter |
| LEF/GDS mismatch disables the project | L | H | Regenerate the LEF from the final GDS; precheck after every change |
| Exams compress W6 | H | M | Submit Fri Dec 4; nothing new after Nov 29 |

---

## 11. Assumptions to review

- **[A1]** No VAPWR; everything runs from VDPWR at 3.3 V.
- **[A2]** GF analog pins behave roughly like SKY's (< 500 Ω, < 5 pF), and the demo board has a 10 kΩ pulldown jumper.
- **[A3]** GF digital I/O is good for ≥ 33 MHz out and ≥ 66 MHz in. VCO/64 is the guaranteed-slow output if not.
- **[A4]** Jitter-budget inputs:
  - ring FOM −157 dBc/Hz;
  - 1/f³ corner 500 kHz;
  - reference floor −130 dBc/Hz at 25 MHz;
  - CP gm/ID = 8.

  All four are guesses, so treat the 9 ps rms as an order of magnitude.
- **[A5]** The presentation is after the Dec 7 submission. If it's earlier, the slides move into W5/W6.
- **[A6]** Only the selected TT project is clocked, so supply noise comes mostly from the mux/controller and the board.
- **[A7]** You're paying for or ordering a 2×2 analog slot (€280) on TTGF26c, or the course is. The 3×2/4×2 sizes are billed as multiple projects.
- **[A8]** Author "Robert Liu" and top module `tt_um_robertliu4_pll` in `info.yaml` (from your git email and GitHub login; change if wrong).
- **[A9]** f_ref = 25 MHz and N = 12 carry over from the chat unchanged. The simulations support it: the VCO lock point is in the CP window at every corner.
- **[A10]** Stay on the 2×2. The design needs roughly 25–40 % of it, and the rest is decap and margin.
- **[A11]** Sizes in `sim/ngspice/02_ring_vco.py` are first-pass. R_s and I0 come from ideal sources; the real bias generator will move them.

## 12. Morning to-do (you)

1. Read §0 and §11, and flag anything wrong.
2. ~~Create the GitHub repo~~ Done Oct 27 (the dummy now passes precheck, see §0): public at <https://github.com/robertliu4/501-pll>. On the first push, `docs` passed and `gds` failed as expected because `gds/tt_um_robertliu4_pll.gds` doesn't exist yet. Precheck and the viewer were skipped. Pages was enabled with source "GitHub Actions" on Oct 27; the viewer deploys on every push.
3. **Ask on TT Discord:**
   - Which board ships with TTGF26c, and are the analog pins routed?
   - Is MIM really unusable in GF tiles (no Metal5)?
   - What are the GF analog-pin R/C and the digital I/O max frequency?
4. Install Docker Desktop or OrbStack, then IIC-OSIC-TOOLS (`curl -fsSL https://osic.tools/install.sh | bash`). This needs about 20 GB of disk; you have 94 GB free.
5. Buy or confirm the slot.

---

## 13. Repo layout and how to rerun

```
PLAN.md                  this file
info.yaml, src/, docs/   Tiny Tapeout template (draft pinout filled in)
.github/workflows/       TT GDS + precheck + docs actions (@ttgf26c), run on every push
layout/                  make_dummy_gds.py (dummy tile: template pins, stripes, one inverter) + tt_analog_2x2.def
gds/, lef/               what the TT action submits; currently the dummy from layout/make_dummy_gds.py
sim/ngspice/             ngspice decks generated from Python (GF180 models via ciel)
  spice.py               model includes, corners, runner
  01_devices.py          gm/ID, Vth
  02_ring_vco.py         ring speed, f(I), tuning curves, supply pushing
  03_divider_speed.py    std-cell DFF vs TSPC divide-by-2
  04_prescaler.py        TSPC /4 driven by the real ring
  05_moscap.py           MOS cap C-V
  06_cp_window.py        CP up/down matching vs Vctrl, simple vs cascoded
  07_bias.py             beta-multiplier reference spread over PVT
sim/results/             plots and tables
model/
  loop_design.py         loop filter values, Bode, robustness, noise budget
  pll_tran.py            behavioural lock sim using the ngspice VCO curves
model/results/
```

```bash
python3 -m venv .venv && .venv/bin/pip install numpy scipy matplotlib ciel
.venv/bin/ciel enable --pdk-family gf180mcu 792ef67037d74c8c51811eab3ce23cf793491296
brew install ngspice
cd sim/ngspice && ../../.venv/bin/python 02_ring_vco.py
cd ../../model && ../.venv/bin/python loop_design.py && ../.venv/bin/python pll_tran.py
```
