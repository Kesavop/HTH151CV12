import os, numpy as np, pandas as pd, streamlit as st, folium
from streamlit_folium import st_folium

st.set_page_config(page_title="Road Repair Prioritizer", layout="wide")

# ---------------- Settings (synthetic - explain to judges) ----------------
CLASS_NAME   = {0:'Longitudinal crack', 1:'Transverse crack', 2:'Alligator crack', 3:'Pothole'}
CLASS_WEIGHT = {0:0.4, 1:0.5, 2:0.8, 3:1.0}
UNIT_COST    = {0:600, 1:600, 2:1200, 3:2500}      # ₹ per m²
FIXED_COST   = 15000                               # ₹ per site
IMG_AREA_M2  = 20
ROAD_TYPES   = {'Highway':30000, 'Arterial':15000, 'Collector':5000, 'Local':1000}
CENTER       = (9.9312, 76.2673)                   # Kochi

# ---------------- Data: real detections if available, else demo ----------------
@st.cache_data
def load_data():
    if os.path.exists('detections.csv'):           # made in Step 5 (segment, road_type, lat, lon, cls, area)
        d = pd.read_csv('detections.csv')
        segs = d.groupby('segment').agg(road_type=('road_type','first'), lat=('lat','first'),
                                        lon=('lon','first')).reset_index()
        segs['detections'] = [list(zip(g.cls, g.area)) for _, g in d.groupby('segment')]
        return segs, 'Real YOLO detections'
    rng = np.random.default_rng(42); rows = []
    for i in range(30):
        road = rng.choice(list(ROAD_TYPES), p=[0.15, 0.3, 0.3, 0.25])
        dets = [(int(rng.choice(4, p=[0.35,0.25,0.2,0.2])), rng.uniform(0.01, 0.15))
                for _ in range(rng.integers(1, 6))]
        rows.append({'segment': f'SEG-{i+1:02d}', 'road_type': road, 'detections': dets,
                     'lat': CENTER[0] + rng.uniform(-0.04, 0.04), 'lon': CENTER[1] + rng.uniform(-0.04, 0.04)})
    return pd.DataFrame(rows), 'Demo data (synthetic)'

df, source = load_data()
df['traffic']  = df.road_type.map(ROAD_TYPES)
df['severity'] = df.detections.apply(lambda d: round(min(sum(CLASS_WEIGHT[c]*a for c, a in d)*20, 10), 2))
df['level']    = pd.cut(df.severity, [-1, 3, 6, 10], labels=['Low', 'Medium', 'High']).astype(str)
df['cost']     = df.detections.apply(lambda d: int(FIXED_COST + sum(UNIT_COST[c]*a*IMG_AREA_M2*10 for c, a in d)))
df['traffic_w']= (np.log10(df.traffic) / np.log10(max(ROAD_TYPES.values()))).round(2)
df['risk']     = (df.severity * df.traffic_w).round(2)
df['damage']   = df.detections.apply(lambda d: ', '.join(sorted({CLASS_NAME[c] for c, _ in d})))

