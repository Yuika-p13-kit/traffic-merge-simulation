from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
STEP = ROOT / "experiments" / "step06-02_on_demand_ramp_metering"
spec = importlib.util.spec_from_file_location("test_step06_02_controller", STEP / "controller.py")
assert spec and spec.loader
controller = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = controller
spec.loader.exec_module(controller)


def settings() -> object:
    return controller.OnDemandSettings(
        release_interval_s=4.0, min_main_vehicles=1,
        activation_speed_m_s=27.0, recovery_speed_m_s=29.0,
        activation_persistence_s=3.0, recovery_persistence_s=10.0,
        min_active_time_s=30.0,
    )


def test_meter_stays_off_during_free_flow() -> None:
    meter = controller.OnDemandRampMeter(settings())
    held, released = meter.update(0.0, [30.0, 30.0, 30.0], {"side.0": 330.0}, {"side.0"})
    assert not meter.active
    assert held == set()
    assert released == set()


def test_persistent_congestion_activates_and_meters_at_four_seconds() -> None:
    meter = controller.OnDemandRampMeter(settings())
    meter.update(0.0, [10.0, 12.0, 14.0], {}, set())
    meter.update(2.0, [10.0, 12.0, 14.0], {}, set())
    held, released = meter.update(
        3.0, [10.0, 12.0, 14.0], {"side.0": 330.0, "side.1": 320.0}, {"side.0"},
    )
    assert meter.active
    assert meter.activations == 1
    assert released == {"side.0"}
    assert held == {"side.1"}
    assert meter.update(6.9, [10.0, 12.0, 14.0], {"side.1": 330.0}, {"side.1"})[1] == set()
    assert meter.update(7.0, [10.0, 12.0, 14.0], {"side.1": 330.0}, {"side.1"})[1] == {"side.1"}


def test_recovery_respects_hysteresis_and_releases_held_vehicles() -> None:
    meter = controller.OnDemandRampMeter(settings())
    meter.update(0.0, [10.0, 10.0, 10.0], {}, set())
    meter.update(3.0, [10.0, 10.0, 10.0], {"side.0": 300.0}, set())
    meter.update(4.0, [30.0, 30.0, 30.0], {"side.0": 310.0}, set())
    held, released = meter.update(33.0, [30.0, 30.0, 30.0], {"side.0": 320.0}, set())
    assert not meter.active
    assert held == set()
    assert released == {"side.0"}


def test_vehicle_too_close_to_stop_is_not_newly_held() -> None:
    meter = controller.OnDemandRampMeter(settings())
    meter.update(0.0, [10.0], {}, set())
    held, released = meter.update(
        3.0, [10.0], {"early": 180.0, "late": 300.0}, set(), {"early"},
    )
    assert held == {"early"}
    assert released == set()
    assert "late" not in meter.registered


def test_invalid_speed_hysteresis_is_rejected() -> None:
    with pytest.raises(ValueError, match="recovery speed"):
        controller.OnDemandSettings(4.0, 3, 25.0, 20.0, 5.0, 10.0, 30.0)
