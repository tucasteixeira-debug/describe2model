# Elevator Example

This example is intended as a proof of concept for the architecture: not as a comprehensive model of elevator control, but as a concrete way of asking how progressively richer information about an industrial control system can be represented, executed, and incorporated without rebuilding the simulation around each new requirement.

A single elevator car serving six floors — ground through five — is deliberately used throughout. Keeping the physical system fixed makes the progression easier to see: what changes from one stage to the next is not the subject being modelled, but **what is known about it and what the simulation is therefore capable of asking**.

The three stages move through three different levels of information:

1. **Control logic** — given the intended behaviour alone, can the system be translated into an executable rule model?
2. **Physical behaviour** — once command and physical outcome are separated, can that same control model interact with an independently simulated plant?
3. **Behaviour over time** — once expected and actual behaviour exist as independent signals, can another layer reason about the difference between them and detect degradation that is not visible from a single observation?

This progression is the point of the example. Each stage introduces a genuinely new modelling requirement, but the engine itself remains the same. Capability is added through the boundaries already present in the architecture: by extending the declarative graph, by attaching a physical model to it, or by composing new analysis on top of signals the system already exposes.

The animations below are not illustrative mock-ups. Each is an unedited recording of its corresponding simulation running from the YAML, engine, and physics code contained in this repository. They are generated directly by [`make_demo_gifs.py`](make_demo_gifs.py).


## `Elevator_System_1/` — control logic

The first stage asks the narrowest question: **what can be represented from the control description alone?**

The elevator is described in plain language and translated into the engine's YAML representation. Calls, dispatch, direction, arrival, door timing, obstruction handling, and stateful behaviour are all executed by the same rule engine described elsewhere in the repository.

There is deliberately no independent physical model yet. Motion between floors is represented logically: a timer produces travel pulses and a counter updates `Current_Floor`. In other words, the control layer both decides that the car should move and owns the variable representing where the car is.

![Elevator_System_1 demo: a call to floor 3, then a call back to floor 0](assets/elevator_1_demo.gif)

That simplification is useful precisely because its limitation is visible.

At this stage, *command* and *outcome* are not independent quantities. If the logic increments `Current_Floor`, then the car has moved by definition. Questions such as whether the physical system accelerated correctly, overshot its target, or behaved differently from what the controller expected cannot yet be asked — the model contains no independent physical observation against which such a difference could exist.

The dispatch policy exposes the same boundary from another direction. In this first implementation, pending calls are handled through a simple priority chain rather than genuine direction-aware elevator dispatch. Implementing LOOK-style dispatch requires comparing pending requests against the car's current physical position, but here `Current_Floor` is itself produced by control logic that already depends on `Target_Floor`. Making the comparison directly closes a real dependency cycle.

So the limitation is not merely that Stage 1 is “less realistic.” It is more precise than that: **the information required by the richer decision does not yet exist independently of the decision itself.**

That becomes the design problem for Stage 2.


## `Elevator_System_2/` — separating control from physics

The second stage introduces a physical boundary.

The logic no longer sets the elevator's position directly. It produces commands — whether the car should move and in which direction — while a separate plant determines what those commands physically produce.

`Current_Floor` therefore changes meaning. It is no longer a counter owned by the control graph; it becomes an observed state written by the plant. Position and velocity evolve from an explicit acceleration–cruise–deceleration model, and travel time emerges from that motion rather than being imposed as a timer value.

![Elevator_System_2 demo: calls to floor 2 and floor 4 together — the car serves the nearer one first](assets/elevator_2_demo.gif)

This is a richer model for a deeper reason than visual realism.

Stage 1 effectively contains one statement:

> this is what the elevator did.

Stage 2 contains two independently produced statements:

> this is what the controller asked the elevator to do;  
> this is what the physical model actually did in response.

At this stage the plant is intentionally obedient, so those two descriptions remain consistent. But they are no longer identical *by construction*. Command and physical state now belong to different parts of the model and communicate only through explicit signals.

That separation immediately makes information available that the first model could not represent.

One consequence is the motion itself: acceleration, velocity, position, braking distance, and arrival become physical quantities rather than logical placeholders.

A second is dispatch. Because `Current_Floor` is now supplied externally by the plant rather than produced by an operation inside the dependency graph, the controller can use it when selecting the next target without creating the cycle encountered in Stage 1. The YAML can therefore implement direction-aware LOOK dispatch: continue serving requests ahead in the current direction and reverse only when none remain.

The animation above deliberately issues calls to floors 2 and 4 together. The car serves the nearer call in its direction of travel first — not because a new dispatch routine was hidden in the simulator, but because the declarative control graph now has access to the information required to make that decision.

This is an important architectural transition: **adding a physical model does not merely make an existing answer more accurate; it creates new observable quantities, and those quantities make new classes of reasoning possible.**

That same separation provides the prerequisite for the third stage.


## `Elevator_System_3/` — reasoning about behaviour over time

Once command and physical outcome are independent, a further question becomes meaningful:

**is the physical system continuing to behave as expected?**

Stage 3 adds a monitoring layer without replacing the dispatch and control structure established before it.

