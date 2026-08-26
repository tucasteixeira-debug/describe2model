# The YAML Guide

The idea is to use a plain data structure — dictionaries containing lists — to describe an industrial control operation using a fixed set of rules, so that an engine can consistently process and interpret anything written in it.

The premise underneath is simple: any real system is built from a finite set of fundamental operations and a finite vocabulary for expressing them. This format makes that structure explicit. In a sense, it is already how PLC systems work — this simply pushes that structure further, making the logic itself a declarative description rather than a procedural program.

The engine takes that finite vocabulary and, with a deliberately simple algorithm, executes it at real speed — that mechanism is covered in [`engine_internals.md`](engine_internals.md), not here. This guide is about the description itself: the three design decisions that shape it are **a syntax simple enough to process without ambiguity, a clear file structure, and a finite vocabulary of fundamental operations**.

That's the order this guide follows — starting with the syntax, since it is what every file and every operation is ultimately written in.


## Syntax

Before anything else, it is worth seeing how an operation is actually written, because the file structure and the vocabulary described below are both just this one rule, applied repeatedly.

The core idea is that every field value is a **JsonLogic node — a dictionary with exactly one key** — and that key's value is either a plain literal or another node.

This is deliberately recursive, and that is the design decision worth making explicit: a dictionary can contain a list, that list can contain more dictionaries, and those dictionaries can contain more lists, to whatever depth the decision requires.

There is no separate expression grammar bolted on top of YAML. The recursive shape of a dictionary containing a list containing dictionaries *is* the language. It is exactly the structure you would naturally arrive at when describing something like “the AND of these conditions, one of which is itself a comparison.”

The engine therefore does not need a custom parser. It only needs to know how to walk a dictionary and a list.

Concretely:

```yaml
{gt: [{var: "Target_Floor"}, {var: "Current_Floor"}]}
```

is a dictionary with one key (`gt`), whose value is a list of two elements, each of which is itself a dictionary with one key (`var`). Three levels of nesting, three nodes, and every level is read the same way: look at the one key, do what it says, and recurse into whatever is inside it.

| Key | Shape | Meaning |
|---|---|---|
| `var` | `{var: "TagName"}` | look up a tag's current value |
| `and` / `or` | `{and: [node, node, ...]}` | variable-length boolean gate |
| `!` | `{"!": node}` | negation, wraps exactly one node |
| `gt` / `lt` / `ge` / `le` / `eq` | `{gt: [a, b]}` | exactly 2 elements |
| `if` | `{if: [condition, then, else]}` | exactly 3 elements, ternary |
| `+` / `-` | `{"+": [a, b]}` | exactly 2 elements |

Comparison and arithmetic operators accept either a nested node or a bare literal in each of their two slots — `{gt: [{var: "X"}, 5]}` is fine.

The one thing that is never allowed is a bare literal as the field itself: `PT: 4` will crash, because `4` is not a node. It has to be `PT: {var: "Some_Tag"}`, backed by an `hmi_configuration` entry.

This is the single most common mistake when writing new YAML.

`load_value` on a `CTUD` is the one deliberate exception — its value really is meant to be a plain number rather than a computed condition.

There is no `max` or `abs` primitive — both can be constructed from `if` / `gt` / `-` when needed. See the CUSUM accumulator in [`engine_internals.md`](engine_internals.md) for a real worked example of that.


## Anatomy of a system file

Up to five top-level sections, plus `operations`:

| Section | What goes here | Shape |
|---|---|---|
| `runtime_inputs` | External signals — buttons, sensors, or anything written every scan by code *outside* the operations graph (including a physics plant) | `{type: BOOL}` or `{type: REAL}` |
| `hmi_configuration` | Fixed parameters referenced *inside* operation expressions | `{type: REAL, default: 4}` |
| `physical_constants` | Values consumed only by external Python, never by an operation | `{type: REAL, value: 9.8}` |
| `outputs` | Every tag any operation writes to — the full tag catalog | `{type: BOOL}` |
| `operations` | The actual control logic | see below |