# ---------------- Optimizer ----------------
def knapsack(costs, values, budget, unit=1000):
    c = np.ceil(np.array(costs)/unit).astype(int); B = int(budget//unit)
    dp = np.zeros(B+1); keep = np.zeros((len(c), B+1), bool)
    for i in range(len(c)):
        if c[i] > B: continue
        cand = np.full(B+1, -1.0); cand[c[i]:] = dp[:B+1-c[i]] + values[i]
        keep[i] = cand > dp; dp = np.maximum(dp, cand)
    chosen, b = [], B
    for i in range(len(c)-1, -1, -1):
        if keep[i][b]: chosen.append(i); b -= c[i]
    return chosen

def worst_first(d, budget):
    chosen, spent = [], 0
    for i in d.sort_values('severity', ascending=False).index:
        if spent + d.cost[i] <= budget: chosen.append(i); spent += d.cost[i]
    return chosen

# ---------------- Sidebar ----------------
st.sidebar.title("⚙️ Controls")
budget = st.sidebar.slider("Maintenance budget (₹ lakh)", 1.0, 20.0, 5.0, 0.5) * 1e5
st.sidebar.caption(f"Data source: **{source}**")
st.sidebar.markdown("**Risk = Severity × Traffic weight**  \nOptimizer: 0/1 knapsack - maximise risk removed within budget.")

opt = knapsack(df.cost.tolist(), df.risk.tolist(), budget)
grd = worst_first(df, budget)
df['repair'] = df.index.isin(opt)
total = df.risk.sum()
opt_pct, grd_pct = df.risk[opt].sum()/total*100, df.risk[grd].sum()/total*100
plan = df[df.repair].sort_values('risk', ascending=False).reset_index(drop=True)
plan.index += 1
rank = {s: i for i, s in plan.segment.items()}

# ---------------- Header + KPIs ----------------
st.title("🛣️ Budget-Constrained Road Maintenance Prioritization")
k = st.columns(5)
k[0].metric("Damaged segments", len(df))
k[1].metric("Cost to fix all", f"₹{df.cost.sum()/1e5:.1f} L")
k[2].metric("Budget", f"₹{budget/1e5:.1f} L")
k[3].metric("Segments repaired", f"{len(opt)} / {len(df)}", f"{len(opt)-len(grd):+d} vs worst-first")
k[4].metric("Network risk removed", f"{opt_pct:.1f}%", f"{opt_pct-grd_pct:+.1f} pts vs worst-first")

# ---------------- Map + plan ----------------
left, right = st.columns([3, 2])
with left:
    st.subheader("🗺️ Priority map")
    m = folium.Map(location=CENTER, zoom_start=12, tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}', attr='Esri')
    for _, r in df.iterrows():
        color = 'green' if r.repair else {'High':'red', 'Medium':'orange', 'Low':'gray'}[r.level]
        status = f"✅ REPAIR - Priority #{rank[r.segment]}" if r.repair else "❌ Not funded"
        popup = (f"<b>{r.segment}</b> ({r.road_type})<br>{status}<br>Damage: {r.damage}<br>"
                 f"Severity: {r.severity} ({r.level})<br>Traffic: {r.traffic:,}/day<br>Cost: ₹{r.cost:,}<br>Risk: {r.risk}")
        folium.CircleMarker([r.lat, r.lon], radius=6 + r.risk*1.5, color=color, fill=True, fill_opacity=0.7,
                            popup=folium.Popup(popup, max_width=260), tooltip=r.segment).add_to(m)
    st_folium(m, height=470, use_container_width=True, returned_objects=[])
    st.caption("🟢 Will be repaired · 🔴 High / 🟠 Medium / ⚪ Low severity - not funded")
with right:
    st.subheader(f"✅ Repair plan ({len(plan)} segments)")
    st.dataframe(plan[['segment','road_type','damage','level','cost','risk']], height=440, width="stretch")
    st.download_button("⬇️ Download plan (CSV)", plan.to_csv().encode(), "repair_plan.csv")

# ---------------- Trade-offs ----------------
st.subheader("⚖️ Explicit trade-offs: what did NOT get funded and why")
cut = plan.risk.min() if len(plan) else 0
def reason(r):
    if r.cost > budget: return "Costs more than the whole budget"
    if r.level == 'High' and r.traffic_w < 0.8: return f"High severity, but {r.road_type.lower()} road with low traffic"
    if r.risk >= cut: return f"Good value, but ₹{r.cost/1e5:.2f} L would displace higher-value repairs"
    return "Lower risk-per-rupee than funded repairs"
nf = df[~df.repair].sort_values('risk', ascending=False).copy()
nf['reason'] = nf.apply(reason, axis=1)
st.dataframe(nf[['segment','road_type','severity','level','cost','risk','reason']], width="stretch", hide_index=True)

# ---------------- Budget curve (bonus) ----------------
st.subheader("📈 Risk removed vs budget - optimizer vs 'fix worst first'")
budgets = np.arange(1, 21) * 1e5
curve = pd.DataFrame({'Budget (₹ lakh)': budgets/1e5,
    'Our optimizer': [df.risk[knapsack(df.cost.tolist(), df.risk.tolist(), b)].sum()/total*100 for b in budgets],
    'Fix worst first': [df.risk[worst_first(df, b)].sum()/total*100 for b in budgets]}).set_index('Budget (₹ lakh)')
st.line_chart(curve, y_label='% network risk removed')
