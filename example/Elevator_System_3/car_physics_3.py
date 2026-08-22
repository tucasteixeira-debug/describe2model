# car_physics_3.py
#
# Elevator_System_3's physics: TWO plants running in parallel every scan,
# not one.
#
#   - NominalPlant: the exact same trapezoidal accel/cruise/decel model as
#     Elevator_System_2's car_physics_2.py -- what a HEALTHY car should be
#     doing, computed fresh from Moving/Target_Floor each scan, completely
#     decoupled from whatever the real car is actually doing. It never
#     reads the actual plant's state at all. This independence matters: if
#     nominal tracked actual even slightly, the residual between them would
#     just be measurement noise, not real accumulated drift.
#
#   - ActualPlant: NOT a repeat of the trapezoidal model. It's a genuine
#     second-order mass-spring-damper system, tracking NominalPlant's
#     position/velocity as its moving setpoint each scan, instead of
#     achieving the commanded motion directly. A real motor-and-car system
#     has inertia and compliance a kinematic model doesn't -- this is that,
#     modeled honestly rather than assumed. When well damped, its response
#     to a moving setpoint stays close to that setpoint with negligible
#     overshoot (a real elevator is deliberately engineered this way -- no
#     one wants a car that bounces). As the damping ratio degrades (see
#     WEAR below), the same tracking law starts to overshoot and ring
#     before settling -- a real, physically motivated failure mode, not an
#     arbitrary number injected to make a demo work.
#
# WEAR: the actual plant's damping ratio isn't fixed. It degrades slowly,
# proportional to how long the car has actually been commanded to move
# (accumulated only while Moving=True, not real/wall-clock time) -- bearing
# and damper wear comes from usage, not from sitting idle. This is what
# Elevator_System_3's CUSUM layer (see elevator_3.yaml) is built to catch:
# not a constant offset between nominal and actual (a fixed threshold would
# catch that on day one, no history needed), but a residual that starts
# near zero and grows slowly, trip after trip, the way a real degrading
# component actually behaves.
#
# Both plants are called from ONE .step(tags) method -- DualPlant below --
# so this still satisfies the same plant interface engine/simulation_runner
# already expects (plant.step(tags), called once per scan after run_scan()).
# Nothing about the engine or the generic runner needed to change for this.
#
# NUMERICAL NOTE, found empirically while building this (not anticipated
# up front): Moving/Target_Floor are only ever sampled once per outer
# 1-second scan, matching this project's scan-cycle convention everywhere
# else -- but the spring-damper's own dynamics have a much faster natural
# timescale (roughly 1/omega_n, well under a second at the values used
# here), so integrating it at 1-second resolution is numerically unstable,
# and holding nominal's setpoint frozen for a whole second while only
# sub-stepping the actual plant against it produces a wrong "chase the
# stationary point, then stop and wait" pattern instead of smooth tracking
# -- both confirmed by actually running it and inspecting the trajectory,
# not predicted in advance. DualPlant fixes this by sub-stepping BOTH
# plants together at a much finer resolution internally, so the actual
# plant is always chasing a target that's genuinely still moving. See
# DualPlant's own docstring for the full account.


class NominalPlant:
    """
    Same trapezoidal model as Elevator_System_2's Elevator_Plant, except
    step() now takes an explicit dt instead of assuming self.scan_time --
    DualPlant below sub-steps both plants together at a much finer
    resolution than the outer 1-second scan (see DualPlant's docstring for
    why), so this needs to integrate correctly at whatever dt it's handed,
    not just at the outer scan's own duration.
    """

    def __init__(self, max_velocity, acceleration, deceleration,
                 arrival_tolerance, top_floor, velocity_snap_tolerance,
                 position=0.0, velocity=0.0):
        self.position = position
        self.velocity = velocity
        self.max_velocity = max_velocity
        self.acceleration = acceleration
        self.deceleration = deceleration
        self.arrival_tolerance = arrival_tolerance
        self.top_floor = top_floor
        self.velocity_snap_tolerance = velocity_snap_tolerance

    def _target_velocity(self, target_floor, moving_permitted):
        if not moving_permitted:
            return 0.0
        distance_remaining = target_floor - self.position
        if distance_remaining == 0:
            return 0.0
        direction = 1.0 if distance_remaining > 0 else -1.0
        current_speed = abs(self.velocity)
        braking_distance = (current_speed ** 2) / (2 * self.deceleration) if self.deceleration > 0 else 0.0
        if abs(distance_remaining) <= braking_distance:
            return 0.0
        return self.max_velocity * direction

    def step(self, target_floor, moving_permitted, dt):
        target_velocity = self._target_velocity(target_floor, moving_permitted)

        if abs(target_velocity) > abs(self.velocity):
            rate = self.acceleration
        else:
            rate = self.deceleration

        if self.velocity < target_velocity:
            self.velocity = min(self.velocity + rate * dt, target_velocity)
        elif self.velocity > target_velocity:
            self.velocity = max(self.velocity - rate * dt, target_velocity)

        self.position = self.position + self.velocity * dt

        if self.position < 0.0:
            self.position = 0.0
            self.velocity = max(self.velocity, 0.0)
        if self.position > self.top_floor:
            self.position = self.top_floor
            self.velocity = min(self.velocity, 0.0)

        if (moving_permitted
                and abs(target_floor - self.position) <= self.arrival_tolerance
                and abs(self.velocity) <= self.velocity_snap_tolerance):
            self.position = target_floor
            self.velocity = 0.0

        return self.position, self.velocity


