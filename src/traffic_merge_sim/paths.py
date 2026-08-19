from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SUMO_DIR = PROJECT_ROOT / "sumo"
GENERATED_OUTPUT_DIR = SUMO_DIR / "output" / "generated"
# Compatibility alias for the closed intersection-style study.  New work must
# select a MergeNetworkConfig explicitly.
NETWORK_PATH = SUMO_DIR / "network" / "minimal_merge.net.xml"
