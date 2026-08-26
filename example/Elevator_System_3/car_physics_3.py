# Elevator System 3 physical models.
#
# NominalPlant defines expected healthy motion.
# ActualPlant tracks that reference through second-order dynamics whose
# damping degrades with use.
# DualPlant advances both models together and exposes their states to the engine.


class NominalPlant:
    """Trapezoidal kinematic reference model used as the healthy trajectory."""

    def __init__(
        self,
        max_velocity,
        acceleration,
        deceleration,
        arrival_tolerance,
        top_floor,
        velocity_snap_tolerance,
        position=0.0,
        velocity=0.0,
    ):
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

        braking_distance = (
            (current_speed ** 2) / (2 * self.deceleration)
            if self.deceleration > 0
            else 0.0
        )

        if abs(distance_remaining) <= braking_distance:
            return 0.0

        return self.max_velocity * direction

    def step(self, target_floor, moving_permitted, dt):
        target_velocity = self._target_velocity(
            target_floor,
            moving_permitted,
        )

        if abs(target_velocity) > abs(self.velocity):
            rate = self.acceleration
        else:
            rate = self.deceleration

        if self.velocity < target_velocity:
            self.velocity = min(
                self.velocity + rate * dt,
                target_velocity,
            )
        elif self.velocity > target_velocity:
            self.velocity = max(
                self.velocity - rate * dt,
                target_velocity,
            )

        self.position += self.velocity * dt

        if self.position < 0.0:
            self.position = 0.0
            self.velocity = max(self.velocity, 0.0)

        if self.position > self.top_floor:
            self.position = self.top_floor
            self.velocity = min(self.velocity, 0.0)

        if (
            moving_permitted
            and abs(target_floor - self.position) <= self.arrival_tolerance
            and abs(self.velocity) <= self.velocity_snap_tolerance
        ):
            self.position = target_floor
            self.velocity = 0.0

        return self.position, self.velocity


class ActualPlant:
    """
    Second-order plant tracking the nominal position and velocity.

    The normalized dynamics are:

        acceleration =
            omega_n^2 * (setpoint_position - position)
            + 2 * zeta * omega_n * (setpoint_velocity - velocity)

    Wear reduces the damping ratio from the healthy critically damped state,
    producing progressively stronger underdamped oscillation.
    """

    def __init__(
        self,
        natural_frequency,
        initial_damping_ratio,
        damping_floor,
        wear_rate,
        arrival_tolerance,
        top_floor,
        velocity_snap_tolerance,
        position=0.0,
        velocity=0.0,
    ):
        self.position = position
        self.velocity = velocity
        self.omega_n = natural_frequency
        self.damping_ratio = initial_damping_ratio
        self.damping_floor = damping_floor
        self.wear_rate = wear_rate
        self.arrival_tolerance = arrival_tolerance
        self.top_floor = top_floor
        self.velocity_snap_tolerance = velocity_snap_tolerance

    def step(
        self,
        target_floor,
        moving_permitted,
        setpoint_position,
        setpoint_velocity,
        dt,
    ):
        omega_n = self.omega_n
        zeta = self.damping_ratio

        acceleration = (
            (omega_n ** 2) * (setpoint_position - self.position)
            + 2 * zeta * omega_n * (setpoint_velocity - self.velocity)
        )

        self.velocity += acceleration * dt
        self.position += self.velocity * dt

        if self.position < 0.0:
            self.position = 0.0
            self.velocity = max(self.velocity, 0.0)

        if self.position > self.top_floor:
            self.position = self.top_floor
            self.velocity = min(self.velocity, 0.0)

        # Arrival is resolved against the real destination, not the
        # instantaneous nominal reference.
        if (
            moving_permitted
            and abs(target_floor - self.position) <= self.arrival_tolerance
            and abs(self.velocity) <= self.velocity_snap_tolerance
        ):
            self.position = target_floor
            self.velocity = 0.0

        return self.position, self.velocity

    def apply_wear(self, moving_permitted, dt):
        """Reduce damping according to accumulated movement time."""
        if moving_permitted:
            self.damping_ratio = max(
                self.damping_floor,
                self.damping_ratio - self.wear_rate * dt,
            )


class DualPlant:
    """
    Advance nominal and actual dynamics together behind one plant interface.

    The engine retains its 1-second outer scan, while both physical models
    are integrated with smaller internal substeps for numerical stability
    and continuous reference tracking.
    """

    def __init__(
        self,
        nominal_plant,
        actual_plant,
        scan_time=1,
        substeps=100,
    ):
        self.nominal_plant = nominal_plant
        self.actual_plant = actual_plant
        self.scan_time = scan_time
        self.substeps = substeps

    def step(self, tags):
        target_floor = tags["Target_Floor"]
        moving_permitted = tags["Moving"]
        dt_sub = self.scan_time / self.substeps

        for _ in range(self.substeps):
            nominal_position, nominal_velocity = self.nominal_plant.step(
                target_floor,
                moving_permitted,
                dt_sub,
            )

            self.actual_plant.step(
                target_floor,
                moving_permitted,
                nominal_position,
                nominal_velocity,
                dt_sub,
            )

        self.actual_plant.apply_wear(
            moving_permitted,
            self.scan_time,
        )

        tags["Nominal_Current_Floor"] = self.nominal_plant.position
        tags["Nominal_Velocity_FloorsPerSec"] = self.nominal_plant.velocity

        # Actual state is authoritative for the control graph.
        tags["Current_Floor"] = self.actual_plant.position
        tags["Velocity_FloorsPerSec"] = self.actual_plant.velocity

        tags["Damping_Ratio"] = self.actual_plant.damping_ratio