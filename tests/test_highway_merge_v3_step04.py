from __future__ import annotations

import importlib
import sys
from pathlib import Path


STEP_DIR = Path(__file__).resolve().parents[1] / "experiments/highway_merge_v3/step04_cooperative_merge"
if str(STEP_DIR) not in sys.path:
    sys.path.insert(0, str(STEP_DIR))

controller = importlib.import_module("controller")


def test_controller_selects_only_a_waiting_ramp_conflict() -> None:
    settings = controller.CooperativeSettings(180, 3, 80, 260, 3, 10, 23.5, 3, 7, 8)
    subject = controller.LimitedCooperativeController(settings)
    ramp = [controller.VehicleState("side_flow.0", 100, 20, 4)]
    main = [controller.VehicleState("main_flow.0", 160, 25)]

    assert subject.select_candidate(10, ramp, main) == "main_flow.0"
    assert subject.interventions == 1


def test_controller_can_use_a_moving_ramp_vehicle_when_threshold_is_zero() -> None:
    settings = controller.CooperativeSettings(180, 0, 80, 260, 3, 10, 23.5, 3, 7, 8)
    subject = controller.LimitedCooperativeController(settings)

    assert subject.select_candidate(
        10,
        [controller.VehicleState("side_flow.0", 100, 20, 0)],
        [controller.VehicleState("main_flow.0", 160, 25)],
    ) == "main_flow.0"


def test_controller_accepts_a_ramp_vehicle_at_the_start_of_parallel_section() -> None:
    settings = controller.CooperativeSettings(606, 0, 80, 260, 3, 10, 23.5, 3, 7, 8)
    subject = controller.LimitedCooperativeController(settings)

    assert subject.select_candidate(
        10,
        [controller.VehicleState("side_flow.0", 580, 20, 0)],
        [controller.VehicleState("main_flow.0", 160, 25)],
    ) == "main_flow.0"


def test_controller_releases_and_cools_down() -> None:
    settings = controller.CooperativeSettings(180, 3, 80, 260, 3, 10, 23.5, 3, 7, 8)
    subject = controller.LimitedCooperativeController(settings, active_main_vehicle="main_flow.0", target_ramp_vehicle="side_flow.0", intervention_started_s=10)

    assert subject.observe(12, True, True) == "main_flow.0"
    assert subject.successful_releases == 1
    assert subject.select_candidate(15, [controller.VehicleState("side_flow.1", 80, 1, 4)], [controller.VehicleState("main_flow.1", 160, 25)]) is None


def test_controller_counts_lane_exit_as_a_successful_release() -> None:
    settings = controller.CooperativeSettings(606, 0, 80, 260, 3, 10, 23.5, 3, 7, 8)
    subject = controller.LimitedCooperativeController(settings, active_main_vehicle="main_flow.0", target_ramp_vehicle="side_flow.0", intervention_started_s=10)

    assert subject.observe(11, True, True) == "main_flow.0"
    assert subject.timed_out_interventions == 0
    assert subject.successful_releases == 1
