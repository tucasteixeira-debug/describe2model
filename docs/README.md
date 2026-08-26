# Documentation

This section develops the framework behind `describe2model`: how an industrial control system can be reduced to a clear, executable representation of its decision-making and control logic, and how that representation can remain modular as the questions asked of the system become richer.

The architecture presented here is one implementation of that idea, not a claim that this is the only or final way to represent such systems. The important part is the separation of concerns: **a small declarative language for describing the system, and a general engine for interpreting and executing that description.**

The two documents below follow those layers directly.

| Document | What it covers |
|---|---|
| [`yaml_guide.md`](yaml_guide.md) | How control behaviour is represented: the YAML file structure, recursive expression syntax, available operations, and the small function-block vocabulary from which larger decisions are composed. |
| [`engine_internals.md`](engine_internals.md) | How that representation becomes executable: recursive evaluation, shared state, dependency-derived execution order, stateful function blocks, and the interface through which external models can participate in the simulation. |

Start with the **[YAML Guide](yaml_guide.md)** to understand the representation itself, then move to **[Engine Internals](engine_internals.md)** to see how that representation is executed.