![Where each section's values go](assets/file_anatomy.svg)

Real excerpt, `example/Elevator_System_2/elevator_2.yaml`:

```yaml
runtime_inputs:
  Call_Floor0: {type: BOOL}
  Current_Floor: {type: REAL, note: "Written every scan by the physics plant, not an operation."}

hmi_configuration:
  Door_Hold_Time: {type: REAL, default: 6}
  Never: {type: BOOL, default: false}

physical_constants:
  Top_Floor: {type: REAL, value: 5}
  Max_Velocity: {type: REAL, value: 0.5, note: "floors/second. Per description_2.md's stated requirement: ~2 seconds per floor."}

outputs:
  Doors_Open: {type: BOOL}
  Moving: {type: BOOL}
```

One distinction is worth being precise about:

- **`runtime_inputs` isn't just “user-facing buttons.”** Anything written every scan by code outside the operations graph belongs here. A physics plant's position output counts exactly the same as a button press. The engine does not distinguish between the two; both are external signals that never get a producer edge in the dependency graph.

That distinction is what makes certain structural upgrades possible at all — see the cycle-detection section of [`engine_internals.md`](engine_internals.md).

`type: BOOL` seeds `False`; anything else seeds `0.0`.

An `hmi_configuration` entry with no `default` still runs, but receives a placeholder value and a load-time warning — a deliberate surfacing of an unconfirmed assumption, rather than a hidden failure.


## Vocabulary and operations

Every entry in `operations` is one of two kinds.

![Every operation is one of two kinds](assets/vocabulary_categories.svg)

**Stateless** (`and`, `or`, `!`, `gt`, `lt`, `ge`, `le`, `eq`, `if`, `+`, `-`, `wiring`) — has an `expression` field: one JsonLogic tree, recomputed fresh every scan with no memory of its own. (`wiring` uses the same mechanism, but acts as a semantic label for a plain signal pass-through or relabel rather than a computation.)

**Function blocks** (`R_TRIG`, `TON`, `RS`, `CTUD`, `PID`) — carry memory between scans and have their own named fields rather than a generic `expression`.

This vocabulary is not arbitrary. `R_TRIG`, `TON`, `RS`, and `CTUD` are named directly after their equivalents in IEC 61131-3, the international standard for programmable controller programming. The format deliberately builds on that same function-block vocabulary rather than inventing a new one.

`PID` is not part of the core IEC 61131-3 block list itself, but it is a near-universal standard-library block across real PLC platforms, serving the same control-loop role here.

- **R_TRIG** — rising-edge detector. Field: `IN`. Outputs `True` for exactly one scan when `IN` goes False → True.
- **TON** — on-delay timer. Fields: `IN`, `PT` (preset time, seconds). Elapsed accumulates while `IN` is true and resets to 0 the instant `IN` goes false. Output is `elapsed >= PT`; it does not auto-reset once reached.
- **RS** — Set/Reset latch, Reset-dominant. Fields: `Set` (list, OR'd), `Reset` (list, OR'd).
- **CTUD** — up/down counter. Fields: `CU`, `CD` (count up/down on rising edge), `R` (reset), `LD` (load), `load_value` (the syntax exception above), `PV` (preset/max). Clamped to `[0, PV]`; precedence when several fire in the same scan is R beats LD beats CU/CD.
- **PID** — Fields: `MANUAL`, `Y_MANUAL`, `RESET`, `KP`, `TN`, `TV`, `Y_MIN`, `Y_MAX`, `SET_POINT`, `ACTUAL`. `Y = KP * (error + I/TN + TV*de/dt)` — `KP` scales the whole sum, not just the P term. Anti-windup is back-calculation, so recovery after a long saturation is not unnecessarily slow. It is not exercised anywhere in the elevator example (a discrete-floor dispatch problem has no continuous setpoint to track), but it is part of the vocabulary for systems that do — a temperature loop, a flow-rate controller, and so on.

Every operation needs `name` (unique), `type`, and `output` (the tag it writes to).

`note` and `source` are optional free-text metadata. They are worth using generously: a `note` explaining *why* something is written the way it is — especially anything that looks unusual — is what makes a YAML file readable months later.

A **self-oscillating pulse**, from `example/Elevator_System_1/elevator_1.yaml`, is worth seeing once because the idiom is not obvious from the field list alone:

```yaml
- name: "Travel_Pulse"
  type: "TON"
  IN:
    and:
      - {var: "Any_Pending"}
      - {"!": {var: "Travel_Pulse"}}
  PT: {var: "Travel_Time_Per_Floor"}
  output: "Travel_Pulse"
```

Gating `IN` on the block's own negated output makes it fire, which makes `!Travel_Pulse` go false on the next scan, resetting elapsed and allowing it to fire again — a periodic pulse built from one timer and a self-reference, with no separate oscillator required.

It is periodic, but not uniformly periodic at `PT`: every pulse after the first is `PT + 1` scans apart. That is a real, measured quirk of the idiom, and worth knowing before relying on exact timing.

And a real `RS` + `CTUD` pair, from `example/Elevator_System_1/elevator_1.yaml`, shows the field shapes above in context:

```yaml
- name: "Doors_Open"
  type: "RS"
  note: "Reset fires on either the normal hold timer OR the manual close-door button."
  Set: [{var: "Just_Arrived"}]
  Reset: [{var: "Door_Timer_Q"}, {var: "Close_Door_Button"}]
  output: "Doors_Open"

- name: "Current_Floor"
  type: "CTUD"
  note: "CU/CD compare Target_Floor against this operation's own output — a direct self-reference."
  CU:
    and:
      - {var: "Travel_Pulse"}
      - gt: [{var: "Target_Floor"}, {var: "Current_Floor"}]
  CD:
    and:
      - {var: "Travel_Pulse"}
      - lt: [{var: "Target_Floor"}, {var: "Current_Floor"}]
  R: {var: "Never"}
  LD: {var: "Never"}
  load_value: 0
  PV: {var: "Top_Floor"}
  output: "Current_Floor"
```


## Naming and documentation conventions

- Operation names: `PascalCase`, descriptive of *what* they compute, not *how* (`Doors_Open`, not `RS_Latch_3`).
- Every operation that isn't self-explanatory gets a `note` explaining *why* — especially anything unusual: a self-reference, a deliberately dropped check, or a known simplification.
- Section comments (`# --- Dispatch ---`) group operations by concept for human readability. They carry no meaning to the engine — they are pure documentation.


## A more complex operation, in full

Every example so far was small enough to read in one glance. It is worth seeing what the same syntax looks like once a real decision becomes genuinely complicated, because that is where the recursive design actually earns its keep.

`Target_Floor`, in `example/Elevator_System_2/elevator_2.yaml`, is the operation that picks which floor the car should go to next — a real LOOK-algorithm dispatch: find the nearest pending call in the car's current direction of travel, or stay put if there isn't one:

```yaml
- name: "Target_Floor"
  type: "if"
  expression:
    if:
      - {var: "Going_Up"}
      - if:
          - {and: [{var: "Call_Floor1"}, {gt: [1, {var: "Current_Floor"}]}]}
          - 1
          - if:
              - {and: [{var: "Call_Floor2"}, {gt: [2, {var: "Current_Floor"}]}]}
              - 2
              - if:
                  - {and: [{var: "Call_Floor3"}, {gt: [3, {var: "Current_Floor"}]}]}
                  - 3
                  - if:
                      - {and: [{var: "Call_Floor4"}, {gt: [4, {var: "Current_Floor"}]}]}
                      - 4
                      - if:
                          - {and: [{var: "Call_Floor5"}, {gt: [5, {var: "Current_Floor"}]}]}
                          - 5
                          - {var: "Current_Floor"}
      - if:
          - {and: [{var: "Call_Floor0"}, {lt: [0, {var: "Current_Floor"}]}]}
          - 0
          - if:
              - {and: [{var: "Call_Floor1"}, {lt: [1, {var: "Current_Floor"}]}]}
              - 1
              - if:
                  - {and: [{var: "Call_Floor2"}, {lt: [2, {var: "Current_Floor"}]}]}
                  - 2
                  - if:
                      - {and: [{var: "Call_Floor3"}, {lt: [3, {var: "Current_Floor"}]}]}
                      - 3
                      - if:
                          - {and: [{var: "Call_Floor4"}, {lt: [4, {var: "Current_Floor"}]}]}
                          - 4
                          - {var: "Current_Floor"}
  output: "Target_Floor"
```

Nothing new is happening here syntactically — it is the exact same `if` / `and` / `gt` / `var` vocabulary from the table above, just nested six levels deep instead of two.

Read it one level at a time: *if going up, check whether floor 1 has a call above the car and pick it; if not, check floor 2; if not, floor 3; and so on, falling back to the car's own current floor if nothing is pending in that direction at all.* The down direction, in the second branch, is the mirror image.

There is no loop anywhere, and no dedicated “find the nearest floor” primitive exists in the vocabulary at all. The entire search is just one `if` calling into another `if`, six times over.

That is precisely the recursive shape from the Syntax section above, `{gt: [{var: "X"}, {var: "Y"}]}`, extended far enough that the pattern stops being trivial and starts doing real work.

The same handful of dictionary-and-list rules, scaled up, is enough to express a genuine dispatch algorithm.