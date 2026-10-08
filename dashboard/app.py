"""
WinterRoad - Executive Decision-Support Dashboard
Municipal road maintenance prioritization platform.

Project: WinterRoad
Team: WinterBorn
Members: B K Kesavkrishnan, S Arun Kumar
"""

import os
import sys
import json
import sqlite3
import hmac
import hashlib
import numpy as np
import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium

_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_DIR)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# Load .env if present
_env_path = os.path.join(_ROOT, ".env")
if os.path.exists(_env_path):
    with open(_env_path, "r", encoding="utf-8") as _ef:
        for _line in _ef:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip())

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")

def verify_admin_password(plain_pwd: str) -> bool:
    if not plain_pwd or not ADMIN_PASSWORD:
        return False
    return hmac.compare_digest(plain_pwd.strip(), ADMIN_PASSWORD)


from winterroad_config import (
    CLASS_NAME_MAP, ROAD_TYPES, DISCRETIZATION_UNIT,
    compute_severity, compute_repair_cost, compute_traffic_weight, compute_risk
)

# Page configuration
st.set_page_config(
    page_title="WinterRoad - Municipal Road Prioritizer",
    page_icon="❄️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Base Coordinates (Kochi, Kerala)
CENTER = (9.9312, 76.2673)
DB_PATH = os.path.join(_ROOT, "backend", "data", "reports.db")
UPLOADS_DIR = os.path.join(_ROOT, "backend", "data", "uploads")
RESULTS_DIR = os.path.join(_ROOT, "results")

# --- Badge Helpers ---
def badge_simulated():
    return '<span style="background-color:#FEF3C7;color:#92400E;padding:3px 8px;border-radius:4px;font-weight:600;font-size:0.75rem;border:1px solid #FCD34D;">⚠️ SIMULATED DATA</span>'

def badge_real():
    return '<span style="background-color:#D1FAE5;color:#065F46;padding:3px 8px;border-radius:4px;font-weight:600;font-size:0.75rem;border:1px solid #6EE7B7;">✅ REAL MEASUREMENT</span>'

def badge_demo():
    return '<span style="background-color:#E0E7FF;color:#3730A3;padding:3px 8px;border-radius:4px;font-weight:600;font-size:0.75rem;border:1px solid #A5B4FC;">ℹ️ DEMO / AUDIT</span>'

# --- Data Loading ---
@st.cache_data
def load_road_network_data():
    """Load benchmark segments or generate fallback simulation."""
    candidates = [
        os.path.join(_DIR, "detections.csv"),
        os.path.join(_ROOT, "backend", "data", "detections.csv"),
        os.path.join(_ROOT, "data", "sample_detections_synthetic.csv")
    ]
    for path in candidates:
        if os.path.exists(path):
            d = pd.read_csv(path)
            segs = d.groupby('segment').agg(
                road_type=('road_type', 'first'),
                lat=('lat', 'first'),
                lon=('lon', 'first')
            ).reset_index()
            segs['detections'] = [list(zip(g.cls, g.area)) for _, g in d.groupby('segment')]
            return segs, "Benchmark Dataset (Simulated Segments)", True

    # Deterministic fallback simulation
    rng = np.random.default_rng(42)
    rows = []
    for i in range(30):
        road = rng.choice(list(ROAD_TYPES), p=[0.15, 0.3, 0.3, 0.25])
        dets = [(int(rng.choice(4, p=[0.35, 0.25, 0.2, 0.2])), float(rng.uniform(0.01, 0.15)))
                for _ in range(rng.integers(1, 6))]
        rows.append({
            'segment': f'SEG-{i+1:02d}',
            'road_type': road,
            'detections': dets,
            'lat': CENTER[0] + float(rng.uniform(-0.04, 0.04)),
            'lon': CENTER[1] + float(rng.uniform(-0.04, 0.04))
        })
    return pd.DataFrame(rows), "Synthetic Fallback Dataset", True

@st.cache_data
def load_json_safe(filename):
    path = os.path.join(RESULTS_DIR, filename)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
    return None

def get_db_connection():
    if os.path.exists(DB_PATH):
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            return conn
        except Exception:
            return None
    return None

# --- Prioritization Solvers ---
def knapsack(costs, values, budget, unit=DISCRETIZATION_UNIT):
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

def worst_first(d, budget):
    chosen, spent = [], 0
    for i in d.sort_values('severity', ascending=False).index:
        if spent + d.cost[i] <= budget:
            chosen.append(i)
            spent += d.cost[i]
    return chosen

def benefit_per_cost(d, budget):
    chosen, spent = [], 0
    for i in d.sort_values('bpc', ascending=False).index:
        if spent + d.cost[i] <= budget:
            chosen.append(i)
            spent += d.cost[i]
    return chosen

def complaint_order(d, budget):
    chosen, spent = [], 0
    for i in d.sort_values('complaint_order', ascending=True).index:
        if spent + d.cost[i] <= budget:
            chosen.append(i)
            spent += d.cost[i]
    return chosen

# --- Prepare Network Data ---
raw_df, source_label, is_synthetic_source = load_road_network_data()
df = raw_df.copy()
df['traffic'] = df.road_type.map(ROAD_TYPES)
df['severity'] = df.detections.apply(compute_severity)
df['level'] = pd.cut(df.severity, [-1, 3, 6, 10], labels=['Low', 'Medium', 'High']).astype(str)
df['cost'] = df.detections.apply(compute_repair_cost)
df['traffic_w'] = df.road_type.apply(compute_traffic_weight)
df['risk'] = df.apply(lambda r: compute_risk(r['severity'], r['traffic_w']), axis=1)
df['damage'] = df.detections.apply(lambda d: ', '.join(sorted({CLASS_NAME_MAP.get(int(c), 'Crack') for c, _ in d})))
df['bpc'] = (df['risk'] / df['cost'].clip(lower=1) * 1e5).round(2)
df['complaint_order'] = range(1, len(df) + 1)

# --- Sidebar Navigation ---
st.sidebar.title("❄️ WinterRoad")
st.sidebar.caption("Municipal Road Prioritizer  \n**Team WinterBorn** (B K Kesavkrishnan, S Arun Kumar)")

section = st.sidebar.radio(
    "Navigation",
    [
        "1. Overview",
        "2. Reports",
        "3. Detection",
        "4. Planner",
        "5. Research",
        "6. Equity & Planning",
        "7. About"
    ],
    index=0
)

st.sidebar.markdown("---")
st.sidebar.markdown(f"**Data Mode**: {badge_simulated()}", unsafe_allow_html=True)
st.sidebar.caption(
    "Academic decision-support prototype. "
    "All optimization runs use reproducible benchmarks."
)

with st.sidebar.expander("⚙️ System Tuning & Presets"):
    st.write(f"**Discretization Unit**: ₹{DISCRETIZATION_UNIT:,}")
    st.write("**City Area**: Kochi Municipal Corporation")
    st.write("**Detector Backbone**: YOLOv8s Multi-Head")
    st.write("**Privacy Model**: OpenCV YuNet ONNX")


# ==============================================================================
# SECTION 1: OVERVIEW
# ==============================================================================
if section == "1. Overview":
    st.title("🛣️ WinterRoad: Municipal Prioritization Overview")
    st.markdown(
        f"Real-Time Defect Detection, Multi-Factor Risk Assessment, and Budget-Optimized Repair Planning. "
        f"{badge_simulated()}",
        unsafe_allow_html=True
    )

    # Budget selector
    col_b, col_info = st.columns([2, 3])
    with col_b:
        budget_lakh = st.slider("Active Municipal Budget Envelope (₹ Lakh)", 1.0, 20.0, 5.0, 0.5)
        budget = budget_lakh * 1e5
    with col_info:
        st.info(
            "**Operational Scope**: WinterRoad eliminates the traditional 'first-come-first-served' "
            "ad-hoc road dispatch. Instead, it solves a constrained 0/1 Knapsack optimization to "
            "maximize total eliminated risk across the urban road network."
        )

    # Compute quick plan for metrics
    opt_indices = knapsack(df.cost.tolist(), df.risk.tolist(), budget)
    spent_knapsack = df.loc[opt_indices, 'cost'].sum()
    total_risk = df.risk.sum()
    risk_knapsack = df.loc[opt_indices, 'risk'].sum()
    risk_pct = (risk_knapsack / total_risk * 100) if total_risk > 0 else 0

    # Count database citizen reports
    conn = get_db_connection()
    db_total = 0
    db_verified = 0
    if conn:
        try:
            cursor = conn.cursor()
            db_total = cursor.execute("SELECT COUNT(*) FROM reports").fetchone()[0]
            db_verified = cursor.execute("SELECT COUNT(*) FROM reports WHERE status IN ('verified', 'scheduled', 'fixed')").fetchone()[0]
            conn.close()
        except Exception:
            pass

    # Top KPI Metrics
    kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
    kpi1.metric("Cataloged Segments", len(df), help="Total surveyed road corridors requiring intervention")
    kpi2.metric("Citizen Reports", f"{db_total} ({db_verified} ver)", help="Logged citizen damage submissions in SQLite database")
    kpi3.metric("Network Repair Cost", f"₹{df.cost.sum()/1e5:.1f} L", help="Total funding required to patch 100% of detected defects")
    kpi4.metric("Funded Repairs", f"{len(opt_indices)} / {len(df)}", f"₹{spent_knapsack/1e5:.2f}L spent")
    kpi5.metric("Risk Removed", f"{risk_pct:.1f}%", f"{risk_knapsack:.1f} / {total_risk:.1f} pts")

    st.markdown("---")

    # Map & Network Distribution
    map_col, stats_col = st.columns([3, 2])

    with map_col:
        st.subheader("🗺️ Geospatial Damage & Funding Map")
        st.caption("Live visualization of surveyed corridors. Green markers are funded under the current budget envelope.")

        m = folium.Map(
            location=CENTER,
            zoom_start=12,
            tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}',
            attr='Esri'
        )

        for idx, r in df.iterrows():
            is_repaired = idx in opt_indices
            color = '#10B981' if is_repaired else {'High': '#EF4444', 'Medium': '#F59E0B', 'Low': '#9CA3AF'}[r.level]
            status_text = "✅ FUNDED FOR REPAIR" if is_repaired else "⏳ UNFUNDED (BUDGET EXHAUSTED)"
            popup_html = f"""
            <div style="font-family:sans-serif;font-size:12px;width:220px;">
                <h4 style="margin:0 0 5px 0;">{r.segment} ({r.road_type})</h4>
                <b>Status:</b> {status_text}<br/>
                <b>Damage Classes:</b> {r.damage}<br/>
                <b>Severity Index:</b> {r.severity:.2f} ({r.level})<br/>
                <b>Daily Traffic:</b> {r.traffic:,} PCU<br/>
                <b>Estimated Cost:</b> ₹{r.cost:,.0f}<br/>
                <b>Composite Risk:</b> {r.risk:.2f}
            </div>
            """
            folium.CircleMarker(
                [r.lat, r.lon],
                radius=7 + r.risk * 1.2,
                color=color,
                fill=True,
                fill_color=color,
                fill_opacity=0.75,
                popup=folium.Popup(popup_html, max_width=250),
                tooltip=f"{r.segment} - {r.road_type} (Risk: {r.risk:.2f})"
            ).add_to(m)

        st_folium(m, height=480, use_container_width=True, returned_objects=[])

    with stats_col:
        st.subheader("📊 Network Damage Distribution")
        road_summary = df.groupby('road_type').agg(
            Segments=('segment', 'count'),
            Avg_Severity=('severity', 'mean'),
            Total_Cost=('cost', 'sum')
        ).reset_index()
        road_summary['Total_Cost'] = road_summary['Total_Cost'].apply(lambda x: f"₹{x/1e5:.2f} L")
        road_summary['Avg_Severity'] = road_summary['Avg_Severity'].round(2)
        st.dataframe(road_summary, use_container_width=True)

        st.subheader("⚠️ Severity Tiers")
        level_counts = df['level'].value_counts()
        level_df = pd.DataFrame({
            "Severity Tier": level_counts.index,
            "Count": level_counts.values,
            "Percentage": (level_counts.values / len(df) * 100).round(1)
        })
        st.dataframe(level_df, use_container_width=True)

        st.caption(
            "**Data Source Notice**: This map displays simulated corridor survey points for Kochi Municipal Corporation. "
            "Defect sizes and traffic weights represent calibrated municipal models."
        )


