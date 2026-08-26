# Elevator System 3: interactive degradation and condition-monitoring simulation.

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
from car_physics_3 import NominalPlant, ActualPlant, DualPlant


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
    """Build nominal and actual plants from the YAML physical constants."""
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

    return DualPlant(
        nominal,
        actual,
        scan_time=1,
        substeps=100,
    )


if __name__ == "__main__":
    operations, fb_instances, tags = setup_simulation(
        str(YAML_PATH),
        scan_time=1,
    )

    plant = build_plant(str(YAML_PATH))
    top_floor = int(tags["Top_Floor"])

    run_interactive(
        operations,
        fb_instances,
        tags,
        top_floor=top_floor,
        plant=plant,
        title="Elevator_System_3 -- watch Damping_Ratio and CUSUM_High over many trips",
        auto_cycle_floors=[0, top_floor],
        initial_speed=1,
    )