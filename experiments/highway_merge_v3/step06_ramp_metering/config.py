DEFAULT_TOTAL_RATE = 3950
DEFAULT_DEMAND_RATIO = "1:2"
DEFAULT_DURATION_S = 1800.0
DEFAULT_CLEARANCE_TIME_S = 600.0
DEFAULT_SEEDS = [7, 42, 99, 123, 2026]
DEFAULT_STRATEGIES = ["uncontrolled", "cooperative_limited", "ramp_fixed_1s", "ramp_fixed_1_25s", "ramp_fixed_1_5s"]
METER_INTERVALS_S = {"ramp_fixed_1s": 1.0, "ramp_fixed_1_25s": 1.25, "ramp_fixed_1_5s": 1.5}
# The ramp is 547 m long; this leaves ample distance for a controlled stop.
METER_STOP_POSITION_M = 400.0
