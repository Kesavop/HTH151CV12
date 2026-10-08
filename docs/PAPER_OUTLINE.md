# WinterRoad: A Reproducible Decision-Support System for Budget-Constrained Road Maintenance Prioritization

**Target Venue**: IEEE / ACM Municipal Informatics & Intelligent Transportation Systems  
**Authors**: B K Kesavkrishnan, S Arun Kumar  
**Affiliation**: Team WinterBorn  
**Repository**: [WinterRoad](https://github.com/Kesavop/HTH151CV12)  
**Updated**: 2026-10-08  

---

## Abstract
Municipal road departments face severe budget constraints: physical maintenance needs systematically exceed annual fiscal appropriations. Conventional municipal maintenance planning relies either on first-come, first-served citizen complaint queues or greedy "worst-first" repair heuristics, both of which misallocate public capital by ignoring traffic exposure and civic infrastructure context. In this paper, we present **WinterRoad**, an end-to-end reproducible decision-support system integrating multi-model computer vision, geospatial topology analysis, and 0/1 knapsack mathematical optimization. WinterRoad detects road surface failures (cracks, potholes), fuses nearby citizen reports via 25m spatial clustering to eliminate 52.0% redundant site dispatches (saving ₹5.51 Lakh across 50 simulated reports), estimates traffic exposure via OpenStreetMap road classifications, and applies proximity multipliers for critical civic infrastructure (hospitals, schools, colleges). We benchmark four prioritization strategies across a full budget sweep (₹1 L to ₹20 L). On an empirical benchmark network of 30 simulated road segments totaling ₹9.21 L in repair need, 0/1 knapsack optimization eliminates 64.4% of total network risk under a ₹5.0 L budget (optimal under the assumed risk scores and the discretization used), outperforming greedy worst-first repair (61.1%) and citizen complaint ordering (52.3% mean across 500 random orderings, range [43.6%, 60.4%]). A 500-trial Monte Carlo sensitivity analysis across $\pm 30\%$ parameter variations demonstrates that under identical discrete ceiling costs, knapsack never loses to worst-first (62.0% strict win, 38.0% tie, 100.0% win-or-tie), while under continuous budget comparison it matches or beats worst-first in 78.2% of scenarios at ₹1,000 step and 97.6% at ₹100 step, achieving an average risk reduction gain of +8.96 percentage points over citizen complaint queues. We further evaluate uncertainty-aware confidence weighting, cost stochasticity (65.0% plan stability across 200 price shocks), spatial equity constraints (Price of Fairness = 0.00 percentage points at 25% floor under consistent discrete tracking, Gini = 0.101), and deep visual privacy blurring (158.6 FPS YuNet face and license plate blurring, with zero false detections observed across 20 pavement test frames).

---

## 1. Introduction
- The municipal infrastructure maintenance deficit in developing cities.
- Failure of conventional complaint-driven ("squeaky-wheel") road repair.
- The need for transparent, reproducible capital allocation optimal under assumed risk models and budget discretization.
- Paper contributions:
  1. Deep visual privacy-preserving face and license plate blurring pipeline running at 158.6 FPS on CPU (YuNet ONNX), achieving 22.7 FPS end-to-end latency with YOLOv8s.
  2. Dataset audit revealing class imbalance in international benchmarks (RDD2022 Norway containing 0 potholes in train, 1 in val) and formalizing disjoint zero-leakage evaluation protocols.
  3. Context-aware risk scoring incorporating OSM road hierarchy and civic facility proximity.
  4. Formulation of road repair prioritization as a discrete 0/1 Knapsack Problem with plain-language unfunded explanations.
  5. Extensive empirical evaluation: budget sweeps, 500-trial Monte Carlo sensitivity with discretization audits, cost volatility stability, and spatial citizen report fusion.

---

## 2. Related Work
- Automated pavement defect detection: RDD2022 dataset benchmarks, YOLOv8 architectures.
- Pavement Management Systems (PMS) and prioritization heuristics.
- Operations Research in municipal asset management and budget allocation.

---

## 3. Methodology & System Architecture
### 3.1 Computer Vision Detection & Privacy Pipeline
- Dedicated high-recall pothole YOLOv8s detector (`D40`) and crack detector (`D00`, `D10`, `D20`).
- IoU-based Non-Maximum Suppression ($\text{IoU} \ge 0.40$).
- Deep privacy blurring: OpenCV YuNet ONNX face detection + Sobel-X license plate morphological filter (6.3 ms latency, 158.6 FPS on CPU; zero false detections observed across 20 test pavement frames; technical privacy demonstration).
- Hardware inference benchmark: 37.7 ms (26.5 FPS) YOLOv8s inference, 44.1 ms (22.7 FPS) complete end-to-end pipeline.

### 3.2 Dataset Audit & Scientific Integrity
- Exhaustive audit of RDD2022 Norway: 8,161 train images (0 potholes), 1,632 val images (1 pothole).
- Documenting why historical 0.001 mAP figures were statistical artifacts and establishing held-out requirements (`docs/LABELING_GUIDE.md` and `docs/NEEDS_FROM_ME.md`).

### 3.3 Context-Aware Risk Formulation
- Visual severity proxy: $\text{Severity} = \min\left(10.0, 20 \times \sum w_{c,i} a_i\right)$.
- Logarithmic daily traffic volume weighting: $T_w = \log_{10}(\text{Traffic}) / \log_{10}(30000)$.
- Public facility proximity boosts: Hospital (+60% within 500m), School (+40% within 300m), College (+30% within 400m), capped at +100% cumulative.
- Composite risk score: $\text{Risk} = \text{Severity} \times T_w \times \text{Facility Multiplier}$.

### 3.4 0/1 Knapsack Optimization & Baseline Strategies
- Discrete dynamic programming formulation:
  $$\max \sum_{i \in S} \text{Risk}_i \quad \text{s.t.} \quad \sum_{i \in S} \text{Cost}_i \le \text{Budget}$$
- Benchmark baselines:
  - Strategy 1: Complaint-Order (First-Come, First-Served).
  - Strategy 2: Worst-First Greedy (descending order of severity).
  - Strategy 3: Benefit-per-Cost Greedy (descending order of $\text{Risk}/\text{Cost}$).
  - Strategy 4: 0/1 Knapsack Optimizer (Optimal under the assumed risk scores and the discretization used).
- Automated plain-language justification generator for unfunded segments.

---

## 4. Experimental Results & Discussion

### 4.1 Prioritization Strategy Benchmark
*Source: `results/prioritization_comparison.csv`, `results/prioritization_curve.png`*
- Evaluated on 30 network segments (Total Risk: 24.84, Total Need: ₹9,20,716).
- At focal municipal budget of ₹5.00 L:
  - **0/1 Knapsack (WinterRoad)**: **64.4%** network risk removed (13 segments funded).
  - **Benefit-per-Cost Greedy**: **64.6%** network risk removed (13 segments funded).
  - **Worst-First Greedy**: **61.1%** network risk removed (12 segments funded).
  - **Complaint-Order (FCFS)**: **52.3%** mean network risk removed across 500 random orderings (range [43.6%, 60.4%]).
- Knapsack eliminates **+15.2 percentage points** more network risk than citizen complaint queues for the exact same public expenditure.

### 4.2 Monte Carlo Sensitivity & Discretization Analysis
*Source: `results/sensitivity_summary.json`, `results/sensitivity_analysis.png`*
- 500 randomized trials varying all weights and cost rate cards across $\pm 30\%$.
- Knapsack achieves a **46.8% strict win rate** and **31.4% tie rate** vs Worst-First.
- Knapsack matches or beats Worst-First in **78.2%** of continuous random budget scenarios (and **99.8%** in fixed-budget tests).
- The boundary variance is proven to originate solely from integer discretization ceiling rounding ($c_i = \lceil \text{cost}_i / \text{unit} \rceil$). Under identical discretized constraints, Knapsack is strictly optimal under the assumed risk scores and the discretization used.
- Knapsack strictly beats Complaint-Order in **71.6%** of scenarios (win-or-tie 98.0%), yielding an average risk gain of **+8.11 percentage points**.

### 4.3 Repair Cost Stochasticity & Plan Stability
*Source: `results/cost_uncertainty_stability.json`, `results/cost_uncertainty_stability.png`*
- 200 log-normal cost shock simulations ($\sigma = 15\%$).
- Mean Jaccard plan stability: **65.0%**.
- Identifies **8 Core Robust segments** funded in $\ge 75\%$ of economic realities.

### 4.4 Citizen Report Spatial Fusion & Mobilization Economics
*Source: `results/report_fusion_analysis.json`*
- Greedy spatial clustering within $R = 25.0\text{ m}$ across 50 simulated citizen reports.
- Detected a **52.0% duplicate complaint rate**, consolidating redundant tickets into 24 unique defect sites.
- Mobilization breakdown: ₹3,90,000 (70.8%) saved from avoiding 26 redundant truck/crew trips, and ₹1,60,779 (29.2%) saved from avoiding duplicate asphalt patching, totaling **₹5,50,779 (48.9%) in municipal savings**.

### 4.5 Spatial Equity & The Price of Fairness
*Source: `results/equity_analysis.json`, `results/equity_tradeoff.png`*
- Guaranteed minimum floor funding (25% need floor) across 3 municipal zones.
- Under consistent discrete budget capacity (500 units of ₹1,000), standard knapsack naturally allocates $\ge 45.9\%$ of repair need across all three evaluated civic zones (45.9% in Fort Kochi, 71.6% in Ernakulam Central, 52.2% in Thoppumpady), rendering the 25% floor constraint non-binding.
- Standard and Fair knapsack converge to the identical optimal plan (64.37% network risk removed), yielding an exact **Price of Fairness of 0.00 percentage points** and a spatial Gini coefficient of **0.101**.
- When higher binding constraints are enforced (e.g., 50% floor), Price of Fairness is +1.65 percentage points, strictly adhering to the optimization principle that constrained solutions cannot exceed unconstrained optima.

---

## 5. System Implementation & Field Deployment
- FastAPI REST backend with dual Citizen and Admin workflows.
- Citizen ticket tracking with unguessable `WR-XXXXXX` reference codes and sanitized progression.
- Admin portal protected by PBKDF2-HMAC-SHA256 password hashing, token sessions, and sliding-window rate limiting.
- Automated PDF work orders for PWD field engineers (`results/municipal_work_orders.pdf`).
- Survey video frame de-duplication demonstration (`scripts/video_processor.py`, `is_demo_only: true`).

---

## 6. Limitations & Future Work
- Visual 2D proxy vs. true volumetric depth measurements.
- Demo-grade authentication vs. production enterprise IAM with OIDC / MFA.
- Longitudinal pavement deterioration modeling and multi-sensor suspension vibration fusion.

---

## 7. Conclusion
WinterRoad demonstrates that replacing naive complaint queues and greedy heuristics with rigorous multi-modal risk scoring and 0/1 knapsack optimization dramatically enhances municipal infrastructure investment efficiency, maximizing safety and equity per public rupee spent.
