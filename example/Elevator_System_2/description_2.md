# Elevator System 2 — Control + Physical Motion

A single elevator serves six floors, from ground floor (`0`) to floor `5`.

This second model separates **control decisions from physical behaviour**. The controller decides where the elevator should go and whether movement is permitted; a separate physical plant determines the car's actual position and velocity.

`Current_Floor` is therefore no longer produced by the control logic. It is an external state observed from the plant.

## Required behaviour

Floor requests, door behaviour, and the basic control sequence remain the same as in `Elevator_System_1`.

When requests are pending, the controller selects a `Target_Floor` and determines whether the car should move up or down.

The plant then moves the car toward that target using a simple trapezoidal velocity profile:

- maximum velocity: **0.5 floors/s**
- acceleration: **0.25 floors/s²**
- deceleration: **0.25 floors/s²**

These values correspond to a deliberately simple design requirement:

- approximately **2 seconds** to accelerate from rest to maximum velocity;
- approximately **2 seconds** to travel one floor at maximum velocity;
- approximately **2 seconds** to decelerate from maximum velocity back to rest.

The plant accelerates toward `Max_Velocity`, cruises when sufficient distance remains, and begins braking when the remaining distance reaches the required stopping distance.

Arrival is resolved numerically using:

- position tolerance: **0.02 floors**
- velocity tolerance: **0.01 floors/s**

These tolerances are simulation details rather than physical design requirements.

The controller still determines whether movement is allowed. In particular, the car must not move while the doors are open. The plant reads that command and produces the resulting position and velocity.

## Dispatch

Because `Current_Floor` now comes from the physical plant rather than from an operation inside the control graph, the controller can use the car's actual position when choosing its next target.

This model therefore uses direction-aware **LOOK dispatch**.

While travelling upward, the elevator serves pending calls above its current position before reversing direction. While travelling downward, it serves pending calls below it first. The direction changes only when no requests remain ahead.

The controller is therefore answering a richer question than in the first model:

**given the pending requests, the current direction of travel, and the car's observed physical position, which floor should be served next?**

## What this model represents

The distinction between command and outcome is now explicit:

- `Target_Floor` and `Moving` describe what the controller wants the system to do;
- `Current_Floor` and `Velocity_FloorsPerSec` describe what the physical plant actually does.

The plant is intentionally simple and perfectly obedient. It is a **kinematic model**, not a full dynamic model: velocity and acceleration are prescribed directly, with no motor torque, mass, force balance, or mechanical compliance.

That is sufficient for the purpose of this stage.

The important addition is not physical completeness, but an independent physical state. The model can now represent acceleration, cruising, braking, stopping distance, and continuous position — and the controller can make decisions using information it does not produce itself.

`Elevator_System_3` builds on that separation by allowing expected and actual physical behaviour to diverge, making degradation detectable rather than merely representable.