"""
WinterRoad - Cost Uncertainty & Plan Stability Monte Carlo Simulation
Models repair cost stochasticity (e.g. material price volatility, site condition surprises)
using log-normal cost perturbations and budget draws over 500 simulations.
Categorizes road segments into Core, Marginal, and Unfunded buckets based on selection probability.

Saves results to:
  - results/cost_uncertainty_stability.json
  - results/cost_uncertainty_stability.png

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

def run_cost_simulation(csv_path, num_draws=500, std_dev_pct=0.15, seed=42):
    rng = np.random.default_rng(seed)
    df = load_dataset(csv_path)
    n = len(df)
    base_costs = df["cost"].values
    risks = df["risk"].values

    selection_counts = np.zeros(n, dtype=int)
    jaccards = []
    base_budget = 500000.0

    # Deterministic reference plan
    ref_idx = set(solve_knapsack(base_costs, risks, base_budget))

    for d in range(num_draws):
        # Sample log-normal multiplicative cost shocks (mean 1.0, std_dev)
        cost_shocks = rng.lognormal(mean=-0.5 * (std_dev_pct**2), sigma=std_dev_pct, size=n)
        draw_costs = np.round(base_costs * cost_shocks).astype(int)

        # Perturb budget slightly (+/- 10%)
        draw_budget = base_budget * rng.uniform(0.9, 1.1)

        chosen = set(solve_knapsack(draw_costs, risks, draw_budget))
        for idx in chosen:
            selection_counts[idx] += 1

        jacc = len(ref_idx & chosen) / len(ref_idx | chosen) if (ref_idx | chosen) else 1.0
        jaccards.append(jacc)

    selection_probs = selection_counts / num_draws

    df["selection_probability"] = selection_probs.round(3)
    df["robustness_category"] = np.where(
        selection_probs >= 0.75, "Core (Robust)",
        np.where(selection_probs >= 0.25, "Marginal (Price-Sensitive)", "Unfunded")
    )

    summary = {
        "data_source": "synthetic",
        "num_simulations": num_draws,
        "cost_volatility_sigma": std_dev_pct,
        "mean_jaccard_stability_to_base_plan": round(float(np.mean(jaccards)), 3),
        "std_jaccard_stability": round(float(np.std(jaccards)), 3),
        "core_segments_count": int((selection_probs >= 0.75).sum()),
        "marginal_segments_count": int(((selection_probs >= 0.25) & (selection_probs < 0.75)).sum()),
        "unfunded_segments_count": int((selection_probs < 0.25).sum()),
        "core_segments": df[df["robustness_category"] == "Core (Robust)"]["segment"].tolist(),
        "marginal_segments": df[df["robustness_category"] == "Marginal (Price-Sensitive)"]["segment"].tolist()
    }
    return df, summary, jaccards

def main():
    parser = argparse.ArgumentParser(description="WinterRoad Cost Uncertainty Simulation")
    parser.add_argument("--csv", default=os.path.join(_ROOT, "data", "sample_detections_synthetic.csv"))
    parser.add_argument("--draws", type=int, default=500)
    parser.add_argument("--output-json", default=os.path.join(_ROOT, "results", "cost_uncertainty_stability.json"))
    parser.add_argument("--output-plot", default=os.path.join(_ROOT, "results", "cost_uncertainty_stability.png"))
    args = parser.parse_args()

    os.makedirs(os.path.dirname(args.output_json), exist_ok=True)
    print(f"Running {args.draws} Monte Carlo cost uncertainty draws (sigma = 15%)...")
    df_res, summary, jaccards = run_cost_simulation(args.csv, num_draws=args.draws)

    with open(args.output_json, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"Mean Plan Stability: {summary['mean_jaccard_stability_to_base_plan']:.1%}")
    print(f"Core Segments ({summary['core_segments_count']}): {summary['core_segments']}")
    print(f"Marginal Segments ({summary['marginal_segments_count']}): {summary['marginal_segments']}")

    # Plot Selection Probabilities
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    
    # 1. Bar chart of selection probability per segment
    df_sorted = df_res.sort_values("selection_probability", ascending=False).reset_index()
    colors = ['#2ca02c' if c == 'Core (Robust)' else '#ff7f0e' if c == 'Marginal (Price-Sensitive)' else '#d62728'
              for c in df_sorted['robustness_category']]
    
    axes[0].bar(range(len(df_sorted)), df_sorted['selection_probability'], color=colors, edgecolor='black', alpha=0.85)
    axes[0].axhline(0.75, color='gray', linestyle='--', label='Core Threshold (75%)')
    axes[0].axhline(0.25, color='gray', linestyle=':', label='Marginal Threshold (25%)')
    axes[0].set_xlabel('Road Segments (Ranked by Stability)', fontweight='bold')
    axes[0].set_ylabel('Selection Probability in Simulation', fontweight='bold')
    axes[0].set_title('Repair Plan Stability Under Cost Volatility [SIMULATED DATA]', fontweight='bold')
    axes[0].set_ylim(0, 1.05)
    axes[0].legend()

    # 2. Histogram of Jaccard stability distribution
    axes[1].hist(jaccards, bins=20, color='#1f77b4', edgecolor='black', alpha=0.75)
    axes[1].axvline(np.mean(jaccards), color='red', linestyle='--', linewidth=2,
                    label=f"Mean Jaccard: {np.mean(jaccards):.2f}")
    axes[1].set_xlabel('Jaccard Similarity to Baseline Plan', fontweight='bold')
    axes[1].set_ylabel('Frequency', fontweight='bold')
    axes[1].set_title('Plan Stability Across Shocks [SIMULATED DATA]', fontweight='bold')
    axes[1].legend()

    plt.tight_layout()
    plt.savefig(args.output_plot, dpi=200)
    plt.close()
    print(f"Saved results to {args.output_json} and {args.output_plot}")

if __name__ == "__main__":
    main()
