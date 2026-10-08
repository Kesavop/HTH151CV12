"""
WinterRoad - Prioritization Comparison Benchmark
Compares four repair selection strategies across a budget sweep:
  1. Complaint-Order (First-Come, First-Served across 500 random arrival orders)
  2. Worst-First Greedy (Severity order under identical discrete ceiling costs)
  3. Benefit-per-Cost Greedy (Risk / Cost ratio under identical discrete ceiling costs)
  4. 0/1 Knapsack Optimizer (Dynamic Programming)

Saves results to:
  - results/prioritization_comparison.csv
  - results/complaint_order_distribution.json
  - results/unfunded_reasons.csv
  - results/prioritization_curve.png

Team: WinterBorn
Authors: B K Kesavkrishnan, S Arun Kumar
"""
import argparse
import json
import os
import sys
import numpy as np
import pandas as pd

# Avoid Matplotlib font cache rebuild overhead
os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from winterroad_config import (
    compute_severity, compute_repair_cost, compute_traffic_weight,
    compute_risk, DISCRETIZATION_UNIT
)

def load_dataset(csv_path):
    """Loads detections CSV and groups by segment."""
    df = pd.read_csv(csv_path)
    segments = []
    for sid, group in df.groupby("segment", sort=False):
        road_type = str(group["road_type"].iloc[0])
        lat = float(group["lat"].iloc[0])
        lon = float(group["lon"].iloc[0])
        dets = [[int(c), float(a)] for c, a in zip(group["cls"], group["area"])]
        sev = compute_severity(dets)
        cost = compute_repair_cost(dets)
        tw = compute_traffic_weight(road_type)
        risk = compute_risk(sev, tw)
        segments.append({
            "segment": str(sid),
            "road_type": road_type,
            "lat": lat,
            "lon": lon,
            "severity": sev,
            "cost": cost,
            "traffic_w": tw,
            "risk": risk,
            "bpc": round(risk / max(cost, 1) * 1e5, 3), # benefit per lakh
            "complaint_order": len(segments) + 1
        })
    return pd.DataFrame(segments)

