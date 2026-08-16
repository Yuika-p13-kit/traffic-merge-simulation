from pathlib import Path
from xml.etree import ElementTree as ET


def estimate_generated_vehicles(main_veh_h: int, side_veh_h: int, end_time: float) -> int:
    return int(round(main_veh_h * end_time / 3600.0)) + int(round(side_veh_h * end_time / 3600.0))


def classify_state(unfinished_vehicles: int, peak_queue_vehicles: int) -> str:
    """Classify flow after clearance, using SUMO's time-series queue observations."""
    if unfinished_vehicles > 0:
        return "breakdown"
    if peak_queue_vehicles > 0:
        return "queue"
    return "free_flow"


def summarize_tripinfo(tripinfo_path: Path, expected_generated: int) -> dict[str, float | int | str]:
    tripinfos = ET.parse(tripinfo_path).getroot().findall("tripinfo")
    if not tripinfos:
        return {
            "generated_veh": expected_generated, "arrived_veh": 0,
            "avg_travel_time_s": 0.0, "total_travel_time_s": 0.0,
            "unfinished_vehicles": expected_generated,
            "avg_wait_time_s": 0.0, "total_wait_time_s": 0.0,
        }
    travel_times = [float(item.attrib["duration"]) for item in tripinfos]
    wait_times = [float(item.attrib.get("waitingTime", 0.0)) for item in tripinfos]
    arrived = len(tripinfos)
    average = sum(travel_times) / arrived
    unfinished = max(0, expected_generated - arrived)
    return {
        "generated_veh": expected_generated, "arrived_veh": arrived,
        "avg_travel_time_s": average, "total_travel_time_s": sum(travel_times),
        "unfinished_vehicles": unfinished,
        "avg_wait_time_s": sum(wait_times) / arrived, "total_wait_time_s": sum(wait_times),
    }


def summarize_step_series(summary_path: Path, demand_duration_s: float) -> dict[str, int]:
    """Extract peak queue during demand and residual vehicles after clearance."""
    steps = ET.parse(summary_path).getroot().findall("step")
    peak_queue = 0
    for step in steps:
        if float(step.attrib["time"]) <= demand_duration_s:
            queued = int(step.attrib.get("halting", 0)) + int(step.attrib.get("waiting", 0))
            peak_queue = max(peak_queue, queued)
    final = steps[-1].attrib if steps else {}
    return {
        "peak_queue_vehicles": peak_queue,
        "final_running_vehicles": int(final.get("running", 0)),
        "final_waiting_vehicles": int(final.get("waiting", 0)),
        "inserted_vehicles": int(final.get("inserted", 0)),
        "loaded_vehicles": int(final.get("loaded", 0)),
        "teleports": int(final.get("teleports", 0)),
        "collisions": int(final.get("collisions", 0)),
    }
