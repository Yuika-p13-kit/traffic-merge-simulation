from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VehicleState:
    vehicle_id: str
    distance_to_merge_m: float
    speed_m_s: float
    waiting_time_s: float = 0.0


@dataclass(frozen=True)
class LimitedSettings:
    side_activation_distance_m: float
    side_wait_threshold_s: float
    main_control_distance_m: float
    main_min_distance_m: float
    min_conflict_eta_s: float
    max_conflict_eta_s: float
    cooperative_speed_m_s: float
    max_intervention_s: float
    cooldown_s: float


@dataclass
class LimitedCooperativeController:
    settings: LimitedSettings
    active_main_vehicle: str | None = None
    target_side_vehicle: str | None = None
    intervention_started_s: float | None = None
    cooldown_until_s: float = 0.0
    interventions: int = 0
    successful_releases: int = 0
    timed_out_interventions: int = 0

    def select_candidate(
        self, now_s: float, side_vehicles: list[VehicleState], main_vehicles: list[VehicleState],
    ) -> str | None:
        if self.active_main_vehicle or now_s < self.cooldown_until_s:
            return self.active_main_vehicle
        waiting_side = [
            vehicle for vehicle in side_vehicles
            if vehicle.distance_to_merge_m <= self.settings.side_activation_distance_m
            and vehicle.waiting_time_s >= self.settings.side_wait_threshold_s
        ]
        if not waiting_side:
            return None

        candidates: list[tuple[float, VehicleState]] = []
        for vehicle in main_vehicles:
            if not self.settings.main_min_distance_m <= vehicle.distance_to_merge_m <= self.settings.main_control_distance_m:
                continue
            eta_s = vehicle.distance_to_merge_m / max(vehicle.speed_m_s, 0.1)
            if self.settings.min_conflict_eta_s <= eta_s <= self.settings.max_conflict_eta_s:
                candidates.append((eta_s, vehicle))
        if not candidates:
            return None

        selected = min(candidates, key=lambda item: item[0])[1].vehicle_id
        self.active_main_vehicle = selected
        self.target_side_vehicle = min(
            waiting_side, key=lambda vehicle: vehicle.distance_to_merge_m
        ).vehicle_id
        self.intervention_started_s = now_s
        self.interventions += 1
        return selected

    def observe(
        self, now_s: float, merged_side_vehicles: set[str], active_vehicle_present: bool,
    ) -> str | None:
        if not self.active_main_vehicle:
            return None
        started = self.intervention_started_s if self.intervention_started_s is not None else now_s
        target_merged = self.target_side_vehicle in merged_side_vehicles
        timed_out = now_s - started >= self.settings.max_intervention_s
        if target_merged or timed_out or not active_vehicle_present:
            released = self.active_main_vehicle
            if target_merged:
                self.successful_releases += 1
            elif timed_out:
                self.timed_out_interventions += 1
            self.active_main_vehicle = None
            self.target_side_vehicle = None
            self.intervention_started_s = None
            self.cooldown_until_s = now_s + self.settings.cooldown_s
            return released
        return None
