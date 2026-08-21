# run_simulation.py -- Elevator_System_1
#
# No scenario_fn anymore -- run_interactive() drives the simulation live,
# in response to floor/close-door buttons actually being clicked, so
# there's no scripted sequence of events left for this file to write. Its
# job is purely setup now: find the YAML, prepare it for stepping, hand it
# to elevator_viz.run_interactive().
#
# Stage 1 has no physics plant -- Current_Floor here comes from the CTUD
# counter inside the YAML itself, not an external object. run_interactive()
# accepts plant=None for exactly this case; nothing else changes.

import sys
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent          # example/Elevator_System_1
EXAMPLE_DIR = THIS_DIR.parent                        # example/
REPO_ROOT = EXAMPLE_DIR.parent                        # repo root
ENGINE_DIR = REPO_ROOT / "engine"

sys.path.insert(0, str(ENGINE_DIR))
sys.path.insert(0, str(EXAMPLE_DIR))

from simulation_runner import setup_simulation
from elevator_viz import run_interactive


def find_yaml(folder):
    # Doesn't assume a specific filename -- just whatever single YAML file
    # lives in this stage's own folder.
    candidates = list(folder.glob("*.yaml")) + list(folder.glob("*.yml"))
    if len(candidates) != 1:
        raise FileNotFoundError(
            f"Expected exactly one YAML file in {folder}, found {len(candidates)}: {candidates}")
    return candidates[0]


YAML_PATH = find_yaml(THIS_DIR)


if __name__ == "__main__":
    operations, fb_instances, tags = setup_simulation(str(YAML_PATH), scan_time=1)

    run_interactive(
        operations, fb_instances, tags,
        top_floor=tags["Top_Floor"],
        plant=None,  # Stage 1: no physics layer, Current_Floor is a CTUD op
        title="Elevator_System_1 -- click a floor to call the car",
    )