from pathlib import Path
from xml.etree import ElementTree as ET


def estimate_generated_vehicles(main_veh_h: int, side_veh_h: int, end_time: float) -> int:
    return int(round(main_veh_h * end_time / 3600.0)) + int(round(side_veh_h * end_time / 3600.0))


def state_from_metrics(avg_travel_time_s: float, unfinished_vehicles: int) -> str:
    """Classify the minimal model using its current exploratory thresholds."""
    if unfinished_vehicles == 0 and avg_travel_time_s <= 60.0:
        return "free_flow"
    if unfinished_vehicles == 0 and avg_travel_time_s <= 75.0:
        return "deceleration"
    if unfinished_vehicles <= 5 and avg_travel_time_s <= 90.0:
        return "queue"
    return "breakdown"


def summarize_tripinfo(tripinfo_path: Path, expected_generated: int) -> dict[str, float | int | str]:
    tripinfos = ET.parse(tripinfo_path).getroot().findall("tripinfo")
    if not tripinfos:
        return {
            "generated_veh": expected_generated, "arrived_veh": 0,
            "avg_travel_time_s": 0.0, "total_travel_time_s": 0.0,
            "unfinished_vehicles": expected_generated, "state": "breakdown",
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
        "unfinished_vehicles": unfinished, "state": state_from_metrics(average, unfinished),
        "avg_wait_time_s": sum(wait_times) / arrived, "total_wait_time_s": sum(wait_times),
    }
