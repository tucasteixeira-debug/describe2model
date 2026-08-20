# Elevator example

The objective of this page is to show the functionality and practicality of this architecture, end to end, on one running example.

We start simple — a single elevator car serving 3 floors — and take it through increasing complexity of design requirements, each stage a genuine upgrade to the system rather than a rebuild, to show how modular this designing system can be:

- **`Elevator_System_1/`** — the system described in plain language, translated into the engine's YAML format, and run as pure logic. No physical modeling yet: motion between floors is a placeholder.
- **`Elevator_System_2/`** — the placeholder motion is replaced with a real physical plant: actual position and velocity, so trip time is a genuine output of physics, not an assumed number.
- **`Elevator_System_3/`** — a monitoring layer (CUSUM, a cumulative-sum control chart) is added on top, comparing the logic's nominal expectation against the physics plant's actual behavior over time, to catch slow drift a simple threshold would miss.

Each stage builds on the last without modifying it — that's the actual point being demonstrated: the same core graph stays intact as capability gets added around it.
