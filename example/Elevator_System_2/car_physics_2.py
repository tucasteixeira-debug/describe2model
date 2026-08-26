# Elevator System 2 physical plant.
#
# This is a kinematic model: position and velocity follow a trapezoidal
# motion profile. Mass, motor torque, and force dynamics are intentionally
# outside the scope of this stage.


class Elevator_Plant:
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
        scan_time=1,
    ):
        self.position = position
        self.velocity = velocity
        self.max_velocity = max_velocity
        self.acceleration = acceleration
        self.deceleration = deceleration
        self.arrival_tolerance = arrival_tolerance
        self.top_floor = top_floor
        self.scan_time = scan_time
        self.velocity_snap_tolerance = velocity_snap_tolerance

    def _target_velocity(self, target_floor, moving_permitted):
        # A withdrawn movement command produces a controlled stop.
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

        # Begin braking once the remaining distance equals the stopping distance.
        if abs(distance_remaining) <= braking_distance:
            return 0.0

        return self.max_velocity * direction

    def step(self, tags):
        target_floor = tags["Target_Floor"]
        moving_permitted = tags["Moving"]

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
                self.velocity + rate * self.scan_time,
                target_velocity,
            )
        elif self.velocity > target_velocity:
            self.velocity = max(
                self.velocity - rate * self.scan_time,
                target_velocity,
            )

        self.position += self.velocity * self.scan_time

        # Enforce the physical shaft limits.
        if self.position < 0.0:
            self.position = 0.0
            self.velocity = max(self.velocity, 0.0)

        if self.position > self.top_floor:
            self.position = self.top_floor
            self.velocity = min(self.velocity, 0.0)

        # Snap to the target only when both position and velocity are close
        # enough to represent a physical stop.
        if (
            moving_permitted
            and abs(target_floor - self.position) <= self.arrival_tolerance
            and abs(self.velocity) <= self.velocity_snap_tolerance
        ):
            self.position = target_floor
            self.velocity = 0.0

        # Plant outputs become runtime inputs for the next control scan.
        tags["Current_Floor"] = self.position
        tags["Velocity_FloorsPerSec"] = self.velocity

        return self.position