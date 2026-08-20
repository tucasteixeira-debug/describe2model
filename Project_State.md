# describe2plc -- Project State

This tracks what the project is for and where it currently stands. Pure technical reference (YAML schema, function blocks, engine internals) lives in `docs/architecture.md`, not here.

## Session protocol (read this first, every session)

These two files are the persistent memory of this project across sessions. Nothing about progress, decisions, or simplifications is "remembered" unless it's written here or in `docs/architecture.md`. At the **end of every working session**, before ending the conversation:

1. **Update `PROJECT_STATE.md`:**
   - Move anything finished out of "Not started yet" and into "Done," described concretely enough that a fresh session understands what exists without re-deriving it.
   - Add any new deliberate simplifications discovered this session to the relevant "Known, deliberate simplifications" list (create a new one per system stage as needed, e.g. for `Elevator_System_2`).
   - If scope changed (something added, dropped, or redefined), edit "Objective" directly rather than leaving stale text plus a correction further down.
2. **Update `docs/architecture.md`:**
   - Any new structural rule, gotcha, or pattern discovered while building (a new cycle pattern, a new function-block quirk, a new expression-syntax edge case) goes here, not in `PROJECT_STATE.md` -- this file is the technical reference, that one is status.
   - Prefer folding new patterns into existing sections (e.g. "Practical patterns that work around this") over appending an unstructured changelog.
3. **Keep the split intact:** `PROJECT_STATE.md` = what's done / what's left / why the project exists. `docs/architecture.md` = how the engine actually works. If unsure which file something belongs in, ask "would this still be true if the elevator example didn't exist?" -- if yes, it's architecture; if no, it's state.
4. **Don't silently drop detail.** If a session ends mid-task, note where it stopped and what the immediate next step is, rather than leaving "Not started yet" as the only signal.

## Objective

A public GitHub portfolio project: an engine that takes a system described in plain language, translates it (via a small set of documented rules) into a declarative YAML graph of operations, and runs it as a scan-cycle simulation -- topologically sorted, not hand-ordered.

The core pitch: once a system is a plain declarative graph instead of hard-coded procedural logic, it stops being rigid. Capability gets added *around* the existing graph (a physics plant replacing a placeholder, a monitoring layer added on top) without rebuilding what's already there.

Demonstrated end-to-end on one running example: a single-car, 3-floor elevator, taken through three stages of increasing requirement complexity, each a genuine upgrade rather than a rebuild:

- **`Elevator_System_1`** -- pure logic, translated from plain English. Motion between floors is a fixed-time placeholder.
- **`Elevator_System_2`** -- the placeholder motion is replaced with a real physics plant (position/velocity), so trip time becomes a genuine output of physics.
- **`Elevator_System_3`** -- a CUSUM (cumulative-sum control chart) monitoring layer, comparing the logic's nominal expectation against the physics plant's actual behavior, to catch slow drift (a synthetic wear parameter injected into the plant) that a simple threshold would miss.

Origin note (goes in the README, not hidden): the project is not connected to or derived from any employer's proprietary system. It's motivated by a real friction point -- conceptually understanding an industrial control system is not the hard part; translating dense technical documentation into working simulation without PLC-specific fluency is.

## Repo name

`describe2plc`. Public, MIT licensed, single `main` branch.

## Current status

**Done:**
- GitHub repo created (public, MIT license), cloned locally over SSH (personal key, not tied to any institutional account), `.gitignore` in place.
- `README.md` at repo root -- written, includes the "why" framing above.
- `engine/` -- all four files in place and scrubbed of any prior-project-specific references:
  - `evaluate.py`, `topological_sort.py` -- generic as-is.
  - `function_blocks.py` -- comments cleaned, technical reasoning (PID back-calculation anti-windup, etc.) kept.
  - `scan_cycle.py` -- refactored so `load_data(path)` takes any YAML path, no hardcoded default.
  - Smoke-tested end to end after cleanup.
- `examples/elevator/README.md` -- brief, staged-objective overview (the 3-system structure above).
- `examples/elevator/Elevator_System_1/description.md` -- plain-English description, concrete numbers (3 floors, 4s per floor traveled, 6s door hold, obstruction restarts the hold), no physics-plant foreshadowing (that's the top README's job).
- `examples/elevator/Elevator_System_1/elevator.yaml` -- full translation, built and behaviorally verified (not just structurally validated) against the actual engine. Operations are grouped by concept (Dispatch / Movement / Doors / Requests) in the file, execution order is produced separately via `topological_sort.py` at load time -- confirmed these two orders are genuinely different and it still runs correctly.
- `docs/architecture.md` -- the technical vocabulary/rules reference, including three real dependency-cycle patterns hit and resolved while building `Elevator_System_1`, each empirically verified against the real `topological_sorter` (not just reasoned through).

**Known, deliberate simplifications in `Elevator_System_1`** (documented inline in the YAML, not hidden):
- Dispatch reads raw call-button state, not a latched/remembered request -- a call has to still be held (or re-pressed) by the time the car is free to serve it, because a latch that drives dispatch and is also cleared by dispatch's result is a same-scan cycle.
- A second call arriving while doors are open at the first can preempt mid-dwell (Target_Floor recomputes every scan from raw inputs) -- not an issue when calls come one at a time.
- The door-obstruction hold-restart is edge-triggered: a long continuous block resets the hold once at the start of the block, not continuously for its whole duration.
- The self-oscillating TON idiom used for `Travel_Pulse` and `Clock_Pulse` is periodic but not *uniformly* periodic: the first pulse after a gating condition goes true fires after `PT` scans, but every pulse after that is `PT+1` scans apart. Measured effect: a ground-to-2nd-floor trip takes 9 scans, not the 8 a naive "4 seconds per floor" reading implies; door-hold runs roughly double the configured `Door_Hold_Time` (~12 scans instead of 6). This was discovered and behaviorally verified while validating the file against the real engine, not part of the original translation intent -- documented rather than fixed for Stage 1. See `docs/architecture.md`'s "Known limitation: self-oscillating pulses aren't uniformly periodic" for the general mechanism, and worth revisiting before `Elevator_System_3`'s CUSUM layer, which will want a clean, uniformly-sampled nominal baseline to compare physics against.

**Not started yet:**
- `examples/elevator/Elevator_System_2/` -- physics plant (position/velocity integration replacing the fixed-4-seconds-per-floor placeholder).
- `examples/elevator/Elevator_System_3/` -- CUSUM monitoring layer, including designing the synthetic wear parameter for the plant.
- `examples/elevator/Elevator_System_1/run_simulation.py` -- a proper runnable script (right now the simulation has only been run ad hoc, inline, to verify behavior -- not yet a clean, presentable script in the repo).
- Final README polish once everything else exists (currently has a placeholder "Status" section).