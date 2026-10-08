# WinterRoad: Audit & Verification Report (`docs/FINAL_FIXES.md`)

**Project**: WinterRoad  
**Team**: WinterBorn  
**Authors**: B K Kesavkrishnan, S Arun Kumar  
**Branch**: `winterroad-v2`  
**Status**: All 9 Audit & Verification Items Diagnosed, Resolved, and Empirically Grounded  

---

## Executive Summary

This pass resolves nine specific empirical, mathematical, security, and architectural issues on branch `winterroad-v2`. In strict compliance with research integrity standards (*"Never invent data. Verify by running scripts"*):
- Every metric in this document is pulled directly from reproducible scripts saving outputs to `results/*.json`.
- The admin password exists exclusively in `.env` (with 0 occurrences in git history and documentation).
- The Norway defect benchmark reports exclusively the 3-class crack mAP (0.353), with the legacy 4-class average purged repo-wide.
- Price of Fairness is theoretically proved and empirically measured across a binding-floor sweep (25%, 40%, 50%, 60%).
- Knapsack vs. Worst-First is evaluated under identical ceiling-rounded costs, confirming that Knapsack **never loses** (0.0% loss rate).
- An engineering cost multiplier sensitivity sweep ($\times 5$ to $\times 15$) is added, and all unverified IRC/MoRTH citations have been removed.
- Complaint-order allocation is quantified via a 500-permutation distribution (mean 52.29%, range [43.6%, 60.4%]).
- All mentions of "100% recall" are removed; real-photo privacy recall is honestly paused awaiting user test data.

| Item | Problem / Diagnostic | Resolution & Empirical Verification | Primary Artifact |
|---|---|---|---|
| **1. Admin Password Security** | Password exposure in documentation and comments. | Purged from all docs, code comments, and output text. Loaded strictly from `.env`. Zero occurrences in git history. User instructed to rotate it. | `.env`, `backend/main.py` |
| **2. Norway mAP Benchmark** | Legacy 4-class average diluted real crack performance with an unrepresentative N=1 pothole split. | Legacy 4-class average purged repo-wide. 3-class crack mAP (**0.353**) reported exclusively, labeled strictly as *Norway validation, crack classes only (D00, D10, D20)*. | `results/detection_metrics.json` |
| **3. Price of Fairness Bound** | Negative PoF violates optimization theory ($\mathcal{F}_{\text{fair}} \subseteq \mathcal{F}_{\text{unconstrained}}$). | Discrete capacity tracked identically across both phases ($B_{\text{rem}} = B - \sum w_i$). Formally proved that two-phase method is a heuristic and its calculated PoF is an upper bound on true optimal PoF. | `scripts/equity_check.py`, `results/equity_analysis.json` |
| **4. Binding-Floor Sweep** | 25% floor was non-binding, masking equity trade-off dynamics. | Added binding-floor sweep across 25%, 40%, 50%, 60%. At 50% floor, constraint binds: PoF = **+1.65 pts**, Gini improves by **43.6%** (0.101 $\to$ 0.057). | `results/equity_sweep.csv`, `results/equity_sweep.png` |
| **5. Discretized Worst-First Comparison** | Coarse ceiling rounding caused asymmetric Knapsack losses vs. float Worst-First. | Evaluated Worst-First under identical ceiling costs $c_i = \lceil \text{cost}_i / \text{unit} \rceil$ and discrete capacity $B$. Knapsack **never loses** (**0.0% losses**, 62.0% strict win, 38.0% tie). | `results/sensitivity_summary.json` |
| **6. Cost Multiplier Sensitivity ($\times 5$ to $\times 15$)** | $\times 10$ scaling lacked empirical sweep and carried unverified IRC citations. | Evaluated sweep across $[5, 7.5, 10, 12.5, 15]$. Gain of Knapsack over WF widens from 0.0 pts (at 5x) to **+3.90 pts** (at 12.5x). Removed all IRC/MoRTH citations repo-wide. | `results/multiplier_sensitivity.csv` |
| **7. Complaint-Order Distribution** | Single static 49.2% number depended on arbitrary CSV row order. | Evaluated 500 randomized arrival permutations at ₹5L budget: **Mean 52.29%**, **Std 2.70%**, **Range [43.60%, 60.43%]**. | `results/complaint_order_distribution.json` |
| **8. Privacy Recall User Text** | "100% recall" text appeared in user-facing report. | Removed all "100% recall" claims. Benchmark honestly labeled as paused awaiting real user photos in `data/own/privacy/`. | `docs/NEEDS_FROM_ME.md` |
| **9. Unified Numbers Table & Tests** | Documentation and dashboard figures needed single-source sync. | Generated `results/numbers_table.{json,csv,md}`. All 19 unit tests pass. All docs and dashboard pages synchronized. | `results/numbers_table.md` |

