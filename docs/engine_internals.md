# Engine Internals

How `engine/` actually runs a YAML file. This is about mechanism, not vocabulary — for what a `TON` or an `RS` *means*, see [`yaml_guide.md`](yaml_guide.md).

While the YAML — the declarative part of this project — is about describing a system using a finite set of fundamental operations and knowns, the engine is the modular software able to process anything written in that set of rules and turn it into a working simulation. The diagram below is the working principle behind that; the rest of this document walks through it piece by piece.

![Scan cycle flow](assets/scan_cycle_flow.svg)

A YAML file gets loaded once, sorted into a valid execution order once, and then `run_scan()` re-evaluates every operation, in that order, forever — the same read-decide-act-repeat cycle a real PLC or microcontroller runs on.

## `evaluate()`: the same principle, made mechanical

The YAML guide's Syntax section makes a design claim: any real system can be described as a finite set of fundamental-level operations, built entirely out of recursive dicts and lists. `evaluate()` is where that claim actually gets exploited, not just asserted — it's the elegant part of this engine precisely because it takes that fact at face value. There's no separate step that "parses" a JsonLogic expression before running it: `evaluate(node, tags)` *is* the interpreter. It looks at one dict's single key, and either returns a value directly (`var`, the base case) or calls itself on whichever sub-nodes that key implies (`and`, `gt`, `if`, ...). An arbitrarily nested expression gets walked correctly with no explicit stack, no tree-building pass, nothing but the Python call stack doing the recursion for free — because the language *is* recursive dicts and lists, the interpreter can just recurse on dicts and lists.

![evaluate() recursion](assets/evaluate_recursion.svg)

Concretely, evaluating `Current_Floor`'s `CU` field —

```python
{and: [{var: "Travel_Pulse"}, {gt: [{var: "Target_Floor"}, {var: "Current_Floor"}]}]}
```

— is one call to `evaluate()`, which sees `and`, and calls `evaluate()` again on each of its two elements; the second of those sees `gt` and calls `evaluate()` twice more on `var` nodes, which are the base case (a direct `tags[...]` lookup, no further recursion). Four calls total, one function, correct for expressions of any depth without the function needing to know how deep they'll go — the six-level `Target_Floor` dispatch tree in the YAML guide runs through this exact same function, unchanged.

`topological_sort.py`'s `collect_vars()` uses the exact same shape of recursion for a different purpose: instead of *computing* a value, it walks the same kind of tree to *discover every tag name referenced inside it*, so `graph_builder()` knows what an operation depends on. Same recursive tree-walk, two different jobs — evaluate a tree, or inventory a tree.

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

One distinction worth keeping straight: `tags` is the *only* state that persists across scans in a way the YAML controls. Function blocks (`function_blocks.py`) additionally keep their own small pocket of private Python state — `self.elapsed` on a `TON`, `self.counter` on a `CTUD` — held in one object per stateful operation, built once by `build_fb_instances()`. That state is real and it does persist, but it's invisible to the declarative graph; the only thing any operation can ever read from another operation is what that operation chose to write into `tags`.

## Topological sort: solving for a valid order once

The YAML is written in whatever order reads best to a human, which means the engine has to work out a valid execution order itself before running anything — this is a real design choice, not an incidental detail, because without it a scan is only correct if `Doors_Open` happens to be evaluated after everything it depends on.

![Topological sort](assets/topological_sort.svg)

```python
graph = graph_builder(raw_operations)
order = topological_sorter(graph)
lookout = build_operation_lookout(raw_operations)
operations = [lookout[name] for name in order]   # this is what run_scan takes
```

`graph_builder` walks every operation's fields with the same recursive tree-walk from above, finds every `{var: "X"}` reference, and adds a dependency edge if `X` is produced by another operation — self-references are skipped on purpose, which is the whole subject of the next section. Function blocks don't share one field name for their logic the way stateless operations do (`RS` uses `Set`/`Reset`, `CTUD` uses `CU`/`CD`/`R`/`LD`, `TON` uses `IN`/`PT`), so `collect_operation_vars` can't assume where to look — it walks every field on an operation except a small fixed set of metadata keys (`name`, `type`, `output`, `note`, `source`, `load_value`) and collects whatever tag references turn up, regardless of which fields happen to hold them. The result is a plain dict: `{operation_name: [names of operations it depends on]}`.

`topological_sorter` itself isn't a hand-rolled algorithm — it's a thin wrapper around Python's own standard library, `graphlib.TopologicalSorter`, built for exactly this job. It's worth being precise about what `static_order()` is actually doing, since "it sorts it" undersells it: every node starts out waiting on however many not-yet-emitted dependencies it has; the moment a node's remaining count hits zero it becomes *ready* and gets emitted; emitting it then lowers the count for everything that depended on it, which can make more nodes ready in turn. That repeats until every node's been emitted, in an order where nothing is ever emitted before something it depends on. A genuine cycle is exactly the case where some subset of nodes can never reach a zero count — each is still waiting on another member of the same subset — so nothing in that subset ever becomes ready, and that stuck state is what surfaces as `CycleError`. `topological_sorter` turns that into one valid order; you never hand-order the YAML file, and the engine only has to solve for that order once, not every scan.

