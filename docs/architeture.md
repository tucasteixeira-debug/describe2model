# describe2plc -- Technical Reference

This is the engine's vocabulary and rulebook: the YAML schema, the function blocks, the expression syntax, and the structural constraints that come from how the engine executes. Nothing project-status related lives here -- see `PROJECT_STATE.md` for that.

## Engine files

- `engine/evaluate.py` -- evaluates one JsonLogic-style expression tree against the current tag state. Pure, stateless, no side effects.
- `engine/function_blocks.py` -- the five stateful/edge-detecting building blocks: `R_TRIG`, `TON`, `RS`, `CTUD`, `PID`.
- `engine/topological_sort.py` -- reads an operations list, figures out which operations depend on which tags, and produces a valid execution order.
- `engine/scan_cycle.py` -- loads a YAML file, seeds initial tag values, builds function-block instances, and runs one scan (`run_scan`) over an already-ordered operations list.

## YAML file structure

A system is described in one YAML file with up to four top-level sections, plus `operations`:

```yaml
runtime_inputs:      # external signals - sensors, buttons, anything the world provides
  Some_Input: {type: BOOL}

hmi_configuration:    # fixed parameters/constants - has a `default` value
  Some_Constant: {type: REAL, default: 4}

outputs:              # every tag any operation writes to (declares the full tag catalog)
  Some_Tag: {type: BOOL}

operations:            # the actual logic - see below
  - name: "..."
    type: "..."
    output: "..."
    # additional fields depend on type, see below
```

`type: BOOL` seeds `False`; anything else seeds `0.0`. `hmi_configuration` entries without a `default` get a placeholder value and are logged as a warning at load time -- that's intentional, not a bug: it surfaces an unconfirmed assumption instead of hiding it.

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

## Known limitation: self-oscillating pulses aren't uniformly periodic

The self-oscillating pulse idiom described above (`IN: {and: [<condition>, {"!": {var: "SelfName"}}]}` on a TON) is periodic, but not periodic at `PT`. Empirically verified against the real engine (`examples/elevator/Elevator_System_1/elevator.yaml`'s `Travel_Pulse` and `Clock_Pulse`):

- The **first** pulse after the gating condition goes true fires after exactly `PT` scans -- elapsed accumulates from 0 with the gate already open.
- **Every pulse after that** is `PT + 1` scans apart, not `PT`. The scan where the block resets itself (elapsed back to 0, because `!SelfName` just went false) doesn't contribute toward the next accumulation, so each steady-state cycle costs one extra scan versus the first.

Concretely, in `Elevator_System_1`: `Travel_Pulse` (`PT = Travel_Time_Per_Floor = 4`) makes the first floor crossing of a trip take 4 scans and every crossing after that in the same trip take 5, so a 2-floor trip takes 9 scans rather than the 8 a plain reading of "4 seconds per floor" would suggest. `Clock_Pulse` (`PT = One_Second = 1`) is the same idiom at the tightest possible `PT`, so it ticks roughly every 2 scans in steady state instead of every 1 -- anything counting off it (here, `Door_Elapsed`) advances at roughly half the configured rate after its first tick.

This is accepted as a known limitation for Stage 1, not fixed -- see `PROJECT_STATE.md`'s simplifications list and the inline notes at `Travel_Pulse` / `Clock_Pulse` in the elevator YAML. If a later stage needs a genuinely uniform pulse rate (e.g. a monitoring layer sampling at a fixed cadence), this idiom is the wrong tool for that and needs a different construction -- worth deciding deliberately rather than reusing this pattern by default.

## Naming and documentation conventions

- Operation names: `PascalCase`, descriptive of what they compute, not how (`Doors_Open`, not `RS_Latch_3`).
- Every operation that isn't self-explanatory gets a `note` field explaining *why*, not just *what* -- especially anything that looks unusual (a self-reference, a deliberately-dropped safety check, a known simplification).
- Section comments (`# --- Dispatch ---`) group operations by concept in the YAML file for human readability -- these carry no meaning to the engine, purely documentation.