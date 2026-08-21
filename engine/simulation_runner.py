# simulation_runner.py
#
# Generic scan-loop harness. Lives in engine/ deliberately -- it is built
# ONLY on top of the four existing engine files (load/sort/seed/run_scan)
# and knows nothing about elevators, floors, doors, or any other example-
# specific concept. It would run identically for a system that isn't the
# elevator at all. Same category of file as topological_sort.py: written
# once, reused unchanged by every example this project ever adds -- exactly
# the "capability added around the existing graph, not rebuilt each time"
# pitch from PROJECT_STATE.md's Objective, applied to the scripts that RUN
# a system, not just the YAML that describes one.
#
# What this replaces: every manual test run so far in this project has
# hand-written the same five lines (load_data, graph_builder,
# topological_sorter, build_operation_lookout, then a for-loop calling
# run_scan and optionally plant.step) at the top of a throwaway script.
# That boilerplate is now here once, verified against the real engine, so
# every example's own run_simulation.py can just call this and get straight
# to the part that's actually specific to that example: which YAML, which
# physics plant (if any), and what scenario to run.

from scan_cycle import load_data, build_initial_tags, seed_operation_outputs, build_fb_instances, run_scan
from topological_sort import graph_builder, topological_sorter, build_operation_lookout


def build_ordered_operations(data):
    # data is whatever load_data() returned -- the parsed YAML dict.
    # Returns the operations list in real execution order (topologically
    # sorted), ready to hand straight to run_scan(). Split out as its own
    # function because a caller occasionally wants just this part (e.g. to
    # inspect the dependency graph or the sort order) without running any
    # scans at all -- exactly what the validation passes earlier in this
    # project's history did by hand.
    raw_operations = data["operations"]
    graph = graph_builder(raw_operations)
    order = topological_sorter(graph)
    operation_lookout = build_operation_lookout(raw_operations)
    return [operation_lookout[name] for name in order]


def setup_simulation(yaml_path, scan_time=1):
    """
    Loads and prepares one system for stepping, but doesn't run any scans.
    Returns (operations, fb_instances, tags) -- operations is topologically
    sorted and ready for run_scan(), tags is fully seeded.

    This is the shared setup path for BOTH of this module's ways of running
    a system: run_scan_loop() below calls this once, then drives it through
    a fixed number of scans itself, in a batch. A live, externally-driven
    loop (elevator_viz.py's run_interactive(), which steps once per real
    timer tick and lets button clicks mutate tags in between ticks) calls
    this once too, then steps it manually, one run_scan()/plant.step() pair
    at a time, forever, instead of in a pre-planned batch. Same setup,
    different driver.
    """
    data = load_data(yaml_path)
    operations = build_ordered_operations(data)

    tags = build_initial_tags(data)
    seed_operation_outputs(operations, tags)
    fb_instances = build_fb_instances(operations, scan_time=scan_time)

    return operations, fb_instances, tags


def run_scan_loop(yaml_path, num_scans, plant=None, scenario_fn=None, scan_time=1, track=None):
    """
    Loads yaml_path, sets everything up, and runs num_scans scan cycles in
    one batch. For a live, interactively-driven session instead (buttons
    clicked in real time rather than a pre-written scenario), use
    setup_simulation() directly and step it yourself -- see
    elevator_viz.run_interactive() for that driver.

    yaml_path    -- path to the system's YAML file.
    num_scans    -- how many scan cycles to run.
    plant        -- optional object with a .step(tags) method, called once
                     per scan immediately AFTER run_scan() -- the same order
                     every physics-plant example in this project uses, and
                     for the same reason: the plant reads THIS scan's fresh
                     logic outputs (e.g. Moving) and writes the tag the
                     NEXT scan's logic will read (e.g. Current_Floor).
                     Leave as None for a stage with no physical layer at
                     all (Elevator_System_1).
    scenario_fn  -- optional callable scenario_fn(tags, t) -> None, called
                     BEFORE each scan (t is 0-indexed), so a scenario can
                     flip runtime_inputs -- button presses, obstructions,
                     whatever the specific example's inputs are -- at
                     whatever scan index it wants. This function has no
                     idea what a valid input even looks like for a given
                     system; that knowledge belongs entirely to the caller.
    scan_time    -- passed straight through to build_fb_instances(). "1
                     scan = 1 second" unless a caller wants otherwise.
    track        -- iterable of tag names to record into history. Defaults
                     to every tag that exists right after setup (the full
                     runtime_inputs + hmi_configuration + outputs +
                     physical_constants catalog) -- almost always what a
                     plotting script wants, but overridable if a system
                     ever gets large enough that copying everything every
                     scan is wasteful.

    Returns (tags, history):
      tags    -- the live tag dict, in its final post-loop state.
      history -- {"t": [0, 1, ...], "SomeTag": [v_at_0, v_at_1, ...], ...},
                 one list per tracked tag (columnar, not a list of
                 per-scan snapshots) -- the shape a plotting script wants
                 directly, one series per line/panel, no reshaping needed.
    """
    operations, fb_instances, tags = setup_simulation(yaml_path, scan_time=scan_time)

    tracked_keys = list(track) if track is not None else list(tags.keys())
    history = {"t": []}
    for key in tracked_keys:
        history[key] = []

    for t in range(num_scans):
        if scenario_fn is not None:
            scenario_fn(tags, t)

        run_scan(operations, fb_instances, tags)

        if plant is not None:
            plant.step(tags)

        history["t"].append(t)
        for key in tracked_keys:
            history[key].append(tags.get(key))

    return tags, history