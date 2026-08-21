# run_simulation.py -- Elevator_System_3
#
# Same setup-only role as Elevator_System_1/2's scripts. One real
# difference this stage's own story benefits from: auto_cycle_floors is
# passed so an "Auto-Cycle" toggle button is available (see
# elevator_viz.run_interactive()'s docstring) -- but it starts OFF, same
# as every other stage. The person calls floors by clicking, same as
# Elevator_System_1/2; auto-cycle is there to reach for if they want to
# skip ahead through the many round trips this stage's wear story needs,
# not something that runs on its own by default. Speed is capped at 5x
# for the same reason -- this is a live simulation someone is watching and
# interacting with, not a batch job to blast through.

import sys
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent          # example/Elevator_System_3
EXAMPLE_DIR = THIS_DIR.parent                        # example/
REPO_ROOT = EXAMPLE_DIR.parent                        # repo root
ENGINE_DIR = REPO_ROOT / "engine"

sys.path.insert(0, str(ENGINE_DIR))
sys.path.insert(0, str(EXAMPLE_DIR))
sys.path.insert(0, str(THIS_DIR))                     # car_physics_3.py lives here

from scan_cycle import load_data
from simulation_runner import setup_simulation
from elevator_viz import run_interactive
from car_physics_3 import NominalPlant, ActualPlant, DualPlant


def find_yaml(folder):
    candidates = list(folder.glob("*.yaml")) + list(folder.glob("*.yml"))
    if len(candidates) != 1:
        raise FileNotFoundError(
            f"Expected exactly one YAML file in {folder}, found {len(candidates)}: {candidates}")
    return candidates[0]


YAML_PATH = find_yaml(THIS_DIR)


def build_plant(yaml_path):
    # Every physical constant is read straight out of the YAML -- no
    # defaults supplied here, same reasoning as Elevator_System_2's
    # build_plant(). NominalPlant and ActualPlant are constructed
    # separately and handed to DualPlant, which owns the actual per-scan
    # choreography (sub-stepping both together -- see car_physics_3.py).
    data = load_data(yaml_path)
    consts = data["physical_constants"]

    def C(name):
        return consts[name]["value"]

    nominal = NominalPlant(
        max_velocity=C("Max_Velocity"),
        acceleration=C("Acceleration"),
        deceleration=C("Deceleration"),
        arrival_tolerance=C("Arrival_Tolerance"),
        top_floor=C("Top_Floor"),
        velocity_snap_tolerance=C("Velocity_Snap_Tolerance"),
    )
    actual = ActualPlant(
        natural_frequency=C("Natural_Frequency"),
        initial_damping_ratio=C("Initial_Damping_Ratio"),
        damping_floor=C("Damping_Floor"),
        wear_rate=C("Wear_Rate"),
        arrival_tolerance=C("Arrival_Tolerance"),
        top_floor=C("Top_Floor"),
        velocity_snap_tolerance=C("Velocity_Snap_Tolerance"),
    )
    return DualPlant(nominal, actual, scan_time=1, substeps=100)


if __name__ == "__main__":
    operations, fb_instances, tags = setup_simulation(str(YAML_PATH), scan_time=1)
    plant = build_plant(str(YAML_PATH))
    top_floor = int(tags["Top_Floor"])

    run_interactive(
        operations, fb_instances, tags,
        top_floor=top_floor,
        plant=plant,
        title="Elevator_System_3 -- watch Damping_Ratio and CUSUM_High over many trips",
        auto_cycle_floors=[0, top_floor],
        initial_speed=1,
    )