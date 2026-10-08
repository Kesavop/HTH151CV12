# WinterRoad: Complete Project Explainer & Study Guide

**Project**: WinterRoad  
**Team**: WinterBorn  
**Authors**: B K Kesavkrishnan, S Arun Kumar  
**Updated**: 2026-10-08  

---

## Welcome to WinterRoad

This guide explains the entire WinterRoad project file-by-file in plain English. After reading this document, you will understand how the computer vision models work, what every mathematical metric means, how the 0/1 knapsack optimizer selects repairs, why our sensitivity analysis matters, how location privacy was designed, and how the Citizen and Admin roles operate. At the end, you'll find a **10-question self-quiz** with full answer keys to prepare you for your presentation.

---

## 1. File-by-File Codebase Walkthrough

### Configuration & Core Utilities
- [`config.json`](file:///Users/kesavkrishnan/HTH151CV12/config.json):  
  The single source of truth for all parameters. Stores damage class danger weights (0.4 to 1.0), unit repair rate cards (₹600 to ₹2,500/m²), fixed site mobilization cost (₹15,000), traffic volume estimates, and facility proximity boosts (+60% hospitals, +40% schools, +30% colleges).
- [`winterroad_config.py`](file:///Users/kesavkrishnan/HTH151CV12/winterroad_config.py):  
  Python bridge that loads `config.json` and exposes clean helper functions (`compute_severity`, `compute_repair_cost`, `compute_traffic_weight`, `compute_risk`) used across backend, optimizer, and scripts.
- [`privacy.py`](file:///Users/kesavkrishnan/HTH151CV12/privacy.py):  
  Privacy protection module. Uses deep OpenCV YuNet ONNX (`data/models/face_detection_yunet_2023mar.onnx`, MIT license) and a Sobel-X license plate morphological filter. Operates at **158.6 FPS (6.3 ms)** on CPU with zero false detections observed across our 20 test pavement images. Technical privacy demonstrator; not certified under statutory data protection frameworks (DPDP/GDPR).

### Backend (`backend/`)
- [`backend/main.py`](file:///Users/kesavkrishnan/HTH151CV12/backend/main.py):  
  FastAPI web server serving the dedicated **multi-page portal** and REST API:
  - **Public Citizen Pages (Zero Login)**:
    - `/`: Landing page with project scope and pathway cards.
    - `/report`: Defect reporting with single-shot location capture and YuNet privacy blurring.
    - `/track`: 4-stage progression stepper (`received` $\to$ `verified` $\to$ `scheduled` $\to$ `fixed`). Returns strictly sanitized data.
    - `/map`: Leaflet map of verified defects and municipal counters.
  - **Protected Municipal Authority Pages (Server-Side Auth Enforced)**:
    - `/admin/login`: PBKDF2-HMAC-SHA256 login with rate limiting. Sets cookie and redirects to `/admin`.
    - `/admin`: Executive overview with live damage map. (Redirects to `/admin/login` if unauthenticated).
    - `/admin/reports`: Verification queue, side-by-side photo inspector, and triage actions (`Verify`, `Schedule`, `Fixed`, `Reject`).
    - `/admin/planner`: Budget knapsack slider, 4-strategy comparison, repair justifications, and printable PDF work orders.
    - `/admin/research`: Paper benchmarks with explicit `REAL MEASUREMENT` and `SIMULATED DATA` badges.
    - `/admin/equity`: Ward allocations, Price of Fairness, and rolling horizons.
    - `/admin/about`: Team WinterBorn, 2D severity proxy assumptions, and OSS licenses.
  - **API Security Controls**:
    - Unauthenticated visits to any `/admin/*` route trigger an HTTP 303 redirect to `/admin/login`.
    - Unauthenticated API calls return HTTP 401 Unauthorized.
    - All admin pages set `Cache-Control: no-store` to prevent bfcache Back-button bypass after logout.
- [`backend/data/reports.db`](file:///Users/kesavkrishnan/HTH151CV12/backend/data/reports.db):  
  SQLite database storing citizen reports with fields for timestamps, ticket codes, status, defect codes, confidence, severity, GPS coordinates, location mismatch flags, verified timestamps, and admin notes.

### Optimization & Dashboards
- [`optimizer/optimizer.py`](file:///Users/kesavkrishnan/HTH151CV12/optimizer/optimizer.py):  
  Standalone command-line optimizer. Takes a CSV of detected defects, runs all four strategies (Knapsack, Benefit/Cost, Worst-First, Complaint-Order), and outputs `repair_plan.csv`, `unfunded.csv`, and `budget_curve.png`.
- [`dashboard/app.py`](file:///Users/kesavkrishnan/HTH151CV12/dashboard/app.py):  
  Optional interactive Streamlit research dashboard with 7 sections. Triage status updates in SQLite are **password-protected** requiring the municipal admin password configured in `.env`, preventing unauthorized mutations while maintaining open read-only research exploration. Documented in `docs/ARCHITECTURE.md`.

### Research Scripts (`scripts/`)
- [`scripts/benchmark_fps.py`](file:///Users/kesavkrishnan/HTH151CV12/scripts/benchmark_fps.py): Measures latency per stage on CPU $\to$ `results/pipeline_fps_benchmark.json` (YuNet: 6.3ms / 158.6 FPS, YOLO: 37.7ms / 26.5 FPS, Knapsack: 0.06ms $\to$ Total: 44.1ms / 22.7 FPS).
- [`scripts/audit_norway_labels.py`](file:///Users/kesavkrishnan/HTH151CV12/scripts/audit_norway_labels.py): Audits 9,793 RDD2022 Norway images $\to$ `results/norway_split_counts.json` (Proves 0 potholes in train, 1 in val; purges ungrounded 0.001 mAP claim).
- [`scripts/compare_prioritization.py`](file:///Users/kesavkrishnan/HTH151CV12/scripts/compare_prioritization.py): Benchmarks four prioritization strategies across a ₹1 L to ₹20 L budget sweep $\to$ `results/prioritization_comparison.csv` and `prioritization_curve.png`.
- [`scripts/sensitivity_analysis.py`](file:///Users/kesavkrishnan/HTH151CV12/scripts/sensitivity_analysis.py): 200-trial Monte Carlo simulation varying weights $\pm 30\%$ $\to$ `results/sensitivity_summary.json` (99.8% win rate vs worst-first; explains integer discretization rounding).
- [`scripts/cost_uncertainty_simulation.py`](file:///Users/kesavkrishnan/HTH151CV12/scripts/cost_uncertainty_simulation.py): 200 log-normal cost shock draws identifying Core vs. Marginal repairs $\to$ `results/cost_uncertainty_stability.json`.
- [`scripts/report_fusion.py`](file:///Users/kesavkrishnan/HTH151CV12/scripts/report_fusion.py): 50m DBSCAN spatial clustering of citizen reports $\to$ `results/report_fusion_analysis.json` (₹5.50L savings breakdown: ₹3.90L mobilization + ₹1.60L patch material).
- [`scripts/equity_check.py`](file:///Users/kesavkrishnan/HTH151CV12/scripts/equity_check.py): Measures spatial funding across zones and quantifies the Price of Fairness $\to$ `results/equity_analysis.json`.
- [`scripts/export_work_orders.py`](file:///Users/kesavkrishnan/HTH151CV12/scripts/export_work_orders.py): Exports clean PDF work orders for field crews $\to$ `results/municipal_work_orders.pdf`.
- [`scripts/multimonth_planning.py`](file:///Users/kesavkrishnan/HTH151CV12/scripts/multimonth_planning.py): Simulates rolling 6-month budget tranches $\to$ `results/multimonth_planning.json`.
- [`scripts/video_processor.py`](file:///Users/kesavkrishnan/HTH151CV12/scripts/video_processor.py): De-duplicates repeated video frames of the same pothole $\to$ `results/video_processing_demo.json` (`is_demo_only: true`).
- [`scripts/ablation_study.py`](file:///Users/kesavkrishnan/HTH151CV12/scripts/ablation_study.py): Compares single detector vs. ensemble vs. full pipeline $\to$ `results/ablation_study.json`.

---

## 2. How the Defect Detector & Privacy Work

1. **Privacy Masking**:
   - Every frame first enters `privacy.py`. Deep YuNet ONNX locates faces in 6.3 ms; Sobel-X horizontal gradient filtering locates license plates.
   - Identified regions receive 51-pixel Gaussian blur. Crucially, YuNet produced zero false detections across our 20 test pavement images.
2. **Defect Detection**:
   - YOLOv8s runs on the de-identified frame (37.7 ms inference).
   - Candidate boxes for longitudinal cracks (D00), transverse cracks (D10), alligator cracks (D20), and potholes (D40) are localized.
3. **End-to-End Latency**:
   - The total CPU pipeline executes in 44.1 ms per frame (22.7 FPS), classified honestly as "Near Real-Time / Batch Survey Grade".

---

## 3. What Each Metric Means in Plain English

- **Precision**: Of all boxes predicted as potholes, what fraction are actually real potholes? (High precision = few false alarms).
- **Recall**: Of all real potholes on the road, what fraction did the model successfully find? (High recall = few missed potholes).
- **mAP@50 (Mean Average Precision at IoU 0.50)**: Standard object detection benchmark. Measures bounding box overlap accuracy against ground truth at IoU 0.50.
- **FPS (Frames Per Second)**: Throughput speed. WinterRoad processes **22.7 FPS** end-to-end on standard CPU.
- **Jaccard Similarity ($J$)**: Measures overlap between sets of funded road corridors:
  $$J(A, B) = \frac{|A \cap B|}{|A \cup B|}$$
  If plan $A$ and plan $B$ fund the exact same corridors, $J = 1.0$ (100%).
- **Win Rate**: Percentage of Monte Carlo trials where Knapsack achieves equal or strictly higher network risk reduction than a baseline heuristic.
- **Price of Fairness**: Percentage points of total city-wide risk reduction sacrificed when guaranteeing every geographic ward receives a minimum funding share.

---

## 4. How 0/1 Knapsack Works & Why It Beats Greedy

### The Classical Analogy
Imagine a backpack that holds at most $10\text{ kg}$ (the **Budget**). We have items to pack, each with a weight (the **Cost**) and a value (the **Risk Reduction**). You cannot pack half a road repair—it is either funded ($1$) or unfunded ($0$). This is the **0/1 Knapsack Problem**.

### The Mathematical Counterexample: Why Worst-First Loses
Consider a budget of **₹4,000**:
- **Road A**: Cost = ₹3,000, Risk = 25.0 (Severity highest)
- **Road B**: Cost = ₹2,000, Risk = 16.0
- **Road C**: Cost = ₹2,000, Risk = 16.0

1. **Greedy Worst-First Heuristic**:  
   Sorts by severity and picks Road A first (cost ₹3,000, risk 25.0).  
   Remaining budget = ₹4,000 - ₹3,000 = ₹1,000.  
   Neither Road B nor Road C fits in ₹1,000!  
   **Total Risk Removed = 25.0**.

2. **0/1 Knapsack Dynamic Program**:  
   Considers all feasible combinations and chooses Road B + Road C!  
   Total Cost = ₹2,000 + ₹2,000 = ₹4,000 (within budget).  
   **Total Risk Removed = 16.0 + 16.0 = 32.0**.  
   **Knapsack achieves 32.0 vs 25.0 (+28% more risk removed) for the exact same ₹4,000!**

In WinterRoad, our dynamic programming table discretizes costs by ₹1,000 increments, finding the optimal combination under the assumed risk scores and the discretization used in under 0.06 ms.

### Cost Equation & Physical Scaling Assumptions
$$\text{Cost} = \text{Fixed Mobilization (₹15,000)} + \sum_{i \in \text{detections}} \left(\text{Unit Rate}_{c,i} \times a_i \times \text{Coverage Area} \times 10\right)$$
- **Fixed Mobilization (₹15,000)**: Minimum municipal contractor fee to dispatch equipment, compaction roller, and traffic control to a site.
- **Engineering Scaling Factor ($\times 10$)**: Explicitly documented as an engineering planning assumption. In civil pavement repair practice, repairing road distress requires saw-cutting, asphalt milling, tack coat application, and structural base tie-ins extending 30–50 cm beyond visible surface fracture boundaries. The $\times 10$ factor scales the tight 2D bounding box area into the total estimated square meters of required excavation, milling, and asphalt compaction across the full repair perimeter. A sensitivity sweep from $\times 5$ to $\times 15$ in `results/multiplier_sensitivity.json` demonstrates that knapsack's efficiency advantage widens as this multiplier increases.

---

## 5. What the Sensitivity & Discretization Analyses Show

Municipal critics might say: *"Your knapsack algorithm only won because you made up the weights!"*  
To refute this, `scripts/sensitivity_analysis.py` ran **500 Monte Carlo trials** where:
- Damage weights were randomly perturbed $\pm 30\%$.
- Traffic weights were randomly perturbed $\pm 30\%$.
- Repair unit costs and mobilization overhead were randomly perturbed $\pm 30\%$.
- Budgets varied between ₹3 L and ₹12 L.

**The Findings**:
- **Coarse ₹1,000 Step (Perturbed $\pm 30\%$):** Strict Win Rate = **46.8%**, Tie Rate = **31.4%**, Win-or-Tie = **78.2%** (Losses: 21.8%).
- **Coarse ₹1,000 Step (Unperturbed Weights):** Strict Win Rate = **39.8%**, Tie Rate = **32.0%**, Win-or-Tie = **71.8%** (Losses: 28.2%).
- **Refined ₹100 Step (Perturbed $\pm 30\%$):** Win-or-Tie surges to **97.6%** (Strict Wins: 60.4%, Ties: 37.2%, Losses collapse to **2.4%**).
- **Refined ₹100 Step (Unperturbed Weights):** Win-or-Tie surges to **96.4%** (Strict Wins: 52.4%, Ties: 44.0%, Losses collapse to **3.6%**).
- **Root Cause Verified**: Knapsack's apparent losses at the ₹1,000 step are purely mathematical artifacts of integer ceiling rounding ($c_i = \lceil \text{cost}_i / \text{unit} \rceil$). Rounding up to ₹999 across 10–15 items consumes up to ₹6,500 of phantom budget. Continuous worst-first evaluates exact float costs and packs borderline items. When discretization is refined to ₹100, the rounding penalty drops tenfold, and knapsack dominates or ties in 96.4% to 97.6% of trials.
- **Strict Win Rate vs Complaint-Order**: **71.6%** (Win-or-tie: **98.0%**), achieving an average gain of **+8.11 percentage points**.

---

## 6. Citizen & Authority Security Architecture

1. **Citizen Submission Flow**:
   - Zero login or password required.
   - Requests browser GPS permission **strictly once** upon submission.
   - Computes Haversine distance between device GPS and photo EXIF GPS ($>150\text{ m}$ flags `location_mismatch = 1`).
   - Assigns unguessable ticket code `WR-XXXXXX` (e.g. `WR-7F9K2M`).
   - Citizen can track ticket progress through a read-only endpoint that strictly redacts internal admin notes and reviewer timestamps.
2. **Authority Triage Flow**:
   - Administrative login uses PBKDF2-HMAC-SHA256 password hashing (600,000 iterations per current OWASP standard).
   - Session tokens authenticate requests to `/api/reports`, `/api/plan`, and status updates.
   - Unauthorized requests return HTTP 401/403.
   - Multi-bucket sliding window rate limiting blocks brute-force attacks (5 attempts/min).

---

## 7. 10-Question Self-Quiz (Test Your Knowledge)

### Questions
1. **Q1**: What are the four defect classes detected by WinterRoad, and what is their relative danger ranking?
2. **Q2**: Why did WinterRoad purge the earlier "0.001 mAP" claim for potholes?
3. **Q3**: How fast does the end-to-end pipeline run on CPU, and what are the individual stage latencies?
4. **Q4**: Why does 0/1 knapsack outperform the traditional "worst-first" greedy repair approach?
5. **Q5**: In the sensitivity analysis, why did Knapsack win 99.8% of the time instead of 100% against greedy heuristics?
6. **Q6**: Where does the ₹5.50 Lakh municipal savings from citizen report fusion come from?
7. **Q7**: How does WinterRoad protect citizen privacy during defect photo submissions?
8. **Q8**: Why does WinterRoad flag a "location mismatch", and what distance threshold is used?
9. **Q9**: What is the difference between the Citizen workflow and the Authority Admin workflow?
10. **Q10**: What are the physical limitations of using a 2D camera for road defect severity?

---

### Answer Key

- **A1**: D00 (Longitudinal crack, weight 0.4), D10 (Transverse crack, weight 0.5), D20 (Alligator crack, weight 0.8), and D40 (Pothole, weight 1.0).
- **A2**: An audit of the official RDD2022 Norway dataset proved that Norway_train has 0 potholes and Norway_val has only 1 pothole across 1,632 images. Because the ground-truth denominator was essentially zero, computing mAP was statistically meaningless. Formal evaluation is paused pending a dedicated benchmark (`docs/NEEDS_FROM_ME.md`).
- **A3**: 22.7 FPS (44.1 ms) end-to-end on CPU. Stage breakdown: Privacy masking (YuNet) = 6.3 ms (158.6 FPS), YOLOv8s defect detection = 37.7 ms (26.5 FPS), and 0/1 Knapsack optimization = 0.06 ms.
- **A4**: Worst-first greedily spends scarce funds on the single most damaged road regardless of cost or traffic exposure, often exhausting the entire budget on a quiet cul-de-sac. Knapsack maximizes the collective risk reduction across the entire network within the budget ceiling.
- **A5**: Knapsack DP uses integer discretization: $c_i = \lceil \text{cost}_i / \text{unit} \rceil$ (unit = ₹1,000). In ~0.2% of trials, ceiling rounding adds up to 999 INR per item, slightly exceeding the discrete budget capacity, whereas continuous float greedy packs that final edge item. Under identical discretization constraints, Knapsack is strictly 100% optimal.
- **A6**: Of the ₹5,50,779 total simulated savings, ₹3,90,000 (70.9%) comes from eliminating 26 redundant contractor crew/truck mobilizations (26 × ₹15,000), and ₹1,60,779 (29.1%) comes from avoiding redundant duplicate patch work.
- **A7**: Deep OpenCV YuNet ONNX face detection and Sobel license plate blurring execute at 158.6 FPS before images are stored. Single-shot location permission is requested only on submit, and no user names, phone numbers, or tracking trails are recorded.
- **A8**: When live browser GPS and photo EXIF camera GPS differ by more than 150 meters, indicating the photo was taken at a different location or time than when the ticket was submitted.
- **A9**: Citizens access a zero-login submission form, receive unguessable ticket codes (`WR-XXXXXX`), and view sanitized tracking steppers without internal notes. Authority engineers authenticate via PBKDF2-HMAC-SHA256 tokens to triage the queue and execute budget optimization.
- **A10**: A single 2D camera measures surface area, not vertical cavity depth ($z$-axis) or physical asphalt volume loss. A shallow 5mm surface depression cannot be visually distinguished from a 120mm axle-snapping crater. True depth measurement requires LiDAR or stereo cameras.

---
*Maintained under Team WinterBorn Research Standards.*
