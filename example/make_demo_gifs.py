# make_demo_gifs.py
#
# Regenerates the three GIFs in assets/ from the real engine and the real
# YAML files -- nothing here is hand-drawn or mocked. Each function below
# runs an actual scripted scenario through run_scan_loop() (the same
# generic harness engine/simulation_runner.py provides for any example,
# not something built one-off for this), then hands the resulting history
# straight to elevator_viz.animate_elevator(), the same rendering path
# show_live()/run_interactive() use for an actual interactive session.
#
# Every scenario below uses the same "hold the call until served" pattern
# elevator_viz.run_interactive() uses for real button clicks -- dispatch in
# every elevator_N.yaml reads the raw Call_FloorN button directly, not a
# remembered latch (see Elevator_System_1's own note 1), so a momentary
# one-scan press would frequently get missed here exactly the same way it
# would from a real, briefly-tapped button.
#
# Run from anywhere: `python make_demo_gifs.py`. Requires matplotlib with
# the pillow writer available (anim.save(..., writer="pillow")).

import sys
from pathlib import Path
import matplotlib
matplotlib.use("Agg")

THIS_DIR = Path(__file__).resolve().parent            # example/
REPO_ROOT = THIS_DIR.parent
ENGINE_DIR = REPO_ROOT / "engine"
ASSETS_DIR = THIS_DIR / "assets"
ASSETS_DIR.mkdir(exist_ok=True)

sys.path.insert(0, str(ENGINE_DIR))
sys.path.insert(0, str(THIS_DIR))

from scan_cycle import load_data
from simulation_runner import run_scan_loop
from elevator_viz import animate_elevator


def _hold_until_served_scenario(call_schedule):
    """
    call_schedule: {scan_index: [floor, floor, ...]} -- floors newly
    called at that scan. Each stays held (Call_FloorN True) every scan
    after that until its Floor{N}_Request has actually gone false again
    (served), not just because the button read false for an instant.
    """
    pending = set()

    def scenario_fn(tags, t):
        if t in call_schedule:
            for floor in call_schedule[t]:
                pending.add(floor)
        for floor in list(pending):
            if t in call_schedule and floor in call_schedule[t]:
                continue  # just added this scan -- not yet run through run_scan
            if not tags.get(f"Floor{floor}_Request", False):
                pending.discard(floor)
        for n in range(6):
            tags[f"Call_Floor{n}"] = n in pending

    return scenario_fn


def _autocycle_scenario(top_floor):
    """
    Bounces the car between floor 0 and top_floor, issuing the next call
    the moment the previous one is fully served and nothing is pending --
    same held-call discipline as _hold_until_served_scenario, just with
    the next target picked automatically instead of from a fixed schedule.
    """
    state = {"target": top_floor, "pending": set()}

    def scenario_fn(tags, t):
        for floor in list(state["pending"]):
            if not tags.get(f"Floor{floor}_Request", False):
                state["pending"].discard(floor)
        if not state["pending"] and not tags.get("Any_Pending", False):
            floor = state["target"]
            state["pending"].add(floor)
            state["target"] = 0 if state["target"] == top_floor else top_floor
        for n in range(top_floor + 1):
            tags[f"Call_Floor{n}"] = n in state["pending"]

    return scenario_fn


def gen_stage1():
    # One call to floor 3, then (once served) one back to floor 0, for a
    # genuine round trip. Stage 1 will NOT return on its own without that
    # second call -- Travel_Pulse only ticks while some call is held, so
    # an unheld car simply sits still, doors closed, regardless of
    # Target_Floor's ground-floor default.
    yaml_path = THIS_DIR / "Elevator_System_1" / "elevator_1.yaml"
    scenario_fn = _hold_until_served_scenario({0: [3], 26: [0]})

    tags, history = run_scan_loop(str(yaml_path), 52, plant=None, scenario_fn=scenario_fn, scan_time=1)
    fig, anim = animate_elevator(history, tags["Top_Floor"],
                                  title="Elevator_System_1 -- pure logic, placeholder motion")
    out = ASSETS_DIR / "elevator_1_demo.gif"
    anim.save(str(out), writer="pillow", fps=8, dpi=90)
    print("saved", out)


