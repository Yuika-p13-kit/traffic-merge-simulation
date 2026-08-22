from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FixedIntervalMeter:
    """Hold ramp vehicles and release the most downstream ready vehicle per interval."""

    release_interval_s: float
    next_release_s: float | None = None
    registered: set[str] = field(default_factory=set)
    held: set[str] = field(default_factory=set)
    release_times_s: list[float] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.release_interval_s <= 0:
            raise ValueError("release_interval_s must be positive")

    def update(self, now_s: float, positions_m: dict[str, float], ready_ids: set[str]) -> tuple[set[str], str | None]:
        present = set(positions_m)
        self.held.intersection_update(present)
        self.held.update(present - self.registered)
        self.registered.update(present)
        if not (ready := self.held & ready_ids) or (self.next_release_s is not None and now_s < self.next_release_s):
            return set(self.held), None
        vehicle_id = max(ready, key=lambda item: (positions_m[item], item))
        self.held.remove(vehicle_id)
        self.release_times_s.append(now_s)
        self.next_release_s = now_s + self.release_interval_s
        return set(self.held), vehicle_id

    @property
    def releases(self) -> int:
        return len(self.release_times_s)