---

## 1. Item 1: Admin Password Sanitization & Rotation Advice

### Sanitization Audit
1. **Source Code & Documentation**: The literal password has been removed from all documentation, code docstrings, and configuration comments.
2. **Environment Variable**: Loaded strictly from `.env` via `os.environ.get("ADMIN_PASSWORD")` and hashed via PBKDF2-HMAC-SHA256 (600,000 iterations per OWASP).
3. **Git History Search**:
   ```bash
   git log -S "<admin_password>" --oneline
   ```
   **Output: 0 commits.** The credentials were never committed to version control.
4. **Gitignore Protection**: `.env` and `.env.*` are excluded by `.gitignore`.

> [!WARNING]
> **Action Required from User**: Although never committed to git history, the password was historically present in local environment scratch files. Please rotate `ADMIN_PASSWORD` in your local `.env` file to a fresh, strong passphrase prior to deployment.

---

## 2. Item 2: Defect Detection Accuracy (3-Class Crack Benchmark)

### Purging the Legacy 4-Class Average
In the official RDD2022 Norway validation split (1,632 images, Roboflow dataset `tdt4265-vd97u`), potholes (`D40`) have only **1 ground-truth annotation** across the entire validation dataset. Calculating a 4-class mean average precision artificially dragged down the aggregate metric due to a single unrepresentative split.

### Verified 3-Class Crack Benchmark (`results/detection_metrics.json`)
The legacy 4-class average has been purged repo-wide and replaced exclusively by the 3-class crack mAP at 1024px:
- **D00 (Longitudinal Crack):** **0.445 mAP@50** (624 ground-truth annotations)
- **D10 (Transverse Crack):** **0.293 mAP@50** (298 ground-truth annotations)
- **D20 (Alligator Crack):** **0.321 mAP@50** (218 ground-truth annotations)
- **Macro 3-Class Crack Mean:** $\frac{0.445 + 0.293 + 0.321}{3} = \mathbf{0.353\text{ mAP@50}}$
- **Standard Label:** **Norway validation, crack classes only (D00, D10, D20)**

---

## 3. Items 3 & 4: Price of Fairness Proof & Binding-Floor Sweep

### Mathematical Formulation & Theoretical Bound
Let the unconstrained knapsack feasible set be:
$$\mathcal{F}_{\text{unconstrained}} = \left\{ x \in \{0, 1\}^N : \sum_{i=1}^N c_i x_i \le B \right\}$$
Let the fair knapsack require each geographic zone $z \in Z$ to receive at least a minimum funding floor:
$$\mathcal{F}_{\text{fair}} = \left\{ x \in \mathcal{F}_{\text{unconstrained}} : \forall z \in Z, \sum_{i \in \text{Zone}_z} c_i x_i \ge \text{floor}_z \right\}$$

Because every fair candidate plan satisfies the total budget constraint, the fair feasible set is a strict subset of the unconstrained feasible set:
$$\mathcal{F}_{\text{fair}} \subseteq \mathcal{F}_{\text{unconstrained}}$$
Therefore, a constrained plan cannot beat the unconstrained optimum:
$$\max_{x \in \mathcal{F}_{\text{fair}}} \sum_{i=1}^N r_i x_i \le \max_{x \in \mathcal{F}_{\text{unconstrained}}} \sum_{i=1}^N r_i x_i$$
Thus, the true optimal Price of Fairness is mathematically non-negative:
$$\text{PoF}^* = \frac{R^*_{\text{std}} - R^*_{\text{fair}}}{R_{\text{total}}} \ge 0$$

### Two-Phase Heuristic Upper Bound Property
In practice, WinterRoad solves the multi-zone fair knapsack problem using a two-phase polynomial-time heuristic:
- **Phase 1**: Greedily funds high benefit-per-cost defects within each zone until the minimum floor is met.
- **Phase 2**: Solves standard 0/1 knapsack with the remaining discrete budget on remaining segments.

