"""
WinterRoad - Uncertainty-Aware Prioritization Experiment
Compares standard risk scoring vs. confidence-weighted expected risk scoring:
  Risk_expected = (sum(w_c * area * conf) * 20) * Traffic_weight
Evaluates plan stability (Jaccard similarity) and ranking shifts.

Saves results to: results/uncertainty_prioritization.json

Team: WinterBorn
Authors: B K Kesavkrishnan, S Arun Kumar
"""
import argparse
import json
import os
import sys
import pandas as pd

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from winterroad_config import CLASS_WEIGHT_MAP, compute_traffic_weight, compute_repair_cost
from scripts.compare_prioritization import solve_knapsack

def main():
    parser = argparse.ArgumentParser(description="Uncertainty-Aware Prioritization")
    parser.add_argument("--csv", default=os.path.join(_ROOT, "data", "sample_detections_synthetic.csv"))
    parser.add_argument("--budget", type=float, default=500000.0)
    parser.add_argument("--output", default=os.path.join(_ROOT, "results", "uncertainty_prioritization.json"))
    args = parser.parse_args()

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    df_raw = pd.read_csv(args.csv)

    segments = []
    for sid, group in df_raw.groupby("segment", sort=False):
        road_type = str(group["road_type"].iloc[0])
        tw = compute_traffic_weight(road_type)
        dets = list(zip(group["cls"], group["area"], group["conf"]))

        # Standard severity (unweighted by confidence)
        sev_std = min(10.0, sum(CLASS_WEIGHT_MAP.get(int(c), 0.5) * float(a) for c, a, _ in dets) * 20.0)
        risk_std = round(sev_std * tw, 2)

        # Confidence-weighted expected severity
        sev_exp = min(10.0, sum(CLASS_WEIGHT_MAP.get(int(c), 0.5) * float(a) * float(cf) for c, a, cf in dets) * 20.0)
        risk_exp = round(sev_exp * tw, 2)

        cost = compute_repair_cost([[int(c), float(a)] for c, a, _ in dets])

        segments.append({
            "segment": str(sid),
            "road_type": road_type,
            "traffic_w": tw,
            "cost": cost,
            "risk_deterministic": risk_std,
            "risk_uncertainty_aware": risk_exp,
            "mean_confidence": round(float(group["conf"].mean()), 3)
        })

    df = pd.DataFrame(segments)

    # Solve knapsack for both formulations
    opt_std = solve_knapsack(df["cost"].tolist(), df["risk_deterministic"].tolist(), args.budget)
    opt_exp = solve_knapsack(df["cost"].tolist(), df["risk_uncertainty_aware"].tolist(), args.budget)

    set_std = set(df.loc[opt_std, "segment"])
    set_exp = set(df.loc[opt_exp, "segment"])

    jaccard = len(set_std & set_exp) / len(set_std | set_exp) if (set_std | set_exp) else 1.0
    swapped_out = list(set_std - set_exp)
    swapped_in = list(set_exp - set_std)

    result = {
        "data_source": "synthetic",
        "budget_inr": args.budget,
        "total_segments": len(df),
        "deterministic_plan_size": len(set_std),
        "uncertainty_aware_plan_size": len(set_exp),
        "plan_jaccard_similarity": round(jaccard, 3),
        "overlap_count": len(set_std & set_exp),
        "removed_under_uncertainty": swapped_out,
        "added_under_uncertainty": swapped_in,
        "interpretation": (
            f"Under budget ₹{args.budget/1e5:.1f} L, the plans share {len(set_std & set_exp)} segments "
            f"with Jaccard stability of {jaccard:.1%}. Factoring detector confidence discounts low-confidence "
            f"detections, swapping {len(swapped_out)} segments for higher-certainty alternatives."
        )
    }

    with open(args.output, "w") as f:
        json.dump(result, f, indent=2)

    print(f"Plan stability (Jaccard): {jaccard:.1%}")
    print(f"Swapped out: {swapped_out} | Swapped in: {swapped_in}")
    print(f"Saved results to {args.output}")

if __name__ == "__main__":
    main()
