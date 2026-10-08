"""
WinterRoad - Spatial Equity & Fairness Analysis
Measures whether budget-constrained optimization leaves specific municipal wards/zones
chronically unfunded. Implements a bounded fairness constraint (minimum funding floor per zone)
and quantifies the 'Price of Fairness' trade-off.

Mathematical Foundation & Price of Fairness Bound:
Let F_unconstrained = { x in {0, 1}^N : sum(c_i * x_i) <= B } be the unconstrained knapsack feasible set.
Let F_fair = { x in F_unconstrained : sum_{i in Zone_z}(c_i * x_i) >= floor_z for all zones z } be the fair feasible set.
Because F_fair is a subset of F_unconstrained (F_fair ⊆ F_unconstrained), any feasible fair plan
is also feasible for the unconstrained problem. Therefore, the optimal unconstrained objective value
is an upper bound on the optimal fair objective value:
    max_{x in F_fair} R(x) <= max_{x in F_unconstrained} R(x)
Hence, the true optimal Price of Fairness is non-negative:
    PoF* = (R*_std - R*_fair) / R_total >= 0.

Heuristic Implementation Note:
The two-phase allocation method (Phase 1: greedy selection within each zone until the minimum floor is met;
Phase 2: standard discrete knapsack on the remaining budget and remaining pool) is a polynomial-time heuristic.
Because Phase 1 may greedily choose items that are suboptimal for the joint global integer program,
the heuristic fair risk R_heuristic <= R*_fair <= R*_std.
Consequently:
    PoF_heuristic = (R*_std - R_heuristic) / R_total >= (R*_std - R*_fair) / R_total = PoF*.
Therefore, the two-phase method's calculated Price of Fairness is an UPPER BOUND on the true optimal Price of Fairness.

Saves results to:
  - results/equity_analysis.json
  - results/equity_sweep.csv
  - results/equity_tradeoff.png
  - results/equity_sweep.png

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

from winterroad_config import DISCRETIZATION_UNIT
from scripts.compare_prioritization import load_dataset, solve_knapsack

# Canonical OpenStreetMap civic zones for Kochi benchmark area
OSM_CIVIC_ZONES = {
    "Fort Kochi / Mattancherry (Zone 1)": (9.965, 76.242),
    "Ernakulam Central (Zone 2)": (9.981, 76.282),
    "Edappally / North (Zone 3)": (10.025, 76.308),
    "Thoppumpady / South (Zone 4)": (9.918, 76.262)
}

def assign_nearest_zone(lat, lon):
    """Assigns coordinate to closest OSM civic place center."""
    best_zone, min_d = None, float("inf")
    for zname, (zlat, zlon) in OSM_CIVIC_ZONES.items():
        d = (lat - zlat)**2 + (lon - zlon)**2
        if d < min_d:
            min_d = d
            best_zone = zname
    return best_zone

def compute_gini(arr):
    """Computes the Gini inequality coefficient across an array of values."""
    arr = np.array(arr, dtype=float)
    if np.sum(arr) == 0:
        return 0.0
    n = len(arr)
    diff_sum = np.sum(np.abs(arr[:, None] - arr[None, :]))
    return float(diff_sum / (2 * n * np.sum(arr)))

def solve_fair_knapsack(df, budget, min_floor_pct=0.25, unit=DISCRETIZATION_UNIT):
    """
    Constrained Fair Knapsack (Two-Phase Heuristic):
    Ensures every geographic zone receives at least min_floor_pct of its total repair need
    (or up to its total need if budget allows), then allocates remaining budget to maximize risk.
    
    Feasible Set & Upper Bound Property:
    Because F_fair ⊆ F_unconstrained, the constrained optimum cannot exceed the unconstrained optimum.
    Since this two-phase solver is a greedy heuristic for Phase 1, its achieved risk is <= R*_fair,
    making the calculated Price of Fairness an upper bound on the true optimal Price of Fairness.
    
    Budget is tracked strictly in discrete units (cost_units = ceil(cost / unit)) so that the
    constrained solution respects identical discrete capacity B = floor(budget // unit), ensuring
    fair_risk <= std_risk (Price of Fairness >= 0).
    """
    zones = sorted(df["zone"].unique())
    B_total = int(budget // unit)
    c_units = np.ceil(df["cost"].values / unit).astype(int)
    unit_map = dict(zip(df.index, c_units))

    forced_idx = []
    used_units = 0

    # Phase 1: Guarantee minimum zone floor funding
    for z in zones:
        z_df = df[df["zone"] == z].sort_values("bpc", ascending=False)
        z_need = z_df["cost"].sum()
        target_floor = z_need * min_floor_pct

        spent_z = 0
        for idx in z_df.index:
            u_cost = unit_map[idx]
            if spent_z < target_floor and (used_units + u_cost <= B_total):
                forced_idx.append(idx)
                spent_z += z_df.loc[idx, "cost"]
                used_units += u_cost

    # Phase 2: Knapsack on remaining pool with remaining discrete budget
    rem_units = B_total - used_units
    rem_df = df[~df.index.isin(forced_idx)]

    if rem_units > 0 and len(rem_df) > 0:
        opt_rem = solve_knapsack(
            rem_df["cost"].tolist(),
            rem_df["risk"].tolist(),
            rem_units * unit,
            unit=unit
        )
        final_chosen = forced_idx + rem_df.index[opt_rem].tolist()
    else:
        final_chosen = forced_idx

    return final_chosen

def run_binding_floor_sweep(df, budget, floors=(0.25, 0.40, 0.50, 0.60), unit=DISCRETIZATION_UNIT):
    """
    Sweeps funding floor requirements across 25%, 40%, 50%, 60%
    to quantify when the fairness constraint becomes binding and measure
    the resulting Price of Fairness (upper bound) and spatial Gini inequality.
    """
    total_risk = df["risk"].sum()
    opt_std = solve_knapsack(df["cost"].tolist(), df["risk"].tolist(), budget, unit=unit)
    std_risk = df.iloc[opt_std]["risk"].sum()
    std_risk_pct = round(std_risk / total_risk * 100.0, 2)

    # Standard zone funding percentages
    std_zone_pcts = {}
    for z in sorted(df["zone"].unique()):
        z_all = df[df["zone"] == z]
        z_need = z_all["cost"].sum()
        z_funded = z_all.iloc[z_all.index.isin(opt_std)]["cost"].sum()
        std_zone_pcts[z] = round(z_funded / max(1, z_need) * 100.0, 1)

    gini_std = round(compute_gini(list(std_zone_pcts.values())), 3)

    sweep_records = []
    for fl in floors:
        fl_pct = round(fl * 100.0, 1)
        opt_fair = solve_fair_knapsack(df, budget, min_floor_pct=fl, unit=unit)
        fair_risk = df.loc[opt_fair]["risk"].sum()
        fair_risk_pct = round(fair_risk / total_risk * 100.0, 2)
        pof_pts = max(0.0, round((std_risk - fair_risk) / total_risk * 100.0, 2))

        # Check zone funding under this floor
        fair_zone_pcts = {}
        for z in sorted(df["zone"].unique()):
            z_all = df[df["zone"] == z]
            z_need = z_all["cost"].sum()
            z_funded = z_all.loc[z_all.index.isin(opt_fair)]["cost"].sum()
            fair_zone_pcts[z] = round(z_funded / max(1, z_need) * 100.0, 1)

        gini_fair = round(compute_gini(list(fair_zone_pcts.values())), 3)
        gini_red_pct = round((gini_std - gini_fair) / max(1e-6, gini_std) * 100.0, 1)

        # Binding check: floor is binding if it altered standard allocation or caused PoF > 0
        min_std_pct = min(std_zone_pcts.values())
        is_binding = bool((fl_pct > min_std_pct) or (pof_pts > 0.0))

        record = {
            "floor_pct": fl_pct,
            "is_binding": is_binding,
            "standard_risk_pct": std_risk_pct,
            "fair_risk_pct": fair_risk_pct,
            "price_of_fairness_pct_pts": pof_pts,
            "gini_standard": gini_std,
            "gini_fair": gini_fair,
            "gini_reduction_pct": gini_red_pct,
            "zone_1_funding_pct": fair_zone_pcts.get("Fort Kochi / Mattancherry (Zone 1)", 0.0),
            "zone_2_funding_pct": fair_zone_pcts.get("Ernakulam Central (Zone 2)", 0.0),
            "zone_3_funding_pct": fair_zone_pcts.get("Edappally / North (Zone 3)", 0.0),
            "zone_4_funding_pct": fair_zone_pcts.get("Thoppumpady / South (Zone 4)", 0.0)
        }
        sweep_records.append(record)

    return pd.DataFrame(sweep_records)

def main():
    parser = argparse.ArgumentParser(description="WinterRoad Spatial Equity Analysis")
    parser.add_argument("--csv", default=os.path.join(_ROOT, "data", "sample_detections_synthetic.csv"))
    parser.add_argument("--budget", type=float, default=500000.0)
    parser.add_argument("--outdir", default=os.path.join(_ROOT, "results"))
    args = parser.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    df = load_dataset(args.csv)

    # Assign zones
    df["zone"] = df.apply(lambda r: assign_nearest_zone(r["lat"], r["lon"]), axis=1)

    # Standard unconstrained Knapsack
    opt_std = solve_knapsack(df["cost"].tolist(), df["risk"].tolist(), args.budget)
    df["funded_standard"] = df.index.isin(opt_std)

    # Fair constrained Knapsack (25% floor per zone)
    opt_fair = solve_fair_knapsack(df, args.budget, min_floor_pct=0.25)
    df["funded_fair"] = df.index.isin(opt_fair)

    total_risk = df["risk"].sum()
    std_risk = df.loc[df["funded_standard"], "risk"].sum()
    fair_risk = df.loc[df["funded_fair"], "risk"].sum()

    price_of_fairness_pts = max(0.0, round((std_risk - fair_risk) / total_risk * 100.0, 2))

    # Zone breakdown for primary 25% floor
    zone_stats = []
    for z in sorted(df["zone"].unique()):
        z_all = df[df["zone"] == z]
        z_need = z_all["cost"].sum()
        z_std_funded = z_all[z_all["funded_standard"]]["cost"].sum()
        z_fair_funded = z_all[z_all["funded_fair"]]["cost"].sum()

        zone_stats.append({
            "zone": z,
            "segments_count": len(z_all),
            "repair_need_inr": int(z_need),
            "standard_funding_inr": int(z_std_funded),
            "standard_funding_pct": round(z_std_funded / max(1, z_need) * 100.0, 1),
            "fair_funding_inr": int(z_fair_funded),
            "fair_funding_pct": round(z_fair_funded / max(1, z_need) * 100.0, 1)
        })

    std_pcts = [z["standard_funding_pct"] for z in zone_stats]
    fair_pcts = [z["fair_funding_pct"] for z in zone_stats]
    gini_std = round(compute_gini(std_pcts), 3)
    gini_fair = round(compute_gini(fair_pcts), 3)
    gini_red = round((gini_std - gini_fair) / max(1e-6, gini_std) * 100.0, 1)

    # Execute binding floor sweep (25%, 40%, 50%, 60%)
    sweep_df = run_binding_floor_sweep(df, args.budget, floors=(0.25, 0.40, 0.50, 0.60))
    sweep_csv_path = os.path.join(args.outdir, "equity_sweep.csv")
    sweep_df.to_csv(sweep_csv_path, index=False)
    print(f"Saved floor sweep table to {sweep_csv_path}")

    summary = {
        "data_source": "synthetic",
        "budget_inr": args.budget,
        "zones_evaluated": len(zone_stats),
        "standard_risk_removed_pct": round(std_risk / total_risk * 100.0, 2),
        "fair_risk_removed_pct": round(fair_risk / total_risk * 100.0, 2),
        "price_of_fairness_pct_pts": price_of_fairness_pts,
        "theoretical_proof_note": (
            "Because F_fair ⊆ F_unconstrained, max_{x in F_fair} R(x) <= max_{x in F_unconstrained} R(x). "
            "A constrained plan cannot beat the unconstrained optimum. The two-phase method is a heuristic, "
            "so its calculated Price of Fairness is an upper bound on the true optimal Price of Fairness."
        ),
        "gini_coefficient_standard": gini_std,
        "gini_coefficient_fair": gini_fair,
        "gini_reduction_pct": gini_red,
        "zone_breakdown": zone_stats,
        "binding_floor_sweep": sweep_df.to_dict(orient="records"),
        "boundary_data_source_note": (
            "OpenStreetMap civic place nodes (suburbs / administrative centres) were used for spatial clustering. "
            "Municipal cadastral polygon shapefiles can be substituted directly if provided by the city."
        )
    }

    out_json = os.path.join(args.outdir, "equity_analysis.json")
    with open(out_json, "w") as f:
        json.dump(summary, f, indent=2)

    print("\nSpatial Equity Analysis Results:")
    print(f"  Standard Knapsack Risk: {std_risk/total_risk*100:.1f}%")
    print(f"  Fair Constrained Risk (25% floor): {fair_risk/total_risk*100:.1f}%")
    print(f"  Price of Fairness (25% floor): {price_of_fairness_pts} percentage points")
    print("\nBinding-Floor Sweep Results:")
    for _, r in sweep_df.iterrows():
        b_str = "BINDING" if r["is_binding"] else "Non-binding"
        print(f"  Floor {r['floor_pct']:.0f}% ({b_str}): Fair Risk={r['fair_risk_pct']:.1f}%, PoF={r['price_of_fairness_pct_pts']:.2f} pts, Gini={r['gini_fair']:.3f} (Δ {r['gini_reduction_pct']:+.1f}%)")
    print(f"\nSaved summary to {out_json}")

    # Plot 1: Zone Allocation Comparison
    z_names = [z["zone"].split(" (")[0] for z in zone_stats]
    x = np.arange(len(z_names))
    width = 0.35

    plt.figure(figsize=(10, 5))
    plt.bar(x - width/2, std_pcts, width, label='Standard Knapsack (Max Risk)', color='#1f77b4', edgecolor='black')
    plt.bar(x + width/2, fair_pcts, width, label='Fair Knapsack (25% Zone Floor)', color='#2ca02c', edgecolor='black')
    plt.axhline(25.0, color='red', linestyle='--', label='25% Minimum Floor')

    plt.xlabel('Municipal Zones', fontweight='bold')
    plt.ylabel('% of Repair Need Funded', fontweight='bold')
    plt.title('Spatial Equity Check: Zone Funding Allocation [SIMULATED DATA]', fontweight='bold')
    plt.xticks(x, z_names, rotation=10, ha='right')
    plt.ylim(0, 100)
    plt.legend()
    plt.grid(True, linestyle='--', alpha=0.4)
    plt.tight_layout()

    out_plot = os.path.join(args.outdir, "equity_tradeoff.png")
    plt.savefig(out_plot, dpi=200)
    plt.close()
    print(f"Saved plot to {out_plot}")

    # Plot 2: Binding Floor Sweep Tradeoff Curve
    fig, ax1 = plt.subplots(figsize=(8, 4.5))
    floors_x = sweep_df["floor_pct"].values
    pof_y = sweep_df["price_of_fairness_pct_pts"].values
    gini_y = sweep_df["gini_fair"].values

    color = '#d62728'
    ax1.set_xlabel('Mandatory Zone Funding Floor (%)', fontweight='bold')
    ax1.set_ylabel('Price of Fairness (pts risk lost)', color=color, fontweight='bold')
    ax1.plot(floors_x, pof_y, marker='o', linewidth=2.5, color=color, label='Price of Fairness (Upper Bound)')
    ax1.tick_params(axis='y', labelcolor=color)
    ax1.grid(True, linestyle='--', alpha=0.3)

    ax2 = ax1.twinx()
    color = '#1f77b4'
    ax2.set_ylabel('Spatial Gini Inequality', color=color, fontweight='bold')
    ax2.plot(floors_x, gini_y, marker='s', linewidth=2.5, linestyle='--', color=color, label='Spatial Gini')
    ax2.tick_params(axis='y', labelcolor=color)

    plt.title('Equity-Efficiency Trade-off: Floor Sweep [SIMULATED DATA]', fontweight='bold')
    fig.tight_layout()
    out_sweep_plot = os.path.join(args.outdir, "equity_sweep.png")
    plt.savefig(out_sweep_plot, dpi=200)
    plt.close()
    print(f"Saved sweep plot to {out_sweep_plot}")

if __name__ == "__main__":
    main()