Because Phase 1 may make greedy choices that are suboptimal for the joint integer program, the heuristic fair risk satisfies $R_{\text{heuristic}} \le R^*_{\text{fair}} \le R^*_{\text{std}}$.
Consequently:
$$\text{PoF}_{\text{heuristic}} = \frac{R^*_{\text{std}} - R_{\text{heuristic}}}{R_{\text{total}}} \ge \frac{R^*_{\text{std}} - R^*_{\text{fair}}}{R_{\text{total}}} = \text{PoF}^* \ge 0$$
**The two-phase method's calculated Price of Fairness is an upper bound on the true optimal Price of Fairness.**

### Binding-Floor Sweep Results (`results/equity_sweep.csv`)
Under the benchmark ₹5.0 Lakh budget across 30 municipal segments:

| Floor Requirement | Constraint Status | Fair Risk Removed | Price of Fairness (Upper Bound) | Spatial Gini Inequality | Gini Disparity Change | Zone 1 Funding % | Zone 2 Funding % | Zone 4 Funding % |
|---|---|---|---|---|---|---|---|---|
| **25% Floor** | Non-binding | 64.37% (15.99) | **0.00% pts** | 0.101 | 0.0% | 45.9% | 71.6% | 52.2% |
| **40% Floor** | Non-binding | 64.37% (15.99) | **0.00% pts** | 0.101 | 0.0% | 45.9% | 71.6% | 52.2% |
| **50% Floor** | **BINDING** | 62.72% (15.58) | **+1.65% pts** | **0.057** | **-43.6% inequality** | 61.9% | 52.6% | 47.9% |
| **60% Floor** | **BINDING** | 62.52% (15.53) | **+1.85% pts** | 0.107 | +5.9% inequality | 61.9% | 71.6% | 43.3% |

**Key Takeaways**:
1. At 25% and 40% floors, Standard Knapsack naturally funds $\ge 45.9\%$ in all zones; hence the constraint does not bind ($\text{PoF} = 0.00$ pts).
2. At a 50% floor, Zone 1 is forced upward from 45.9% to 61.9%, sacrificing 1.65 percentage points of global risk reduction in exchange for a **43.6% reduction in geographic funding inequality** (Gini drops from 0.101 to 0.057).

---

## 4. Item 5: Knapsack vs. Worst-First under Identical Discrete Costs

### The Discretization Asymmetry Diagnostic
In earlier trials, Knapsack appeared to tie or lose in 21.8% of trials when compared to Worst-First. Investigation revealed an unfair evaluation asymmetry:
- Knapsack DP discretized costs into integer ceiling quanta: $c_i = \lceil \text{cost}_i / 1000 \rceil$, consuming up to ₹6,500 of phantom budget.
- Worst-First was evaluated using continuous floating-point costs ($\sum \text{cost}_i \le \text{budget}$), allowing it to pack borderline items that Knapsack was rounded out of fitting.

### Rerun Under Identical Ceiling Costs (`results/sensitivity_summary.json`)
When both algorithms are evaluated under the exact same ceiling-rounded costs $c_i = \lceil \text{cost}_i / \text{unit} \rceil$ and discrete capacity $B = \lfloor \text{budget} / \text{unit} \rfloor$ over 500 Monte Carlo trials ($\pm 30\%$ parameter variations):

| Formulation | Discretization Step | Strict Win % | Tie % | Win-or-Tie % | Loss % | Status |
|---|---|---|---|---|---|---|
| **Identical Ceiling Costs** | ₹1,000 unit | **62.0%** | **38.0%** | **100.0%** | **0.0%** | **Knapsack Never Loses** |
| **Identical Ceiling Costs (Unperturbed)** | ₹1,000 unit | **55.4%** | **44.6%** | **100.0%** | **0.0%** | **Knapsack Never Loses** |
| Continuous Worst-First (Asymmetric) | ₹1,000 unit | 46.8% | 31.4% | 78.2% | 21.8% | Discretization Artifact |

**Mathematical Conclusion**:
Because 0/1 dynamic programming solves the discrete problem to global optimality, any discrete greedy solution by Worst-First is merely a candidate in the discrete feasible set. Under identical discretization, **Knapsack mathematically can NEVER lose** (0.0% loss rate across all 500 trials).

---

## 5. Item 6: Cost Multiplier Sensitivity Sweep ($\times 5$ to $\times 15$)

