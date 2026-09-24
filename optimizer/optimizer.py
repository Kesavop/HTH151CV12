"""
Gladiators - budget-constrained road repair optimizer.

Usage:
    python optimizer.py                          # sample data, budget Rs 5 lakh
    python optimizer.py --csv ../data/sample_detections_synthetic.csv --budget 800000

Input CSV columns: segment, road_type, lat, lon, cls, area
    cls  : 0=longitudinal crack, 1=transverse crack, 2=alligator crack, 3=pothole
    area : box area as a fraction of the image (w*h, normalized)
Outputs: repair_plan.csv, unfunded.csv, budget_curve.png, map.html
"""
import argparse
import numpy as np
import pandas as pd

CLASS_NAME   = {0: 'Longitudinal crack', 1: 'Transverse crack', 2: 'Alligator crack', 3: 'Pothole'}
CLASS_WEIGHT = {0: 0.4, 1: 0.5, 2: 0.8, 3: 1.0}      # danger of each damage type
UNIT_COST    = {0: 600, 1: 600, 2: 1200, 3: 2500}    # Rs per m2 (synthetic rate card)
FIXED_COST   = 15000                                 # Rs per site: crew + equipment
IMG_AREA_M2  = 20                                    # road area seen in one image
ROAD_TYPES   = {'Highway': 30000, 'Arterial': 15000, 'Collector': 5000, 'Local': 1000}  # vehicles/day
CENTER       = (9.9312, 76.2673)                     # Kochi


def sample_segments(n=30, seed=42):
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n):
        road = rng.choice(list(ROAD_TYPES), p=[0.15, 0.3, 0.3, 0.25])
        dets = [(int(rng.choice(4, p=[0.35, 0.25, 0.2, 0.2])), rng.uniform(0.01, 0.15))
                for _ in range(rng.integers(1, 6))]
        rows.append({'segment': f'SEG-{i+1:02d}', 'road_type': road, 'detections': dets,
                     'lat': CENTER[0] + rng.uniform(-0.04, 0.04), 'lon': CENTER[1] + rng.uniform(-0.04, 0.04)})
    return pd.DataFrame(rows)


def load_csv(path):
    d = pd.read_csv(path)
    segs = d.groupby('segment').agg(road_type=('road_type', 'first'), lat=('lat', 'first'),
                                    lon=('lon', 'first')).reset_index()
    segs['detections'] = [list(zip(g.cls, g.area)) for _, g in d.groupby('segment')]
    return segs


def score(df):
    df = df.copy()
    df['traffic']   = df.road_type.map(ROAD_TYPES)
    df['severity']  = df.detections.apply(lambda d: round(min(sum(CLASS_WEIGHT[c] * a for c, a in d) * 20, 10), 2))
    df['level']     = pd.cut(df.severity, [-1, 3, 6, 10], labels=['Low', 'Medium', 'High']).astype(str)
    df['cost']      = df.detections.apply(lambda d: int(FIXED_COST + sum(UNIT_COST[c] * a * IMG_AREA_M2 * 10 for c, a in d)))
    df['traffic_w'] = (np.log10(df.traffic) / np.log10(max(ROAD_TYPES.values()))).round(2)
    df['risk']      = (df.severity * df.traffic_w).round(2)
    df['damage']    = df.detections.apply(lambda d: ', '.join(sorted({CLASS_NAME[c] for c, _ in d})))
    return df


def knapsack(costs, values, budget, unit=1000):
    """0/1 knapsack: maximise total risk removed with total cost <= budget."""
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
    """Baseline: fix the most severe segments first until money runs out."""
    chosen, spent = [], 0
    for i in df.sort_values('severity', ascending=False).index:
        if spent + df.cost[i] <= budget:
            chosen.append(i)
            spent += df.cost[i]
    return chosen


