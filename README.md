# describe2plc

Describe a control system in plain language and get a working, simulatable rule engine — no PLC programming language required.

## Why I built this

Iterating on a system starts as a hypothesis, not a certainty. What actually moves it forward is information, not more ideas — you usually already have the idea; what's expensive is finding out, cheaply and quickly, whether it holds up against reality. That's exactly why simulation and instrumentation matter so much in industrial process work: they're the fastest route to that information without touching the real thing.

During an internship working with real industrial control logic, I ran into that gap directly. Understanding the system — conceptually, logically, physically — was rarely the hard part; I usually had a clear picture of what was going on and ideas for how to improve it. The bottleneck was everything *between* that understanding and information I could actually test against: dense technical documentation, a simulation workflow bound by strict PLC-specific rules and vendor tooling, and an outcome that was rigid by construction, mostly pure logic with little room to represent anything else. Even with the right idea already in hand, there was still a wide gap between understanding a system and being able to cheaply find out whether that idea actually worked.

`describe2plc` is the tool I built to close that gap — to let domain knowledge translate directly into testable information, without first requiring fluency in a dense, PLC-specific toolchain.

## How it works

You describe a system in plain language, then use a small set of documented translation rules to turn that description into a declarative graph — a YAML file containing named operations and the data they depend on.

The engine takes it from there. It topologically sorts the operations into the correct execution order and evaluates them scan-by-scan, mirroring the way a real PLC continuously re-evaluates its logic.

The goal isn't simply to *“translate English into PLC logic.”* By representing a system as a declarative graph rather than hard-coded procedural logic, `describe2plc` makes the simulation itself flexible.

You can swap a physics model in where a sensor used to be, add a new rule without restructuring the rest of the system, or iterate on the design without assuming that the underlying structure has to be fixed from the beginning.

That modularity isn't just an architectural nicety — it's the actual point. A better simulation is more information, and more information is what turns the next idea into something you can test, not just something you can reason about. A placeholder becoming a real physics plant, a physics plant later feeding a monitoring layer, a monitoring layer eventually informed by something like ML — each of those is capability added on top of the same graph, not a rebuild, so the ceiling on how much information you can get out of the system keeps moving as you iterate.

## Status

Early stage. The core engine — dependency-graph parsing, topological sorting, and scan-cycle evaluation — is working.

A worked toy example, the full translation-rules guide, and setup instructions are currently in progress.

## License

MIT — see [LICENSE](LICENSE).