"""State machine for a bounded, lane-specific v3 merge speed advisory."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VehicleState:
    vehicle_id: str
    distance_to_merge_end_m: float
    speed_m_s: float
    waiting_time_s: float = 0.0


@dataclass(frozen=True)
class CooperativeSettings:
    ramp_activation_distance_m: float
    ramp_wait_threshold_s: float
    main_min_distance_m: float
    main_control_distance_m: float
    min_conflict_eta_s: float
    max_conflict_eta_s: float
    max_pair_eta_gap_s: float
    cooperative_speed_m_s: float
    max_intervention_s: float
    cooldown_s: float


@dataclass
class LimitedCooperativeController:
    settings: CooperativeSettings
    active_main_vehicle: str | None = None
    target_ramp_vehicle: str | None = None
    intervention_started_s: float | None = None
    cooldown_until_s: float = 0.0
    interventions: int = 0
    successful_releases: int = 0
    timed_out_interventions: int = 0

    def select_candidate(
        self, now_s: float, ramp_vehicles: list[VehicleState], main_vehicles: list[VehicleState],
    ) -> str | None:
        if self.active_main_vehicle or now_s < self.cooldown_until_s:
            return self.active_main_vehicle
        waiting_ramp = [
            vehicle for vehicle in ramp_vehicles
            if vehicle.distance_to_merge_end_m <= self.settings.ramp_activation_distance_m
            and vehicle.waiting_time_s >= self.settings.ramp_wait_threshold_s
        ]
        if not waiting_ramp:
            return None
        candidates: list[tuple[float, VehicleState, VehicleState]] = []
        for vehicle in main_vehicles:
            if not self.settings.main_min_distance_m <= vehicle.distance_to_merge_end_m <= self.settings.main_control_distance_m:
                continue
            eta_s = vehicle.distance_to_merge_end_m / max(vehicle.speed_m_s, 0.1)
            if self.settings.min_conflict_eta_s <= eta_s <= self.settings.max_conflict_eta_s:
                for ramp in waiting_ramp:
                    ramp_eta_s = ramp.distance_to_merge_end_m / max(ramp.speed_m_s, 0.1)
                    eta_gap_s = abs(eta_s - ramp_eta_s)
                    if eta_gap_s <= self.settings.max_pair_eta_gap_s:
                        candidates.append((eta_gap_s, vehicle, ramp))
        if not candidates:
            return None
        _, selected, target_ramp = min(candidates, key=lambda item: item[0])
        self.active_main_vehicle = selected.vehicle_id
        self.target_ramp_vehicle = target_ramp.vehicle_id
        self.intervention_started_s = now_s
        self.interventions += 1
        return selected.vehicle_id

    def observe(self, now_s: float, target_ramp_completed: bool, active_vehicle_present: bool) -> str | None:
        if not self.active_main_vehicle:
            return None
        started = self.intervention_started_s if self.intervention_started_s is not None else now_s
        timed_out = now_s - started >= self.settings.max_intervention_s
        if not (target_ramp_completed or timed_out or not active_vehicle_present):
            return None
        released = self.active_main_vehicle
        if target_ramp_completed:
            self.successful_releases += 1
        elif timed_out:
            self.timed_out_interventions += 1
        self.active_main_vehicle = None
        self.target_ramp_vehicle = None
        self.intervention_started_s = None
        self.cooldown_until_s = now_s + self.settings.cooldown_s
        return released
