# docs

This section is about presenting the concept and framework behind `describe2model`, then diving into the technical mechanism underneath it — describing industrial control systems, their actual decision-making and control logic, in a modular way. The concept matters more here than this specific design does; what follows is my particular approach to it, very much a first pass, with plenty of room left to update and refine. The two documents below walk through it one layer at a time — first how a system gets *described*, then how that description actually *runs*.

| Document | What it covers |
|---|---|
| [`yaml_guide.md`](yaml_guide.md) | How to translate a system's decision-making and control logic — the same kind of thing that would run on a PLC or a microcontroller — into the YAML format itself: the file's structure, the expression syntax, and the small set of function blocks everything is built from. |
| [`engine_internals.md`](engine_internals.md) | How the engine actually takes that YAML and runs it: the shared state every operation reads and writes, the recursive mechanism that evaluates an expression, and the seam where a physics plant hooks in. |

Start with the YAML guide — it's the vocabulary everything else assumes.