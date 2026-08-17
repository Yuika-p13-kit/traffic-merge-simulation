from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SUMO_DIR = PROJECT_ROOT / "sumo"
GENERATED_OUTPUT_DIR = SUMO_DIR / "output" / "generated"
NETWORK_PATH = SUMO_DIR / "network" / "minimal_merge.net.xml"
FIXED_CONTROL_NETWORK_PATH = SUMO_DIR / "network" / "fixed_control_merge.net.xml"
