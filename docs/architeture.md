# describe2plc -- Technical Reference

This is the engine's vocabulary and rulebook: the YAML schema, the function blocks, the expression syntax, and the structural constraints that come from how the engine executes. Nothing project-status related lives here -- see `PROJECT_STATE.md` for that.

## Engine files

- `engine/evaluate.py` -- evaluates one JsonLogic-style expression tree against the current tag state. Pure, stateless, no side effects.
- `engine/function_blocks.py` -- the five stateful/edge-detecting building blocks: `R_TRIG`, `TON`, `RS`, `CTUD`, `PID`.
- `engine/topological_sort.py` -- reads an operations list, figures out which operations depend on which tags, and produces a valid execution order.
- `engine/scan_cycle.py` -- loads a YAML file, seeds initial tag values, builds function-block instances, and runs one scan (`run_scan`) over an already-ordered operations list.

## YAML file structure

A system is described in one YAML file with up to five top-level sections, plus `operations`:

```yaml
runtime_inputs:      # external signals - sensors, buttons, anything the world provides
  Some_Input: {type: BOOL}

hmi_configuration:    # fixed parameters/constants - has a `default` value
  Some_Constant: {type: REAL, default: 4}

physical_constants:   # physical properties consumed only by external Python (a physics plant), never by any operation's expression - has a `value`, not a `default`
  Some_Physical_Property: {type: REAL, value: 9.8}

outputs:              # every tag any operation writes to (declares the full tag catalog)
  Some_Tag: {type: BOOL}

operations:            # the actual logic - see below
  - name: "..."
    type: "..."
    output: "..."
    # additional fields depend on type, see below
```

`type: BOOL` seeds `False`; anything else seeds `0.0`. `hmi_configuration` entries without a `default` get a placeholder value and are logged as a warning at load time -- that's intentional, not a bug: it surfaces an unconfirmed assumption instead of hiding it.

