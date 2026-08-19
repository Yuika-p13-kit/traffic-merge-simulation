from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FixedIntervalMeter:
    """Hold side-road vehicles and release at most one per fixed interval."""

    release_interval_s: float
    next_release_s: float | None = None
    registered: set[str] = field(default_factory=set)
    held: set[str] = field(default_factory=set)
    released: set[str] = field(default_factory=set)
    release_times_s: list[float] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.release_interval_s <= 0:
            raise ValueError("release_interval_s must be positive")

    def update(
        self, now_s: float, side_positions_m: dict[str, float], ready_ids: set[str] | None = None,
    ) -> tuple[set[str], str | None]:
        present = set(side_positions_m)
        self.held.intersection_update(present)
        new_ids = present - self.registered
        self.registered.update(new_ids)
        self.held.update(new_ids)

        released_id: str | None = None
        release_due = self.next_release_s is None or now_s >= self.next_release_s
        ready = self.held if ready_ids is None else self.held & ready_ids
        if ready and release_due:
            released_id = max(ready, key=lambda vehicle_id: (side_positions_m[vehicle_id], vehicle_id))
            self.held.remove(released_id)
            self.released.add(released_id)
            self.release_times_s.append(now_s)
            self.next_release_s = now_s + self.release_interval_s
        return set(self.held), released_id

    @property
    def releases(self) -> int:
        return len(self.release_times_s)
