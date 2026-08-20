# describe2plc

Describe a control system in plain language, and get a working, simulate-able rule engine out — no PLC programming language required.

## Why I built this

I don't know PLC programming languages. During an internship working with real industrial control logic, that was a real barrier — the systems themselves (staged equipment, timers, thresholds, interlocks) were conceptually simple to describe in plain English, but getting from that description into something I could actually run and test meant learning an unfamiliar, rigid syntax first.

`describe2plc` is the tool I built to remove that barrier.

## How it works

You describe a system in words, then follow a small set of documented translation rules to turn that description into a declarative graph — a YAML file listing named operations and the data they depend on. The engine takes it from there: it topologically sorts the operations into the correct execution order, then runs them scan-by-scan, the same way a real PLC continuously re-evaluates its logic.

The point isn't just "translate English into PLC logic." It's that once a system exists as a plain declarative graph instead of hard-coded procedural logic, it stops being rigid. You can swap in a physics model where a sensor used to be, layer in a new rule without touching the rest, or iterate on the design as many times as you want — without the assumption a typical logic simulator makes, that the structure is fixed from the start.

## Status

Early stage. The core engine (dependency-graph parsing, topological sort, scan-cycle evaluation) works. A worked toy example, the full translation-rules guide, and setup instructions are in progress.

## License

MIT — see [LICENSE](LICENSE).