Two physical trajectories are now evaluated. A **nominal model** represents the expected behaviour of a healthy system. An **actual model**, implemented as a second-order mass–spring–damper system, represents the physical response being observed. A synthetic wear parameter gradually reduces damping while the elevator is in use, causing the actual response to diverge progressively from the nominal one.

The monitoring layer observes that divergence using a CUSUM — cumulative sum — detector.

![Elevator_System_3 demo: normal dispatch running alongside the live Damping Ratio / CUSUM monitoring panel](assets/elevator_3_demo.gif)

The important addition here is not simply “fault detection.” It is another level of information.

Neither the controller's commands nor the instantaneous physical state alone tells us whether degradation is accumulating. The useful quantity arises from a **relationship between two signals over time**: what a nominal system predicts, what the actual system produces, and how the residual between them evolves across repeated operation.

The chosen failure mode is intentionally gradual. As damping deteriorates, the car begins to ring more strongly around the nominal trajectory. A threshold on a single residual sample would either miss early degradation or have to be made sensitive enough to react to ordinary transient variation. The CUSUM instead accumulates small pieces of evidence across time.

This makes Stage 3 qualitatively different from simply adding another sensor or another rule. The new layer derives information that was not explicitly present in any individual signal.


### What had to be learned empirically

The final monitoring configuration is not presented as if its design parameters followed automatically from the architecture. Several aspects had to be discovered by running the model and observing where the assumptions failed.

The first implementation was **numerically unstable**. The outer simulation convention uses a one-second scan period, which is adequate for the slower control logic but too coarse for the natural timescale of the second-order plant. Integrating that plant directly at one-second resolution caused the numerical solution to diverge. The final model therefore retains the one-second control scan while integrating the continuous dynamics through smaller internal substeps.

The first sub-stepped implementation was also wrong in a subtler way. Sub-stepping only the actual plant while holding the nominal target fixed over an outer scan caused the actual system to repeatedly chase a stationary point rather than track a continuously moving reference. Both models now evolve together within the internal integration steps.

The initial CUSUM formulation also monitored the wrong statistical quantity. A signed, two-sided CUSUM was introduced first, on the assumption that wear would create a persistent positive or negative velocity residual. Inspection of the simulated trajectories showed something different: underdamping produces an oscillatory residual that repeatedly changes sign. Positive and negative excursions therefore cancelled rather than accumulating.

The monitoring signal was consequently changed to residual **magnitude**. The quantity of interest was not a sustained shift in mean but an increasing amount of deviation around the nominal trajectory.

These corrections matter to the example because they distinguish the architecture from the particular modelling choices made with it. The architecture makes the layers composable; it does not make the physical assumptions automatically correct. Those still have to be formulated, tested, and revised against observed behaviour.


### What the final tuning demonstrates

The values used here are demonstration parameters, not measurements from a real elevator and not claimed as a validated condition-monitoring design.

They were selected empirically so that the synthetic example contains a meaningful separation between healthy transient behaviour and progressively degraded behaviour.

With the final configuration, a healthy simulation run over 200 round trips keeps `CUSUM_High` below `0.0114`, while the alarm threshold is `0.25`. With the synthetic wear rate used in the example, the monitor crosses that threshold at approximately trip 46, as the damping ratio approaches its imposed lower bound.

The GIF intentionally stops before that alarm occurs. Showing 45–50 complete trips would either make the animation unnecessarily long or require temporal subsampling severe enough to obscure the individual motion that the visualisation is intended to expose. What is shown is therefore the real monitoring computation running during ordinary trips, with `Damping_Ratio` and `CUSUM_High` already evolving; the final alarm behaviour is reproducible from the same model rather than staged for the animation.


## What the three stages demonstrate

Taken together, the examples form a progression in what can be known about the same system:

**Stage 1 — specification → executable logic**

The available information is primarily behavioural: requests, conditions, timing, state transitions, and control decisions. The engine turns that description into an executable rule graph.

**Stage 2 — executable logic + physical model → observable behaviour**

Control intent and physical outcome become distinct. Position and velocity are no longer declared by the controller but produced by a separate model, giving the control layer access to physical state and making questions such as braking, trajectory, and position-dependent dispatch meaningful.

**Stage 3 — expected behaviour + observed behaviour over time → diagnostic information**

Once nominal and actual behaviour exist independently, another layer can reason about their discrepancy. Monitoring becomes an operation over information already produced by the system rather than a redesign of the system underneath it.

That progression is the architectural claim being tested here.

It is deliberately a proof of concept, not evidence that the particular elevator models are industrially complete or that the monitoring parameters would transfer to a real installation. The elevator provides a compact system in which stateful control, timing, physical dynamics, feedback, dependency constraints, and condition monitoring can all be made visible without requiring a large domain-specific codebase.

What the example is intended to demonstrate is narrower and more general: **as the information required to understand a control process becomes richer, the simulation can grow by composing new sources and interpretations of that information around the same underlying execution model.**

The complexity of the question increases. The architecture does not have to be replaced with it.


## Reproducing the demos

From `example/`:

```bash
python make_demo_gifs.py
```

This regenerates all three animations in `assets/` directly from the engine, YAML descriptions, and physical models contained in the repository.

The animations are therefore outputs of the examples they document, rather than illustrations constructed separately from them.