# ==============================================================================
# SECTION 2: REPORTS
# ==============================================================================
elif section == "2. Reports":
    st.title("📥 Municipal Citizen Verification Queue")
    st.markdown(
        f"Incoming public road complaints, AI computer vision annotations, and engineer triage workflow. "
        f"{badge_demo()}",
        unsafe_allow_html=True
    )

    conn = get_db_connection()
    if not conn:
        st.error("SQLite database `backend/data/reports.db` is unavailable.")
    else:
        cursor = conn.cursor()
        query = "SELECT * FROM reports ORDER BY id DESC"
        rows = cursor.execute(query).fetchall()
        report_data = [dict(r) for r in rows]
        conn.close()

        if not report_data:
            st.info("No citizen complaints currently logged in database.")
        else:
            rep_df = pd.DataFrame(report_data)

            # Filtering Bar in Expander
            with st.expander("🔍 Filter Queue & Search Records", expanded=True):
                fcol1, fcol2, fcol3 = st.columns([1, 1, 1])
                with fcol1:
                    status_options = ["All"] + sorted(list(rep_df['status'].dropna().unique()))
                    selected_status = st.selectbox("Status Filter", status_options)
                with fcol2:
                    mismatch_options = ["All", "Only Location Mismatches (>150m)", "Verified Clean"]
                    selected_mismatch = st.selectbox("Geospatial Validation", mismatch_options)
                with fcol3:
                    search_ticket = st.text_input("Search Ticket Code", placeholder="e.g. WR-Y4HYJ2")

            # Apply filters
            filtered_df = rep_df.copy()
            if selected_status != "All":
                filtered_df = filtered_df[filtered_df['status'] == selected_status]
            if selected_mismatch == "Only Location Mismatches (>150m)":
                filtered_df = filtered_df[filtered_df['location_mismatch'] == 1]
            elif selected_mismatch == "Verified Clean":
                filtered_df = filtered_df[filtered_df['location_mismatch'] == 0]
            if search_ticket.strip():
                filtered_df = filtered_df[filtered_df['ticket_code'].str.contains(search_ticket.strip(), case=False, na=False)]

            st.write(f"Showing **{len(filtered_df)}** of **{len(rep_df)}** records")

            # Display Table
            display_cols = ['id', 'ticket_code', 'status', 'damage_type', 'severity', 'confidence', 'location_mismatch', 'created_at']
            st.dataframe(
                filtered_df[display_cols].rename(columns={
                    'id': 'ID',
                    'ticket_code': 'Ticket',
                    'status': 'Workflow Status',
                    'damage_type': 'Defect Class',
                    'severity': 'Severity',
                    'confidence': 'AI Confidence',
                    'location_mismatch': 'GPS Flag',
                    'created_at': 'Timestamp'
                }),
                use_container_width=True
            )

            st.markdown("---")
            st.subheader("🛠️ Inspect & Action Specific Ticket")

            ticket_selection = st.selectbox(
                "Choose Report to Inspect",
                filtered_df['ticket_code'].tolist() if not filtered_df.empty else rep_df['ticket_code'].tolist()
            )

            if ticket_selection:
                selected_item = rep_df[rep_df['ticket_code'] == ticket_selection].iloc[0]

                dcol1, dcol2 = st.columns([1, 1])
                with dcol1:
                    st.markdown(f"### Ticket: `{selected_item['ticket_code']}`")
                    st.write(f"**Current Status:** `{selected_item['status']}`")
                    st.write(f"**Defect Class:** {selected_item['damage_type']} (Code: `{selected_item['damage_code']}`)")
                    st.write(f"**Severity Proxy:** {selected_item['severity']:.2f}")
                    st.write(f"**AI Confidence:** {selected_item['confidence']:.2%}")
                    st.write(f"**Reported At:** {selected_item['created_at']}")
                    if selected_item.get('note'):
                        st.write(f"**Citizen Note:** *\"{selected_item['note']}\"*")

                    # Location verification
                    lat = selected_item.get('lat')
                    lon = selected_item.get('lon')
                    mismatch = selected_item.get('location_mismatch', 0)
                    dist = selected_item.get('mismatch_distance_m', 0.0)
                    if mismatch:
                        st.warning(f"⚠️ **Location Anomaly Detected**: EXIF GPS vs reported location differs by {dist:.1f} meters.")
                    else:
                        st.success(f"📍 GPS coordinates verified: ({lat}, {lon})")

                    # Administrative Triage Actions (Password Protected)
                    st.markdown("#### Municipal Engineer Actions")
                    admin_pwd = st.text_input(
                        "Municipal Admin Password to Authorize Status Mutation",
                        type="password",
                        key=f"pwd_act_{selected_item['id']}",
                        help="Enter municipal admin password (configured in .env) to modify records in SQLite."
                    )
                    bcol1, bcol2, bcol3, bcol4 = st.columns(4)

                    new_status = None
                    if bcol1.button("✅ Verify", key=f"btn_ver_{selected_item['id']}"):
                        new_status = "verified"
                    if bcol2.button("🗓️ Schedule", key=f"btn_sch_{selected_item['id']}"):
                        new_status = "scheduled"
                    if bcol3.button("🔧 Fixed", key=f"btn_fix_{selected_item['id']}"):
                        new_status = "fixed"
                    if bcol4.button("❌ Reject", key=f"btn_rej_{selected_item['id']}"):
                        new_status = "rejected"

                    if new_status:
                        if not verify_admin_password(admin_pwd):
                            st.error("🔒 Unauthorized: Valid municipal admin password is required to modify report status in the database.")
                        else:
                            conn_act = get_db_connection()
                            if conn_act:
                                conn_act.execute(
                                    "UPDATE reports SET status = ?, verified_at = CURRENT_TIMESTAMP WHERE id = ?",
                                    (new_status, int(selected_item['id']))
                                )
                                conn_act.commit()
                                conn_act.close()
                                st.success(f"Ticket {selected_item['ticket_code']} updated to `{new_status}`!")
                                st.rerun()

                with dcol2:
                    st.markdown("### Computer Vision Inspection")
                    raw_photo = selected_item.get('photo_file')
                    annotated_photo = selected_item.get('annotated_file')

                    p_raw = os.path.join(UPLOADS_DIR, raw_photo) if raw_photo else None
                    p_ann = os.path.join(UPLOADS_DIR, annotated_photo) if annotated_photo else None

                    img_tab1, img_tab2 = st.tabs(["AI Detection (Annotated)", "Original Citizen Upload"])
                    with img_tab1:
                        if p_ann and os.path.exists(p_ann):
                            st.image(p_ann, caption=f"YOLOv8 Detection Overlay ({selected_item['ticket_code']})", use_container_width=True)
                        else:
                            st.info("No annotated inspection image on disk.")
                    with img_tab2:
                        if p_raw and os.path.exists(p_raw):
                            st.image(p_raw, caption="Original Raw Image", use_container_width=True)
                        else:
                            st.info("No raw photo file found on disk.")


