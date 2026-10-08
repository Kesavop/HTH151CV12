# WinterRoad: 18 Likely Research Defense Questions & Honest Answers

**Project**: WinterRoad  
**Team**: WinterBorn  
**Authors**: B K Kesavkrishnan, S Arun Kumar  
**Updated**: 2026-10-08  

---

### Q1: Why not just fix the worst damage first? Isn't that what public works departments do?
**Honest Answer**:
Public works departments frequently use a greedy "worst-first" heuristic, but mathematically, this suffers from severe capital inefficiency. If a massive, expensive crater is located on a quiet residential cul-de-sac with 50 cars a day, repairing it can consume ₹1.5 lakh of a ₹5 lakh budget, leaving no funds for five moderate potholes on a major arterial carrying 30,000 vehicles a day. WinterRoad proves empirically that 0/1 knapsack removes 64.4% of total network risk compared to 61.1% for worst-first under a ₹5 Lakh budget, eliminating +3.3 percentage points more risk for the exact same public expenditure.

---

### Q2: How do you prevent malicious citizens from spamming fake reports or submitting photos of the same pothole from different angles?
**Honest Answer**:
We implement a three-tier defense:
1. **Client Rate Limiting**: The FastAPI backend enforces a multi-bucket sliding window limiting any IP address to at most 5 report submissions per minute (HTTP 429).
2. **AI Confidence & Area Gating**: Photos must contain verified defect textures (D00-D40) with positive confidence; blank or indoor images are rejected without persistence.
3. **Spatial Report Fusion**: In `scripts/report_fusion.py`, nearby reports within 50 meters are automatically clustered via DBSCAN into a single physical defect site. Multiple citizen reports boost confidence and verification status without generating duplicate contractor work orders.

---

### Q3: How do you handle citizen location privacy? Are you continuously tracking users?
**Honest Answer**:
No, absolutely not. WinterRoad does not track users, maintain location trails, or run background location services:
- Location permission is requested **strictly once** at the moment the citizen clicks submit.
- The system captures only a single coordinate pair, timestamp, defect photo, and AI classification.
- We do **not** collect names, phone numbers, email addresses, IMEI numbers, or device identifiers.
- Human faces and vehicle license plates are automatically detected and blurred via deep OpenCV YuNet ONNX and Sobel morphology before any image is saved to disk or displayed.

---

### Q4: What happens if a citizen takes a photo at home of a downloaded picture, or if phone GPS drifts?
**Honest Answer**:
We cross-compare the browser's live device GPS with the photo's EXIF camera metadata using the Haversine formula. If the device location and photo EXIF GPS differ by more than 150 meters, the system automatically flags the submission with `location_mismatch = 1` and logs the exact discrepancy distance in meters. This alerts municipal dispatchers that the report requires manual verification rather than blind trust.

---

### Q5: What happened to the earlier "0.001 mAP" claim for potholes? Why was it purged?
**Honest Answer**:
We conducted an exhaustive audit of the official RDD2022 Norway dataset (`scripts/audit_norway_labels.py` -> `results/norway_split_counts.json`). The audit revealed that **Norway_train contains exactly 0 pothole annotations**, and **Norway_val contains only 1 pothole annotation across 1,632 images**. Because the ground-truth denominator was essentially zero, computing mAP on this split was statistically meaningless. To preserve scientific integrity, that number was completely purged from our papers and claims. Formal evaluation is paused pending a real held-out labeled benchmark as documented in `docs/NEEDS_FROM_ME.md`.

---

### Q6: How do you measure defect severity? Can a 2D camera really tell how deep a pothole is?
**Honest Answer**:
No, a standard monocular RGB smartphone camera cannot measure physical cavity depth ($z$-axis) or volumetric asphalt loss. We state this clearly in our UI, documentation, and paper: our severity score ($0 \dots 10$) is an **empirical visual proxy** calculated from the 2D bounding box area scaled by damage class weights. True volumetric depth requires 3D LiDAR or structured stereo camera rigs, which we outline in `docs/FUTURE_WORK.md`.

---

### Q7: Where do traffic volume numbers come from? Are they measured in real-time?
**Honest Answer**:
No. As documented in `docs/ASSUMPTIONS.md`, real-time sensor loop counts are not available for every municipal street. WinterRoad infers daily traffic volume from OpenStreetMap road hierarchy tags (Motorway $\to$ 30,000 veh/day, Arterial $\to$ 15,000 veh/day, Residential $\to$ 1,000 veh/day) using a logarithmic scaling formula. This is a configurable planning assumption, not an inductive loop count.

---

