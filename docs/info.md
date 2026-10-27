<!---
Datasheet for the TT GF26c submission. Images must be < 512 kB each and < 1 MB in total.
DRAFT: fill in measured/post-layout numbers before submitting.
-->

## How it works

An integer-N charge-pump PLL that multiplies the 25 MHz reference on `clk` by N = 8, 12 or 16 (nominal 12, giving 300 MHz).

- **VCO:** a 5-stage current-starved ring on 3.3 V devices with a degenerated V-to-I converter, running from an RC-filtered local supply.
- **Dividers:** a true-single-phase-clock divide-by-4 prescaler, then a standard-cell divide-by-2/3/4.
- **PFD:** standard-cell flip-flops with a reset delay. UP and DN are matched through an inverter and a transmission gate.
- **Charge pump and loop filter:** a 40 µA current-steering charge pump with a unity-gain buffer that holds the dummy node at Vctrl, then a passive R-C1-C2 loop filter built from MOS capacitors and a poly resistor.

In OPEN_LOOP mode the charge pump is disconnected and Vctrl comes from `ua[0]`, so the VCO and dividers can be characterised on their own.

## How to test

1. Set `ui[2]` (OPEN_LOOP) = 0 and `ui[1:0]` = 01 (N = 12), apply 25 MHz on `clk`, and release `rst_n`.
2. `uo[0]` should read 300 MHz / 16 = 18.75 MHz. `uo[2]` (FB_DIV) should be phase-locked to `uo[3]` (REF_OUT).
3. Open-loop VCO curve: set OPEN_LOOP = 1, drive `ua[0]` from 1.0 to 2.8 V, and read `uo[1]` (VCO/64) on a frequency counter.

## External hardware

A frequency counter or oscilloscope. Optionally, a clean signal generator on `ui[7]` with REF_SEL (`ui[6]`) = 1, and a DC source on `ua[0]`.