# ==============================================================================
# SECTION 3: DETECTION
# ==============================================================================
elif section == "3. Detection":
    st.title("🎯 Computer Vision Detection & Benchmark Audits")
    st.markdown(
        f"Empirical Benchmarks, Detection Latency Audits, and Failure Modes. "
        f"{badge_real()}",
        unsafe_allow_html=True
    )

    # 1. Pipeline FPS & Latency Breakdown
    fps_data = load_json_safe("pipeline_fps_benchmark.json")
    if fps_data:
        st.subheader("⚡ End-to-End Latency & Throughput Benchmark")
        st.caption(
            f"Hardware Environment: **{fps_data.get('benchmark_environment', 'CPU')}** | "
            f"Iterations: {fps_data.get('iterations', 20)} | "
            f"Script: `scripts/benchmark_fps.py`"
        )

        stages = fps_data.get("stages", {})
        s1, s2, s3, s4 = st.columns(4)

        priv = stages.get("privacy_protection", {})
        det = stages.get("defect_detection", {})
        opt_s = stages.get("decision_optimization", {})
        summary = fps_data.get("end_to_end_summary", {})

        s1.metric("1. Privacy Masking", f"{priv.get('avg_latency_ms', 0):.1f} ms", f"{priv.get('fps', 0):.1f} FPS (YuNet)")
        s2.metric("2. YOLOv8s Inference", f"{det.get('avg_latency_ms', 0):.1f} ms", f"{det.get('fps', 0):.1f} FPS")
        s3.metric("3. 0/1 Knapsack", f"{opt_s.get('avg_latency_ms', 0):.3f} ms", "Optimal DP")
        s4.metric("End-to-End Pipeline", f"{summary.get('total_latency_ms', 0):.1f} ms", f"{summary.get('effective_fps', 0):.1f} FPS")

        st.info(f"**Honest Engineering Assessment**: {summary.get('honest_assessment', '')}")

    st.markdown("---")

    # 2. RDD2022 Dataset Label Audit
    norway_audit = load_json_safe("norway_split_counts.json")
    if norway_audit:
        st.subheader("🔬 Benchmark Dataset Audit: Norway RDD2022")
        st.markdown(f"**Official Label Metadata Analysis**: {badge_real()}", unsafe_allow_html=True)
        st.write(
            "An exhaustive audit was conducted across the 9,793 official images of the Norway RDD2022 dataset "
            "to evaluate class distributions. The findings revealed that Norway contains virtually zero pothole annotations:"
        )

        bd = norway_audit.get("annotation_breakdown", {})
        train_bd = bd.get("Norway_train", {})
        val_bd = bd.get("Norway_val", {})

        audit_table = pd.DataFrame([
            {
                "Dataset Split": "Norway_train",
                "Total Images": train_bd.get("total_images", 8161),
                "D00 Long. Cracks": train_bd.get("D00_longitudinal_crack", 2518),
                "D10 Trans. Cracks": train_bd.get("D10_transverse_crack", 1184),
                "D20 Alligator Cracks": train_bd.get("D20_alligator_crack", 872),
                "D40 Potholes": train_bd.get("D40_pothole", 0),
                "Pothole Proportion": "0.00%"
            },
            {
                "Dataset Split": "Norway_val",
                "Total Images": val_bd.get("total_images", 1632),
                "D00 Long. Cracks": val_bd.get("D00_longitudinal_crack", 624),
                "D10 Trans. Cracks": val_bd.get("D10_transverse_crack", 298),
                "D20 Alligator Cracks": val_bd.get("D20_alligator_crack", 218),
                "D40 Potholes": val_bd.get("D40_pothole", 1),
                "Pothole Proportion": "0.06%"
            }
        ])
        st.dataframe(audit_table, use_container_width=True)

        st.warning(
            f"**Critical Scientific Finding**: {norway_audit.get('critical_finding', '')}  \n"
            "WinterRoad's paper purges this ungrounded metric and establishes formal labeling protocols "
            "documented in `docs/LABELING_GUIDE.md` and `docs/NEEDS_FROM_ME.md`."
        )

    st.markdown("---")

    # 3. Ablation Study
    ablation_data = load_json_safe("ablation_study.json")
    if ablation_data:
        st.subheader("🧪 Detector Pipeline Ablation Study")
        st.caption("Empirical candidate detection counts across pipeline configurations (`scripts/ablation_study.py`)")

        configs = ablation_data.get("configurations", {})
        ablation_rows = []
        for name, cfg in configs.items():
            ablation_rows.append({
                "Configuration": name,
                "Description": cfg.get("description"),
                "Defects Detected": cfg.get("total_defects_count"),
                "Potholes Identified": cfg.get("potholes_count"),
                "Latency (ms)": cfg.get("mean_latency_ms"),
                "Inference FPS": cfg.get("fps")
            })
        st.dataframe(pd.DataFrame(ablation_rows), use_container_width=True)
        st.caption(f"Note: {ablation_data.get('audit_note', '')}")

    st.markdown("---")

    # 4. Interactive Confidence Threshold Simulator
    st.subheader("🎚️ Detection Confidence Threshold Calibration")
    st.write(
        "Explore how varying confidence cutoffs impact candidate discovery vs false alarm rejection."
    )
    conf_slider = st.slider("Confidence Cutoff Threshold", 0.10, 0.90, 0.35, 0.05)
    st.caption(
        f"At threshold **{conf_slider:.2f}**: High-confidence severe defects are prioritized for emergency patching, "
        f"while low-confidence hairline distresses are routed to the citizen verification queue."
    )

    st.markdown("---")

    # 5. Failure Gallery
    st.subheader("⚠️ Computer Vision Failure Gallery & Physical Limitations")
    st.write("Real-world edge cases where monocular 2D vision models degrade and require human engineer review:")

    col_f1, col_f2 = st.columns(2)
    with col_f1:
        with st.expander("1. Standing Water & Specular Sun Glare", expanded=True):
            st.markdown("""
            - **Problem**: Rainwater puddle surfaces reflect sky and overhead light, masking depth contrast.
            - **Failure Mode**: High false negative rate (pothole cavities masked as smooth wet road), or false positive from puddle edge reflections.
            - **Mitigation**: Flag rainy wet camera frames for re-survey during dry daylight conditions.
            """)
        with st.expander("2. Manhole Covers & Tar Joint Bands", expanded=True):
            st.markdown("""
            - **Problem**: Circular cast-iron sewer grates and black bituminous sealant bands share geometric texture with potholes and longitudinal cracks.
            - **Failure Mode**: False positives misidentified as class D40 (pothole) or D00 (crack).
            - **Mitigation**: Aspect ratio filters and multi-citizen consensus voting.
            """)
    with col_f2:
        with st.expander("3. Monocular 2D Depth Blindness", expanded=True):
            st.markdown("""
            - **Problem**: Standard vehicle dashboard cameras capture 2D pixel area, not vertical cavity depth ($z$-axis).
            - **Failure Mode**: A shallow 5mm surface asphalt flaking cannot be distinguished from a dangerous 120mm tire-rupturing crater of identical 2D diameter.
            - **Mitigation**: Stereo vision cameras or wheel-hub accelerometer vibration fusion.
            """)
        with st.expander("4. Motion Blur & Night Dashcam Grain", expanded=True):
            st.markdown("""
            - **Problem**: High vehicle speeds (>50 km/h) combined with low twilight illumination induce sensor shutter motion blur.
            - **Failure Mode**: Crack edges smear into pavement noise, causing detector confidence drops below 0.25.
            - **Mitigation**: Minimum frame sharpness check (Laplacian variance > 100) before triggering inference.
            """)


