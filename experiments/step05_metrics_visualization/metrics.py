from __future__ import annotations

from dataclasses import dataclass, field


def stream_for_vehicle(vehicle_id: str) -> str:
    if vehicle_id.startswith("main_flow"):
        return "main"
    if vehicle_id.startswith("side_flow"):
        return "side"
    raise ValueError(f"Unknown vehicle stream: {vehicle_id}")


@dataclass
class NetworkMetrics:
    """Accumulate metrics from per-step TraCI snapshots.

    Total Time Spent (TTS) integrates all vehicles still in the network, so it
    does not discard the cost of vehicles that have not arrived by simulation end.
    Waiting time uses SUMO's conventional halting threshold of 0.1 m/s.
    """

    step_length_s: float = 1.0
    total_time_spent_s: dict[str, float] = field(
        default_factory=lambda: {"main": 0.0, "side": 0.0}
    )
    total_wait_time_s: dict[str, float] = field(
        default_factory=lambda: {"main": 0.0, "side": 0.0}
    )
    peak_queue_vehicles: dict[str, int] = field(
        default_factory=lambda: {"main": 0, "side": 0}
    )
    loaded_vehicle_ids: set[str] = field(default_factory=set)
    arrived_vehicle_ids: set[str] = field(default_factory=set)

    def observe(
        self,
        vehicle_speeds: dict[str, float],
        departed_ids: set[str],
        arrived_ids: set[str],
        *,
        within_demand: bool,
    ) -> None:
        self.loaded_vehicle_ids.update(departed_ids)
        self.arrived_vehicle_ids.update(arrived_ids)
        queue = {"main": 0, "side": 0}
        for vehicle_id, speed_m_s in vehicle_speeds.items():
            stream = stream_for_vehicle(vehicle_id)
            self.total_time_spent_s[stream] += self.step_length_s
            if speed_m_s < 0.1:
                self.total_wait_time_s[stream] += self.step_length_s
                queue[stream] += 1
        if within_demand:
            for stream in queue:
                self.peak_queue_vehicles[stream] = max(
                    self.peak_queue_vehicles[stream], queue[stream]
                )

    def result(self) -> dict[str, float | int]:
        output: dict[str, float | int] = {}
        for stream in ("main", "side"):
            loaded = sum(stream_for_vehicle(item) == stream for item in self.loaded_vehicle_ids)
            arrived = sum(stream_for_vehicle(item) == stream for item in self.arrived_vehicle_ids)
            output.update({
                f"{stream}_loaded_veh": loaded,
                f"{stream}_arrived_veh": arrived,
                f"{stream}_unfinished_veh": max(0, loaded - arrived),
                f"{stream}_total_time_spent_s": self.total_time_spent_s[stream],
                f"{stream}_total_wait_time_s": self.total_wait_time_s[stream],
                f"{stream}_avg_wait_time_s": (
                    self.total_wait_time_s[stream] / loaded if loaded else 0.0
                ),
                f"{stream}_peak_queue_vehicles": self.peak_queue_vehicles[stream],
            })
        output["total_time_spent_s"] = sum(self.total_time_spent_s.values())
        output["total_wait_time_s"] = sum(self.total_wait_time_s.values())
        return output


@dataclass
class InterventionResponseTracker:
    response_window_s: float
    starts: list[float] = field(default_factory=list)
    counted_side_ids: set[str] = field(default_factory=set)

    def start(self, now_s: float) -> None:
        self.starts.append(now_s)

    def observe_side_merges(self, now_s: float, side_ids: set[str]) -> None:
        if any(0.0 <= now_s - start <= self.response_window_s for start in self.starts):
            self.counted_side_ids.update(side_ids)

    @property
    def side_merges_after_intervention(self) -> int:
        return len(self.counted_side_ids)