## Cycles, and the one exception that makes self-reference possible

If operation A reads a tag produced by B, and B (even transitively) reads a tag produced by A, that's a dependency **cycle** — `topological_sorter` raises `CycleError` rather than silently picking an order. This happens more than it sounds like it should, because "X determines Y, and Y's outcome should affect X" is a very natural thing to want to describe in plain language, and it's exactly what breaks a single-pass evaluation.

**The one exception:** an operation reading its **own** output tag is not a real dependency edge — `graph_builder` explicitly skips it. That's what lets a timer check whether it's already running, or a counter compare against its own position, without being flagged. This exemption is for literal self-reference only — it doesn't extend to two operations referencing each other, no matter how many operations sit between them.

**A concrete example, from the elevator, showing this isn't just a technicality.** A real LOOK-algorithm dispatch needs to compare pending calls against the car's own position. If `Current_Floor` is an operation the logic drives itself (`Elevator_System_1`'s `CTUD`), giving `Target_Floor` a `{var: "Current_Floor"}` reference closes a genuine cross-operation cycle — confirmed empirically by actually building that graph and hitting `CycleError`. Move `Current_Floor` to a `runtime_input` written by external code instead (`Elevator_System_2`), and the identical comparison costs nothing, because `runtime_inputs` never get a producer edge in the first place. The lesson generalizes: some upgrades aren't blocked by missing logic, they're blocked by *who owns the tag* the logic needs to read.

**The exemption isn't limited to function blocks.** A plain stateless `if`/`+`/`-` operation can self-reference its own output the same way, since the exemption is about the tag reference, not the operation type. That's what lets a running accumulator — the kind a CUSUM control chart needs — live as genuine declarative YAML instead of hidden Python state, `example/Elevator_System_3/elevator_3.yaml`:

```yaml
- name: "CUSUM_High"
  type: "if"
  note: "C = max(0, C_prev + |residual| - k). Self-references its own output to accumulate across scans."
  expression:
    if:
      - gt: [{"-": [{"+": [{var: "CUSUM_High"}, {var: "Abs_Velocity_Residual"}]}, {var: "Slack_K"}]}, 0]
      - {"-": [{"+": [{var: "CUSUM_High"}, {var: "Abs_Velocity_Residual"}]}, {var: "Slack_K"}]}
      - 0
  output: "CUSUM_High"
```

It creates no cycle risk despite reading its own output every scan, for the same reason the `Current_Floor` counter above doesn't.

**When you hit a `CycleError`**, the fix is essentially always the same: find the tag read by both sides of the loop, and change one side to read something else — a raw input instead of a derived value, or the block's own self-reference instead of a separate named intermediate.

## Extension and modularity: swapping in a physics plant

Everything above exists to make one thing possible: once a system's core logic is genuinely solidified — working, and simple enough to trust — real capability can keep getting added on top of it, layer after layer, without ever going back and rebuilding what already works. That's not an aspiration about the design, it's exactly what happened across the three stages of `example/`, and it's worth walking through concretely rather than just asserting it: the same headroom that let a physics plant and a monitoring layer get added here is the same headroom available for whatever gets built on top of this next — a different dispatch strategy, a maintenance-cost model, a second car sharing the shaft. The simplicity of the syntax and the elegance of the recursive design covered above aren't just clean for their own sake; they're precisely what keeps that door open, because neither the vocabulary nor the engine has to change shape to accommodate something new.

This is the one seam worth understanding precisely, without getting into any plant's own physics (see `example/Elevator_System_2/car_physics_2.py` and `example/Elevator_System_3/car_physics_3.py` for that): a plant is nothing but another writer to the same `tags` dict, called once per scan from `simulation_runner.py`, immediately *after* `run_scan()`.

![Plant integration](assets/plant_integration.svg)

```python
run_scan(operations, fb_instances, tags)
if plant is not None:
    plant.step(tags)
```

That ordering is the whole trick: `plant.step(tags)` reads *this* scan's fresh logic outputs (e.g. `Moving`) and writes the tag *next* scan's logic will read (e.g. `Current_Floor`) — which is exactly why that tag has to live under `runtime_inputs` rather than `outputs` (see the YAML guide's note on that section). The engine itself never imports or knows about any plant class; `run_scan_loop()`'s `plant` parameter just accepts anything with a `.step(tags)` method, or `None` for a stage with no physical layer at all (`Elevator_System_1`). Swapping in a different plant, or none, changes nothing about `engine/`.

That's one axis of extension — a whole new subsystem written *underneath* the logic, without the logic knowing it's there. The CUSUM monitoring layer above is the other axis: a capability added entirely *within* the declarative graph itself, by adding new operations that read outputs which already existed (`Abs_Velocity_Residual`, and ultimately the plant's own state), with nothing about `Elevator_System_2`'s dispatch or door logic touched at all. One extension went underneath the graph; the other went inside it. Neither required rebuilding anything the stage before it had already gotten working — and those are just the two extensions that actually got built here, not a ceiling on what the same two seams can take next.