### Engineering Rationale & Citation Cleanup
All informal references to IRC:82 and MoRTH Section 3004 have been removed repo-wide. The $\times 10$ scaling factor is explicitly documented as an engineering planning assumption:
- Bounding boxes tightly encapsulate only the 2D surface crack opening or crater cavity.
- In civil pavement repair practice, repairing distress requires saw-cutting vertical distress perimeters, milling degraded asphalt, applying tack coat bitumen emulsion, and compacting tie-in seams across a **structural buffer of 30–50 cm beyond visible boundaries**.
- The multiplier scales the 2D bounding box area into the total estimated square meters of required excavation, milling, and asphalt compaction.

### Sensitivity Sweep Results (`results/multiplier_sensitivity.csv`)
Evaluated across $[5.0\times, 7.5\times, 10.0\times, 12.5\times, 15.0\times]$ at the focal ₹5.0 Lakh budget:

| Multiplier | Total Repair Cost | Knapsack Risk Removed | Funded Segments (KS) | Worst-First Risk Removed | Funded Segments (WF) | Knapsack Gain over WF |
|---|---|---|---|---|---|---|
| **$5.0\times$** | ₹6,85,358 | 84.51% | 19 segs | 84.51% | 19 segs | **0.00 pts** (Abundant budget) |
| **$7.5\times$** | ₹8,03,036 | 73.16% | 16 segs | 72.80% | 15 segs | **+0.36 pts** |
| **$10.0\times$** | ₹9,20,716 | 64.35% | 13 segs | 61.09% | 12 segs | **+3.26 pts** (Baseline) |
| **$12.5\times$** | ₹10,38,396 | 57.38% | 12 segs | 53.48% | 10 segs | **+3.90 pts** (High scarcity) |
| **$15.0\times$** | ₹11,56,074 | 51.75% | 11 segs | 47.93% | 9 segs | **+3.82 pts** |

**Observed Trend**:
As the cost multiplier increases, budget scarcity tightens. Under abundant budget ($5\times$), greedy heuristics tie because almost all roads are funded. Under tight budgets ($10\times$ to $15\times$), Worst-First squanders funds on 1–2 large repairs, causing Knapsack's optimization advantage to widen from **0.0 pts to +3.90 pts**.

---

## 6. Item 7: Complaint-Order Distribution (500 Random Orderings)

Rather than quoting a single arbitrary number (49.2%) derived from static CSV row order, `scripts/compare_prioritization.py` evaluated **500 random grievance arrival permutations** at ₹5.0 Lakh budget:
- **Mean Network Risk Removed:** **52.29%**
- **Standard Deviation:** **2.70%**
- **Empirical Range [Min, Max]:** **[43.60%, 60.43%]**
- **Knapsack Performance:** **64.37%** (13 segments)

Knapsack's 64.37% risk reduction strictly exceeds the maximum possible complaint-order realization (60.43%) across all 500 trials, providing statistically robust evidence that objective-driven optimization dominates grievance-order response.

---

## 7. Item 8: Privacy Blur Recall Status

All references to "100% recall" have been purged from user-facing documentation. The privacy blurring benchmark is honestly reported as **paused awaiting user test data**:
- **Face Blurring (YuNet)**: Runs in 6.3 ms / 158.6 FPS on CPU.
- **License Plate Blurring (Morphological filter)**: Fully operational.
- **Recall Evaluation Status**: Per project rules (*"Never invent data. If a fix needs data I have not provided, stop that item, list exactly what you need in docs/NEEDS_FROM_ME.md"*), empirical recall is paused pending real user photos in `data/own/privacy/faces/` and `data/own/privacy/plates/`.
- **Benchmark Script Ready**: `scripts/evaluate_privacy_recall.py` is fully prepared to calculate True Positives, False Negatives, and Recall the moment photos are provided.

---

## 8. Item 9: Consolidated Numbers Table (`results/numbers_table.md`)

All documents, slides, and dashboard pages reflect the single source of truth generated by `scripts/make_numbers_table.py`:

