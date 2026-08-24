# Engine Internals

How `engine/` actually runs a YAML file. This is about mechanism, not vocabulary — for what a `TON` or an `RS` *means*, see [`yaml_guide.md`](yaml_guide.md).

## Tags: the world model

There's exactly one piece of shared state in the whole engine: a plain Python `dict` called `tags`. Every input, every constant, every operation's output — the entire condition of the system at this instant — lives in that one dict, and every operation both reads and writes it through nothing but `tags["SomeName"]`.

That sounds almost too simple to be worth naming, but it's the actual design: the engine doesn't model "the elevator" or "the traffic light" as an object with methods. It models a world as a dictionary of named values, and a list of small functions that each read a few keys and write one key, run in sequence. Real complexity comes from having *many* of these small operations, not from any one of them being clever — `run_scan()` (in `scan_cycle.py`) is a five-line loop:

```python
def run_scan(operations, fb_instances, tags):
    for op in operations:
        op_type = op["type"]
        if op_type in STATELESS_TYPES:
            result = evaluate(op["expression"], tags)
        else:
            instance = fb_instances[op["name"]]
            result = instance.check(op, tags)   # or .control_loop() for PID
        tags[op["output"]] = result
```

A whole elevator's dispatch, motion gating, and door sequencing is this loop running ~30 times over a list of ~30 tiny operations, once per scan, rather than one large function trying to decide everything at once. That's a deliberate trade: many small, independently-readable steps over shared state, instead of one big procedure — the same reason ladder logic and structured text are built out of small rungs/statements rather than monolithic routines.

## `evaluate()`: one recursive function, no separate parser

The elegant part of this engine is that there's no separate step that "parses" a JsonLogic expression before running it. `evaluate(node, tags)` *is* the interpreter — it looks at one dict's single key, and either returns a value directly (`var`) or calls itself on whichever sub-nodes that key implies (`and`, `gt`, `if`, ...). An arbitrarily nested expression gets walked correctly with no explicit stack, no tree-building pass, nothing but the Python call stack doing the recursion for free.

![evaluate() recursion](assets/evaluate_recursion.svg)

Concretely, evaluating `Current_Floor`'s `CU` field —

```python
{and: [{var: "Travel_Pulse"}, {gt: [{var: "Target_Floor"}, {var: "Current_Floor"}]}]}
```

— is one call to `evaluate()`, which sees `and`, and calls `evaluate()` again on each of its two elements; the second of those sees `gt` and calls `evaluate()` twice more on `var` nodes, which are the base case (a direct `tags[...]` lookup, no further recursion). Four calls total, one function, correct for expressions of any depth without the function needing to know how deep they'll go.

`topological_sort.py`'s `collect_vars()` uses the exact same shape of recursion for a different purpose: instead of *computing* a value, it walks the same kind of tree to *discover every tag name referenced inside it*, so `graph_builder()` knows what an operation depends on. Same recursive tree-walk, two different jobs — evaluate a tree, or inventory a tree.

## The four files

- **`evaluate.py`** — the recursive expression interpreter above. Pure: given a node and the current `tags`, always returns the same result, no side effects.
- **`function_blocks.py`** — `R_TRIG`, `TON`, `RS`, `CTUD`, `PID`. Each is a small class holding whatever it needs to remember between scans (`self.elapsed`, `self.counter`, `self.value`...) — real Python state, distinct from anything in `tags`. One instance gets built per operation of that type; `.check(op, tags)` (or `.control_loop()` for `PID`) reads its own fields via `evaluate()`, updates its own internal state, and returns this scan's output.
- **`topological_sort.py`** — figures out execution order once, before any scan runs (mechanics covered in the YAML guide's cycle-rule section; not repeated here).
- **`scan_cycle.py`** — everything around a single scan: `load_data()` reads the YAML, `build_initial_tags()`/`seed_operation_outputs()` seed `tags` before scan 1, `build_fb_instances()` builds one function-block object per stateful operation, `run_scan()` is the loop above.

## Where a physics plant actually hooks in

This is the one seam worth understanding precisely, without getting into any plant's own physics (see `example/Elevator_System_2/car_physics_2.py` and `example/Elevator_System_3/car_physics_3.py` for that): a plant is nothing but another writer to the same `tags` dict, called once per scan from `simulation_runner.py`, immediately *after* `run_scan()`.

![Plant integration](assets/plant_integration.svg)

```python
run_scan(operations, fb_instances, tags)
if plant is not None:
    plant.step(tags)
```

That ordering is the whole trick: `plant.step(tags)` reads *this* scan's fresh logic outputs (e.g. `Moving`) and writes the tag *next* scan's logic will read (e.g. `Current_Floor`) — which is exactly why that tag has to live under `runtime_inputs` rather than `outputs` (see the YAML guide's note on that section). The engine itself never imports or knows about any plant class; `run_scan_loop()`'s `plant` parameter just accepts anything with a `.step(tags)` method, or `None` for a stage with no physical layer at all (`Elevator_System_1`). Swapping in a different plant, or none, changes nothing about `engine/`.