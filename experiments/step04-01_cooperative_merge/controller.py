from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VehiclePosition:
    vehicle_id: str
    distance_to_merge_m: float
    waiting_time_s: float = 0.0


@dataclass(frozen=True)
class CooperativeSettings:
    side_activation_distance_m: float
    side_wait_threshold_s: float
    main_control_distance_m: float
    main_min_distance_m: float
    cooperative_speed_m_s: float


def select_yield_vehicle(
    side_vehicles: list[VehiclePosition],
    main_vehicles: list[VehiclePosition],
    settings: CooperativeSettings,
) -> str | None:
    """Select the closest safely controllable mainline vehicle when side traffic is waiting."""
    side_needs_gap = any(
        vehicle.distance_to_merge_m <= settings.side_activation_distance_m
        and vehicle.waiting_time_s >= settings.side_wait_threshold_s
        for vehicle in side_vehicles
    )
    if not side_needs_gap:
        return None

    candidates = [
        vehicle for vehicle in main_vehicles
        if settings.main_min_distance_m <= vehicle.distance_to_merge_m <= settings.main_control_distance_m
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda vehicle: vehicle.distance_to_merge_m).vehicle_id
