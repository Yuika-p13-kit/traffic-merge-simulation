from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class OnDemandSettings:
    release_interval_s: float
    min_main_vehicles: int
    activation_speed_m_s: float
    recovery_speed_m_s: float
    activation_persistence_s: float
    recovery_persistence_s: float
    min_active_time_s: float

    def __post_init__(self) -> None:
        if self.release_interval_s <= 0:
            raise ValueError("release_interval_s must be positive")
        if self.recovery_speed_m_s <= self.activation_speed_m_s:
            raise ValueError("recovery speed must exceed activation speed")


@dataclass
class OnDemandRampMeter:
    """Activate fixed metering only during persistent mainline congestion."""

    settings: OnDemandSettings
    active: bool = False
    low_speed_since_s: float | None = None
    recovered_since_s: float | None = None
    active_since_s: float | None = None
    next_release_s: float | None = None
    registered: set[str] = field(default_factory=set)
    held: set[str] = field(default_factory=set)
    activations: int = 0
    releases: int = 0
    active_time_s: float = 0.0
    last_observation_s: float | None = None

    def update(
        self,
        now_s: float,
        main_speeds_m_s: list[float],
        controllable_side_positions_m: dict[str, float],
        ready_ids: set[str],
        eligible_new_ids: set[str] | None = None,
    ) -> tuple[set[str], set[str]]:
        if self.last_observation_s is not None and self.active:
            self.active_time_s += max(0.0, now_s - self.last_observation_s)
        self.last_observation_s = now_s
        mean_speed = sum(main_speeds_m_s) / len(main_speeds_m_s) if main_speeds_m_s else float("inf")
        congested = (
            len(main_speeds_m_s) >= self.settings.min_main_vehicles
            and mean_speed <= self.settings.activation_speed_m_s
        )
        recovered = (
            len(main_speeds_m_s) < self.settings.min_main_vehicles
            or mean_speed >= self.settings.recovery_speed_m_s
        )

        released: set[str] = set()
        if not self.active:
            self.low_speed_since_s = now_s if congested and self.low_speed_since_s is None else self.low_speed_since_s
            if not congested:
                self.low_speed_since_s = None
            if self.low_speed_since_s is not None and now_s - self.low_speed_since_s >= self.settings.activation_persistence_s:
                self.active = True
                self.active_since_s = now_s
                self.next_release_s = None
                self.recovered_since_s = None
                self.activations += 1
        else:
            self.recovered_since_s = now_s if recovered and self.recovered_since_s is None else self.recovered_since_s
            if not recovered:
                self.recovered_since_s = None
            active_for = now_s - (self.active_since_s if self.active_since_s is not None else now_s)
            if (self.recovered_since_s is not None
                    and now_s - self.recovered_since_s >= self.settings.recovery_persistence_s
                    and active_for >= self.settings.min_active_time_s):
                self.active = False
                released.update(self.held)
                self.held.clear()
                self.registered.clear()
                self.low_speed_since_s = None
                self.recovered_since_s = None
                self.active_since_s = None
                self.next_release_s = None

        present = set(controllable_side_positions_m)
        self.held.intersection_update(present)
        if self.active:
            eligible = present if eligible_new_ids is None else present & eligible_new_ids
            new_ids = eligible - self.registered
            self.registered.update(new_ids)
            self.held.update(new_ids)
            ready = self.held & ready_ids
            if ready and (self.next_release_s is None or now_s >= self.next_release_s):
                vehicle_id = max(ready, key=lambda item: (controllable_side_positions_m[item], item))
                self.held.remove(vehicle_id)
                released.add(vehicle_id)
                self.releases += 1
                self.next_release_s = now_s + self.settings.release_interval_s
        return set(self.held), released
