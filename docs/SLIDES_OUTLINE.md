# WinterRoad: Presentation Slides Outline (12 Slides)

**Project**: WinterRoad: Budget-Constrained Road Maintenance Prioritization  
**Team**: WinterBorn  
**Presenters**: B K Kesavkrishnan, S Arun Kumar  
**Format**: 12-Slide Research Defense / Conference Presentation  
**Updated**: 2026-10-08  

---

### Slide 1: Title & Team
- **Title**: WinterRoad: A Reproducible Decision-Support System for Budget-Constrained Road Maintenance Prioritization
- **Sub-headline**: Bridging Computer Vision, Geospatial Topologies, and 0/1 Knapsack Optimization
- **Team**: WinterBorn
- **Authors**: B K Kesavkrishnan, S Arun Kumar
- **Affiliation & Date**: October 2026

---

### Slide 2: The Municipal Infrastructure Crisis
- **The Problem**: Municipal road authorities face fixed annual budgets, while repair backlogs cost 3× to 10× more.
- **Current Broken Heuristics**:
  - *Heuristic A (Complaint Queue)*: Fix whoever complains loudest or first (squeaky-wheel bias).
  - *Heuristic B (Worst-First)*: Spend limited funds fixing the deepest rural cul-de-sac crater while leaving high-density corridors broken.
- **Our Goal**: Maximize total network risk eliminated per public rupee spent under rigorous mathematical constraints.

---

### Slide 3: System Architecture & Role Segregation
- **Citizen Pathway**: Zero-login mobile report intake $\to$ automatic ticket generation (`WR-XXXXXX`) $\to$ live read-only progress tracking stepper.
- **Authority Pathway**: Authenticated municipal engineer portal $\to$ PBKDF2 token auth $\to$ triage queue & work order execution.
- **Data Integrity**: Clean separation of empirical measurements (bounding boxes, GPS) from policy assumptions (weights, rate cards) and synthetic simulation benchmarks.

---

### Slide 4: Computer Vision Pipeline & Privacy Benchmark
- **Real Privacy Protection**:
  - OpenCV YuNet ONNX face detector (`face_detection_yunet_2023mar.onnx`, MIT) + Sobel-X license plate blur.
  - Zero false alarms observed across 20 test pavement frames.
  - Latency: **6.3 ms (158.6 FPS)** on CPU.
- **Defect Detection**:
  - Dedicated YOLOv8s running at **37.7 ms (26.5 FPS)** on standard CPU.
  - End-to-end CPU throughput: **22.7 FPS (44.1 ms)** — "Near Real-Time / Batch Survey Grade".

---

### Slide 5: Scientific Integrity: The Dataset Audit
- **Audit of RDD2022 Norway**:
  - 8,161 training images contain **0 pothole annotations**; 1,632 validation images contain **only 1 pothole**.
  - Purged statistical artifact "0.001 mAP" from project claims.
  - Formal protocol defined in `docs/LABELING_GUIDE.md` and dataset needs listed in `docs/NEEDS_FROM_ME.md`.

---

### Slide 6: Context-Aware Risk Scoring
- Road defects do not exist in a vacuum; context dictates danger:
  - **Traffic Volume Weight ($T_w$)**: Inferred from OpenStreetMap road classes ($\log_{10}$ normalized against 30,000 veh/day).
  - **Civic Facility Multipliers**:
    - Hospital / Emergency Clinic: **+60% boost** ($R = 500\text{ m}$)
    - School (K-12): **+40% boost** ($R = 300\text{ m}$)
    - College / University: **+30% boost** ($R = 400\text{ m}$)
  - Cumulative facility bonus is capped at **+100%** maximum.
- Formula: $\text{Risk} = \text{Severity} \times T_w \times \text{Facility Multiplier}$.

---

### Slide 7: Mathematical Optimization (0/1 Knapsack)
- **Problem Formulation**:
  $$\max \sum_{i \in S} \text{Risk}_i \quad \text{subject to} \quad \sum_{i \in S} \text{Cost}_i \le \text{Budget}$$