`physical_constants` is a separate section from `hmi_configuration`, not a variant of it, and the distinction is real: `hmi_configuration` entries get referenced inside JsonLogic expressions (`{var: "Some_Constant"}`), so they need the node-wrapping discipline described below. `physical_constants` entries are never referenced by any operation -- nothing in the declarative graph needs to know a physics plant's natural frequency or wear rate -- so they're read directly out of the loaded YAML dict by whatever Python code constructs the plant (`entry["value"]`, not evaluated through `evaluate.py` at all), and they use `value` instead of `default` to signal that difference at a glance. Keeping every tunable physical constant here, in one place, rather than as a hardcoded Python default, is deliberate: a constant that only exists as a Python default is a second, silent source of truth that can drift from the YAML without either file ever showing a diff for it. The stronger version of this discipline (seen in `Elevator_System_2`/`3`'s physics plant constructors) is giving these parameters no Python default at all -- a missing constant then fails loudly (a `TypeError`) rather than silently substituting a number nobody asked for.

**`runtime_inputs` isn't just for user-facing buttons.** Anything written every scan by code *outside* the operations graph -- a physics plant, a sensor simulator, any external process the engine doesn't control -- belongs in `runtime_inputs`, not `outputs`, even if it's a continuous physical quantity like a position or velocity rather than a button press. The engine doesn't distinguish "a person pressing something" from "a plant computing something": both are external signals `graph_builder` never gives a producer edge to, seeded the same way, read the same way (`{var: "TagName"}`). This is what lets a physics plant's own output feed straight back into dispatch logic (`Elevator_System_2`'s `Target_Floor` reading `Current_Floor`) with zero cycle risk, where the same comparison against an *operation*-owned tag (`Elevator_System_1`'s `Current_Floor`, a `CTUD`) would be a real, confirmed `CycleError` -- see "LOOK dispatch and the position-ownership cycle" below for the concrete example.

## Operations: the two kinds

Every entry in `operations` is either **stateless** or a **function block**.

**Stateless** types: `and`, `or`, `!`, `gt`, `lt`, `ge`, `le`, `eq`, `if`, `+`, `-`, `wiring`. These have an `expression` field (one JsonLogic tree) and are recomputed fresh every scan -- no memory.

**Function blocks** (`R_TRIG`, `TON`, `RS`, `CTUD`, `PID`) carry memory between scans and have their own named fields instead of a generic `expression`.

Every operation needs: `name` (unique), `type`, `output` (the tag it writes to). `note` and `source` are optional free-text metadata. `load_value` is a special field (see CTUD below) that is NOT itself a JsonLogic node.

## Expression syntax (JsonLogic-style)

Every value fed into any field that isn't `load_value` **must be a JsonLogic node -- a dict with one key** -- even for a plain constant. A bare literal like `PT: 4` will crash; write `PT: {var: "Some_Constant_Tag"}` instead, backed by an `hmi_configuration` entry. This is the single most common mistake when writing new YAML.

Recognized keys:

| Key | Shape | Meaning |
|---|---|---|
| `var` | `{var: "TagName"}` | look up a tag's current value |
| `and` / `or` | `{and: [node, node, ...]}` | variable-length boolean gate |
| `!` | `{"!": node}` | negation, wraps exactly one node |
| `gt` / `lt` / `ge` / `le` / `eq` | `{gt: [node_or_literal, node_or_literal]}` | exactly 2 elements |
| `if` | `{if: [condition, then_value, else_value]}` | exactly 3 elements, ternary |
| `+` / `-` | `{"+": [node_or_literal, node_or_literal]}` | exactly 2 elements |

Comparison/arithmetic operators accept either a nested node or a bare literal in each of their two slots (`{gt: [{var: "X"}, 5]}` is fine) -- it's only the *field itself* (`PT`, `IN`, etc.) that can't be a bare literal directly.

## Function blocks

**R_TRIG** -- rising-edge detector. Fields: `IN`. Outputs `True` for exactly one scan when `IN` transitions False->True.

**TON** -- on-delay timer. Fields: `IN`, `PT` (preset time, in seconds). Elapsed time accumulates while `IN` is true; resets to 0 the instant `IN` goes false. Output is `elapsed >= PT`. Note: once `PT` is reached, output stays true for as long as `IN` stays true -- it does not auto-reset itself.

**RS** -- Set/Reset latch, Reset-dominant. Fields: `Set` (list of nodes, OR'd together), `Reset` (list of nodes, OR'd together). If both fire the same scan, Reset wins.

**CTUD** -- up/down counter. Fields: `CU` (count up on rising edge), `CD` (count down on rising edge), `R` (reset to 0 on rising edge), `LD` (load on rising edge), `load_value` (**a bare literal, not a JsonLogic node** -- the one exception), `PV` (preset/max value). Clamped to `[0, PV]`. Precedence when multiple fire the same scan: R beats LD beats CU/CD.

**PID** -- Fields: `MANUAL`, `Y_MANUAL`, `RESET`, `KP`, `TN`, `TV`, `Y_MIN`, `Y_MAX`, `SET_POINT`, `ACTUAL`. Formula: `Y = KP * (error + I/TN + TV*de/dt)` -- KP scales the whole sum, not just the P term. Anti-windup is back-calculation, not clamping: the integral is rewritten (not frozen) whenever the output saturates, so it doesn't accumulate an unreachable value during a long saturation.

## Execution order: the engine sorts it, you don't have to

**Operations do not need to be listed in the YAML in the order they execute.** Write the file in whatever order reads best to a human (grouped by concept, by stage, whatever). Before running, build the real execution order:

```python
from topological_sort import graph_builder, topological_sorter, build_operation_lookout

graph = graph_builder(raw_operations)
order = topological_sorter(graph)
lookout = build_operation_lookout(raw_operations)
operations = [lookout[name] for name in order]   # this is what you pass to run_scan
```

`graph_builder` walks every operation's fields, finds every `{var: "X"}` reference, and adds a dependency edge if `X` is produced by another operation. `topological_sorter` then produces a valid order via `graphlib.TopologicalSorter`.

## The one rule that will bite you: same-scan cycles

If operation A reads a tag produced by operation B, and B (even transitively, through other operations) reads a tag produced by A, that's a dependency **cycle** -- `topological_sorter` will raise a `CycleError`, not silently pick an order. This happens more often than it sounds like it should, because "X determines Y, and Y's outcome should affect X" is an extremely natural thing to want to describe in plain language, and it's precisely what breaks a single-pass evaluation.

**The one exception:** an operation reading its **own** output tag is not treated as a real dependency edge -- `graph_builder` explicitly skips it. This is what lets a stateful block reference its own prior value (a timer checking whether it's already running, a counter comparing against its own current position) without being flagged as a cycle. This exemption is **only for literal self-reference** (the exact same operation's own tag appearing in its own fields) -- it does not extend to two different operations that reference each other, no matter how many intermediate operations sit between them.

**Practical patterns that work around this**, discovered while building the elevator example (`examples/elevator/Elevator_System_1/elevator.yaml` has all of these with inline comments at the point of use):

- **A self-oscillating pulse**: `IN: {and: [<condition>, {"!": {var: "SelfName"}}]}` on a TON creates a periodic pulse -- it fires, which makes its own `!SelfName` go false next scan, resetting elapsed, letting it fire again. Safe because it only references itself.
- **Inline a comparison directly into a stateful block's own fields**, rather than computing it in a separate named operation first, if that comparison needs the block's own output. E.g., a counter's `CU`/`CD` conditions can safely compare against `{var: "SelfCounterName"}` directly, because that's a literal self-reference -- but routing the *same* comparison through a separate named operation first is a real, blocked cycle.
- **A latch that feeds a dispatch/selection decision cannot also be cleared by the result of that decision.** If you want "remembered until served" behavior, the clearing condition needs to depend on something that does *not* trace back (even indirectly) to the latch itself -- e.g., read raw inputs for the decision, and let the latch be a pure downstream sink (nothing reads it back into the decision) so it can be reset by anything without risk.
- **Don't gate a movement/progress timer on a state that's downstream of arrival**, if arrival is itself downstream of that timer. A self-referencing counter that naturally stops once it reaches its target (via the self-reference exemption) is usually enough on its own, without needing an explicit external gate.

When you hit a `CycleError`, the fix is essentially always: find the tag that's read by both "sides" of the loop, and change one side to read something else -- a raw input instead of a derived/latched value, or the block's own self-reference instead of a separate named intermediate.

### A concrete example: LOOK dispatch and the position-ownership cycle

A real elevator's dispatch algorithm (researched, not assumed -- "Selective Collective" control, known in computer science as the LOOK algorithm) needs to compare pending calls against the car's own current position, to know what's "ahead" of it in the direction it's already moving. This is a genuinely useful, concrete test case for the cycle rule above, because it fails or succeeds depending entirely on *where position lives*, not on the dispatch logic itself:

- If `Current_Floor` is a `CTUD` operation the logic drives itself (as in `Elevator_System_1`), giving `Target_Floor` a `{var: "Current_Floor"}` reference closes a real cross-operation cycle -- `Current_Floor`'s own `CU`/`CD` fields already read `Target_Floor`, so the two operations would need each other's output in the same scan. Confirmed empirically: constructing exactly this graph and running it through `topological_sorter` raises a genuine `CycleError`, not a hypothetical one.
- If `Current_Floor` is a `runtime_input` written by external code instead (as in `Elevator_System_2`), the identical comparison in `Target_Floor` costs nothing -- `runtime_inputs` never get a producer edge at all, so there's no cycle to detect in the first place.

The general lesson: some structural upgrades aren't blocked by missing logic, they're blocked by *who owns the tag* the logic would need to read. Moving a tag from an operation's output to an externally-written `runtime_input` doesn't just avoid a workaround -- it can make an entire category of previously-impossible comparison trivial, with no change to the comparison itself.

## Stateless self-referencing accumulators

The self-reference exemption described above (`graph_builder` skips an operation reading its own output tag) was first demonstrated with function blocks (`TON`, `CTUD`) -- but it isn't restricted to them. Confirmed empirically before relying on it in production (a standalone toy test, not just reasoning): a plain **stateless** operation (`if`, `+`, `-`, etc.) can self-reference its own output the exact same way, because the exemption is about the *tag reference*, not the operation type. Every operation's result gets written into the same shared `tags` dict that persists across scans, regardless of whether it's a function block with its own Python state or a stateless expression re-evaluated from scratch each scan -- so `{var: "SelfName"}` inside a stateless operation's own expression reads *last scan's* value of `SelfName`, exactly like a function block's self-reference does.

This is what lets a running accumulator -- the kind a CUSUM (cumulative sum) control-chart needs -- live as genuine declarative YAML logic instead of hidden Python state. The pattern, using only primitives already in the expression vocabulary (no new engine capability required):

```yaml
- name: "Cumulative_Sum"
  type: "if"
  expression:
    if:
      - gt: [{"-": [{"+": [{var: "Cumulative_Sum"}, {var: "Increment"}]}, {var: "Slack"}]}, 0]
      - {"-": [{"+": [{var: "Cumulative_Sum"}, {var: "Increment"}]}, {var: "Slack"}]}
      - 0
  output: "Cumulative_Sum"
```

This computes `max(0, Cumulative_Sum_prev + Increment - Slack)` every scan -- a standard one-sided CUSUM accumulator, with the `max(0, x)` clamp built from `if`/`gt` since there's no dedicated `max` primitive in the expression vocabulary. `graph_builder` gives `Cumulative_Sum` zero dependency edges (pure self-reference, same as any `TON`'s own self-oscillation), so this creates no cycle risk despite reading its own output every single scan.

