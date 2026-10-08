"""
WinterRoad configuration module.
Loads unified parameters from config.json and provides shared constants and helpers.
Team: WinterBorn
Members: B K Kesavkrishnan, S Arun Kumar
"""
import json
import os
import numpy as np

# Find root directory containing config.json
_ROOT = os.path.dirname(os.path.abspath(__file__))
_CONFIG_PATH = os.path.join(_ROOT, "config.json")

def load_config(path=None):
    target = path or _CONFIG_PATH
    if not os.path.exists(target):
        # Look one level up if called from subdirectory
        parent = os.path.join(os.path.dirname(target), "..", "config.json")
        if os.path.exists(parent):
            target = parent
    with open(target, "r") as f:
        return json.load(f)

CONFIG = load_config()

# Damage classes
CLASSES = CONFIG["classes"]
CODES = [CLASSES[k]["code"] for k in sorted(CLASSES.keys())]
CLASS_NAME = [CLASSES[k]["name"] for k in sorted(CLASSES.keys())]
CLASS_WEIGHT = [CLASSES[k]["danger_weight"] for k in sorted(CLASSES.keys())]
UNIT_COST = [CLASSES[k]["unit_cost_inr_per_m2"] for k in sorted(CLASSES.keys())]

# Map dictionaries
CLASS_NAME_MAP = {CLASSES[k]["id"]: CLASSES[k]["name"] for k in CLASSES}
CLASS_WEIGHT_MAP = {CLASSES[k]["id"]: CLASSES[k]["danger_weight"] for k in CLASSES}
UNIT_COST_MAP = {CLASSES[k]["id"]: CLASSES[k]["unit_cost_inr_per_m2"] for k in CLASSES}
COLOR_MAP = {CLASSES[k]["id"]: CLASSES[k]["color"] for k in CLASSES}

# Cost parameters
COSTS = CONFIG["costs"]
FIXED_COST = COSTS["fixed_mobilization_cost_inr"]
IMG_AREA_M2 = COSTS["photo_coverage_area_m2"]
DISCRETIZATION_UNIT = COSTS["cost_discretization_unit_inr"]
COST_UNCERTAINTY_STD_PCT = COSTS.get("cost_uncertainty_std_pct", 0.15)

# Traffic parameters
TRAFFIC_CONFIG = CONFIG["traffic"]
ROAD_TYPES = {k: TRAFFIC_CONFIG[k]["vehicles_per_day"] for k in TRAFFIC_CONFIG}
TRAFFIC_WEIGHTS = {k: TRAFFIC_CONFIG[k]["weight"] for k in TRAFFIC_CONFIG}
MAX_TRAFFIC = max(ROAD_TYPES.values()) if ROAD_TYPES else 30000

# Facility multipliers
FACILITY_BOOSTS = CONFIG["facility_boosts"]
OSM_ROAD_CLASSES = CONFIG["osm_road_classes"]

# Privacy & Rate Limit
PRIVACY = CONFIG["privacy"]
RATE_LIMIT = CONFIG["rate_limit"]
GPS_VALIDATION = CONFIG["gps_validation"]

def compute_traffic_weight(road_type: str) -> float:
    """Returns log-normalized traffic weight for a road type."""
    if road_type in TRAFFIC_WEIGHTS:
        return float(TRAFFIC_WEIGHTS[road_type])
    vol = ROAD_TYPES.get(road_type, 1000)
    return round(float(np.log10(vol) / np.log10(MAX_TRAFFIC)), 2)

def compute_severity(detections) -> float:
    """
    Compute 0-10 severity proxy from normalized bbox areas.
    detections: list of [cls_id, area] or [cls_id, area, conf]
    """
    raw_sum = sum(CLASS_WEIGHT_MAP.get(int(c), 0.5) * float(a) for c, a, *_ in detections)
    return round(float(min(10.0, raw_sum * 20.0)), 2)

def compute_repair_cost(detections, noise_factor: float = 1.0) -> int:
    """
    Compute estimated repair cost in INR.
    cost = Fixed site mobilization (₹15,000) + sum(unit_rate * area * img_m2 * scaling)
    Assumptions:
      - img_m2 = IMG_AREA_M2 (20 m²): Assumed pavement area captured per photo frame.
      - scaling = 10: Engineering scaling factor converting 2D normalized bbox area
        into the estimated excavation, milling, and tack coat envelope (saw-cutting buffer assumption).
      - noise_factor: Optional scalar to simulate cost uncertainty shocks.
    """
    variable = sum(UNIT_COST_MAP.get(int(c), 1000) * float(a) * IMG_AREA_M2 * 10 for c, a, *_ in detections)
    total = (FIXED_COST + variable) * noise_factor
    return int(round(total))

def compute_risk(severity: float, traffic_weight: float, facility_multiplier: float = 1.0) -> float:
    """Compute composite risk score."""
    return round(float(severity * traffic_weight * facility_multiplier), 2)
