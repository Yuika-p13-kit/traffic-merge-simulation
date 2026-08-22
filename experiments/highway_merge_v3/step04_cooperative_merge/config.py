"""Initial limited-intervention settings for highway_merge_v3 Step 4."""

DEFAULT_TOTAL_RATES = [3950]
DEFAULT_DEMAND_RATIOS = ["1:2"]
DEFAULT_STRATEGIES = ["uncontrolled", "cooperative_limited"]
DEFAULT_SEEDS = [7, 42, 99, 123, 2026]
DEFAULT_DURATION_S = 1800.0
DEFAULT_CLEARANCE_TIME_S = 600.0

# Distances are upstream from the end of the 600 m parallel merge section.
# Ramp vehicles may prepare their lane change throughout the 600 m parallel
# section, well before the lane drop at its end.
RAMP_ACTIVATION_DISTANCE_M = 606.0
# The v3 bottleneck first appears as upstream insertion delay, so a moving ramp
# vehicle near the lane drop is the actionable signal rather than stopped time.
RAMP_WAIT_THRESHOLD_S = 0.0
MAIN_MIN_DISTANCE_M = 80.0
MAIN_CONTROL_DISTANCE_M = 500.0
MIN_CONFLICT_ETA_S = 3.0
MAX_CONFLICT_ETA_S = 20.0
MAX_PAIR_ETA_GAP_S = 3.0
COOPERATIVE_SPEED_M_S = 20.0
MAX_INTERVENTION_S = 7.0
COOLDOWN_S = 8.0
