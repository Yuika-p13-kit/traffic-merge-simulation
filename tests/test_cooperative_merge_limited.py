import importlib.util
import sys
from pathlib import Path

MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "step04-02_cooperative_merge"
    / "controller.py"
)
SPEC = importlib.util.spec_from_file_location("step04_02_controller", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

LimitedCooperativeController = MODULE.LimitedCooperativeController
LimitedSettings = MODULE.LimitedSettings
VehicleState = MODULE.VehicleState

SETTINGS = LimitedSettings(80.0, 2.0, 180.0, 40.0, 2.0, 8.0, 22.5, 8.0, 8.0)


def test_limited_controller_releases_after_side_merge_and_observes_cooldown() -> None:
    controller = LimitedCooperativeController(SETTINGS)
    side = [VehicleState("side.1", 40.0, 0.0, 3.0)]
    main = [VehicleState("main.1", 90.0, 20.0)]

    assert controller.select_candidate(10.0, side, main) == "main.1"
    assert controller.target_side_vehicle == "side.1"
    assert controller.observe(12.0, {"side.1"}, active_vehicle_present=True) == "main.1"
    assert controller.successful_releases == 1
    assert controller.select_candidate(15.0, side, main) is None
    assert controller.select_candidate(21.0, side, main) == "main.1"


def test_limited_controller_ignores_non_conflicting_arrival_time() -> None:
    controller = LimitedCooperativeController(SETTINGS)
    side = [VehicleState("side.1", 40.0, 0.0, 3.0)]

    assert controller.select_candidate(0.0, side, [VehicleState("too_soon", 45.0, 30.0)]) is None
    assert controller.select_candidate(0.0, side, [VehicleState("too_late", 180.0, 10.0)]) is None
