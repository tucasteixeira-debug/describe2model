# describe2model

Describe an industrial control system in plain language and turn it into a working, simulatable model — without first having to formalize it in a rigid technical environment.

## Why I built this

When developing a system, the bottleneck is often not coming up with the next idea. It is getting the information needed to refine it.

Iteration is essentially a loop:

**idea / hypothesis → information → refined idea / hypothesis → information → ...**

That information is more than just validation. It means understanding how the system actually behaves: how its different parts interact, how outcomes can be traced through those interactions, what each building block contributes, the subtleties in their behaviour, the physical processes underneath the logic, its robustness and edge cases, and the consequences of changing something.

For effective iteration, the rate at which you can generate ideas should be matched by the rate at which you can generate information about them. That is what makes simulation so powerful.

During an internship working with real industrial control systems, I ran into this problem directly. Understanding the system — conceptually, logically, and physically — was rarely the hard part. The bottleneck was getting from that understanding to something I could quickly interrogate and learn from.

There was a lot in the way: dense technical documentation, PLC programming languages, functional descriptions, vendor-specific tooling, and simulation workflows constrained by rigid logic and predefined structure.

Even when the system was conceptually understood, getting useful information out of it could still be slow.

`describe2model` is an attempt to close that gap.

The method is specifically motivated by industrial control systems, but the underlying idea is broader: **make models flexible enough that they can keep up with the process of understanding and developing the system itself.**

## How it works

You describe a system in plain language, then use a small set of documented translation rules to turn that description into a declarative graph — a YAML file containing named operations and the data they depend on.

The engine takes it from there. It topologically sorts the operations into the correct execution order and evaluates them scan-by-scan, mirroring the way a real PLC continuously re-evaluates its logic.

The goal isn't simply to *“translate English into PLC logic.”* By representing a system as a declarative graph rather than hard-coded procedural logic, `describe2model` makes the simulation itself flexible.

You can swap a physics model in where a sensor used to be, add a new rule without restructuring the rest of the system, or iterate on the design without assuming that the underlying structure has to be fixed from the beginning.

That modularity isn't just an architectural nicety — it's the actual point. A better simulation is more information, and more information is what turns the next idea into something you can test, not just something you can reason about.

A placeholder becoming a real physics plant, a physics plant later feeding a monitoring layer, a monitoring layer eventually informed by something like ML — each of those is capability added on top of the same graph, not a rebuild.

## Status

Early stage. The core engine — dependency-graph parsing, topological sorting, and scan-cycle evaluation — is working.

A worked toy example, the full translation-rules guide, and setup instructions are currently in progress.

## License

MIT — see [LICENSE](LICENSE).