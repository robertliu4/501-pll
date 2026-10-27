# 501-pll

Integer-N charge-pump PLL for **Tiny Tapeout TTGF26c** (GF180MCU, 3.3 V), due **2026-12-07 20:00 UTC**.

- **[PLAN.md](PLAN.md):** the plan, architecture decisions and trade-offs, schedule, risks and open assumptions. Start here.
- `sim/ngspice/`: transistor-level simulations on the GF180 models (ngspice + ciel PDK). Results are in `sim/results/`.
- `model/`: Python loop design and a behavioural closed-loop model. Results are in `model/results/`.
- `info.yaml`, `src/`, `docs/`, `.github/`: the Tiny Tapeout GF analog template (draft values).

Rerun everything with the commands at the end of PLAN.md.
