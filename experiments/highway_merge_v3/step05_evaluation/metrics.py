from __future__ import annotations

from dataclasses import dataclass, field


def stream_for_vehicle(vehicle_id: str) -> str:
    if vehicle_id.startswith("main_flow"):
        return "main"
    if vehicle_id.startswith("side_flow"):
        return "ramp"
    raise ValueError(f"Unknown vehicle stream: {vehicle_id}")


def _zeros() -> dict[str, float]:
    return {"main": 0.0, "ramp": 0.0}


def _counts() -> dict[str, int]:
    return {"main": 0, "ramp": 0}


@dataclass
class CompleteTTSMetrics:
    """Integrate in-network presence and pending insertion time by stream."""

    network_time_spent_s: dict[str, float] = field(default_factory=_zeros)
    insertion_wait_time_s: dict[str, float] = field(default_factory=_zeros)
    stopped_time_s: dict[str, float] = field(default_factory=_zeros)
    peak_pending_vehicles: dict[str, int] = field(default_factory=_counts)
    loaded_vehicle_ids: set[str] = field(default_factory=set)
    departed_vehicle_ids: set[str] = field(default_factory=set)
    arrived_vehicle_ids: set[str] = field(default_factory=set)
    pending_vehicle_ids_end: set[str] = field(default_factory=set)

    def observe(self, vehicle_speeds: dict[str, float], pending_ids: set[str], loaded_ids: set[str], departed_ids: set[str], arrived_ids: set[str], *, within_demand: bool, step_length_s: float = 1.0) -> None:
        self.loaded_vehicle_ids.update(loaded_ids)
        self.departed_vehicle_ids.update(departed_ids)
        self.arrived_vehicle_ids.update(arrived_ids)
        self.pending_vehicle_ids_end = set(pending_ids)
        pending_counts = _counts()
        for vehicle_id, speed in vehicle_speeds.items():
            stream = stream_for_vehicle(vehicle_id)
            self.network_time_spent_s[stream] += step_length_s
            if speed < 0.1:
                self.stopped_time_s[stream] += step_length_s
        for vehicle_id in pending_ids:
            stream = stream_for_vehicle(vehicle_id)
            self.insertion_wait_time_s[stream] += step_length_s
            pending_counts[stream] += 1
        if within_demand:
            for stream in pending_counts:
                self.peak_pending_vehicles[stream] = max(self.peak_pending_vehicles[stream], pending_counts[stream])

    def result(self) -> dict[str, float | int]:
        result: dict[str, float | int] = {}
        for stream in ("main", "ramp"):
            loaded = sum(stream_for_vehicle(vehicle) == stream for vehicle in self.loaded_vehicle_ids)
            departed = sum(stream_for_vehicle(vehicle) == stream for vehicle in self.departed_vehicle_ids)
            arrived = sum(stream_for_vehicle(vehicle) == stream for vehicle in self.arrived_vehicle_ids)
            pending = sum(stream_for_vehicle(vehicle) == stream for vehicle in self.pending_vehicle_ids_end)
            network = self.network_time_spent_s[stream]
            insertion = self.insertion_wait_time_s[stream]
            result.update({
                f"{stream}_loaded_veh": loaded, f"{stream}_departed_veh": departed,
                f"{stream}_arrived_veh": arrived, f"{stream}_pending_veh_end": pending,
                f"{stream}_total_unfinished_veh": max(0, loaded - arrived),
                f"{stream}_network_time_spent_s": network, f"{stream}_insertion_wait_time_s": insertion,
                f"{stream}_total_time_spent_s": network + insertion,
                f"{stream}_stopped_time_s": self.stopped_time_s[stream],
                f"{stream}_peak_pending_vehicles": self.peak_pending_vehicles[stream],
            })
        result["network_time_spent_s"] = sum(self.network_time_spent_s.values())
        result["insertion_wait_time_s"] = sum(self.insertion_wait_time_s.values())
        result["total_time_spent_s"] = float(result["network_time_spent_s"]) + float(result["insertion_wait_time_s"])
        result["accounted_loaded_veh"] = len(self.loaded_vehicle_ids)
        return result