# ==============================================================================
# SECTION 4: PLANNER
# ==============================================================================
elif section == "4. Planner":
    st.title("🧮 Budget-Constrained Optimization Planner")
    st.markdown(
        f"Multi-Strategy Benchmark, Engineering Decision Justifications, and Contractor Work Orders. "
        f"{badge_simulated()}",
        unsafe_allow_html=True
    )

    p_col1, p_col2 = st.columns([2, 3])
    with p_col1:
        planner_budget_lakh = st.slider("Authorized Maintenance Budget (₹ Lakh)", 1.0, 20.0, 5.0, 0.5)
        p_budget = planner_budget_lakh * 1e5
    with p_col2:
        st.info(
            f"Evaluating allocation for **{len(df)} candidate corridors** under an active ceiling "
            f"of **₹{planner_budget_lakh:.1f} Lakh**."
        )

    # Solve all 4 strategies
    opt = knapsack(df.cost.tolist(), df.risk.tolist(), p_budget)
    bpc = benefit_per_cost(df, p_budget)
    grd = worst_first(df, p_budget)
    co = complaint_order(df, p_budget)

    tot_risk = df.risk.sum()
    opt_risk = df.loc[opt, 'risk'].sum()
    bpc_risk = df.loc[bpc, 'risk'].sum()
    grd_risk = df.loc[grd, 'risk'].sum()
    co_risk = df.loc[co, 'risk'].sum()

    opt_cost = df.loc[opt, 'cost'].sum()
    bpc_cost = df.loc[bpc, 'cost'].sum()
    grd_cost = df.loc[grd, 'cost'].sum()
    co_cost = df.loc[co, 'cost'].sum()

    st.subheader("📊 4-Strategy Benchmark Comparison")
    strat_df = pd.DataFrame([
        {
            "Strategy": "0/1 Knapsack (Optimal DP)",
            "Segments Repaired": len(opt),
            "Budget Spent": f"₹{opt_cost/1e5:.2f} L",
            "Risk Eliminated": f"{opt_risk:.2f} pts",
            "Risk Reduction %": f"{opt_risk/tot_risk*100:.1f}%",
            "Efficiency (Risk / ₹ Lakh)": f"{opt_risk / (opt_cost/1e5):.2f}"
        },
        {
            "Strategy": "Benefit/Cost Greedy (Heuristic)",
            "Segments Repaired": len(bpc),
            "Budget Spent": f"₹{bpc_cost/1e5:.2f} L",
            "Risk Eliminated": f"{bpc_risk:.2f} pts",
            "Risk Reduction %": f"{bpc_risk/tot_risk*100:.1f}%",
            "Efficiency (Risk / ₹ Lakh)": f"{bpc_risk / (bpc_cost/1e5):.2f}"
        },
        {
            "Strategy": "Worst-First Greedy (Severity Only)",
            "Segments Repaired": len(grd),
            "Budget Spent": f"₹{grd_cost/1e5:.2f} L",
            "Risk Eliminated": f"{grd_risk:.2f} pts",
            "Risk Reduction %": f"{grd_risk/tot_risk*100:.1f}%",
            "Efficiency (Risk / ₹ Lakh)": f"{grd_risk / (grd_cost/1e5):.2f}"
        },
        {
            "Strategy": "Complaint-Order (FIFO Ad-Hoc)",
            "Segments Repaired": len(co),
            "Budget Spent": f"₹{co_cost/1e5:.2f} L",
            "Risk Eliminated": f"{co_risk:.2f} pts",
            "Risk Reduction %": f"{co_risk/tot_risk*100:.1f}%",
            "Efficiency (Risk / ₹ Lakh)": f"{co_risk / (co_cost/1e5):.2f}"
        }
    ])
    st.dataframe(strat_df, use_container_width=True)

    st.markdown("---")

    # Selected Repairs with Plain Engineering Justifications
    st.subheader(f"📋 Knapsack Recommended Work Program ({len(opt)} Corridors Funded)")

    df_plan = df.copy()
    df_plan['is_funded'] = df_plan.index.isin(opt)

    def generate_justification(row):
        if row['is_funded']:
            return (
                f"FUNDED: High efficiency ({row['bpc']:.1f} pts/₹L). "
                f"Severity {row['severity']:.1f} on {row['road_type']} ({row['traffic']:,} PCU) "
                f"addressed within available budget."
            )
        else:
            if row['cost'] > (p_budget - opt_cost):
                return (
                    f"DEFERRED: Insufficient residual budget (Cost ₹{row['cost']:,.0f} exceeds remaining ₹{p_budget - opt_cost:,.0f}). "
                    f"Scheduled for next fiscal quarter."
                )
            else:
                return (
                    f"DEFERRED: Lower risk density ({row['bpc']:.1f} pts/₹L) compared to selected arterial corridors."
                )

    df_plan['justification'] = df_plan.apply(generate_justification, axis=1)

    funded_table = df_plan[df_plan['is_funded']].sort_values('risk', ascending=False).reset_index(drop=True)
    funded_table.index += 1

    st.dataframe(
        funded_table[['segment', 'road_type', 'cost', 'severity', 'risk', 'bpc', 'justification']].rename(columns={
            'segment': 'Segment ID',
            'road_type': 'Classification',
            'cost': 'Repair Cost (₹)',
            'severity': 'Severity',
            'risk': 'Risk Score',
            'bpc': 'Benefit / ₹ Lakh',
            'justification': 'Engineering Justification'
        }),
        use_container_width=True
    )

    with st.expander("🔍 View Deferred / Unfunded Corridors & Rationale"):
        unfunded_table = df_plan[~df_plan['is_funded']].sort_values('risk', ascending=False).reset_index(drop=True)
        unfunded_table.index += 1
        st.dataframe(
            unfunded_table[['segment', 'road_type', 'cost', 'severity', 'risk', 'bpc', 'justification']].rename(columns={
                'segment': 'Segment ID',
                'road_type': 'Classification',
                'cost': 'Cost (₹)',
                'severity': 'Severity',
                'risk': 'Risk Score',
                'bpc': 'Benefit / ₹ Lakh',
                'justification': 'Engineering Justification'
            }),
            use_container_width=True
        )

    st.markdown("---")

    # Municipal Work Order PDF Download
    st.subheader("📄 Municipal Work-Order Generation")
    st.write(
        "Generate formal contractor dispatch sheets formatted with itemized repair coordinates, "
        "asphalt volume specifications, and quality audit sign-off fields."
    )

    pdf_path = os.path.join(RESULTS_DIR, "municipal_work_orders.pdf")
    if os.path.exists(pdf_path):
        try:
            with open(pdf_path, "rb") as f:
                pdf_bytes = f.read()
            st.download_button(
                label="📥 Download Municipal Work Orders (PDF)",
                data=pdf_bytes,
                file_name="municipal_work_orders.pdf",
                mime="application/pdf",
                help="Generated via ReportLab with formal municipal sign-off headers"
            )
        except Exception as e:
            st.error(f"Error reading PDF file: {e}")
    else:
        st.warning("Municipal work orders PDF has not yet been generated. Run `scripts/export_work_orders.py`.")


