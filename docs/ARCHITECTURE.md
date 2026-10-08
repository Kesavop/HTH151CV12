# WinterRoad System Architecture & Multi-Page Web Portal

**Project:** WinterRoad  
**Team:** WinterBorn  
**Authors:** B K Kesavkrishnan, S Arun Kumar  

---

## 1. Architectural Overview

WinterRoad is structured into a decoupled, reproducible civil engineering decision-support platform consisting of:
1. **Core Mathematical & Inference Engine**:
   - Multi-class defect object detection (Ultralytics YOLOv8s backbone + OpenCV YuNet privacy blurring).
   - Constrained 0/1 knapsack dynamic programming repair optimizer (`winterroad_config.py`, `optimizer/optimizer.py`).
2. **FastAPI Multi-Page Municipal Web Portal**:
   - High-throughput asynchronous backend (`backend/main.py`).
   - Server-side route authorization with strict HTTP 303 redirection for unauthenticated `/admin/*` visits.
   - Dedicated public citizen services and municipal administration surfaces.
3. **Streamlit Decision-Support Research Dashboard**:
   - Interactive exploratory analysis and decision simulation console (`dashboard/app.py`).
   - Protected with administrative credential gating on database write operations.

```
                              ┌───────────────────────────────────┐
                              │     WinterRoad Unified System     │
                              └─────────────────┬─────────────────┘
                                                │
                 ┌──────────────────────────────┴──────────────────────────────┐
                 ▼                                                             ▼
   ┌───────────────────────────┐                                 ┌───────────────────────────┐
   │    FastAPI Web Portal     │                                 │    Streamlit Dashboard    │
   │      (Port 8000)          │                                 │       (Port 8501)         │
   └─────────────┬─────────────┘                                 └─────────────┬─────────────┘
                 │                                                             │
        ┌────────┴────────┐                                           ┌────────┴────────┐
        ▼                 ▼                                           ▼                 ▼
 ┌──────────────┐  ┌──────────────┐                            ┌──────────────┐  ┌──────────────┐
 │ Public Pages │  │ Admin Pages  │                            │ Exploratory  │  │ Password-    │
 │ (No Login)   │  │ (Auth Guard) │                            │ Research View│  │ Protected    │
 │ /, /report,  │  │ /admin/*     │                            │ (Read-Only)  │  │ Mutation     │
 │ /track, /map │  │ Cookie Auth  │                            └──────────────┘  └──────────────┘
 └──────────────┘  └──────────────┘
```

---

## 2. Multi-Page Web Portal Design

### 2.1 The Problem with Single-Page Architectures for Municipal Civic Tech
In single-page applications (SPAs) or single-file interfaces:
- Unauthenticated users can easily bypass client-side DOM hiding via developer tools.
- Browser history, bookmarks, and back/forward navigation break because all states share `/`.
- Public citizens and municipal engineers share the same surface, risking leaks of internal notes or unverified submissions.

### 2.2 Dedicated Multi-Page Routing Schema
WinterRoad implements distinct URLs where each page functions independently when pasted directly into a fresh browser tab:

#### Public Citizen Pages (Zero Login Required)
| Route | Page | Purpose & Security Controls |
|---|---|---|
| `/` | Landing | System introduction, problem overview, and clear pathways to citizen reporting or admin login. |
| `/report` | Defect Reporting | Single-shot photo upload, GPS consent, OpenCV YuNet face/plate blurring, unguessable ticket receipt generation (`WR-XXXXXX`). |
| `/track` | Ticket Tracking | Real-time 4-stage stepper (`received` $\to$ `verified` $\to$ `scheduled` $\to$ `fixed`). Returns strictly sanitized data (no phone, no internal notes). |
| `/map` | Public Safety Map | Leaflet map displaying officially verified defects and completed repairs. Coordinates rounded to 4 decimals for citizen privacy. |

#### Municipal Admin Pages (Server-Side Authentication Enforced)
| Route | Page | Purpose & Security Controls |
|---|---|---|
| `/admin/login` | Admin Login | Salted PBKDF2-HMAC-SHA256 password verification with 60-second rate limiting. Redirects to `/admin` upon success. |
| `/admin` | Executive Overview | Key municipal KPIs, live damage distribution map, and quick navigation modules. |
| `/admin/reports` | Verification Queue | Full audit table, side-by-side photo inspection (annotated vs raw), GPS tamper detection, triage actions. |
| `/admin/planner` | Knapsack Planner | Rupee budget slider, 4-strategy comparison, repair justifications, and printable work-order PDF sheets. |
| `/admin/research` | Model Research | Clear `REAL MEASUREMENT` vs `SIMULATED DATA` badges, mAP tables, latency profiles, and reproducibility commands. |
| `/admin/equity` | Ward Equity | Spatial Gini coefficient, price of fairness analysis, and multi-month rolling repair horizon. |
| `/admin/about` | Provenance & Licenses | Team WinterBorn attribution, 2D severity proxy assumptions, limitations, and open-source licenses. |

---

## 3. Server-Side Authentication Enforcement (Rule 1)

All `/admin/*` routes are guarded on the server in `backend/main.py`:
1. **Cookie Verification**: The server inspects the `winterroad_token` cookie. If missing, expired (>24 hours), or not belonging to an active session with role `"admin"`, the server immediately responds with an **HTTP 303 See Other** redirect to `/admin/login`.
2. **Cache-Control Headers**: Admin pages are served with:
   ```http
   Cache-Control: no-cache, no-store, must-revalidate
   Pragma: no-cache
   Expires: 0
   ```
   This ensures that after logout, pressing the browser's "Back" button re-queries the server and is redirected to `/admin/login`.
3. **API Authorization**: All protected endpoints (`/api/plan`, `/api/reports`, `/api/reports/{id}/status`, `/api/admin/metrics`, `/api/reports.csv`) enforce `check_admin_auth()` returning **HTTP 401 Unauthorized** if the Bearer token or cookie is missing or invalid.

---

## 4. Role of the Streamlit Decision-Support Dashboard

The Streamlit dashboard (`dashboard/app.py`) is retained as an **optional research and executive inspection tool**:
- **Why keep it?**: Streamlit provides rapid interactive parameter sweeps, multi-factor trade-off visualizations, and deep research inspection for academic paper evaluators.
- **Security & Authorization Decision**:
  - In earlier hackathon prototypes, Streamlit directly executed `UPDATE reports` without requiring authorization.
  - In WinterRoad v2, report status triage actions in Streamlit are guarded by **administrative credential verification**:
    ```python
    if not verify_admin_password(admin_pwd):
        st.error("🔒 Unauthorized: Valid municipal admin password is required to modify report status in the database.")
    ```
  - Without the correct administrative password configured in `.env`, Streamlit cannot alter report records in SQLite.
  - All standard research tabs remain accessible for read-only paper evaluation.
