"""
WinterRoad - Multi-Month Sequential Budget Planning Simulation
Simulates rolling multi-month maintenance planning across 6 months.
In each month, an allocated budget tranche is spent, funded roads are repaired,
new defect reports arrive dynamically, and the knapsack optimizer re-plans.

Outputs:
  - results/multimonth_planning.json
  - results/multimonth_planning.png

Team: WinterBorn
Authors: B K Kesavkrishnan, S Arun Kumar
"""
import argparse
import json
import os
import sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from scripts.compare_prioritization import load_dataset, solve_knapsack

def run_multimonth_simulation(csv_path, total_budget=1200000.0, months=6, seed=42):
    rng = np.random.default_rng(seed)
    initial_df = load_dataset(csv_path)

    monthly_tranche = total_budget / months
    active_backlog = initial_df.copy()
    monthly_logs = []

    cumulative_repaired_segments = 0
    cumulative_spend = 0.0

    for m in range(1, months + 1):
        backlog_count = len(active_backlog)
        backlog_risk = active_backlog["risk"].sum()

        # Run Knapsack for current month
        opt_idx = solve_knapsack(
            active_backlog["cost"].tolist(),
            active_backlog["risk"].tolist(),
            monthly_tranche
        )
        funded = active_backlog.iloc[opt_idx]
        spent = funded["cost"].sum()
        risk_removed = funded["risk"].sum()

        cumulative_repaired_segments += len(funded)
        cumulative_spend += spent

        # Remove repaired roads from backlog
        repaired_ids = set(funded["segment"])
        remaining_backlog = active_backlog[~active_backlog["segment"].isin(repaired_ids)].copy()

        # New defects arrive (e.g. 3 to 6 new defects reported this month)
        new_arrivals_count = rng.integers(3, 7) if m < months else 0
        new_rows = []
        for a in range(new_arrivals_count):
            proto = initial_df.sample(1, random_state=int(rng.integers(0, 10000))).iloc[0]
            new_id = f"M{m}-ARR-{a+1:02d}"
            new_rows.append({
                "segment": new_id,
                "road_type": proto["road_type"],
                "lat": proto["lat"] + float(rng.uniform(-0.01, 0.01)),
                "lon": proto["lon"] + float(rng.uniform(-0.01, 0.01)),
                "severity": round(float(rng.uniform(2.0, 7.5)), 2),
                "cost": int(round(proto["cost"] * rng.uniform(0.8, 1.2))),
                "traffic_w": proto["traffic_w"],
                "risk": round(float(proto["traffic_w"] * rng.uniform(2.0, 7.5)), 2),
                "bpc": round(float(proto["bpc"] * rng.uniform(0.8, 1.2)), 2),
                "complaint_order": 999
            })

        if new_rows:
            active_backlog = pd.concat([remaining_backlog, pd.DataFrame(new_rows)], ignore_index=True)
        else:
            active_backlog = remaining_backlog.reset_index(drop=True)

        monthly_logs.append({
            "month": int(m),
            "starting_backlog_segments": int(backlog_count),
            "starting_backlog_risk": round(float(backlog_risk), 2),
            "budget_allocated_inr": float(monthly_tranche),
            "budget_spent_inr": int(spent),
            "segments_repaired": int(len(funded)),
            "risk_eliminated": round(float(risk_removed), 2),
            "new_defects_reported": int(new_arrivals_count),
            "ending_backlog_segments": int(len(active_backlog)),
            "ending_backlog_risk": round(float(active_backlog["risk"].sum()), 2)
        })

    summary = {
        "data_source": "synthetic",
        "simulation_months": int(months),
        "total_authorized_budget_inr": float(total_budget),
        "total_spent_inr": int(cumulative_spend),
        "total_repaired_segments": int(cumulative_repaired_segments),
        "initial_backlog": int(len(initial_df)),
        "final_remaining_backlog": int(len(active_backlog)),
        "monthly_progression": monthly_logs
    }
    return summary, monthly_logs

def main():
    parser = argparse.ArgumentParser(description="Multi-Month Rolling Budget Planning")
    parser.add_argument("--csv", default=os.path.join(_ROOT, "data", "sample_detections_synthetic.csv"))
    parser.add_argument("--budget", type=float, default=1200000.0)
    parser.add_argument("--months", type=int, default=6)
    parser.add_argument("--output-json", default=os.path.join(_ROOT, "results", "multimonth_planning.json"))
    parser.add_argument("--output-plot", default=os.path.join(_ROOT, "results", "multimonth_planning.png"))
    args = parser.parse_args()

    os.makedirs(os.path.dirname(args.output_json), exist_ok=True)
    summary, logs = run_multimonth_simulation(args.csv, total_budget=args.budget, months=args.months)

    with open(args.output_json, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"Multi-Month Simulation ({args.months} Months):")
    print(f"  Total Repaired: {summary['total_repaired_segments']} segments")
    print(f"  Total Spend: Rs {summary['total_spent_inr']:,} / Rs {args.budget:,.0f}")
    print(f"  Backlog reduced from {summary['initial_backlog']} to {summary['final_remaining_backlog']} segments")

    # Plot Multi-Month Progression
    df_logs = pd.DataFrame(logs)
    fig, ax1 = plt.subplots(figsize=(9, 5))

    color1 = "#1f77b4"
    ax1.set_xlabel("Planning Month", fontweight="bold")
    ax1.set_ylabel("Active Backlog Risk Score", color=color1, fontweight="bold")
    ax1.plot(df_logs["month"], df_logs["starting_backlog_risk"], "o-", color=color1, linewidth=2, label="Backlog Risk")
    ax1.tick_params(axis="y", labelcolor=color1)
    ax1.grid(True, linestyle="--", alpha=0.4)

    ax2 = ax1.twinx()
    color2 = "#2ca02c"
    ax2.set_ylabel("Segments Repaired per Month", color=color2, fontweight="bold")
    ax2.bar(df_logs["month"] + 0.15, df_logs["segments_repaired"], width=0.3, color=color2, alpha=0.7, label="Repaired Segments")
    ax2.tick_params(axis="y", labelcolor=color2)

    plt.title("WinterRoad Rolling 6-Month Planning & Dynamic Defect Arrival [SIMULATED DATA]", fontweight="bold")
    plt.tight_layout()
    plt.savefig(args.output_plot, dpi=200)
    plt.close()
    print(f"Saved results to {args.output_json} and {args.output_plot}")

if __name__ == "__main__":
    main()