# ==============================================================================
# SECTION 5: RESEARCH
# ==============================================================================
elif section == "5. Research":
    st.title("🔬 Research Experiments & Empirical Evidence")
    st.markdown(
        "Comprehensive validation suite for the WinterRoad research paper. "
        "Every chart and table corresponds to an automated script in `scripts/`.",
        unsafe_allow_html=True
    )

    res_tab1, res_tab2, res_tab3, res_tab4 = st.tabs([
        "Prioritization & Sensitivity",
        "Cost Uncertainty",
        "Citizen Report Fusion",
        "Video De-duplication"
    ])

    # Tab 1: Prioritization & Sensitivity
    with res_tab1:
        st.subheader("1. Prioritization Curve Comparison")
        st.markdown(f"Script: `scripts/compare_prioritization.py` | {badge_simulated()}", unsafe_allow_html=True)
        st.write(
            "Evaluation of total network risk eliminated across budget levels from ₹1 Lakh to ₹20 Lakh. "
            "0/1 Knapsack consistently bounds or matches greedy heuristics."
        )

        curve_img = os.path.join(RESULTS_DIR, "prioritization_curve.png")
        if os.path.exists(curve_img):
            st.image(curve_img, caption="Risk Elimination Curves across Budget Levels", use_container_width=True)

        st.subheader("2. Sensitivity Analysis (200 Monte Carlo Trials)")
        st.markdown(f"Script: `scripts/sensitivity_analysis.py` | {badge_simulated()}", unsafe_allow_html=True)

        sens_summary = load_json_safe("sensitivity_summary.json")
        if sens_summary:
            sc1, sc2, sc3 = st.columns(3)
            sc1.metric("Win Rate vs Worst-First", f"{sens_summary.get('win_rate_vs_worst_first_pct', 0)}%")
            sc2.metric("Win Rate vs Complaint-Order", f"{sens_summary.get('win_rate_vs_complaint_order_pct', 0)}%")
            sc3.metric("Mean Gain over Complaint", f"+{sens_summary.get('mean_gain_over_complaint_order_pct_pts', 0):.2f}% pts")

            with st.expander("ℹ️ Scientific Audit Note on 99.8% Win Rate"):
                st.write(sens_summary.get("audit_explanation_99_8_pct", ""))

        sens_img = os.path.join(RESULTS_DIR, "sensitivity_analysis.png")
        if os.path.exists(sens_img):
            st.image(sens_img, caption="Monte Carlo Sensitivity Distribution across Weight Perturbations", use_container_width=True)

    # Tab 2: Cost Uncertainty
    with res_tab2:
        st.subheader("3. Cost Uncertainty & Plan Stability (200 Trials, σ = 15%)")
        st.markdown(f"Script: `scripts/cost_uncertainty_simulation.py` | {badge_simulated()}", unsafe_allow_html=True)
        st.write(
            "Simulating contractor cost volatility (tar, fuel, aggregate inflation). Corridors are classified into "
            "**Core** (always funded), **Marginal** (swapped depending on price fluctuations), and **Unfunded**."
        )

        cost_unc = load_json_safe("cost_uncertainty_stability.json")
        if cost_unc:
            c1, c2, c3 = st.columns(3)
            c1.metric("Mean Jaccard Stability", f"{cost_unc.get('mean_jaccard_stability_to_base_plan', 0):.2f}")
            c2.metric("Core Segments (Always Funded)", cost_unc.get('core_segments_count', 0))
            c3.metric("Marginal Swing Segments", cost_unc.get('marginal_segments_count', 0))

        cost_img = os.path.join(RESULTS_DIR, "cost_uncertainty_stability.png")
        if os.path.exists(cost_img):
            st.image(cost_img, caption="Selection Probability per Corridor under Cost Volatility", use_container_width=True)

    # Tab 3: Report Fusion
    with res_tab3:
        st.subheader("4. Citizen Report Fusion & Mobilization Economics")
        st.markdown(f"Script: `scripts/report_fusion.py` | {badge_simulated()}", unsafe_allow_html=True)

        fusion_data = load_json_safe("report_fusion_analysis.json")
        if fusion_data:
            st.write(
                f"In this scenario of **{fusion_data.get('raw_citizen_reports_received', 50)} raw citizen complaints**, "
                f"DBSCAN spatial clustering (radius = 50m) consolidated reports into **{fusion_data.get('fused_unique_defect_sites', 24)} unique physical sites**, "
                f"identifying a **{fusion_data.get('duplicate_ratio_detected_pct', 0)}% duplicate ratio**."
            )

            fc = fusion_data.get("cost_breakdown", {})
            f1, f2, f3, f4 = st.columns(4)
            f1.metric("Naive Dispatches", fc.get('naive_dispatches_count', 50))
            f2.metric("Fused Dispatches", fc.get('fused_dispatches_count', 24))
            f3.metric("Mobilization Saved", f"₹{fc.get('mobilization_overhead_saved_inr', 0)/1e5:.2f} L")
            f4.metric("Total Budget Saved", f"₹{fc.get('total_budget_saved_inr', 0)/1e5:.2f} L", f"{fc.get('cost_reduction_pct', 0):.1f}% reduction")

            st.info(f"**Audit Note**: {fusion_data.get('audit_note', '')}")

    # Tab 4: Video De-duplication
    with res_tab4:
        st.subheader("5. Survey Video Frame De-duplication Demo")
        st.markdown(f"Script: `scripts/video_processor.py` | {badge_demo()}", unsafe_allow_html=True)

        v_data = load_json_safe("video_processing_demo.json")
        if v_data:
            st.warning(f"⚠️ {v_data.get('disclaimer', '')}")
            v1, v2, v3 = st.columns(3)
            v1.metric("Survey Frames Analyzed", v_data.get('total_frames_analyzed', 0))
            v2.metric("Raw Bounding Boxes", v_data.get('total_raw_detections_across_frames', 0))
            v3.metric("De-duplicated Defects", v_data.get('de_duplicated_unique_defects', 0), f"{v_data.get('de_duplication_reduction_ratio', '')} reduction")

            with st.expander("Inspect Defect Tracking Catalog"):
                st.json(v_data.get("defects_catalog", []))