| Category | Metric / Parameter | Value | Unit | Data Source | Source File |
|---|---|---|---|---|---|
| **Computer Vision** | D00 Longitudinal Crack mAP@50 | 0.445 | mAP@50 (1024px) | Real (RDD2022 Norway val split) | `results/detection_metrics.json` |
| **Computer Vision** | D10 Transverse Crack mAP@50 | 0.293 | mAP@50 (1024px) | Real (RDD2022 Norway val split) | `results/detection_metrics.json` |
| **Computer Vision** | D20 Alligator Crack mAP@50 | 0.321 | mAP@50 (1024px) | Real (RDD2022 Norway val split) | `results/detection_metrics.json` |
| **Computer Vision** | 3-Class Crack mAP@50 (1024px) | 0.353 | mAP@50 | Norway validation, crack classes only | `results/detection_metrics.json` |
| **Computer Vision** | Pothole (D40) Validation Status | Excluded | Categorical | Audit (RDD2022 Norway metadata, N=1) | `results/norway_split_counts.json` |
| **System Performance** | Privacy Blurring Latency (YuNet) | 6.30 | ms (158.6 FPS) | Real Benchmark (macOS CPU) | `results/pipeline_fps_benchmark.json` |
| **System Performance** | YOLOv8s Defect Detection Latency | 37.69 | ms (26.5 FPS) | Real Benchmark (macOS CPU) | `results/pipeline_fps_benchmark.json` |
| **System Performance** | 0/1 Knapsack DP Solver Latency | 0.06 | ms (>1,000 FPS) | Real Benchmark (macOS CPU) | `results/pipeline_fps_benchmark.json` |
| **System Performance** | End-to-End Pipeline Throughput | 22.7 | FPS (44.1 ms/frame) | Real Benchmark (macOS CPU) | `results/pipeline_fps_benchmark.json` |
| **Prioritization** | Benchmark Budget | ₹5,00,000 | INR (₹5.0 Lakh) | Simulated Network (30 segments) | `results/prioritization_comparison.csv` |
| **Prioritization** | Knapsack Risk Removed @ ₹5L | 64.4% | % of network risk | Simulated Network (30 segments) | `results/prioritization_comparison.csv` |
| **Prioritization** | Worst-First Risk Removed @ ₹5L | 61.1% | % of network risk | Simulated Network (30 segments) | `results/prioritization_comparison.csv` |
| **Prioritization** | Benefit-Cost Greedy Risk Removed @ ₹5L | 63.9% | % of network risk | Simulated Network (30 segments) | `results/prioritization_comparison.csv` |
| **Prioritization** | Complaint-Order Risk (500 FCFS Mean) | 52.3% | % of network risk | Simulated (500 random FCFS orderings) | `results/complaint_order_distribution.json` |
| **Prioritization** | Complaint-Order Risk Range [Min, Max] | [43.6%, 60.4%] | % range | Simulated (500 random FCFS orderings) | `results/complaint_order_distribution.json` |
| **Sensitivity Analysis** | Strict Win Rate vs Worst-First (Ceiling Costs) | 62.0% | % of trials strictly higher | Simulated (500 trials, $\pm 30\%$ weights) | `results/sensitivity_summary.json` |
| **Sensitivity Analysis** | Tie Rate vs Worst-First (Ceiling Costs) | 38.0% | % of trials identical | Simulated (500 trials, $\pm 30\%$ weights) | `results/sensitivity_summary.json` |
| **Sensitivity Analysis** | Win-or-Tie Rate vs Worst-First (Ceiling Costs) | 100.0% | % of trials $\ge$ worst-first | Simulated (Loss rate: 0.0% - Knapsack never loses) | `results/sensitivity_summary.json` |
| **Sensitivity Analysis** | Mean Gain over Worst-First (Ceiling Costs) | +1.54 | Percentage points | Simulated (500 trials, $\pm 30\%$ weights) | `results/sensitivity_summary.json` |
| **Multiplier Sensitivity** | Multiplier Sweep Range | x5 to x15 | Scaling buffer factor | Simulated Network (₹5.0L budget) | `results/multiplier_sensitivity.json` |
| **Multiplier Sensitivity** | Knapsack Gain over WF @ 10x | +3.26 | Percentage points | Simulated Network (₹5.0L budget, 10x multiplier) | `results/multiplier_sensitivity.json` |
| **Multiplier Sensitivity** | Knapsack Gain over WF @ 12.5x | +3.90 | Percentage points | Simulated Network (₹5.0L budget, 12.5x multiplier) | `results/multiplier_sensitivity.json` |
| **Spatial Equity** | Price of Fairness @ 25% Floor (Upper Bound) | 0.00 | Percentage points | Simulated Network (3 zones, non-binding) | `results/equity_analysis.json` |
| **Spatial Equity** | Spatial Gini Index (Standard Knapsack) | 0.101 | Gini Index (0 to 1) | Simulated Network (3 zones) | `results/equity_analysis.json` |
| **Spatial Equity** | Price of Fairness @ 50% Binding Floor | +1.65 | Percentage points | Simulated Network (Binding 50% floor) | `results/equity_sweep.csv` |
| **Spatial Equity** | Fairness Gini Reduction @ 50% Floor | 43.6% | % reduction in inequality | Simulated Network (Gini drops 0.101 $\to$ 0.057) | `results/equity_sweep.csv` |
| **Spatial Equity** | Price of Fairness @ 60% Binding Floor | +1.85 | Percentage points | Simulated Network (Binding 60% floor) | `results/equity_sweep.csv` |
| **Citizen Fusion** | Spatial Clustering Radius | 25.0 | meters | Simulated GPS Reports (greedy radius) | `scripts/report_fusion.py` |
| **Citizen Fusion** | Duplicate Complaints Detected | 52.0% | % duplicate tickets | Simulated GPS Reports (50 tickets $\to$ 24 sites) | `results/report_fusion_analysis.json` |
| **Citizen Fusion** | Total Budget Saved via Fusion | ₹5,50,779 | INR (48.9% saved) | Simulated GPS Reports | `results/report_fusion_analysis.json` |
| **Citizen Fusion** | Mobilization Overhead Saved (Dispatches) | ₹3,90,000 | INR (70.8% of savings) | 26 fewer contractor truck mobilizations | `results/report_fusion_analysis.json` |
| **Citizen Fusion** | Material Patch Savings | ₹1,60,779 | INR (29.2% of savings) | Avoided duplicate paving | `results/report_fusion_analysis.json` |
| **Cost Uncertainty** | Plan Jaccard Stability across Shocks | 0.65 | Jaccard index (0 to 1) | Simulated Log-Normal Shocks (200 draws) | `results/cost_uncertainty_stability.json` |
| **Cost Uncertainty** | Core Segments (Always Funded) | 8 | segments | Simulated Log-Normal Shocks | `results/cost_uncertainty_stability.json` |
| **Engineering Parameters** | Fixed Mobilization Cost per Site | ₹15,000 | INR / site visit | PWD Standard Rate Assumption | `config.json` |
| **Engineering Parameters** | D00/D10 Crack Unit Cost | ₹600 | INR / m² | PWD Standard Rate Assumption | `config.json` |
| **Engineering Parameters** | D20 Alligator Crack Unit Cost | ₹1,200 | INR / m² | PWD Standard Rate Assumption | `config.json` |
| **Engineering Parameters** | D40 Pothole Patch Unit Cost | ₹2,500 | INR / m² | PWD Standard Rate Assumption | `config.json` |
| **Engineering Parameters** | Hospital Proximity Boost | +60% within 500m | Priority multiplier | Engineering Policy Rule | `config.json` |
| **Engineering Parameters** | School Proximity Boost | +40% within 300m | Priority multiplier | Engineering Policy Rule | `config.json` |
| **Engineering Parameters** | College Proximity Boost | +30% within 400m | Priority multiplier | Engineering Policy Rule | `config.json` |
| **Engineering Assumptions** | Photo Perspective Coverage Area | 20 | $\text{m}^2$ / image frame | Downward camera geometry assumption | `config.json` |
| **Engineering Assumptions** | Distress Area to Repair Multiplier | 10x | Scaling multiplier | Pavement saw-cut & tack coat buffer | `winterroad_config.py` |

---

## 9. Verification Commands & Test Results

All verification commands run cleanly with exit code 0:

```bash
# 1. Run Spatial Equity & Binding-Floor Sweep
python scripts/equity_check.py
# Outputs: results/equity_analysis.json, results/equity_sweep.csv, results/equity_sweep.png

# 2. Run Prioritization Strategy Comparison & 500 Complaint Order Permutations
python scripts/compare_prioritization.py
# Outputs: results/prioritization_comparison.csv, results/complaint_order_distribution.json

# 3. Run Monte Carlo Sensitivity & Cost Multiplier Sweep (x5 to x15)
python scripts/sensitivity_analysis.py --trials 500 --unit 1000
# Outputs: results/sensitivity_summary.json, results/multiplier_sensitivity.csv

# 4. Generate Unified Numbers Table
python scripts/make_numbers_table.py
# Outputs: results/numbers_table.{json,csv,md}

# 5. Run Complete Unit Test Suite
python -m unittest discover -s tests -v
# Output: Ran 19 tests in 0.285s -- OK
```

*Branch `winterroad-v2` is completely reconciled, empirically grounded, and mathematically verified.*
