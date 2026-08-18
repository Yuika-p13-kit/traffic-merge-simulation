from __future__ import annotations

from dataclasses import dataclass, field


def stream_for_vehicle(vehicle_id: str) -> str:
    if vehicle_id.startswith("main_flow"):
        return "main"
    if vehicle_id.startswith("side_flow"):
        return "side"
    raise ValueError(f"Unknown vehicle stream: {vehicle_id}")


def _stream_values() -> dict[str, float]:
    return {"main": 0.0, "side": 0.0}


def _stream_counts() -> dict[str, int]:
    return {"main": 0, "side": 0}


@dataclass
class CompleteTTSMetrics:
    """Measure in-network TTS plus delay while waiting for insertion.

    SUMO's pending vehicle list contains vehicles whose intended departure time
    has passed but which cannot enter the network. Integrating both active and
    pending vehicles makes the accounting cover every loaded, unfinished vehicle.
    """

    step_length_s: float = 1.0
    network_time_spent_s: dict[str, float] = field(default_factory=_stream_values)
    insertion_wait_time_s: dict[str, float] = field(default_factory=_stream_values)
    stopped_time_s: dict[str, float] = field(default_factory=_stream_values)
    peak_network_queue_vehicles: dict[str, int] = field(default_factory=_stream_counts)
    peak_pending_vehicles: dict[str, int] = field(default_factory=_stream_counts)
    departed_vehicle_ids: set[str] = field(default_factory=set)
    loaded_vehicle_ids: set[str] = field(default_factory=set)
    arrived_vehicle_ids: set[str] = field(default_factory=set)
    pending_vehicle_ids_end: set[str] = field(default_factory=set)

    def observe(
        self,
        vehicle_speeds: dict[str, float],
        pending_ids: set[str],
        loaded_ids: set[str],
        departed_ids: set[str],
        arrived_ids: set[str],
        *,
        within_demand: bool,
    ) -> None:
        self.loaded_vehicle_ids.update(loaded_ids)
        self.departed_vehicle_ids.update(departed_ids)
        self.arrived_vehicle_ids.update(arrived_ids)
        self.pending_vehicle_ids_end = set(pending_ids)
        network_queue = _stream_counts()
        pending_count = _stream_counts()

        for vehicle_id, speed_m_s in vehicle_speeds.items():
            stream = stream_for_vehicle(vehicle_id)
            self.network_time_spent_s[stream] += self.step_length_s
            if speed_m_s < 0.1:
                self.stopped_time_s[stream] += self.step_length_s
                network_queue[stream] += 1

        for vehicle_id in pending_ids:
            stream = stream_for_vehicle(vehicle_id)
            self.insertion_wait_time_s[stream] += self.step_length_s
            pending_count[stream] += 1

        if within_demand:
            for stream in ("main", "side"):
                self.peak_network_queue_vehicles[stream] = max(
                    self.peak_network_queue_vehicles[stream], network_queue[stream]
                )
                self.peak_pending_vehicles[stream] = max(
                    self.peak_pending_vehicles[stream], pending_count[stream]
                )

    def result(self) -> dict[str, float | int]:
        output: dict[str, float | int] = {}
        for stream in ("main", "side"):
            departed = sum(stream_for_vehicle(item) == stream for item in self.departed_vehicle_ids)
            loaded = sum(stream_for_vehicle(item) == stream for item in self.loaded_vehicle_ids)
            arrived = sum(stream_for_vehicle(item) == stream for item in self.arrived_vehicle_ids)
            pending = sum(stream_for_vehicle(item) == stream for item in self.pending_vehicle_ids_end)
            network_tts = self.network_time_spent_s[stream]
            insertion_tts = self.insertion_wait_time_s[stream]
            output.update({
                f"{stream}_loaded_veh": loaded,
                f"{stream}_departed_veh": departed,
                f"{stream}_arrived_veh": arrived,
                f"{stream}_network_unfinished_veh": max(0, departed - arrived),
                f"{stream}_pending_veh_end": pending,
                f"{stream}_total_unfinished_veh": max(0, loaded - arrived),
                f"{stream}_network_time_spent_s": network_tts,
                f"{stream}_insertion_wait_time_s": insertion_tts,
                f"{stream}_total_time_spent_s": network_tts + insertion_tts,
                f"{stream}_stopped_time_s": self.stopped_time_s[stream],
                f"{stream}_avg_stopped_time_s": self.stopped_time_s[stream] / departed if departed else 0.0,
                f"{stream}_peak_network_queue_vehicles": self.peak_network_queue_vehicles[stream],
                f"{stream}_peak_pending_vehicles": self.peak_pending_vehicles[stream],
            })

        output["network_time_spent_s"] = sum(self.network_time_spent_s.values())
        output["insertion_wait_time_s"] = sum(self.insertion_wait_time_s.values())
        output["total_time_spent_s"] = (
            float(output["network_time_spent_s"]) + float(output["insertion_wait_time_s"])
        )
        output["accounted_loaded_veh"] = int(output["main_loaded_veh"]) + int(output["side_loaded_veh"])
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