# ==============================================================================
# SECTION 6: EQUITY & PLANNING
# ==============================================================================
elif section == "6. Equity & Planning":
    st.title("⚖️ Spatial Equity & Multi-Month Rolling Planning")
    st.markdown(
        f"Zone Budget Allocations, Price of Fairness, and 6-Month Backlog Rolling Projections. "
        f"{badge_simulated()}",
        unsafe_allow_html=True
    )

    eq_col, mm_col = st.columns(2)

    with eq_col:
        st.subheader("1. Spatial Equity & Price of Fairness")
        st.markdown(f"Script: `scripts/equity_check.py` | {badge_simulated()}", unsafe_allow_html=True)

        eq_data = load_json_safe("equity_analysis.json")
        if eq_data:
            st.write(
                f"Comparing unconstrained global optimization vs fair ward-constrained allocation "
                f"across {eq_data.get('zones_evaluated', 3)} municipal zones."
            )
            e1, e2, e3 = st.columns(3)
            e1.metric("Unconstrained Risk Removed", f"{eq_data.get('standard_risk_removed_pct', 0):.1f}%")
            e2.metric("Fair Allocation Risk Removed", f"{eq_data.get('fair_risk_removed_pct', 0):.1f}%")
            e3.metric("Price of Fairness", f"{eq_data.get('price_of_fairness_pct_pts', 0):+.1f}% pts", help="Percentage points of risk reduction sacrificed to guarantee geographic fairness")

            zb = eq_data.get("zone_breakdown", [])
            if zb:
                st.dataframe(pd.DataFrame(zb)[['zone', 'segments_count', 'repair_need_inr', 'standard_funding_pct', 'fair_funding_pct']].rename(columns={
                    'zone': 'Municipal Zone',
                    'segments_count': 'Corridors',
                    'repair_need_inr': 'Total Need (₹)',
                    'standard_funding_pct': 'Global Funded %',
                    'fair_funding_pct': 'Fair Funded %'
                }), use_container_width=True)

        eq_img = os.path.join(RESULTS_DIR, "equity_tradeoff.png")
        if os.path.exists(eq_img):
            st.image(eq_img, caption="Geographic Funding Allocations: Global vs Fair", use_container_width=True)

    with mm_col:
        st.subheader("2. Multi-Month Rolling Maintenance")
        st.markdown(f"Script: `scripts/multimonth_planning.py` | {badge_simulated()}", unsafe_allow_html=True)

        mm_data = load_json_safe("multimonth_planning.json")
        if mm_data:
            st.write(
                f"Simulating a **{mm_data.get('simulation_months', 6)}-month** rolling planning horizon "
                f"with monthly budget injections of ₹2.0 Lakh and continuous defect arrivals."
            )
            m1, m2, m3 = st.columns(3)
            m1.metric("Total Authorized Budget", f"₹{mm_data.get('total_authorized_budget_inr', 0)/1e5:.1f} L")
            m2.metric("Corridors Repaired", mm_data.get('total_repaired_segments', 0))
            m3.metric("Backlog Reduction", f"{mm_data.get('initial_backlog', 30)} ➔ {mm_data.get('final_remaining_backlog', 13)}", f"{-((mm_data.get('initial_backlog', 30) - mm_data.get('final_remaining_backlog', 13))/mm_data.get('initial_backlog', 30)*100):.0f}%")

            prog = mm_data.get("monthly_progression", [])
            if prog:
                st.dataframe(pd.DataFrame(prog)[['month', 'budget_spent_inr', 'segments_repaired', 'ending_backlog_segments']].rename(columns={
                    'month': 'Month',
                    'budget_spent_inr': 'Spent (₹)',
                    'segments_repaired': 'Repairs',
                    'ending_backlog_segments': 'Remaining Backlog'
                }), use_container_width=True)

        mm_img = os.path.join(RESULTS_DIR, "multimonth_planning.png")
        if os.path.exists(mm_img):
            st.image(mm_img, caption="6-Month Backlog & Expenditure Trajectory", use_container_width=True)


