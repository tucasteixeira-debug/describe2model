# Elevator System 1 — Control Logic

A single elevator serves six floors, from ground floor (`0`) to floor `5`.

This first model focuses only on the **control and decision-making layer**. There is no independent physical model of the elevator yet: movement and position are represented directly by the control logic.

## Required behaviour

Each floor can generate a request. Internal and external floor buttons are treated identically — the controller only needs to know that a floor is waiting to be served.

When one or more requests are active, the controller selects a `Target_Floor`.

The elevator then decides whether it must move up, move down, or remain where it is. Travel is represented as taking **4 seconds per floor**, with `Current_Floor` updated as each floor is crossed.

When the elevator reaches the target:

1. movement stops;
2. the request is considered served;
3. the doors open.

The doors normally remain open for **6 seconds**. They may be closed early with `Close_Door_Button`, while `Door_Obstruction` prevents them from closing until the obstruction has cleared.

The elevator must never move while its doors are open.

Once the doors close, the controller evaluates the remaining requests and repeats the sequence.

## Dispatch in this first model

The dispatch policy is deliberately simple: when several floors are requested, the controller selects the **lowest-numbered active floor**.

This is sufficient for the purpose of the first example: to represent and execute the core control sequence — request, target selection, direction, travel, arrival, and door handling — entirely within the declarative rule graph.

It is not intended to reproduce realistic elevator scheduling.

A more realistic direction-aware policy requires the controller to reason about the car's physical position independently of the logic that commands its movement. In this first model, `Current_Floor` is itself produced by the control graph, so that information is not yet independent.

`Elevator_System_2` introduces a separate physical model and makes `Current_Floor` an externally observed state, allowing the dispatch logic to become correspondingly richer.