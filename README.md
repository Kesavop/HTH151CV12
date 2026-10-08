# WinterRoad: Budget-Constrained Road Maintenance Prioritization

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com/)
[![YOLOv8](https://img.shields.io/badge/YOLOv8-Ultralytics-orange.svg)](https://ultralytics.com/)
[![OpenCV YuNet](https://img.shields.io/badge/OpenCV-YuNet%20ONNX-blue.svg)](https://github.com/opencv/opencv_zoo)
[![License](https://img.shields.io/badge/License-AGPL--3.0-lightgrey.svg)](LICENSE)

**Project**: WinterRoad  
**Team**: WinterBorn  
**Authors**: B K Kesavkrishnan, S Arun Kumar  
**Live Demo**: [WinterRoad Web Client](https://gladiators-roads.netlify.app) (Local: `http://127.0.0.1:8000`)

---

## 1. Overview

Municipal road authorities face a systemic capital allocation dilemma: **annual road maintenance backlogs systematically exceed municipal budgets**. Traditional approaches either fix roads in the order citizens complain (first-come, first-served) or greedily repair the single worst pothole first, frequently wasting public funds on low-traffic residential alleys while high-density commercial corridors and hospital routes remain broken.

**WinterRoad** is an end-to-end reproducible decision-support system combining:
1. **Multi-Model Computer Vision (YOLOv8 & OpenCV YuNet)**: Detects surface fissures (`D00`, `D10`, `D20`) and acute potholes (`D40`) with deep real-time face and license plate privacy blurring running at **158 FPS** on CPU (22.7 FPS end-to-end pipeline).
2. **Context-Aware Geospatial Topologies (OpenStreetMap)**: Integrates road hierarchy traffic estimates and safety proximity multipliers (+60% hospitals, +40% schools, +30% colleges).
3. **0/1 Knapsack Mathematical Optimization**: Solves the global budget allocation problem via dynamic programming, eliminating **64.4% of network risk** under a ₹5.0 L budget (vs. 61.1% for greedy worst-first and 52.3% mean for complaint queues [range 43.6%–60.4%]).
4. **Citizen & Admin Role Segregation**: Public zero-login ticket reporting with unguessable tracking codes (`WR-XXXXXX`), paired with authenticated administrative triage queues (PBKDF2-HMAC-SHA256 password hashing and token sessions).

---

## 2. Repository Structure

```
winterroad/
├── config.json                     # Single source of truth configuration
├── winterroad_config.py            # Centralized Python parameter loader & helpers
├── privacy.py                      # Deep OpenCV YuNet face & license plate blurring
├── .env.example                    # Sample environment variables for admin auth
├── run_all.sh                      # One-click launcher for macOS & Linux
├── run_all.bat                     # One-click launcher for Windows
├── requirements.txt                # Unified Python dependencies
│
├── backend/                        # FastAPI REST API & SQLite persistence
│   ├── main.py                     # API server, PBKDF2 auth, rate limiting, and GPS validation
│   ├── best.pt                     # Primary RDD2022 YOLOv8s weights
│   ├── pothole_best.pt             # Dedicated pothole YOLOv8s weights
│   ├── data/                       # SQLite reports.db and upload directory
│   └── static/                     # Dedicated multi-page citizen & admin web portal
│       ├── index.html              # Public landing page (/)
│       ├── report.html             # Citizen defect reporting (/report)
│       ├── track.html              # Citizen ticket tracking (/track)
│       ├── map.html                # Public verified defect map (/map)
│       ├── css/style.css           # Unified municipal styling & responsive tokens
│       ├── js/common.js            # Shared session, auth, currency, and DOM helpers
│       └── admin/                  # Protected municipal engineering portal
│           ├── login.html          # Admin authentication (/admin/login)
│           ├── index.html          # Executive overview & damage map (/admin)
│           ├── reports.html        # Verification & triage queue (/admin/reports)
│           ├── planner.html        # Knapsack budget optimizer (/admin/planner)
│           ├── research.html       # Empirical paper benchmarks (/admin/research)
│           ├── equity.html         # Ward allocation & rolling horizon (/admin/equity)
│           └── about.html          # Research provenance & OSS licenses (/admin/about)
│
├── optimizer/                      # Standalone CLI optimizer
│   └── optimizer.py                # 4-strategy budget optimizer
│
├── dashboard/                      # Executive decision dashboard
│   └── app.py                      # Reorganized 7-section Streamlit GIS dashboard (Password-protected status mutations)
│
├── website/                        # Standalone static mirror of multi-page web portal
│
├── scripts/                        # Reproducible research benchmark scripts
│   ├── benchmark_fps.py            # Latency & FPS breakdown per pipeline stage
│   ├── audit_norway_labels.py      # Exhaustive audit of RDD2022 Norway label distribution
│   ├── compare_prioritization.py   # 4-strategy prioritization & sweep curve
│   ├── sensitivity_analysis.py     # 200-trial Monte Carlo weight sensitivity
│   ├── uncertainty_prioritization.py # Detector confidence-weighted risk
│   ├── cost_uncertainty_simulation.py# 200 stochastic cost shock draws
│   ├── report_fusion.py            # Citizen spatial report clustering (50m DBSCAN)
│   ├── equity_check.py             # Spatial ward equity & Price of Fairness
│   ├── export_work_orders.py       # Field engineering PDF work order export
│   ├── multimonth_planning.py      # Rolling 6-month budget tranche simulation
│   ├── video_processor.py          # Temporal IoU video frame de-duplication demo
│   ├── ablation_study.py           # Single vs. ensemble vs. cavity fallback
│   └── transfer_adaptation.py      # Transfer test on user images (data/own/)
│
├── tests/                          # Automated unit test suite (19 passing tests)
│   ├── test_optimizer.py           # Hand-checkable knapsack proofs
│   ├── test_scoring.py             # Deterministic arithmetic checks
│   └── test_auth_roles.py          # Security, auth, ticket redaction & rate limit tests
│
├── results/                        # Generated benchmark artifacts & plots
│   ├── pipeline_fps_benchmark.json # Latency breakdown (YuNet 6.3ms, YOLO 37.7ms)
│   ├── norway_split_counts.json    # RDD2022 Norway label distribution audit
│   ├── prioritization_comparison.csv # Budget sweep strategy table
│   ├── prioritization_curve.png    # 4-strategy budget sweep curve plot
│   ├── sensitivity_summary.json    # Monte Carlo sensitivity metrics
│   ├── sensitivity_analysis.png    # Sensitivity gain distribution plot
│   ├── report_fusion_analysis.json # Redundant mobilization savings breakdown
│   ├── municipal_work_orders.pdf   # Official PDF work orders for crews
│   └── ...                         # All research outputs
│
└── docs/                           # Comprehensive research documentation
    ├── CURRENT_STATE.md            # Pre-modification codebase audit
    ├── ASSUMPTIONS.md              # Policy assumptions vs measurements
    ├── CREDITS.md                  # Third-party dataset & library attributions
    ├── LIMITATIONS.md              # Technical, sensor & auth boundary conditions
    ├── FUTURE_WORK.md              # Empirical research roadmap
    ├── FAILURE_GALLERY.md          # Visual failure cases with error analysis
    ├── LABELING_GUIDE.md           # Zero-leakage disjoint data split protocol
    ├── NUMBER_AUDIT.md             # Detailed mathematical audits of paper claims
    ├── LICENSE_NOTES.md            # AGPL-3.0, OpenCV MIT, and OSM license review
    ├── NEEDS_FROM_ME.md            # Specific datasets required from user
    ├── PAPER_OUTLINE.md            # IEEE/ACM research paper outline
    ├── SLIDES_OUTLINE.md           # 12-slide conference defense outline
    ├── LIKELY_QUESTIONS.md         # 18 defense questions & honest answers
    └── EXPLAINER.md                # File-by-file walkthrough & 10-question self-quiz
```

---

## 3. Installation & Setup

### Prerequisites
- Python 3.10+ (tested on Python 3.13)
- macOS, Linux, or Windows

### Setup Environment
```bash
# Clone the repository and enter directory
git clone https://github.com/Kesavop/HTH151CV12.git
cd HTH151CV12

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure administrative credentials
cp .env.example .env
# Edit .env to set ADMIN_USERNAME and ADMIN_PASSWORD (or ADMIN_PASSWORD_HASH)
```

---

## 4. Quick Start (Launch Everything)

### One-Click Launch
```bash
./run_all.sh      # macOS / Linux
# OR
run_all.bat       # Windows
```
This automatically starts:
- **FastAPI Backend**: `http://127.0.0.1:8000` (API Docs: `/docs`)
- **Streamlit Dashboard**: `http://localhost:8501`
- **Web Portal**: Opens `website/index.html` or embedded backend client in your browser.

---

## 5. Multi-Page Web Portal & Roles

### 1. Public Citizen Portal (Zero Login Required)
- **Landing Page (`/`)**: Project background, municipal problem description, and clear entry pathways.
- **Defect Reporting (`/report`)**:
  - Single-shot camera upload + one-time GPS consent (or interactive map pin).
  - OpenCV YuNet automatically blurs human faces and license plates prior to storage.
  - Generates unguessable ticket reference code: `WR-XXXXXX` (e.g. `WR-7F9K2M`).
- **Ticket Tracking (`/track`)**:
  - Look up repair progression by ticket code (`received` ➔ `verified` ➔ `scheduled` ➔ `fixed`).
  - Strictly sanitized public payload (zero citizen names, phone numbers, or internal reviewer notes).
- **Public Verified Map (`/map`)**:
  - Live Leaflet map displaying verified road defects and completed repairs with civic counters.
  - Coordinates rounded to 4 decimals for citizen privacy; unverified photos are never exposed.

### 2. Municipal Authority Portal (Server-Side Authentication Enforced)
- **Admin Login (`/admin/login`)**:
  - Authenticates municipal credentials (configured in `.env`, username default `admin`) with PBKDF2-HMAC-SHA256 password hashing.
  - Protected against brute-force attacks via sliding-window rate limiting (5 attempts/min lockout).
  - Successful login sets cookie `winterroad_token` and redirects to `/admin`.
- **Server-Side Redirect Enforcement (Rule 1)**:
  - Visiting any `/admin/*` page (`/admin`, `/admin/reports`, `/admin/planner`, `/admin/research`, `/admin/equity`, `/admin/about`) without an active session triggers an immediate **HTTP 303 redirect to `/admin/login`**.
  - All admin responses set `Cache-Control: no-store` so the browser Back button cannot display cached admin pages after logout.
- **Executive Overview (`/admin`)**: Key KPIs, summary counts, and live network damage geometry map.
- **Verification Queue (`/admin/reports`)**: Full triage table, side-by-side photo inspection, GPS tamper detection, and action buttons (`Verify`, `Schedule`, `Fixed`, `Reject`).
- **Knapsack Planner (`/admin/planner`)**: Budget slider, 4-strategy comparison, repair justifications, and printable work-order PDF sheets.
- **Model Research (`/admin/research`)**: Empirical mAP accuracy tables, pipeline latency profiles, and explicit `REAL MEASUREMENT` vs `SIMULATED DATA` badges.
- **Ward Equity (`/admin/equity`)**: Spatial Gini coefficient, Price of Fairness analysis, and multi-month rolling repair horizon.
- **Provenance & Licenses (`/admin/about`)**: Team WinterBorn attribution, 2D severity proxy assumptions, limitations, and OSS licenses.

### 3. Streamlit Decision Dashboard Security
- Retained as an optional research and interactive exploration console (`http://localhost:8501`).
- Status triage actions in SQLite are **password-protected** requiring the municipal admin password configured in `.env`, preventing unauthorized database modifications. Full architectural rationale documented in `docs/ARCHITECTURE.md`.

---

## 6. How to Reproduce Every Research Experiment

Every result reported in our research paper outline comes directly from executable Python scripts saving artifacts into `results/`:

```bash
# 1. Benchmark end-to-end pipeline latency and FPS:
python scripts/benchmark_fps.py
# Outputs: results/pipeline_fps_benchmark.json (YuNet: 158 FPS, YOLO: 26.5 FPS, Knapsack: 0.06ms)

# 2. Audit official RDD2022 Norway label distribution:
python scripts/audit_norway_labels.py
# Outputs: results/norway_split_counts.json (Proves 0 potholes in train, 1 in val)

# 3. Compare 4 prioritization strategies across budget sweep (Rs 1L - 20L):
python scripts/compare_prioritization.py --budget 500000
# Outputs: results/prioritization_comparison.csv, prioritization_curve.png, unfunded_reasons.csv

# 4. Run 500-trial Monte Carlo parameter sensitivity analysis (+/- 30% weights):
python scripts/sensitivity_analysis.py --trials 500
# Outputs: results/sensitivity_summary.json, results/multiplier_sensitivity.csv (Identical ceiling costs: 100% win-or-tie, 0% losses; Asymmetric: 78.2%)

# 5. Evaluate uncertainty-aware prioritization (detector confidence discounting):
python scripts/uncertainty_prioritization.py --budget 500000
# Outputs: results/uncertainty_prioritization.json (58.8% plan stability)

# 6. Simulate stochastic cost volatility shocks (200 draws, sigma=15%):
python scripts/cost_uncertainty_simulation.py --draws 200
# Outputs: results/cost_uncertainty_stability.json, cost_uncertainty_stability.png

# 7. Evaluate citizen report spatial fusion & redundant dispatch savings:
python scripts/report_fusion.py
# Outputs: results/report_fusion_analysis.json (Rs 5.50L savings, 48.9% cost reduction)

# 8. Evaluate spatial equity across municipal zones:
python scripts/equity_check.py --budget 500000
# Outputs: results/equity_analysis.json, results/equity_sweep.csv (Price of Fairness: 0.00% pts at 25% floor; +1.65 pts at binding 50% floor with 43.6% Gini reduction)

# 9. Export official municipal engineering work orders as a clean PDF:
python scripts/export_work_orders.py --budget 500000
# Outputs: results/municipal_work_orders.pdf

# 10. Simulate rolling 6-month budget tranches with dynamic arrivals:
python scripts/multimonth_planning.py --months 6
# Outputs: results/multimonth_planning.json, multimonth_planning.png

# 11. Run survey video frame temporal de-duplication demo:
python scripts/video_processor.py
# Outputs: results/video_processing_demo.json (is_demo_only: true)

# 12. Run detector pipeline ablation study:
python scripts/ablation_study.py
# Outputs: results/ablation_study.json

# 13. Evaluate face and license plate privacy blur recall on real photos:
python scripts/evaluate_privacy_recall.py
# Outputs: results/privacy_recall_benchmark.json (Awaiting user test photos per docs/NEEDS_FROM_ME.md)
```

### Running Automated Unit Tests
```bash
python -m unittest discover -s tests -p "test_*.py"
# Ran 19 tests in 0.045s - OK
```

---

## 7. Research Team & Credits

- **Project**: WinterRoad
- **Team**: WinterBorn
- **Members**: B K Kesavkrishnan, S Arun Kumar
- **Documentation**: Comprehensive background and 10-question self-quiz available in [`docs/EXPLAINER.md`](file:///Users/kesavkrishnan/HTH151CV12/docs/EXPLAINER.md).
- **Number Audit**: Complete justification of mathematical findings in [`docs/NUMBER_AUDIT.md`](file:///Users/kesavkrishnan/HTH151CV12/docs/NUMBER_AUDIT.md).
- **License Notes**: Review of AGPL-3.0, OpenCV MIT, and OSM ODbL in [`docs/LICENSE_NOTES.md`](file:///Users/kesavkrishnan/HTH151CV12/docs/LICENSE_NOTES.md).
- **Data Blockers**: Explicit list of required datasets in [`docs/NEEDS_FROM_ME.md`](file:///Users/kesavkrishnan/HTH151CV12/docs/NEEDS_FROM_ME.md).