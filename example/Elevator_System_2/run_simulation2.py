# Elevator System 2: interactive simulation with an external physics plant.

import sys
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
EXAMPLE_DIR = THIS_DIR.parent
REPO_ROOT = EXAMPLE_DIR.parent
ENGINE_DIR = REPO_ROOT / "engine"

sys.path.insert(0, str(ENGINE_DIR))
sys.path.insert(0, str(EXAMPLE_DIR))
sys.path.insert(0, str(THIS_DIR))

from scan_cycle import load_data
from simulation_runner import setup_simulation
from elevator_viz import run_interactive
from car_physics_2 import Elevator_Plant


def find_yaml(folder):
    """Return the single YAML system description in this example folder."""
    candidates = list(folder.glob("*.yaml")) + list(folder.glob("*.yml"))

    if len(candidates) != 1:
        raise FileNotFoundError(
            f"Expected exactly one YAML file in {folder}, "
            f"found {len(candidates)}: {candidates}"
        )

    return candidates[0]


YAML_PATH = find_yaml(THIS_DIR)


def build_plant(yaml_path):
    """Build the plant from the physical constants declared in the YAML."""
    data = load_data(yaml_path)
    consts = data["physical_constants"]

    return Elevator_Plant(
        max_velocity=consts["Max_Velocity"]["value"],
        acceleration=consts["Acceleration"]["value"],
        deceleration=consts["Deceleration"]["value"],
        arrival_tolerance=consts["Arrival_Tolerance"]["value"],
        top_floor=consts["Top_Floor"]["value"],
        velocity_snap_tolerance=consts["Velocity_Snap_Tolerance"]["value"],
        scan_time=1,
    )


if __name__ == "__main__":
    operations, fb_instances, tags = setup_simulation(
        str(YAML_PATH),
        scan_time=1,
    )

    plant = build_plant(str(YAML_PATH))

    run_interactive(
        operations,
        fb_instances,
        tags,
        top_floor=tags["Top_Floor"],
        plant=plant,
        title="Elevator_System_2 -- click a floor to call the car",
    )