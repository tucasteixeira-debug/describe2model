# Elevator System 3 — Physical Degradation + Monitoring

A single elevator serves six floors, from ground floor (`0`) to floor `5`.

This third model keeps the control and dispatch structure from `Elevator_System_2`, but introduces a new question:

**is the physical elevator still behaving as a healthy elevator should?**

To answer that, the simulation now runs two physical models in parallel:

- a **nominal plant**, representing the expected behaviour of a healthy elevator;
- an **actual plant**, representing the physical behaviour being observed.

The difference between them becomes the basis for a condition-monitoring layer.

## Physical models

The nominal plant is the same trapezoidal motion model used in `Elevator_System_2`:

- maximum velocity: **0.5 floors/s**
- acceleration: **0.25 floors/s²**
- deceleration: **0.25 floors/s²**

It provides the reference trajectory — the position and velocity the elevator is expected to follow under normal operation.

The actual plant is instead represented as a second-order mass–spring–damper system tracking that reference.

Its behaviour is defined by:

- natural frequency: **2.0 rad/s**
- initial damping ratio: **1.0**
- minimum damping ratio: **0.15**
- wear rate: **0.0015 damping-ratio units per second of movement**

A damping ratio of `1.0` represents the healthy, critically damped condition: the system follows the reference without oscillatory overshoot.

Wear is applied only while the elevator is moving. As use accumulates, the damping ratio gradually falls toward `0.15`, making the physical response increasingly underdamped and causing progressively stronger overshoot and ringing.

`Current_Floor` and `Velocity_FloorsPerSec` come from the **actual** plant and remain the physical states used by the controller.

The nominal plant exists only as an independent reference for monitoring.

## Monitoring requirement

The objective is not to detect an obvious instantaneous fault. It is to detect **slow degradation that becomes meaningful only when evidence is accumulated over time**.

The monitor compares actual and nominal velocity:

`Velocity_Residual = Actual_Velocity - Nominal_Velocity`

Because damping degradation produces an oscillatory residual — sometimes positive and sometimes negative — the monitoring signal uses its magnitude:

`Abs_Velocity_Residual = |Velocity_Residual|`

A CUSUM accumulator then tracks persistent excess deviation:

`CUSUM_High = max(0, CUSUM_High_previous + Abs_Velocity_Residual - Slack_K)`

with:

- CUSUM slack `Slack_K`: **0.02 floors/s**
- alarm threshold `Threshold_H`: **0.25**

An alarm is raised when:

`CUSUM_High >= Threshold_H`

The controller itself does not use this alarm to alter the elevator's behaviour. The monitoring layer is observational: it derives information about the condition of the physical system without changing the dispatch or door logic underneath it.

## Numerical integration

The control engine continues to operate with a **1-second outer scan**.

The second-order plant evolves on a significantly faster timescale, so both physical models are integrated internally using **100 substeps per scan**, giving an internal integration step of **0.01 s**.

The controller therefore still makes decisions once per second, while the physical dynamics are resolved at a sufficiently fine timestep to remain numerically stable.

Arrival uses the same numerical tolerances as `Elevator_System_2`:

- position tolerance: **0.02 floors**
- velocity tolerance: **0.01 floors/s**

## What this model represents

The system now contains three distinct levels of information:

- **control intent** — where the controller wants the elevator to go;
- **observed physical behaviour** — what the actual plant does;
- **expected physical behaviour** — what the nominal plant predicts a healthy system should do.

The monitoring layer reasons about the relationship between the last two.

This allows the model to answer a new question:

**is the difference between expected and observed behaviour remaining consistent with normal operation, or is evidence of degradation accumulating over time?**

With zero wear, a 200-round-trip simulation keeps `CUSUM_High` below approximately **0.0114**, well below the alarm threshold of `0.25`.

With the default wear rate of `0.0015`, the CUSUM reaches the alarm threshold at approximately **trip 46**, as the damping ratio approaches its lower bound of `0.15`.

These values are demonstration parameters rather than measurements from a real elevator or a validated predictive-maintenance system.

The purpose of the model is narrower: to show that once expected and observed behaviour are represented independently, a new diagnostic layer can be added around the existing control and physical model without requiring either to be redesigned.