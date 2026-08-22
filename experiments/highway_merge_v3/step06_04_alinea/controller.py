from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AlineaMeter:
    """Update ramp release rate from the observed merge-lane vehicle count."""
    target_vehicles: float = 8.0
    gain_veh_h_per_vehicle: float = 120.0
    min_rate_veh_h: float = 1800.0
    max_rate_veh_h: float = 3600.0
    update_period_s: float = 20.0
    rate_veh_h: float = 3000.0
    next_update_s: float = 0.0
    next_release_s: float | None = None
    held: set[str] = field(default_factory=set)
    seen: set[str] = field(default_factory=set)
    releases: int = 0
    rate_updates: int = 0
    rate_history: list[float] = field(default_factory=list)

    def update(self, now_s: float, main_vehicle_count: int, positions: dict[str, float], ready: set[str]) -> tuple[set[str], set[str]]:
        if now_s >= self.next_update_s:
            self.rate_veh_h = min(self.max_rate_veh_h, max(self.min_rate_veh_h, self.rate_veh_h + self.gain_veh_h_per_vehicle * (self.target_vehicles - main_vehicle_count)))
            self.next_update_s = now_s + self.update_period_s; self.rate_updates += 1; self.rate_history.append(self.rate_veh_h)
        self.held.intersection_update(positions); self.held.update(set(positions) - self.seen); self.seen.update(positions)
        released: set[str] = set(); candidates = self.held & ready
        if candidates and (self.next_release_s is None or now_s >= self.next_release_s):
            vehicle = max(candidates, key=lambda item: (positions[item], item)); self.held.remove(vehicle); released.add(vehicle); self.releases += 1; self.next_release_s = now_s + 3600.0 / self.rate_veh_h
        return set(self.held), released
