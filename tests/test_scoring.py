"""
Unit tests for WinterRoad Cost, Severity, Traffic, and Risk Scoring Calculations.
Contains hand-checkable deterministic arithmetic tests.

Team: WinterBorn
Authors: B K Kesavkrishnan, S Arun Kumar
"""
import unittest
import sys
import os

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from winterroad_config import (
    compute_severity, compute_repair_cost, compute_traffic_weight,
    compute_risk, FIXED_COST, IMG_AREA_M2
)

class TestScoringCalculations(unittest.TestCase):

    def test_severity_calculation(self):
        """
        Severity formula: min(10.0, 20 * sum(w_c * area))
        - Defect: Pothole (cls 3, weight 1.0), normalized area 0.05
        - Expected: 20 * (1.0 * 0.05) = 1.00
        """
        dets = [[3, 0.05]]
        sev = compute_severity(dets)
        self.assertEqual(sev, 1.00)

    def test_severity_saturation_cap(self):
        """Massive defect area must be capped at 10.0 scale maximum."""
        dets = [[3, 0.80]] # 20 * (1.0 * 0.80) = 16.0 -> capped at 10.0
        sev = compute_severity(dets)
        self.assertEqual(sev, 10.0)

    def test_repair_cost_fixed_mobilization(self):
        """Empty detections must still incur fixed site mobilization cost."""
        cost = compute_repair_cost([])
        self.assertEqual(cost, FIXED_COST)
        self.assertEqual(cost, 15000)

    def test_repair_cost_variable_rate(self):
        """
        Unit rate test:
        - Defect: Pothole (cls 3, rate = Rs 2,500 / m2)
        - Area = 0.02
        - Image road area = 20 m2
        - Scaling factor = 10
        - Variable cost = 2500 * 0.02 * 20 * 10 = 10,000
        - Total cost = 15,000 + 10,000 = Rs 25,000
        """
        dets = [[3, 0.02]]
        cost = compute_repair_cost(dets)
        self.assertEqual(cost, 25000)

    def test_traffic_weight_hierarchy(self):
        """Highway traffic weight must exceed Arterial, Collector, and Local."""
        w_hw = compute_traffic_weight("Highway")
        w_art = compute_traffic_weight("Arterial")
        w_coll = compute_traffic_weight("Collector")
        w_loc = compute_traffic_weight("Local")

        self.assertEqual(w_hw, 1.00)
        self.assertGreater(w_hw, w_art)
        self.assertGreater(w_art, w_coll)
        self.assertGreater(w_coll, w_loc)

    def test_composite_risk_with_facility_boost(self):
        """
        Risk = Severity * Traffic_w * Facility_multiplier
        - Severity = 5.0
        - Traffic_w = 1.0 (Highway)
        - Hospital boost (+60% = 1.60)
        - Risk = 5.0 * 1.0 * 1.60 = 8.00
        """
        risk = compute_risk(severity=5.0, traffic_weight=1.0, facility_multiplier=1.60)
        self.assertEqual(risk, 8.00)

if __name__ == "__main__":
    unittest.main()