def gen_stage2():
    # Floors 2 and 4 called together, both above the car -- a real
    # decision for LOOK dispatch to make: nearest active call in the
    # direction of travel (2), not the furthest (4), the genuine
    # capability Stage 1 was structurally unable to have.
    this_dir = THIS_DIR / "Elevator_System_2"
    sys.path.insert(0, str(this_dir))
    from car_physics_2 import Elevator_Plant

    yaml_path = this_dir / "elevator_2.yaml"

    data = load_data(str(yaml_path))
    consts = data["physical_constants"]
    plant = Elevator_Plant(
        max_velocity=consts["Max_Velocity"]["value"],
        acceleration=consts["Acceleration"]["value"],
        deceleration=consts["Deceleration"]["value"],
        arrival_tolerance=consts["Arrival_Tolerance"]["value"],
        top_floor=consts["Top_Floor"]["value"],
        velocity_snap_tolerance=consts["Velocity_Snap_Tolerance"]["value"],
        scan_time=1,
    )
    scenario_fn = _hold_until_served_scenario({0: [2, 4]})

    tags, history = run_scan_loop(str(yaml_path), 40, plant=plant, scenario_fn=scenario_fn, scan_time=1)
    fig, anim = animate_elevator(history, tags["Top_Floor"],
                                  title="Elevator_System_2 -- real physics, LOOK dispatch (calls: floor 2 then floor 4)")
    out = ASSETS_DIR / "elevator_2_demo.gif"
    anim.save(str(out), writer="pillow", fps=8, dpi=90)
    print("saved", out)


def gen_stage3():
    # Honest scope: elevator_3.yaml's own Wear_Rate note says the alarm
    # doesn't fire until roughly 45-50 one-way trips -- far more than a
    # short clip can show without either running very long or subsampling
    # frames enough to blur the per-trip physics this is actually trying
    # to showcase. This clip auto-cycles a handful of REAL round trips and
    # shows the monitoring layer genuinely running -- Damping_Ratio and
    # CUSUM_High tracking real values, already visibly trending, well
    # before alarm -- not a forced or accelerated failure.
    this_dir = THIS_DIR / "Elevator_System_3"
    sys.path.insert(0, str(this_dir))
    from car_physics_3 import NominalPlant, ActualPlant, DualPlant

    yaml_path = this_dir / "elevator_3.yaml"

    data = load_data(str(yaml_path))
    consts = data["physical_constants"]

    def C(name):
        return consts[name]["value"]

    nominal = NominalPlant(
        max_velocity=C("Max_Velocity"), acceleration=C("Acceleration"), deceleration=C("Deceleration"),
        arrival_tolerance=C("Arrival_Tolerance"), top_floor=C("Top_Floor"),
        velocity_snap_tolerance=C("Velocity_Snap_Tolerance"))
    actual = ActualPlant(
        natural_frequency=C("Natural_Frequency"), initial_damping_ratio=C("Initial_Damping_Ratio"),
        damping_floor=C("Damping_Floor"), wear_rate=C("Wear_Rate"), arrival_tolerance=C("Arrival_Tolerance"),
        top_floor=C("Top_Floor"), velocity_snap_tolerance=C("Velocity_Snap_Tolerance"))
    plant = DualPlant(nominal, actual, scan_time=1, substeps=100)

    top_floor = int(C("Top_Floor"))
    scenario_fn = _autocycle_scenario(top_floor)

    tags, history = run_scan_loop(str(yaml_path), 130, plant=plant, scenario_fn=scenario_fn, scan_time=1)
    fig, anim = animate_elevator(history, top_floor,
                                  title="Elevator_System_3 -- LOOK dispatch + CUSUM monitoring layer")
    out = ASSETS_DIR / "elevator_3_demo.gif"
    anim.save(str(out), writer="pillow", fps=8, dpi=72)
    print("saved", out)


if __name__ == "__main__":
    gen_stage1()
    gen_stage2()
    gen_stage3()
