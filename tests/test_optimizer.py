"""
Unit tests for WinterRoad 0/1 Knapsack Optimizer and Baseline Strategies.
Contains small, hand-checkable mathematical cases with provable analytical solutions.

Team: WinterBorn
Authors: B K Kesavkrishnan, S Arun Kumar
"""
import unittest
import numpy as np
import pandas as pd
import sys
import os

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from scripts.compare_prioritization import (
    solve_knapsack, solve_worst_first, solve_benefit_cost, solve_complaint_order
)

class TestKnapsackOptimizer(unittest.TestCase):

    def test_provable_knapsack_advantage(self):
        """
        Hand-checkable counterexample proving Knapsack strictly beats Greedy Worst-First:
        - Segment A: Cost Rs 3,000, Risk 25.0  (Severity highest)
        - Segment B: Cost Rs 2,000, Risk 16.0
        - Segment C: Cost Rs 2,000, Risk 16.0
        - Budget: Rs 4,000

        Worst-First greedily picks Segment A (cost 3000, risk 25), leaving Rs 1000.
        Neither B nor C fits in Rs 1000.
        Total Risk removed by Worst-First = 25.0.

        Knapsack picks Segment B + Segment C (cost 2000 + 2000 = 4000 <= 4000).
        Total Risk removed by Knapsack = 16.0 + 16.0 = 32.0.
        Knapsack strictly beats Worst-First: 32.0 > 25.0 (+28% risk removed).
        """
        costs = [3000, 2000, 2000]
        risks = [25.0, 16.0, 16.0]
        budget = 4000

        # Knapsack
        chosen_ks = solve_knapsack(costs, risks, budget, unit=1000)
        self.assertCountEqual(chosen_ks, [1, 2], "Knapsack must select items B and C")
        self.assertEqual(sum(risks[i] for i in chosen_ks), 32.0)

        # Worst-First
        df = pd.DataFrame({
            "severity": [10.0, 6.0, 6.0], # A is worst
            "cost": costs,
            "risk": risks,
            "complaint_order": [1, 2, 3]
        })
        chosen_wf = solve_worst_first(df, budget)
        self.assertCountEqual(chosen_wf, [0], "Worst-first greedily picks only item A")
        self.assertEqual(sum(risks[i] for i in chosen_wf), 25.0)

        # Assertion: Knapsack mathematically superior
        self.assertGreater(sum(risks[i] for i in chosen_ks), sum(risks[i] for i in chosen_wf))

    def test_zero_budget_edge_case(self):
        """Zero budget must result in empty plan without throwing exceptions."""
        costs = [10000, 20000]
        risks = [5.0, 10.0]
        chosen = solve_knapsack(costs, risks, budget=0, unit=1000)
        self.assertEqual(chosen, [])

    def test_cost_exceeds_entire_budget(self):
        """Segments exceeding budget cannot be selected."""
        costs = [50000]
        risks = [10.0]
        chosen = solve_knapsack(costs, risks, budget=10000, unit=1000)
        self.assertEqual(chosen, [])

    def test_all_items_fit(self):
        """When budget is abundant, all segments must be funded."""
        costs = [1000, 2000, 3000]
        risks = [4.0, 5.0, 6.0]
        chosen = solve_knapsack(costs, risks, budget=10000, unit=1000)
        self.assertCountEqual(chosen, [0, 1, 2])

    def test_complaint_order_fcfs(self):
        """Complaint order picks items strictly by chronological ticket order."""
        df = pd.DataFrame({
            "cost": [2000, 2000, 2000],
            "severity": [3.0, 9.0, 8.0],
            "complaint_order": [1, 2, 3]
        })
        chosen = solve_complaint_order(df, budget=4000)
        self.assertCountEqual(chosen, [0, 1], "FCFS must pick ticket 1 and 2")

if __name__ == "__main__":
    unittest.main()
