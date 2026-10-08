"""
WinterRoad - Budget-Constrained Road Repair Optimizer
Compares optimization strategies (Knapsack, Benefit/Cost, Worst-First, Complaint-Order)
and generates municipal repair plans with explicit unfunded reasons.

Project: WinterRoad
Team: WinterBorn
Members: B K Kesavkrishnan, S Arun Kumar

Usage:
    python optimizer.py
    python optimizer.py --csv ../data/sample_detections_synthetic.csv --budget 500000
"""
import argparse
import os
import sys
import numpy as np
import pandas as pd

# Add parent directory for shared configuration
_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_DIR)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from winterroad_config import (
    CLASS_NAME_MAP, CLASS_WEIGHT_MAP, UNIT_COST_MAP,
    FIXED_COST, IMG_AREA_M2, ROAD_TYPES, DISCRETIZATION_UNIT,
    compute_severity, compute_repair_cost, compute_traffic_weight, compute_risk
)

CENTER = (9.9312, 76.2673)  # Benchmark coordinates (Kochi)

def sample_segments(n=30, seed=42):
    """Generates synthetic benchmark segments if no CSV is provided."""
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n):
        road = rng.choice(list(ROAD_TYPES), p=[0.15, 0.3, 0.3, 0.25])
        dets = [(int(rng.choice(4, p=[0.35, 0.25, 0.2, 0.2])), float(rng.uniform(0.01, 0.15)))
                for _ in range(rng.integers(1, 6))]
        rows.append({
            'segment': f'SEG-{i+1:02d}',
            'road_type': road,
            'detections': dets,
            'lat': CENTER[0] + float(rng.uniform(-0.04, 0.04)),
            'lon': CENTER[1] + float(rng.uniform(-0.04, 0.04)),
            'complaint_order': i + 1
        })
    return pd.DataFrame(rows)

def load_csv(path):
    """Loads detections CSV and formats into segment records."""
    d = pd.read_csv(path)
    segs = d.groupby('segment').agg(
        road_type=('road_type', 'first'),
        lat=('lat', 'first'),
        lon=('lon', 'first')
    ).reset_index()
    segs['detections'] = [list(zip(g.cls, g.area)) for _, g in d.groupby('segment')]
    segs['complaint_order'] = range(1, len(segs) + 1)
    return segs

def score(df):
    """Computes engineering metrics for each segment."""
    df = df.copy()
    df['severity'] = df.detections.apply(compute_severity)
    df['level'] = pd.cut(df.severity, [-1, 3, 6, 10], labels=['Low', 'Medium', 'High']).astype(str)
    df['cost'] = df.detections.apply(compute_repair_cost)
    df['traffic_w'] = df.road_type.apply(compute_traffic_weight)
    df['risk'] = df.apply(lambda r: compute_risk(r['severity'], r['traffic_w']), axis=1)
    df['bpc'] = (df['risk'] / df['cost'].clip(lower=1) * 1e5).round(2)
    df['damage'] = df.detections.apply(lambda d: ', '.join(sorted({CLASS_NAME_MAP.get(int(c), 'Crack') for c, _ in d})))
    return df

def knapsack(costs, values, budget, unit=DISCRETIZATION_UNIT):
    """0/1 Knapsack dynamic programming."""
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

def worst_first(df, budget):
    """Greedy by physical severity."""
    chosen, spent = [], 0
    for i in df.sort_values('severity', ascending=False).index:
        if spent + df.cost[i] <= budget:
            chosen.append(i)
            spent += df.cost[i]
    return chosen

def benefit_per_cost(df, budget):
    """Greedy by risk / cost ratio."""
    chosen, spent = [], 0
    for i in df.sort_values('bpc', ascending=False).index:
        if spent + df.cost[i] <= budget:
            chosen.append(i)
            spent += df.cost[i]
    return chosen

def complaint_order(df, budget):
    """First-come first-served baseline."""
    chosen, spent = [], 0
    for i in df.sort_values('complaint_order', ascending=True).index:
        if spent + df.cost[i] <= budget:
            chosen.append(i)
            spent += df.cost[i]
    return chosen

def reason(r, budget, cut):
    """Plain-language explanation for why a road was unfunded."""
    if r.cost > budget:
        return 'Costs more than total available budget'
    if r.level == 'High' and r.traffic_w < 0.8:
        return f'High severity ({r.severity}/10), but low-volume {r.road_type.lower()} road'
    if r.risk >= cut:
        return f'Cost of Rs {r.cost/1e5:.2f} L would displace multiple higher-yield repairs'
    return f'Lower risk reduction per rupee than funded repairs (Ratio: {r.bpc:.1f})'