def solve_knapsack(costs, values, budget, unit=DISCRETIZATION_UNIT):
    """0/1 Knapsack dynamic programming using discrete ceiling units."""
    c = np.ceil(np.array(costs) / unit).astype(int)
    B = int(budget // unit)
    dp = np.zeros(B + 1)
    keep = np.zeros((len(c), B + 1), bool)
    for i in range(len(c)):
        if c[i] > B:
            continue
        cand = np.full(B + 1, -1.0)
        cand[c[i]:] = dp[:B + 1 - c[i]] + values[i]
        keep[i] = cand > dp
        dp = np.maximum(dp, cand)
    chosen, b = [], B
    for i in range(len(c) - 1, -1, -1):
        if keep[i][b]:
            chosen.append(i)
            b -= c[i]
    return chosen

def solve_worst_first(df, budget, unit=DISCRETIZATION_UNIT):
    """Greedy by physical severity under identical discrete ceiling costs."""
    if unit is not None and unit > 0:
        B = int(budget // unit)
        c = np.ceil(df["cost"].values / unit).astype(int)
        chosen, spent = [], 0
        for i in df.sort_values("severity", ascending=False).index:
            pos = df.index.get_loc(i)
            if spent + c[pos] <= B:
                chosen.append(i)
                spent += c[pos]
        return chosen
    else:
        chosen, spent = [], 0
        for i in df.sort_values("severity", ascending=False).index:
            if spent + df.loc[i, "cost"] <= budget:
                chosen.append(i)
                spent += df.loc[i, "cost"]
        return chosen

def solve_benefit_cost(df, budget, unit=DISCRETIZATION_UNIT):
    """Greedy by benefit-per-cost ratio (risk / cost) under identical discrete ceiling costs."""
    if unit is not None and unit > 0:
        B = int(budget // unit)
        c = np.ceil(df["cost"].values / unit).astype(int)
        chosen, spent = [], 0
        ratios = df["risk"] / df["cost"]
        for i in ratios.sort_values(ascending=False).index:
            pos = df.index.get_loc(i)
            if spent + c[pos] <= B:
                chosen.append(i)
                spent += c[pos]
        return chosen
    else:
        chosen, spent = [], 0
        ratios = df["risk"] / df["cost"]
        for i in ratios.sort_values(ascending=False).index:
            if spent + df.loc[i, "cost"] <= budget:
                chosen.append(i)
                spent += df.loc[i, "cost"]
        return chosen

def solve_complaint_order(df, budget, unit=DISCRETIZATION_UNIT):
    """Single-run complaint order under identical discrete ceiling costs."""
    if unit is not None and unit > 0:
        B = int(budget // unit)
        c = np.ceil(df["cost"].values / unit).astype(int)
        chosen, spent = [], 0
        for i in df.sort_values("complaint_order", ascending=True).index:
            pos = df.index.get_loc(i)
            if spent + c[pos] <= B:
                chosen.append(i)
                spent += c[pos]
        return chosen
    else:
        chosen, spent = [], 0
        for i in df.sort_values("complaint_order", ascending=True).index:
            if spent + df.loc[i, "cost"] <= budget:
                chosen.append(i)
                spent += df.loc[i, "cost"]
        return chosen

def evaluate_complaint_order_distribution(df, budget=500000.0, num_permutations=500, seed=42, unit=DISCRETIZATION_UNIT):
    """
    Evaluates complaint-order allocation over randomized arrival permutations.
    Returns mean, std, min, and max % risk removed across trials.
    """
    total_risk = df["risk"].sum()
    B = int(budget // unit)
    c = np.ceil(df["cost"].values / unit).astype(int)
    rng = np.random.default_rng(seed)

    trials_pct = []
    n = len(df)
    for _ in range(num_permutations):
        perm = rng.permutation(n)
        spent = 0
        chosen = []
        for idx in perm:
            if spent + c[idx] <= B:
                chosen.append(idx)
                spent += c[idx]
        risk_sum = df.iloc[chosen]["risk"].sum()
        trials_pct.append(risk_sum / total_risk * 100.0)

    trials_arr = np.array(trials_pct)
    return {
        "budget_inr": budget,
        "num_permutations": num_permutations,
        "mean_pct": round(float(np.mean(trials_arr)), 2),
        "std_pct": round(float(np.std(trials_arr)), 2),
        "min_pct": round(float(np.min(trials_arr)), 2),
        "max_pct": round(float(np.max(trials_arr)), 2),
        "range_str": f"[{np.min(trials_arr):.1f}%, {np.max(trials_arr):.1f}%]"
    }

def generate_unfunded_reason(row, budget, min_funded_risk):
    """Provides human-readable municipal justification for why a road was not funded."""
    if row["cost"] > budget:
        return f"Exceeds total available budget (Cost: ₹{row['cost']:,})"
    if row["severity"] >= 6.0 and row["traffic_w"] < 0.8:
        return f"Severe defect ({row['severity']}/10), but low-volume {row['road_type'].lower()} road"
    if row["risk"] >= min_funded_risk:
        return f"High cost (₹{row['cost']/1e5:.2f} L) would displace multiple higher-yield repairs"
    return f"Lower risk reduction per rupee than funded repairs (Ratio: {row['bpc']:.1f})"

def main():
    parser = argparse.ArgumentParser(description="WinterRoad Prioritization Strategy Comparison")
    parser.add_argument("--csv", default=os.path.join(_ROOT, "data", "sample_detections_synthetic.csv"))
    parser.add_argument("--budget", type=float, default=500000.0, help="Focal budget in INR")
    parser.add_argument("--outdir", default=os.path.join(_ROOT, "results"))
    args = parser.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    df = load_dataset(args.csv)
    total_risk = df["risk"].sum()
    total_cost = df["cost"].sum()

    print(f"Loaded {len(df)} segments from {args.csv}")
    print(f"Total Network Risk: {total_risk:.2f} | Total Cost to Fix All: ₹{total_cost:,.0f}")

    # 1. Budget Sweep Evaluation
    budget_sweep = np.arange(100000, 2100000, 100000) # 1 Lakh to 20 Lakh
    sweep_rows = []

    for b in budget_sweep:
        idx_ks = solve_knapsack(df["cost"].tolist(), df["risk"].tolist(), b)
        idx_wf = solve_worst_first(df, b)
        idx_bpc = solve_benefit_cost(df, b)
        # For complaint order in sweep, compute distribution over 100 permutations per budget step
        co_dist = evaluate_complaint_order_distribution(df, budget=b, num_permutations=100)

        sweep_rows.append({
            "budget_inr": b,
            "budget_lakh": b / 1e5,
            "knapsack_risk_pct": round(df.iloc[idx_ks]["risk"].sum() / total_risk * 100.0, 2),
            "benefit_cost_risk_pct": round(df.loc[idx_bpc]["risk"].sum() / total_risk * 100.0, 2),
            "worst_first_risk_pct": round(df.loc[idx_wf]["risk"].sum() / total_risk * 100.0, 2),
            "complaint_order_risk_pct": co_dist["mean_pct"],
            "complaint_order_min_pct": co_dist["min_pct"],
            "complaint_order_max_pct": co_dist["max_pct"],
            "knapsack_segments": len(idx_ks),
            "benefit_cost_segments": len(idx_bpc),
            "worst_first_segments": len(idx_wf),
            "complaint_order_segments_mean": int(round(np.mean([len(idx_wf), len(idx_bpc)]))),
            "data_source": "synthetic"
        })

    sweep_df = pd.DataFrame(sweep_rows)
    sweep_csv_path = os.path.join(args.outdir, "prioritization_comparison.csv")
    sweep_df.to_csv(sweep_csv_path, index=False)
    print(f"Saved budget sweep comparison to {sweep_csv_path}")

    # 2. Focal Plan and Complaint-Order Distribution (500 orderings)
    focal_ks = solve_knapsack(df["cost"].tolist(), df["risk"].tolist(), args.budget)
    focal_wf = solve_worst_first(df, args.budget)
    focal_bpc = solve_benefit_cost(df, args.budget)
    focal_co_dist = evaluate_complaint_order_distribution(df, budget=args.budget, num_permutations=500)

    focal_co_json_path = os.path.join(args.outdir, "complaint_order_distribution.json")
    with open(focal_co_json_path, "w") as f:
        json.dump(focal_co_dist, f, indent=2)
    print(f"Saved 500-permutation complaint order distribution to {focal_co_json_path}")

    ks_pct = round(df.iloc[focal_ks]["risk"].sum() / total_risk * 100.0, 2)
    wf_pct = round(df.loc[focal_wf]["risk"].sum() / total_risk * 100.0, 2)
    bpc_pct = round(df.loc[focal_bpc]["risk"].sum() / total_risk * 100.0, 2)

    print(f"\nFocal ₹{args.budget/1e5:.1f} Lakh Prioritization Results:")
    print(f"  0/1 Knapsack Optimizer:   {ks_pct}% risk removed ({len(focal_ks)} segments)")
    print(f"  Benefit-Cost Greedy:      {bpc_pct}% risk removed ({len(focal_bpc)} segments)")
    print(f"  Worst-First (Severity):   {wf_pct}% risk removed ({len(focal_wf)} segments)")
    print(f"  Complaint-Order (500 FCFS): Mean {focal_co_dist['mean_pct']}%, range {focal_co_dist['range_str']}")

    df["funded_knapsack"] = df.index.isin(focal_ks)
    min_funded_risk = df.loc[df["funded_knapsack"], "risk"].min() if df["funded_knapsack"].any() else 0.0

    unfunded = df[~df["funded_knapsack"]].copy().sort_values("risk", ascending=False)
    unfunded["unfunded_reason"] = unfunded.apply(
        lambda r: generate_unfunded_reason(r, args.budget, min_funded_risk), axis=1
    )
    unfunded["data_source"] = "synthetic"
    unfunded_csv_path = os.path.join(args.outdir, "unfunded_reasons.csv")
    unfunded[["segment", "road_type", "severity", "cost", "risk", "unfunded_reason", "data_source"]].to_csv(
        unfunded_csv_path, index=False
    )
    print(f"Saved unfunded explanations for ₹{args.budget/1e5:.1f} L to {unfunded_csv_path}")

    # 3. Plot Budget Sweep Curves
    plt.figure(figsize=(10, 6))
    plt.plot(sweep_df["budget_lakh"], sweep_df["knapsack_risk_pct"], "o-", color="#1f77b4", linewidth=2.5, label="0/1 Knapsack Optimizer (WinterRoad)")
    plt.plot(sweep_df["budget_lakh"], sweep_df["benefit_cost_risk_pct"], "^--", color="#2ca02c", linewidth=2.0, label="Benefit-per-Cost Greedy")
    plt.plot(sweep_df["budget_lakh"], sweep_df["worst_first_risk_pct"], "s-.", color="#d62728", linewidth=2.0, label="Worst-First Greedy (Severity)")
    plt.plot(sweep_df["budget_lakh"], sweep_df["complaint_order_risk_pct"], "x:", color="#7f7f7f", linewidth=1.8, label="Complaint-Order Mean (Random FCFS)")
    plt.fill_between(
        sweep_df["budget_lakh"],
        sweep_df["complaint_order_min_pct"],
        sweep_df["complaint_order_max_pct"],
        color="#7f7f7f", alpha=0.15, label="Complaint-Order Range [Min, Max]"
    )
    
    plt.axvline(args.budget / 1e5, color="black", linestyle=":", alpha=0.7, label=f"Focal Budget (₹{args.budget/1e5:.1f} L)")
    plt.xlabel("Maintenance Budget (Lakh INR)", fontsize=12, fontweight="bold")
    plt.ylabel("% Total Network Risk Removed", fontsize=12, fontweight="bold")
    plt.title("Road Repair Strategy Comparison vs. Budget [SIMULATED DATA]", fontsize=13, fontweight="bold")
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.legend(fontsize=10, loc="lower right")
    plt.tight_layout()

    plot_path = os.path.join(args.outdir, "prioritization_curve.png")
    plt.savefig(plot_path, dpi=200)
    plt.close()
    print(f"Saved prioritization curve plot to {plot_path}")

if __name__ == "__main__":
    main()
