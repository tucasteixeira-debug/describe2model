# describe2model

Turn an understanding of an industrial control system into an executable model — through a small declarative language and a modular simulation architecture.

## Why I built this

When developing a system, the bottleneck is often not coming up with the next idea. It is getting the information needed to refine it.

Iteration is essentially a loop:

**idea / hypothesis → information → refined idea / hypothesis → information → ...**

That information is more than validation. It means understanding how the system actually behaves: how its parts interact, how outcomes can be traced through those interactions, what each building block contributes, the subtleties in its behaviour, the physical processes beneath the logic, its robustness and edge cases, and the consequences of changing something.

For effective iteration, the rate at which you can generate ideas should be matched by the rate at which you can generate information about them. That is what makes simulation so powerful.

During an internship working with real industrial control systems, I encountered this problem directly. Understanding a system — conceptually, logically, and physically — was rarely the hardest part. The bottleneck was getting from that understanding to something executable that I could quickly interrogate, test, and learn from.

A great deal stood in between: dense technical documentation, PLC programming languages, functional descriptions, vendor-specific tooling, and simulation workflows constrained by rigid logic and predefined structure.

Even when the system was conceptually understood, turning that understanding into useful information could still be slow.

`describe2model` is an attempt to close that gap.

The method is specifically motivated by industrial control systems, but the underlying idea is broader: **make the path from understanding a system to executing a representation of it short enough that the model can evolve with the understanding itself.**

## How it works

A system is first described in plain language, then translated through a small set of documented rules into a declarative graph — a YAML file containing named operations and the data they depend on.

The engine takes it from there. It derives the dependency graph, resolves the operations into a valid execution order, and evaluates them scan by scan, following the same repeated read–decide–act structure that underlies PLC execution.

The goal is not simply to *translate English into PLC logic*. The more important choice is to represent the system as a declarative graph rather than as hard-coded procedural logic.

That representation gives the model room to evolve.

A placeholder can become a physical model. New behaviour can be introduced without restructuring unrelated logic. New information can be derived from signals the system already exposes. The representation does not need to be discarded each time the question being asked of the system becomes richer.

That modularity is not merely an architectural convenience — it is the point. A better model produces better information, and better information is what allows the next idea to be tested rather than only reasoned about.

The examples in this repository make that progression concrete: control logic becomes coupled to physical behaviour, and that physical behaviour later becomes the basis for a monitoring layer. Each stage asks more of the model while preserving the same underlying execution architecture.

## Where to go from here

- **[`docs/`](docs/)** — the technical foundation: the YAML representation, its expression syntax, and the mechanisms by which the engine interprets and executes a system scan by scan.
- **[`example/`](example/)** — the architecture as a proof of concept. A single elevator is taken through three progressively richer modelling requirements, making the effect of each new source of information visible in a working simulation.

If you want to run the examples yourself: Python 3.9+, `pip install pyyaml matplotlib`, then `cd` into any elevator stage and run its corresponding `run_simulationN.py`.

## Status

Early stage. The core engine — declarative expression evaluation, dependency-graph construction, topological ordering, stateful function blocks, and scan-cycle execution — is working.

The repository currently includes the translation guide, engine documentation, and a three-stage worked example demonstrating the architecture from control logic through physical simulation and condition monitoring.

## License

MIT — see [`LICENSE`](LICENSE).