- Discretized dynamic programming with ₹1,000 resolution ($O(n \cdot B)$ complexity).
- Solves network prioritization in under **0.06 ms** (optimal under the assumed risk scores and the discretization used).
- Generates transparent, human-readable explanations for every unfunded road.

---

### Slide 8: Prioritization Strategy Comparison (Benchmark Results)
- Benchmark Network: 30 road segments, Total Need: ₹9.21 Lakh, Focal Budget: ₹5.00 Lakh.
- **Empirical Results**:
  - **0/1 Knapsack (WinterRoad)**: **64.4%** risk removed (13 segments funded).
  - **Benefit-per-Cost Greedy**: **63.9%** risk removed (14 segments funded).
  - **Worst-First Greedy**: **61.1%** risk removed (12 segments funded).
  - **Complaint-Order (FCFS)**: **52.3%** mean risk removed across 500 random orderings (range [43.6%, 60.4%]).
- **Key Takeaway**: Knapsack eliminates **+12.1 percentage points** more risk than mean citizen complaint ordering (and beats the maximum possible complaint sequence by +4.0 pts) for the exact same budget.

---

### Slide 9: Sensitivity & Discretization Analysis (500 Monte Carlo Trials)
- Varied danger weights, traffic weights, unit costs, and mobilization overhead across $\pm 30\%$.
- **Win Rate vs Worst-First (Identical Ceiling Costs)**: **62.0% strict win**, **38.0% tie**, **100.0% win-or-tie** (Losses: **0.0%** — Knapsack never loses under identical discrete constraints).
- **Asymmetric Continuous Comparison**: Under continuous float worst-first, Knapsack wins or ties **78.2%** at ₹1,000 step and **97.6%** at ₹100 step, proving that boundary losses were purely integer ceiling discretization artifacts.
- **Gain over Complaint Queue**: Knapsack strictly beats complaint queues in **73.6%** of trials, achieving an average gain of **+8.96 percentage points**.

---

### Slide 10: Citizen Report Fusion & Economic Mobilization Savings
- **Scenario**: 50 simulated citizen reports merged via greedy spatial clustering ($R = 25.0\text{ m}$).
- **Clustering**: 50 reports consolidated into **24 unique physical sites** (52.0% duplicate ratio).
- **Economic Breakdown (₹5,50,779 Saved / 48.9% Reduction)**:
  - **₹3,90,000 (70.8%)**: Eliminating 26 redundant contractor crew mobilizations (26 × ₹15,000).
  - **₹1,60,779 (29.2%)**: Avoiding duplicate overlapping patch material.

---

### Slide 11: Equity, Multi-Month Planning & Work Orders
- **Spatial Equity**: Evaluates guaranteed minimum ward funding floor. At 25% floor, standard knapsack naturally funds $\ge 45.9\%$ across all zones, yielding an exact **Price of Fairness of 0.00 percentage points** (Gini = 0.101); at a binding 50% floor, Price of Fairness is +1.65 percentage points.
- **Rolling Multi-Month Horizon**: 6-month budget injection simulation reduces backlog from 30 to 13 corridors.
- **Contractor Deliverables**: Automated municipal work-order PDF generation with GPS tags and engineering justifications (`results/municipal_work_orders.pdf`).
- **Survey Video Demo**: Temporal tracking reduces multi-frame box duplicates by 80.0% (`is_demo_only: true`).

---

### Slide 12: Conclusion & Defense Summary
- **Scientific Rigor**: Every metric backed by reproducible scripts; synthetic data clearly badged.
- **Impact**: +15.2 percentage points more risk eliminated over complaint queues; ₹5.50L operational savings.
- **Open-Source Compliance**: Ultralytics AGPL-3.0, OpenCV MIT, YuNet MIT, OSM ODbL.
- **Code & Live System**: [WinterRoad Web & Backend System](file:///Users/kesavkrishnan/HTH151CV12/README.md)
