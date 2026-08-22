from __future__ import annotations

from dataclasses import dataclass, field


def _zeros() -> dict[str, float]: return {"main": 0.0, "ramp": 0.0}
def _counts() -> dict[str, int]: return {"main": 0, "ramp": 0}
def _stream(vehicle: str) -> str: return "main" if vehicle.startswith("main_flow") else "ramp"


@dataclass
class CompleteTTSMetrics:
    network: dict[str, float] = field(default_factory=_zeros)
    insertion: dict[str, float] = field(default_factory=_zeros)
    loaded: set[str] = field(default_factory=set)
    pending_end: set[str] = field(default_factory=set)

    def observe(self, speeds: dict[str, float], pending: set[str], loaded: set[str], departed: set[str], arrived: set[str], *, within_demand: bool, step_length_s: float = 1.0) -> None:
        self.loaded.update(loaded); self.pending_end = set(pending)
        for vehicle in speeds: self.network[_stream(vehicle)] += step_length_s
        for vehicle in pending: self.insertion[_stream(vehicle)] += step_length_s

    def result(self) -> dict[str, float | int]:
        result: dict[str, float | int] = {"accounted_loaded_veh": len(self.loaded)}
        for stream in ("main", "ramp"):
            result[f"{stream}_network_time_spent_s"] = self.network[stream]
            result[f"{stream}_insertion_wait_time_s"] = self.insertion[stream]
            result[f"{stream}_total_time_spent_s"] = self.network[stream] + self.insertion[stream]
        result["network_time_spent_s"] = sum(self.network.values()); result["insertion_wait_time_s"] = sum(self.insertion.values()); result["total_time_spent_s"] = result["network_time_spent_s"] + result["insertion_wait_time_s"]
        return result
