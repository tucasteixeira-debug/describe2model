# car_physics_2.py
#
# Elevator_System_2's physics plant. NOT PLC logic -- a kinematic model
# invented for this project so the engine has real motion to simulate,
# never something you'd find in an operations list. Kept in its own file,
# outside engine/ entirely (engine/ stays generic, per PROJECT_STATE.md's
# own stated architecture) -- this is elevator-specific, so it lives
# alongside elevator_2.yaml.
#
# Runs OUTSIDE the operations sequence -- called once per scan, AFTER
# run_scan() (so it can read this scan's real Moving/Target_Floor), writing
# the NEXT scan's Current_Floor/Velocity_FloorsPerSec into tags before
# run_scan() is called again. Same seam as any runtime_input a real sensor
# would feed -- see elevator_2.yaml's note 1 for why Current_Floor is declared
# under runtime_inputs, not outputs.
#
# SCOPE: this is a KINEMATIC model (velocity and acceleration specified
# directly, in floors and floors/second) not a DYNAMIC one (no mass, no
# motor torque, no force balance). That's a deliberate simplification, not
# an oversight -- Elevator_System_2's actual requirement (see description_2.md)
# is that the logic stops owning position and has to command/read a
# physical layer instead. Getting a genuine trapezoidal velocity profile in
# is enough to satisfy that; deriving it from force and mass would add
# complexity the stated problem doesn't ask for. Worth being honest about
# rather than dressing this up as more physically complete than it is.
#
# Motion profile: a standard trapezoidal speed profile --
#   - accelerate toward Max_Velocity while there's more distance to travel
#     than the current braking distance would need,
#   - hold Max_Velocity (the "cruise" phase happens automatically once
#     velocity saturates -- no separate cruise-state bookkeeping needed),
#   - decelerate into Target_Floor once remaining distance drops to (or
#     below) the braking distance v^2 / (2 * Deceleration) at the current
#     speed.
# Acceleration and Deceleration are independent, tunable rates (see
# elevator_2.yaml's physical_constants -- they default equal, but nothing in
# this class assumes they are).

class Elevator_Plant:
    def __init__(self, max_velocity, acceleration, deceleration,
                 arrival_tolerance, top_floor, velocity_snap_tolerance,
                 position=0.0, velocity=0.0, scan_time=1):
        # max_velocity/acceleration/deceleration/arrival_tolerance/top_floor/
        # velocity_snap_tolerance have NO defaults, deliberately. Every one
        # of them is a physical property of the car and belongs in exactly
        # one place -- elevator_2.yaml's physical_constants -- with its
        # justification traced back to description_2.md's stated requirement
        # (cruise speed and accel/decel both set by "~2 seconds," arrival/
        # velocity tolerances flagged there as having no requirement behind
        # them at all). A default here would be a second, silent source of
        # truth that could drift from the YAML without either file ever
        # showing a diff -- exactly what this project's own architecture.md
        # already warns about for hmi_configuration constants. Any caller
        # constructs this by reading those tags and passing them through;
        # if one is missing, this should fail loudly (a TypeError), not
        # quietly substitute a number nobody asked for.
        #
        # position/velocity/scan_time DO keep defaults -- they aren't
        # physical properties of the car, they're simulation-run parameters
        # (starting state, and the scan-time convention TON/PID already
        # use), the same category as run_scan()'s own scan_time argument.
        self.position = position                # floors
        self.velocity = velocity                # floors/second, signed (+up, -down)
        self.max_velocity = max_velocity         # floors/second
        self.acceleration = acceleration         # floors/second^2, speeding up
        self.deceleration = deceleration         # floors/second^2, slowing down
        self.arrival_tolerance = arrival_tolerance
        self.top_floor = top_floor
        self.scan_time = scan_time
        # How close to a full stop counts as "stopped," for arrival snapping.
        # Separate from arrival_tolerance (a position tolerance) because the
        # two are different physical quantities -- conflating them would mean
        # a fast-moving car passing near the target briefly satisfies a
        # position-only check and gets treated as arrived while still moving.
        self.velocity_snap_tolerance = velocity_snap_tolerance

    def _target_velocity(self, target_floor, moving_permitted):
        # What speed (signed) the car should currently be trying to hold,
        # before any acceleration-rate limiting is applied. This is the one
        # place direction and the decelerate-early decision both get made.
        if not moving_permitted:
            # The logic has withdrawn run permission (see elevator_2.yaml note
            # 2 -- this is Moving going false). Modeled as commanding a
            # controlled stop, not an instant freeze -- a real drive doesn't
            # teleport to zero speed just because an interlock dropped.
            return 0.0

        distance_remaining = target_floor - self.position
        if distance_remaining == 0:
            return 0.0

        direction = 1.0 if distance_remaining > 0 else -1.0
        current_speed = abs(self.velocity)
        braking_distance = (current_speed ** 2) / (2 * self.deceleration) if self.deceleration > 0 else 0.0

        if abs(distance_remaining) <= braking_distance:
            # Close enough that holding cruise speed any longer would
            # overshoot -- start braking now, regardless of Max_Velocity.
            return 0.0
        return self.max_velocity * direction

    def step(self, tags):
        target_floor = tags["Target_Floor"]
        moving_permitted = tags["Moving"]

        target_velocity = self._target_velocity(target_floor, moving_permitted)

        # Whichever direction of change is actually happening -- speeding up
        # (in magnitude) uses Acceleration, slowing down uses Deceleration.
        # Comparing |target| to |current| rather than just their signs is
        # what makes this handle a fresh start (0 -> cruise, accelerating)
        # and a braking approach (cruise -> 0, decelerating) correctly with
        # the same two lines, without a separate case for each.
        if abs(target_velocity) > abs(self.velocity):
            rate = self.acceleration
        else:
            rate = self.deceleration

        if self.velocity < target_velocity:
            self.velocity = min(self.velocity + rate * self.scan_time, target_velocity)
        elif self.velocity > target_velocity:
            self.velocity = max(self.velocity - rate * self.scan_time, target_velocity)

        self.position = self.position + self.velocity * self.scan_time

        # Defensive shaft bounds. Target_Floor's own dispatch logic (the
        # nested `if` chain in elevator_2.yaml) never asks for a value outside
        # [0, Top_Floor], so this shouldn't trigger in normal operation --
        # it's a bound on the physical shaft, not a substitute for the
        # dispatch logic staying in range. Same "correcting a numerical
        # artifact, not inventing physics" reasoning as the arrival snap
        # below: floating-point integration overshoot near a limit is not a
        # real event.
        if self.position < 0.0:
            self.position = 0.0
            self.velocity = max(self.velocity, 0.0)
        if self.position > self.top_floor:
            self.position = self.top_floor
            self.velocity = min(self.velocity, 0.0)

        # Arrival snap: once close enough in BOTH position and speed, land
        # exactly on the target floor and come to an exact stop. Without
        # this, continuous integration would leave a permanent, ever-
        # shrinking residual error instead of the clean equality
        # Just_Arrived_Condition's `eq` check needs to match against.
        if (moving_permitted
                and abs(target_floor - self.position) <= self.arrival_tolerance
                and abs(self.velocity) <= self.velocity_snap_tolerance):
            self.position = target_floor
            self.velocity = 0.0

        tags["Current_Floor"] = self.position                  # next scan reads this
        tags["Velocity_FloorsPerSec"] = self.velocity
        return self.position