def reason(r, budget, cut):
    if r.cost > budget:
        return 'Costs more than the whole budget'
    if r.level == 'High' and r.traffic_w < 0.9:
        return f'High severity, but {r.road_type.lower()} road with low traffic'
    if r.risk >= cut:
        return f'Rs {r.cost/1e5:.2f} L would push out higher-value repairs'
    return 'Lower risk-per-rupee than funded repairs'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--csv', help='detections.csv from the Colab notebook')
    ap.add_argument('--budget', type=float, default=500000, help='budget in rupees')
    args = ap.parse_args()

    df = score(load_csv(args.csv) if args.csv else sample_segments())
    budget = args.budget
    opt = knapsack(df.cost.tolist(), df.risk.tolist(), budget)
    grd = worst_first(df, budget)
    total = df.risk.sum()
    df['repair'] = df.index.isin(opt)

    print(f"Segments            : {len(df)}")
    print(f"Cost to fix all     : Rs {df.cost.sum():,}")
    print(f"Budget              : Rs {budget:,.0f}")
    print(f"Optimizer           : {len(opt)} segments, {df.risk[opt].sum()/total*100:.1f}% risk removed")
    print(f"Fix worst first     : {len(grd)} segments, {df.risk[grd].sum()/total*100:.1f}% risk removed")

    plan = df[df.repair].sort_values('risk', ascending=False).reset_index(drop=True)
    plan.index += 1
    plan.index.name = 'priority'
    plan[['segment', 'road_type', 'damage', 'severity', 'level', 'cost', 'risk']].to_csv('repair_plan.csv')
    cut = plan.risk.min() if len(plan) else 0
    nf = df[~df.repair].sort_values('risk', ascending=False).copy()
    nf['reason'] = nf.apply(lambda r: reason(r, budget, cut), axis=1)
    nf[['segment', 'road_type', 'severity', 'level', 'cost', 'risk', 'reason']].to_csv('unfunded.csv', index=False)
    print("\nREPAIR PLAN\n", plan[['segment', 'road_type', 'level', 'cost', 'risk']].to_string())

    # before/after curve
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    budgets = np.arange(1, 21) * 1e5
    o = [df.risk[knapsack(df.cost.tolist(), df.risk.tolist(), b)].sum() / total * 100 for b in budgets]
    g = [df.risk[worst_first(df, b)].sum() / total * 100 for b in budgets]
    fig, ax = plt.subplots(1, 2, figsize=(13, 4.5))
    ax[0].plot(budgets / 1e5, o, 'o-', label='Our optimizer')
    ax[0].plot(budgets / 1e5, g, 's--', label='Fix worst first')
    ax[0].axvline(budget / 1e5, color='gray', ls=':')
    ax[0].set_xlabel('Budget (lakh)'); ax[0].set_ylabel('% network risk removed')
    ax[0].set_title('Risk removed vs budget'); ax[0].legend(); ax[0].grid(alpha=.3)
    after = total - df.risk[opt].sum()
    ax[1].bar(['Before repairs', 'After repairs'], [total, after], color=['#d9534f', '#5cb85c'])
    ax[1].set_title(f'Network risk: -{(total-after)/total*100:.0f}%'); ax[1].set_ylabel('Total network risk')
    plt.tight_layout(); plt.savefig('budget_curve.png', dpi=110)

    # map
    import folium
    m = folium.Map(location=CENTER, zoom_start=12,
                   tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}',
                   attr='Esri')
    rank = {s: i for i, s in plan.segment.items()}
    for _, r in df.iterrows():
        color = 'green' if r.repair else {'High': 'red', 'Medium': 'orange', 'Low': 'gray'}[r.level]
        status = f"REPAIR - Priority #{rank[r.segment]}" if r.repair else "Not funded"
        folium.CircleMarker([r.lat, r.lon], radius=6 + r.risk * 1.5, color=color, fill=True, fill_opacity=0.7,
                            popup=folium.Popup(f"<b>{r.segment}</b> ({r.road_type})<br>{status}<br>"
                                               f"Damage: {r.damage}<br>Severity: {r.severity}<br>"
                                               f"Cost: Rs {r.cost:,}<br>Risk: {r.risk}", max_width=260)).add_to(m)
    m.save('map.html')
    print("\nSaved: repair_plan.csv, unfunded.csv, budget_curve.png, map.html")


if __name__ == '__main__':
    main()
