# Charge and range, done properly

Two complaints about the stock display started this: the charge gauge dropping
under throttle and recovering when you coast, and a range estimate that does
not feel right. Both have established answers, and neither needed inventing.

## The model

The standard treatment of a battery under load is the **Rint equivalent
circuit**:

```
V_terminal = OCV(SoC) - I * R0
```

An open-circuit voltage that depends only on state of charge, minus the drop
across an internal resistance. The Thevenin model adds an RC pair for
polarisation transients; at 5 Hz on a skateboard that is detail we cannot
resolve and do not need.

State of charge is then estimated by **coulomb counting**, with an **OCV lookup**
to seed and correct it at rest. That is what a BMS does, and what the
literature agrees on.

## What we do with it

**R0 is measured, not assumed.** `Resistance` watches the lightest and heaviest
loaded samples and takes the slope of voltage against current between them. It
reports nothing until it has seen at least 8 A of spread, because a slope
fitted to noise is worse than no slope, and it rejects a negative resistance as
the measurement artefact it is.

On a synthetic 40 mΩ pack it recovers 0.0400 Ω.

**Charge is compensated.** With R0 in hand, `soc_loaded()` reads the
open-circuit voltage rather than the terminal voltage. The difference is not
subtle: a 12s pack at 48 V open-circuit, pulling 28 A through 40 mΩ, reads
46.9 V at the terminals. The naive gauge calls that **41%**; the truth is
**51%**. That ten-point swing is the gauge "dropping when you accelerate", and
it was never the charge moving.

## Why range falls faster than charge

Two effects compound as a pack empties, and a naive estimate misses both.

**Power is V × I, and the current limit does not move.** At 50.4 V a 60 A limit
is 3.0 kW; at 40 V the same limit is 2.4 kW. A fifth of the punch, gone, without
touching a setting.

| Pack voltage | Charge | Power available | Cost per km |
|---|---|---|---|
| 50.4 V | 100% | 3024 W (100%) | ×1.00 |
| 45.8 V | 57% | 2748 W (91%) | ×1.30 |
| 43.2 V | 33% | 2592 W (86%) | ×1.53 |
| 40.0 V | 7% | 2400 W (79%) | ×1.85 |

**And the same power costs more current at lower voltage**, so I²R losses grow
with the square of it. The last third of a pack genuinely costs more per
kilometre than the first third.

So `range_km()` integrates the pack downward in steps rather than dividing
remaining energy by today's rate. On the reference board at a measured
18.7 Wh/km from 45.8 V:

```
naive  (remaining / rate)   18.0 km
sag-aware                   15.2 km
```

The honest number is **shorter**, which is the uncomfortable direction — but a
range estimate that flatters you is the one that strands you.

## Sources

- [Electrical equivalent circuit models of lithium-ion batteries](https://cdn.intechopen.com/pdfs/78501.pdf) — Rint, Thevenin, PNGV and n-RC compared
- [Lithium-ion battery modelling and SoC estimation](https://kth.diva-portal.org/smash/get/diva2:1802829/FULLTEXT01.pdf) — coulomb counting, OCV and EKF
- [Online identification of Thevenin parameters and SoC estimation](https://www.researchgate.net/publication/328973295_Online_Identification_of_Thevenin_Equivalent_Circuit_Model_Parameters_and_Estimation_State_of_Charge_of_Lithium-Ion_Batteries)

An extended Kalman filter over the same model is the accurate answer and the
usual next step. It is not obviously worth it here: the gain is in the
transient, and this display samples at 5 Hz on a vehicle whose current swings
by 80 A in a second.
