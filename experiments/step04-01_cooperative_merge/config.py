DEFAULT_TOTAL_RATES = [1000]
DEFAULT_DEMAND_RATIOS = ["1:2", "1:3"]
DEFAULT_STRATEGIES = ["uncontrolled", "cooperative"]
DEFAULT_DURATION = 1800.0
DEFAULT_CLEARANCE_TIME = 600.0
DEFAULT_SEEDS = [1, 2, 3, 4, 5]

# A side vehicle must be near the merge and waiting before cooperation starts.
SIDE_ACTIVATION_DISTANCE_M = 80.0
SIDE_WAIT_THRESHOLD_S = 2.0

# Slow one approaching mainline vehicle to create a usable gap ahead of it.
MAIN_CONTROL_DISTANCE_M = 180.0
MAIN_MIN_DISTANCE_M = 40.0
COOPERATIVE_SPEED_M_S = 15.0
