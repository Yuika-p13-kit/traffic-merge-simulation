from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class OnDemandMeter:
    """Use fixed-interval releases only while a mainline speed trigger persists."""

    interval_s: float = 1.5
    activation_speed_m_s: float = 27.0
    recovery_speed_m_s: float = 29.0
    activation_persistence_s: float = 3.0
    recovery_persistence_s: float = 10.0
    min_active_s: float = 30.0
    active: bool = False
    low_since_s: float | None = None
    recovery_since_s: float | None = None
    active_since_s: float | None = None
    next_release_s: float | None = None
    held: set[str] = field(default_factory=set)
    seen: set[str] = field(default_factory=set)
    activations: int = 0
    releases: int = 0
    active_time_s: float = 0.0
    last_time_s: float | None = None

    def update(self, now_s: float, main_speeds: list[float], positions: dict[str, float], ready: set[str]) -> tuple[set[str], set[str]]:
        if self.last_time_s is not None and self.active:
            self.active_time_s += now_s - self.last_time_s
        self.last_time_s = now_s
        mean_speed = sum(main_speeds) / len(main_speeds) if main_speeds else float("inf")
        congested, recovered = bool(main_speeds) and mean_speed <= self.activation_speed_m_s, not main_speeds or mean_speed >= self.recovery_speed_m_s
        released: set[str] = set()
        if not self.active:
            self.low_since_s = now_s if congested and self.low_since_s is None else self.low_since_s
            if not congested: self.low_since_s = None
            if self.low_since_s is not None and now_s - self.low_since_s >= self.activation_persistence_s:
                self.active = True; self.active_since_s = now_s; self.next_release_s = None; self.activations += 1
        else:
            self.recovery_since_s = now_s if recovered and self.recovery_since_s is None else self.recovery_since_s
            if not recovered: self.recovery_since_s = None
            if self.recovery_since_s is not None and now_s - self.recovery_since_s >= self.recovery_persistence_s and now_s - (self.active_since_s or now_s) >= self.min_active_s:
                self.active = False; released, self.held = set(self.held), set(); self.seen.clear(); self.recovery_since_s = None; self.low_since_s = None; self.next_release_s = None
        self.held.intersection_update(positions)
        if self.active:
            self.held.update(set(positions) - self.seen); self.seen.update(positions)
            candidates = self.held & ready
            if candidates and (self.next_release_s is None or now_s >= self.next_release_s):
                vehicle = max(candidates, key=lambda item: (positions[item], item)); self.held.remove(vehicle); released.add(vehicle)
                self.releases += 1; self.next_release_s = now_s + self.interval_s
        return set(self.held), released