### Q8: What if a municipal engineer disagrees with the facility multipliers (e.g. +60% for hospitals)?
**Honest Answer**:
All multipliers, danger weights, and rate cards are fully decoupled into [`config.json`](file:///Users/kesavkrishnan/HTH151CV12/config.json). If a municipal council decides that school zones should receive a +70% boost while hospitals receive +50%, they simply edit `config.json` without modifying any backend or optimization code. Rerunning `scripts/compare_prioritization.py` recalculates the repair plan instantly.

---

### Q9: Does the Knapsack optimizer ever lose to Worst-First heuristics, and what is its win rate?
**Honest Answer**:
Under identical discrete ceiling costs ($c_i = \lceil \text{cost}_i / \text{unit} \rceil$) and discrete budget capacity ($B = \lfloor \text{budget} / \text{unit} \rfloor$), **Knapsack mathematically NEVER loses** (0.0% loss rate across 500 trials; **62.0% strict win**, **38.0% tie**, **100.0% win-or-tie**). Because dynamic programming solves the 0/1 integer program to global optimality over the discrete feasible set, any discrete greedy selection is merely a candidate within that set whose sum of values cannot exceed the optimum.

The previously reported 21.8% losses occurred exclusively due to an evaluation asymmetry: Knapsack was evaluated with integer ceiling rounding, while Worst-First was given continuous float costs, allowing it to pack marginal items with residual fractional budget. Against citizen complaint queues, Knapsack strictly wins in **73.6%** of trials with an average risk reduction gain of **+8.96 percentage points**.

---

### Q10: How stable is the repair plan if asphalt and material prices fluctuate?
**Honest Answer**:
In `scripts/cost_uncertainty_simulation.py`, we subjected repair costs to 200 stochastic log-normal cost shocks ($\sigma = 15\%$). The average Jaccard similarity across plans was 65.0%. More importantly, the simulation identifies **8 Core Robust segments** that remain funded in $>75\%$ of price realities, giving municipal engineers high confidence on which contracts to tender first.

---

### Q11: Does your optimizer neglect poorer or outlying wards because they have lower traffic?
**Honest Answer**:
Pure risk maximization can indeed concentrate repairs on high-volume commercial corridors. To address this spatial bias, we developed an equity check in `scripts/equity_check.py` that enforces a minimum funding floor across every geographic zone. Under the benchmark ₹5.0L budget and a 25% floor, standard knapsack already funds between 45.9% and 71.6% across all three zones, making the 25% constraint naturally non-binding. Under consistent discrete capacity tracking, standard and fair knapsack achieve the identical optimal 64.37% risk removal, resulting in a **Price of Fairness of 0.00 percentage points** and Gini of **0.101**. When a binding 50% floor is applied, the Price of Fairness is +1.65 percentage points, exactly confirming theoretical bounds that constrained optimization cannot exceed the unconstrained optimum.

---

### Q12: Why use dynamic programming for 0/1 knapsack instead of Integer Linear Programming (ILP)?
**Honest Answer**:
For municipal divisions with up to a few thousand road segments, discretized dynamic programming (unit = ₹1,000) solves in sub-millisecond time (<0.1 ms) without requiring external commercial solver licenses (such as Gurobi or CPLEX). For state-wide or national networks with $>100,000$ segments, the knapsack formulation can be passed to open-source ILP solvers like HiGHS.

---

### Q13: What happens when budget constraints span multiple months?
**Honest Answer**:
We implemented a rolling multi-month simulation in `scripts/multimonth_planning.py`. The budget is distributed in sequential monthly tranches (e.g. ₹2 Lakh/month across 6 months). In each month, funded roads are marked repaired and cleared from the backlog, while new citizen reports dynamically enter the queue. The backlog was reduced from 30 initial segments to 13 segments by month 6 while absorbing incoming reports.

---

### Q14: What is the status of the video survey de-duplication pipeline?
**Honest Answer**:
In `scripts/video_processor.py`, we implemented a temporal tracking module using Intersection-over-Union association ($\text{IoU} \ge 0.30$) over sliding frames. However, because we do not currently possess a frame-by-frame ground-truth annotated road video benchmark, this module is transparently marked `is_demo_only: true` in `results/video_processing_demo.json`. We list the exact required video dataset in `docs/NEEDS_FROM_ME.md`.

---

### Q15: How is privacy blurring implemented and does it create latency bottlenecks?
**Honest Answer**:
We upgraded the privacy pipeline (`privacy.py`) from legacy Haar cascades to deep OpenCV YuNet (`face_detection_yunet_2023mar.onnx`, MIT license) coupled with a Sobel-X license plate morphological filter. On CPU, it executes in 6.3 ms (158.6 FPS), adding virtually zero latency overhead to the 37.7 ms YOLO inference. In testing on 20 pavement frames, it produced zero false detections on asphalt pavement textures. It serves as a technical privacy demonstrator rather than a certified statutory compliance mechanism (e.g. DPDP / GDPR).

---

### Q16: Where does the ₹5.50 Lakh savings from citizen report fusion come from?
**Honest Answer**:
In `scripts/report_fusion.py` (`results/report_fusion_analysis.json`), 50 simulated citizen reports were clustered into 24 physical sites using greedy spatial clustering with a 25.0-meter radius. The ₹550,779 total savings consists of:
- **₹390,000 (70.8%)**: Eliminating 26 redundant contractor crew & equipment mobilizations (26 × ₹15,000 fixed fee).
- **₹160,779 (29.2%)**: Avoiding redundant overlapping asphalt patch material.
This models the real-world operational overhead of municipal road dispatch.

---

### Q17: How is authentication handled between citizens and administrators?
**Honest Answer**:
WinterRoad implements strict role segregation:
- **Citizen Flow**: Requires zero login or registration. Submissions generate unguessable ticket codes (`WR-XXXXXX`). Citizens track status via a read-only endpoint that redacts internal notes, AI debug confidence, and reviewer timestamps.
- **Admin Flow**: Administrative endpoints (`/api/reports`, `/api/plan`, status triage) are protected server-side with PBKDF2-HMAC-SHA256 password hashing and token sessions, returning HTTP 401/403 upon unauthorized access. As documented in `docs/LIMITATIONS.md`, this is demo-grade authentication suitable for evaluation, not high-availability enterprise IAM.

---

### Q18: Why is this system named WinterRoad, and what is the team composition?
**Honest Answer**:
The project was originally conceived during a hackathon under the prototype name "Gladiators". It has been comprehensively re-engineered, mathematically formalized, and validated as **WinterRoad** for research presentation by **Team WinterBorn** (B K Kesavkrishnan and S Arun Kumar). Every performance metric reported is reproducible from standalone scripts in `scripts/` and saved to `results/`.
