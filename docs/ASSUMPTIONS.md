# WinterRoad: System Assumptions & Calibration Rationale

**Project**: WinterRoad  
**Team**: WinterBorn  
**Authors**: B K Kesavkrishnan, S Arun Kumar  
**Configuration Reference**: [`config.json`](file:///Users/kesavkrishnan/HTH151CV12/config.json), [`winterroad_config.py`](file:///Users/kesavkrishnan/HTH151CV12/winterroad_config.py)

---

## 1. Philosophical Distinction: Measurement vs. Assumption

> [!IMPORTANT]
> A core requirement of reproducible scientific research is cleanly separating **empirical measurements** from **planning assumptions**. In WinterRoad, neural network bounding boxes and geospatial coordinates are empirical observations; all multipliers, rates, and priority formulas are explicitly treated as **configurable policy assumptions**.

None of the weights in this document represent universal laws of physics. Instead, they model municipal maintenance planning trade-offs. Municipal authorities deploying WinterRoad in production can recalibrate these values to match their local city Schedule of Rates (SOR) and road safety priorities.

---

## 2. Road Defect Severity & Danger Weights

| Defect Code | Defect Type | Danger Weight ($w_c$) | Rationale as an Assumption |
| :--- | :--- | :---: | :--- |
| **D00** | Longitudinal Crack | `0.4` | Longitudinal cracks follow wheel paths. While structurally problematic over time, they present minimal immediate blowout or destabilization risk to moving vehicles. |
| **D10** | Transverse Crack | `0.5` | Transverse cracks cross the road surface. High-speed traversal causes vehicle vibration and ride discomfort, but low acute accident likelihood. |
| **D20** | Alligator Crack | `0.8` | Interconnected crocodile-skin cracking indicates underlying subgrade base failure. Water penetration rapidly accelerates structural collapse. |
| **D40** | Pothole | `1.0` | Severe localized cavities present immediate acute risk: tire blowout, wheel rim fracture, motorcycle loss of control, and emergency swerving accidents. |

### Severity Scoring Heuristic
$$\text{Severity} = \min\left(10.0, 20 \times \sum_{i \in \text{detections}} w_{c,i} \cdot a_i\right)$$
- **Assumption**: $a_i$ is the 2D bounding box area normalized to $[0, 1]$.
- **Scaling Factor (20)**: Maps typical cumulative defect areas ($0.05 \dots 0.50$ of frame) into a conventional $0 \dots 10$ municipal rating scale.
- **Limitation**: This is a visual area proxy, not a laser profilometer measurement of pothole cavity depth or volumetric displacement.

---

## 3. Road Hierarchy & Traffic Estimation

Because real-time inductive loop or sensor counts are rarely available for every municipal lane, daily traffic volume is inferred from OpenStreetMap (OSM) highway tag classifications.

| Road Class | OSM Highway Tags | Estimated Traffic Volume | Normalized Weight ($T_w$) |
| :--- | :--- | :---: | :---: |
| **Highway / Arterial** | `motorway`, `trunk`, `primary` | ~30,000 vehicles/day | `1.00` |
| **Major Secondary** | `secondary`, `secondary_link` | ~15,000 vehicles/day | `0.93` |
| **Collector** | `tertiary`, `tertiary_link` | ~5,000 vehicles/day | `0.82` |
| **Local / Residential**| `residential`, `living_street`, `unclassified` | ~1,000 vehicles/day | `0.67` |

### Normalization Formula
$$T_w = \frac{\log_{10}(\text{Vehicles per Day})}{\log_{10}(30000)}$$
- **Assumption**: Road hazard impact scales logarithmically with vehicle exposure. A pothole seen by 30,000 cars daily causes vastly higher aggregate wear and risk than one seen by 1,000 cars, but not 30× worse for an individual driver.

---

## 4. Public Facility Proximity Multipliers

When road defects occur within walking or emergency transit distance of critical civic infrastructure, failure consequences are magnified.

| Facility Type | Distance Threshold ($R$) | Priority Boost ($B_f$) | Policy Rationale |
| :--- | :---: | :---: | :--- |
| **Hospital / Emergency Clinic** | $500\text{ m}$ | **+60%** | Ambulances carrying critical patients require smooth pavement. Sharp potholes risk exacerbating traumatic spinal or cardiovascular conditions and delay emergency triage. |
| **School (K-12)** | $300\text{ m}$ | **+40%** | Concentrated pedestrian foot traffic of young children, school buses, and bicycles. Sudden evasive swerving by cars presents extreme pedestrian hazard. |
| **College / University** | $400\text{ m}$ | **+30%** | High density of two-wheeler commuters (scooters, motorcycles) who are disproportionately vulnerable to pothole-induced falls. |

### Proximity Multiplier Application
$$\text{Facility Multiplier} = 1.0 + \sum_{f \in \text{nearby}} \frac{B_f}{100} \cdot \max\left(0, 1 - \frac{d_f}{R_f}\right)$$
In current discrete mode, a flat bonus $1 + B_f/100$ applies if any qualifying facility is located within radius $R_f$.

---

## 5. Repair Cost Rate Card (Synthetic Schedule of Rates)

Actual municipal repairs depend on asphalt batch mix prices, roller rentals, and labor contracts. For the research prototype, WinterRoad utilizes a standardized synthetic rate card reflecting typical urban Indian road works.

| Parameter | Value | Unit | Description |
| :--- | :---: | :---: | :--- |
| **Fixed Mobilization** | ₹15,000 | ₹ per site | Minimum overhead to dispatch asphalt crew, compacting roller, safety barricades, and traffic control. |
| **Crack Sealing (D00, D10)**| ₹600 | ₹ / $\text{m}^2$ | Cold-pour or hot-pour elastomeric sealant injection. |
| **Surface Milling & Patching (D20)** | ₹1,200 | ₹ / $\text{m}^2$ | Asphalt milling, tack coat, and thin dense-graded bituminous overlay. |
| **Full-Depth Pothole Patch (D40)** | ₹2,500 | ₹ / $\text{m}^2$ | Saw cutting, excavation, aggregate base compaction, tack coat, and hot-mix asphalt (HMA) compaction. |
| **Image Coverage Assumption** | 20 | $\text{m}^2$ | Road surface area captured within standard mobile camera perspective frame. |
| **Cost Discretization Unit** | ₹1,000 | ₹ | Discretization step used by 0/1 knapsack dynamic programming array. |
| **Cost Uncertainty ($\sigma$)** | 15% | % | Standard deviation for Monte Carlo cost sensitivity simulations. |
| **Spatial Fusion Cluster Radius** | 25 | meters | Greedy spatial radius for merging multiple citizen tickets at the same defect site. |
| **Temporal Duplicate Window** | 30 | days | Max timeframe within which co-located reports are treated as duplicate sightings of the same damage. |

### Citizen Report Fusion & Mobilization Economics [SIMULATED DATA]
When multiple citizens independently submit reports for the same physical pothole:
1. **Spatial Clustering**: Reports within 25m of each other are fused into a single canonical physical repair site using greedy distance clustering (`scripts/report_fusion.py`).
2. **Economic Savings**: Consolidating 50 simulated reports into 24 unique sites avoids 26 redundant dispatches: $26 \times ₹15,000 = ₹390,000$ in contractor equipment mobilization overhead (70.8% of savings) plus $₹160,779$ in duplicate paving material (29.2% of savings), totaling **₹5,50,779 (48.9%) in municipal budget savings**.
3. **Simulation Status**: All 50 citizen tickets were **SIMULATED** using synthetic GPS coordinates sampled around Kochi center coordinates `(9.9312, 76.2673)` with perturbed Gaussian GPS noise ($\sigma \approx 8\text{m}$).

### Simulated Complaint Order Generation Protocol
In `scripts/compare_prioritization.py`, the baseline **Complaint-Order (FCFS)** heuristic evaluates traditional municipal grievance resolution:
- **Arrival Sequence**: Each road corridor in `data/sample_detections_synthetic.csv` is assigned a sequential complaint order index $1, 2, \dots, N$ representing the chronological arrival timestamp into a civic helpline (e.g. 1076 or Spandana).
- **Dispatch Rule**: Under Complaint-Order prioritization, corridors are funded in strict submission sequence ($1 \to 2 \to 3 \dots$) until the available maintenance budget is completely exhausted.
- **Data Status**: Labeled **SIMULATED DATA**. This queue isolates the exact efficiency penalty of servicing complaints in intake order without considering physical defect severity or road traffic hierarchy.

### Segment Repair Cost Equation & Engineering Scaling Assumptions
$$\text{Cost} = \text{Fixed Site Cost (₹15,000)} + \sum_{i \in \text{detections}} \left(\text{Unit Rate}_{c,i} \times a_i \times \text{Coverage Area} \times 10\right)$$

#### Explicit Engineering Assumptions:
1. **Photo Coverage Area ($20\text{ m}^2$)**:
   - Assumes a standard vehicle dashboard mount or handheld smartphone camera held at approximately 1.2m–1.5m height, angled downward at 15°–25° toward the asphalt surface.
   - Geometrical perspective foreshortening projects a trapezoidal field of view capturing roughly $4\text{m} \times 5\text{m} \approx 20\text{ m}^2$ of pavement surface within the frame.
   - Normalized bounding box area $a_i = \text{width} \times \text{height} \in [0, 1]$ represents the 2D pixel area fraction of that $20\text{ m}^2$ frame (e.g., $a_i = 0.05 \implies 0.05 \times 20\text{ m}^2 = 1.0\text{ m}^2$ of visible surface defect).

2. **Engineering Scaling Factor ($\times 10$)**:
   - Bounding boxes generated by YOLOv8 tightly encapsulate only the immediate visible crack aperture or localized pothole cavity.
   - In civil highway repair practice, repairing distress requires saw-cutting vertical edges, milling degraded binder material, applying tack coat bitumen emulsion, and placing compacted dense bituminous macadam extending a **structural safety buffer of 30–50 cm beyond visible distress perimeters**, plus sub-base compaction.
   - The $\times 10$ multiplier is an **engineering planning assumption** that converts 2D normalized surface defect area fraction into the total estimated square meters of required pavement milling, tack coat, and compacted asphalt repair envelope across the full distress perimeter.
   - It is explicitly treated as a configurable engineering parameter in `winterroad_config.py` rather than a direct physical sensor measurement, and can be adjusted by municipal PWD engineers to match local contract specifications. A sensitivity sweep from $\times 5$ to $\times 15$ is provided in `results/multiplier_sensitivity.json`.

---

## 6. How to Recalibrate for Real Cities

To deploy WinterRoad in a municipality such as Chennai, Bengaluru, or Kochi:
1. Open [`config.json`](file:///Users/kesavkrishnan/HTH151CV12/config.json).
2. Substitute the unit rates in `unit_cost_inr_per_m2` with the Public Works Department (PWD) official Schedule of Rates (SOR).
3. If local municipal guidelines prioritize school zones over hospital corridors, adjust `facility_boosts`.
4. Rerun `scripts/compare_prioritization.py` and `scripts/sensitivity_analysis.py` to regenerate all research plots with the updated rate card.