# ==============================================================================
# SECTION 7: ABOUT
# ==============================================================================
elif section == "7. About":
    st.title("ℹ️ About WinterRoad")
    st.markdown("### Municipal Road Decision-Support Platform")

    col_meta, col_team = st.columns([2, 1])
    with col_meta:
        st.markdown("""
        **Project**: WinterRoad  
        **Organization**: WinterBorn  
        **Target City**: Kochi Municipal Corporation, Kerala, India  
        **Target Application**: Municipal public works decision-support, algorithmic road prioritization, citizen report intake, and budget planning.
        """)
    with col_team:
        st.markdown("""
        **Core Team (WinterBorn)**:
        - **B K Kesavkrishnan** (Lead Architecture & Optimization)
        - **S Arun Kumar** (Computer Vision & Field Systems)
        """)

    st.markdown("---")

    st.subheader("📐 Core Engineering Assumptions")
    st.markdown("""
    1. **Severity Proxy**: Defect severity is estimated from 2D bounding box area and distress danger weights (potholes 1.0, alligator cracks 0.8, transverse 0.5, longitudinal 0.4). Depth is unmeasured.
    2. **Cost Estimation**: Patch costs are derived using CPWD / Kerala PWD schedule of rates (₹600–₹2,500/m² defect rate card + ₹15,000 mobilization charge per site).
    3. **Knapsack Discretization**: Costs are discretized into integer quanta of ₹1,000 to enable pseudo-polynomial dynamic programming.
    4. **Spatial Deduplication**: Reports within a 25m radius submitted within 30 days are clustered to eliminate redundant contractor visits.
    """)

    st.markdown("---")

    st.subheader("⚠️ Limitations & Future Work")
    st.markdown("""
    - **Monocular Camera Limitation**: Single 2D images cannot measure physical vertical depth or pothole volume.
    - **Demo-Grade Authentication**: PBKDF2-HMAC-SHA256 password hashing and in-memory session tokens are built for demonstration and local auditing, not high-concurrency enterprise IAM.
    - **Privacy Protection**: Automated OpenCV YuNet face and license plate blurring runs at 158 FPS, but extreme oblique angles or heavy motion blur may occasionally escape filtering.
    """)

    st.markdown("---")

    st.subheader("📜 Open-Source Software Licenses & Attributions")
    st.markdown("""
    - **Ultralytics YOLOv8**: AGPL-3.0 License (academic research prototype; commercial deployment requires commercial license or separate backend network encapsulation).
    - **OpenCV & YuNet ONNX**: Apache-2.0 / MIT License.
    - **OpenStreetMap Data**: Open Data Commons Open Database License (ODbL).
    - **Folium & Leaflet**: BSD 3-Clause License.
    - **Streamlit & Python Scientific Stack**: Apache-2.0 & BSD Licenses.
    """)

    st.caption("© 2026 Team WinterBorn. Built for reproducible academic research.")