One real design lesson from building `Elevator_System_3`'s actual CUSUM this way, worth carrying forward: **feed the accumulator a signal whose sign matches the thing you're actually trying to detect.** A first attempt used two mirror-image accumulators (one watching for a positive-signed residual, one for negative), intended to catch a physical system drifting away from a healthy reference in either direction. It never accumulated meaningfully even with a confirmed, real drift present, because the drift in question was a symmetric oscillation around zero (increasing *ringing amplitude*, not a shift to one side) -- the positive and negative excursions of a single oscillation cancelled against each other's accumulator instead of building toward either threshold. Feeding the accumulator the signal's *magnitude* instead (built the same way `abs(x)` has to be here -- `if gt(x, 0) then x else 0 - x`, since there's no `abs` primitive either) fixed it: a magnitude-based CUSUM is the standard, correct tool for detecting growing spread around a stable mean, which is what the underlying physical failure mode actually was.

## Known limitation: self-oscillating pulses aren't uniformly periodic

The self-oscillating pulse idiom described above (`IN: {and: [<condition>, {"!": {var: "SelfName"}}]}` on a TON) is periodic, but not periodic at `PT`. Empirically verified against the real engine (`examples/elevator/Elevator_System_1/elevator.yaml`'s `Travel_Pulse` and `Clock_Pulse`):

- The **first** pulse after the gating condition goes true fires after exactly `PT` scans -- elapsed accumulates from 0 with the gate already open.
- **Every pulse after that** is `PT + 1` scans apart, not `PT`. The scan where the block resets itself (elapsed back to 0, because `!SelfName` just went false) doesn't contribute toward the next accumulation, so each steady-state cycle costs one extra scan versus the first.

Concretely, in `Elevator_System_1`: `Travel_Pulse` (`PT = Travel_Time_Per_Floor = 4`) makes the first floor crossing of a trip take 4 scans and every crossing after that in the same trip take 5, so a 2-floor trip takes 9 scans rather than the 8 a plain reading of "4 seconds per floor" would suggest. `Clock_Pulse` (`PT = One_Second = 1`) is the same idiom at the tightest possible `PT`, so it ticks roughly every 2 scans in steady state instead of every 1 -- anything counting off it (here, `Door_Elapsed`) advances at roughly half the configured rate after its first tick.

This is accepted as a known limitation for Stage 1, not fixed -- see `PROJECT_STATE.md`'s simplifications list and the inline notes at `Travel_Pulse` / `Clock_Pulse` in the elevator YAML.

Worth correcting in hindsight: this section originally speculated that a later monitoring stage would need to revisit this for a uniform sampling cadence. That's not what happened. `Elevator_System_3`'s `Clock_Pulse`/`Door_Elapsed` are byte-for-byte unchanged from `Elevator_System_2` -- CUSUM's timing concern turned out to be a completely different, more fundamental one: not the scan-level pulse-periodicity quirk here, but the physics plant needing sub-scan integration resolution entirely (see `PROJECT_STATE.md`'s `Elevator_System_3` simplifications list, bug 1). The two timing issues look superficially similar (both about "is one scan per second fine-grained enough") but turned out to be unrelated in practice -- worth not assuming a documented limitation will turn out to matter for whatever comes next, even when it seems like an obvious connection at the time.

## Naming and documentation conventions

- Operation names: `PascalCase`, descriptive of what they compute, not how (`Doors_Open`, not `RS_Latch_3`).
- Every operation that isn't self-explanatory gets a `note` field explaining *why*, not just *what* -- especially anything that looks unusual (a self-reference, a deliberately-dropped safety check, a known simplification).
- Section comments (`# --- Dispatch ---`) group operations by concept in the YAML file for human readability -- these carry no meaning to the engine, purely documentation.