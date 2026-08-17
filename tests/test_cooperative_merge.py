import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STEP_DIR = ROOT / "experiments" / "step04-01_cooperative_merge"
for path in (ROOT, STEP_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from controller import (
    CooperativeSettings,
    VehiclePosition,
    select_yield_vehicle,
)


SETTINGS = CooperativeSettings(
    side_activation_distance_m=80.0,
    side_wait_threshold_s=2.0,
    main_control_distance_m=180.0,
    main_min_distance_m=40.0,
    cooperative_speed_m_s=15.0,
)


def test_cooperation_requires_a_waiting_side_vehicle() -> None:
    main = [VehiclePosition("main.1", 100.0)]

    assert select_yield_vehicle([VehiclePosition("side.1", 50.0, 1.0)], main, SETTINGS) is None
    assert select_yield_vehicle([VehiclePosition("side.1", 90.0, 5.0)], main, SETTINGS) is None


def test_cooperation_selects_closest_safely_controllable_main_vehicle() -> None:
    side = [VehiclePosition("side.1", 50.0, 3.0)]
    main = [
        VehiclePosition("too_close", 20.0),
        VehiclePosition("selected", 60.0),
        VehiclePosition("farther", 120.0),
        VehiclePosition("too_far", 200.0),
    ]

    assert select_yield_vehicle(side, main, SETTINGS) == "selected"