def main():
    ap = argparse.ArgumentParser(description="WinterRoad Optimizer")
    ap.add_argument('--csv', help='Detections CSV file')
    ap.add_argument('--budget', type=float, default=500000, help='Budget in INR')
    args = ap.parse_args()

    df = score(load_csv(args.csv) if args.csv and os.path.exists(args.csv) else sample_segments())
    budget = args.budget

    opt = knapsack(df.cost.tolist(), df.risk.tolist(), budget)
    bpc = benefit_per_cost(df, budget)
    grd = worst_first(df, budget)
    comp = complaint_order(df, budget)

    total = df.risk.sum()
    df['repair'] = df.index.isin(opt)

    print("==================================================================")
    print("   WinterRoad - Municipal Road Repair Optimization Summary        ")
    print("   Team: WinterBorn | Authors: B K Kesavkrishnan, S Arun Kumar    ")
    print("==================================================================")
    print(f"Total Road Segments : {len(df)}")
    print(f"Cost to Fix All     : Rs {df.cost.sum():,}")
    print(f"Allocated Budget    : Rs {budget:,.0f} ({budget/1e5:.1f} Lakh)")
    print("------------------------------------------------------------------")
    print(f"0/1 Knapsack (Ours) : {len(opt)} segments | {df.risk[opt].sum()/total*100:.1f}% risk eliminated")
    print(f"Benefit-per-Cost    : {len(bpc)} segments | {df.risk[bpc].sum()/total*100:.1f}% risk eliminated")
    print(f"Worst-First Greedy  : {len(grd)} segments | {df.risk[grd].sum()/total*100:.1f}% risk eliminated")
    print(f"Complaint-Order     : {len(comp)} segments | {df.risk[comp].sum()/total*100:.1f}% risk eliminated")
    print("------------------------------------------------------------------")

    plan = df[df.repair].sort_values('risk', ascending=False).reset_index(drop=True)
    plan.index += 1
    plan.index.name = 'priority'
    plan[['segment', 'road_type', 'damage', 'severity', 'level', 'cost', 'risk', 'bpc']].to_csv('repair_plan.csv')

    cut = plan.risk.min() if len(plan) else 0
    nf = df[~df.repair].sort_values('risk', ascending=False).copy()
    nf['reason'] = nf.apply(lambda r: reason(r, budget, cut), axis=1)
    nf[['segment', 'road_type', 'severity', 'level', 'cost', 'risk', 'bpc', 'reason']].to_csv('unfunded.csv', index=False)

    print("\nFUNDED REPAIR PLAN:")
    print(plan[['segment', 'road_type', 'level', 'cost', 'risk']].to_string())

    # Generate budget sweep chart
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    budgets = np.arange(1, 21) * 1e5
    o = [df.risk[knapsack(df.cost.tolist(), df.risk.tolist(), b)].sum() / total * 100 for b in budgets]
    b_curve = [df.risk[benefit_per_cost(df, b)].sum() / total * 100 for b in budgets]
    g = [df.risk[worst_first(df, b)].sum() / total * 100 for b in budgets]
    c_curve = [df.risk[complaint_order(df, b)].sum() / total * 100 for b in budgets]

    fig, ax = plt.subplots(1, 2, figsize=(13, 4.5))
    ax[0].plot(budgets / 1e5, o, 'o-', color='#1f77b4', label='0/1 Knapsack (WinterRoad)')
    ax[0].plot(budgets / 1e5, b_curve, '^--', color='#2ca02c', label='Benefit-per-Cost')
    ax[0].plot(budgets / 1e5, g, 's-.', color='#d62728', label='Worst-First Greedy')
    ax[0].plot(budgets / 1e5, c_curve, 'x:', color='#7f7f7f', label='Complaint-Order')
    ax[0].axvline(budget / 1e5, color='gray', ls=':', label=f'Budget (Rs {budget/1e5:.1f} L)')
    ax[0].set_xlabel('Budget (Lakh INR)', fontweight='bold')
    ax[0].set_ylabel('% Total Network Risk Removed', fontweight='bold')
    ax[0].set_title('Risk Removed vs. Budget Sweep', fontweight='bold')
    ax[0].legend(fontsize=9)
    ax[0].grid(alpha=.3)

    after = total - df.risk[opt].sum()
    ax[1].bar(['Before repairs', 'After repairs'], [total, after], color=['#d9534f', '#5cb85c'])
    ax[1].set_title(f'Network Risk Eliminated: -{(total-after)/total*100:.0f}%', fontweight='bold')
    ax[1].set_ylabel('Total Network Risk', fontweight='bold')
    plt.tight_layout()
    plt.savefig('budget_curve.png', dpi=120)
    print("\nSaved repair_plan.csv, unfunded.csv, and budget_curve.png")

if __name__ == "__main__":
    main()
