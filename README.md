# describe2plc

Describe a control system in plain language and get a working, simulatable rule engine — no PLC programming language required.

## Why I built this

During an internship working with real industrial control logic, I found that understanding a system conceptually was rarely the hard part. The challenge was everything between that understanding and a working simulation: dense technical documentation, customer- and vendor-specific tools, and a PLC programming language I had no prior experience with.

Getting from *“I understand this system”* to *“I can run and test this system”* meant first becoming fluent in all of that before writing a single useful line of logic.

And even after clearing that hurdle, most logic simulators assume the resulting system is rigid: fixed structure, fixed behaviour, logic and nothing else. That becomes a limitation as soon as you want to go beyond pure logic — for example, replacing a sensor with a physics model, adding a new rule, or eventually integrating something like ML.

`describe2plc` is the tool I built to remove both barriers.

## How it works

You describe a system in plain language, then use a small set of documented translation rules to turn that description into a declarative graph — a YAML file containing named operations and the data they depend on.

The engine takes it from there. It topologically sorts the operations into the correct execution order and evaluates them scan-by-scan, mirroring the way a real PLC continuously re-evaluates its logic.

The goal isn't simply to *“translate English into PLC logic.”* By representing a system as a declarative graph rather than hard-coded procedural logic, `describe2plc` makes the simulation itself flexible.

You can swap a physics model in where a sensor used to be, add a new rule without restructuring the rest of the system, or iterate on the design without assuming that the underlying structure has to be fixed from the beginning.

## Status

Early stage. The core engine — dependency-graph parsing, topological sorting, and scan-cycle evaluation — is working.

A worked toy example, the full translation-rules guide, and setup instructions are currently in progress.

## License

MIT — see [LICENSE](LICENSE).