class ActualPlant:
    """
    Second-order mass-spring-damper tracking of a moving setpoint
    (nominal_position, nominal_velocity), using the standard normalized
    form:

        acceleration = omega_n^2 * (setpoint_position - position)
                      + 2 * zeta * omega_n * (setpoint_velocity - velocity)

    omega_n (natural frequency, rad/s) sets how AGGRESSIVELY the actual
    system chases the setpoint -- higher means faster response. zeta
    (damping ratio) sets HOW it chases it: zeta=1 (critical damping) is
    the fastest response with no overshoot; zeta<1 (underdamped) overshoots
    and rings before settling; zeta>1 (overdamped) is sluggish. Starts
    critically damped (zeta=1) -- a real elevator is deliberately
    engineered not to bounce -- and degrades toward underdamped as WEAR
    accumulates.

    step() takes an explicit dt and the setpoint as of THIS instant, not a
    value held fixed for a whole outer scan -- see DualPlant's docstring
    for why that distinction turned out to matter a great deal here.

    Arrival snapping is checked against target_floor directly (the real
    destination), gated on moving_permitted -- independent of the
    setpoint, deliberately: the actual car's job is to arrive at the real
    target floor and stop, not to exactly shadow nominal's position at
    every instant.
    """

    def __init__(self, natural_frequency, initial_damping_ratio, damping_floor,
                 wear_rate, arrival_tolerance, top_floor, velocity_snap_tolerance,
                 position=0.0, velocity=0.0):
        self.position = position
        self.velocity = velocity
        self.omega_n = natural_frequency
        self.damping_ratio = initial_damping_ratio
        self.damping_floor = damping_floor
        self.wear_rate = wear_rate                  # damping ratio lost per second of Moving=True
        self.arrival_tolerance = arrival_tolerance
        self.top_floor = top_floor
        self.velocity_snap_tolerance = velocity_snap_tolerance

    def step(self, target_floor, moving_permitted, setpoint_position, setpoint_velocity, dt):
        omega_n = self.omega_n
        zeta = self.damping_ratio

        acceleration = (omega_n ** 2) * (setpoint_position - self.position) \
            + 2 * zeta * omega_n * (setpoint_velocity - self.velocity)

        self.velocity = self.velocity + acceleration * dt
        self.position = self.position + self.velocity * dt

        if self.position < 0.0:
            self.position = 0.0
            self.velocity = max(self.velocity, 0.0)
        if self.position > self.top_floor:
            self.position = self.top_floor
            self.velocity = min(self.velocity, 0.0)

        if (moving_permitted
                and abs(target_floor - self.position) <= self.arrival_tolerance
                and abs(self.velocity) <= self.velocity_snap_tolerance):
            self.position = target_floor
            self.velocity = 0.0

        return self.position, self.velocity

    def apply_wear(self, moving_permitted, dt):
        # Called once per OUTER scan (not per sub-step) by DualPlant --
        # wear accrues at a rate defined in terms of real seconds of
        # Moving=True, and doing it once per outer scan with dt = the full
        # outer scan duration is simpler and numerically identical to
        # spreading the same total across every sub-step.
        if moving_permitted:
            self.damping_ratio = max(self.damping_floor, self.damping_ratio - self.wear_rate * dt)


class DualPlant:
    """
    The actual plant object handed to engine/simulation_runner -- same
    .step(tags) interface every physics-plant example in this project
    uses, from the outside. Internally, though, this does something the
    other examples don't: it sub-steps BOTH plants together, at a much
    finer resolution than the outer 1-second scan.

    Why: Moving/Target_Floor are only ever sampled once per outer scan
    (matching a real PLC's scan rate), but the physics itself needs a much
    finer integration step to be numerically stable and accurate at all --
    confirmed empirically, this was not a style choice. omega_n around
    8 rad/s gives the spring-damper system its own natural timescale of
    roughly 1/omega_n ~ 0.125s, an order of magnitude finer than the
    1-second outer scan. A first attempt held nominal's setpoint fixed for
    the whole outer scan and only sub-stepped the actual plant against
    that frozen target -- wrong, and caught by actually inspecting a
    single scan's trajectory: the fast spring-damper would catch up to the
    artificially stationary setpoint well before the second was over, then
    just sit there with near-zero velocity, instead of smoothly tracking a
    continuously advancing one. The fix is to sub-step NominalPlant too,
    at the same fine resolution, so ActualPlant is always chasing a target
    that's actually still moving.
    """

    def __init__(self, nominal_plant, actual_plant, scan_time=1, substeps=100):
        self.nominal_plant = nominal_plant
        self.actual_plant = actual_plant
        self.scan_time = scan_time
        self.substeps = substeps

    def step(self, tags):
        target_floor = tags["Target_Floor"]
        moving_permitted = tags["Moving"]
        dt_sub = self.scan_time / self.substeps

        for _ in range(self.substeps):
            nominal_position, nominal_velocity = self.nominal_plant.step(target_floor, moving_permitted, dt_sub)
            self.actual_plant.step(target_floor, moving_permitted, nominal_position, nominal_velocity, dt_sub)

        self.actual_plant.apply_wear(moving_permitted, self.scan_time)

        tags["Nominal_Current_Floor"] = self.nominal_plant.position
        tags["Nominal_Velocity_FloorsPerSec"] = self.nominal_plant.velocity
        tags["Current_Floor"] = self.actual_plant.position             # authoritative -- logic reads this
        tags["Velocity_FloorsPerSec"] = self.actual_plant.velocity
        tags["Damping_Ratio"] = self.actual_plant.damping_ratio         # observability only, no operation reads it