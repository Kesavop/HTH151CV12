# Needs From Me (WinterRoad Data Requirements)

**Project**: WinterRoad  
**Team**: WinterBorn  
**Authors**: B K Kesavkrishnan, S Arun Kumar  
**Status**: Active Blocking Items for Ground-Truth Empirical Evaluations  

---

## Overview

Per the WinterRoad scientific integrity protocol (**"Never invent data, metrics or results"**), evaluation of computer vision detection accuracy (mAP), local domain transfer, and video tracking has been **paused** rather than simulated or fabricated.

The synthetic experiments (Knapsack DP vs Greedy, Monte Carlo sensitivity, DBSCAN report fusion economics) are fully reproducible via scripts in `scripts/`. However, to publish formal computer vision accuracy numbers in the research paper, the following datasets are needed from the team or municipal partners.

---

## 1. Held-Out Labeled Pothole Test Set (for mAP50 / mAP50-95)

### Why it is needed:
Our exhaustive audit of the official RDD2022 Norway dataset (`results/norway_split_counts.json`) revealed that **Norway_train contains 0 pothole annotations** and **Norway_val contains only 1 pothole annotation across 1,632 images**. Any reported mAP on this split is statistically meaningless. To report honest mAP50 and mAP50-95 numbers in Table 1 of the paper, we need an independent labeled test set.

### Required Specifications:
- **Quantity**: 200 to 500 real road photos from vehicle dashcams or smartphone mounts.
- **Pothole representation**: At least 150+ verified pothole instances (class `D40`).
- **Annotation Format**: Standard YOLO format `.txt` files matching each image name:
  ```text
  <class_id> <x_center> <y_center> <width> <height>
  ```
  Where coordinates are normalized floats $[0.0, 1.0]$.
- **Class Map**:
  - `0`: D00 (Longitudinal Crack)
  - `1`: D10 (Transverse Crack)
  - `2`: D20 (Alligator / Fatigue Crack)
  - `3`: D40 (Pothole)
- **Zero Data Leakage**: Must be captured on completely different road segments from any training data (see `docs/LABELING_GUIDE.md`).
- **Target Folder**: `data/benchmark_test/images/` and `data/benchmark_test/labels/`.

---

## 2. Local Indian / Kochi Municipal Road Images (for Domain Adaptation)

### Why it is needed:
Pretrained weights reflect Japanese and Scandinavian asphalt textures. Roads in Kochi feature tropical monsoon weather, bituminous patchwork, concrete pavers, and shoulder degradation. To validate transfer robustness or fine-tune local weights, real local imagery is required.

### Required Specifications:
- **Quantity**: 100 to 300 photos taken on Kochi municipal roads (e.g. Fort Kochi, MG Road, Thoppumpady, Edappally).
- **Camera Settings**: Standard smartphone or dashboard camera mounted at 1.2m–1.5m height, angled downward at 15°–25° toward the roadway.
- **Environmental Diversity**:
  - 50% dry sunny conditions
  - 30% overcast / twilight conditions
  - 20% damp / post-rain conditions (to benchmark puddle reflection robustness)
- **Target Folder**: `data/own/images/` and `data/own/labels/`.

---

## 3. Ground-Truth Annotated Video Sequences (for Temporal De-duplication)

### Why it is needed:
The current temporal IoU de-duplication script (`scripts/video_processor.py`) is marked as `is_demo_only: true` with an explicit disclaimer. Without ground truth tracks across frames, we cannot report Multiple Object Tracking Accuracy (MOTA) or exact false-duplicate suppression rates.

### Required Specifications:
- **Quantity**: 3 to 5 continuous driving video clips (30 to 60 seconds each, 1080p, 20–30 FPS).
- **Vehicle Speed**: 20 km/h to 45 km/h urban driving speed.
- **Telemetry**: Synchronized GPS coordinates (either embedded MP4 EXIF metadata, GPX track log, or accompanying CSV timestamped per frame).
- **Ground Truth**: Ground-truth count of distinct physical potholes passed during each clip to measure the true physical deduplication efficiency.
- **Target Folder**: `data/video_benchmarks/`.

---

## 4. Real Municipal Road Survey & Cadastral GIS Network Data (for Real Prioritization)

### Why it is needed:
All prioritization results currently reported in WinterRoad (the 30-segment benchmark network, ₹9.21 Lakh repair need, ₹5.0 Lakh focal budget, 64.4% risk reduction, Ward equity allocations, and 6-month multi-month rollouts) are computed on **SIMULATED ROAD SEGMENTS** (`data/sample_detections_synthetic.csv`) generated around Kochi center coordinates `(9.9312, 76.2673)`. While the 0/1 knapsack mathematical model, DP solvers, and sensitivity analyses are fully functional and reproducible, deploying the system for real city planning requires real municipal engineering inputs.

### Required Specifications:
- **Road Network GIS Geometry**: GeoJSON or ESRI Shapefile of municipal road centerlines with official functional hierarchy classifications (National Highway, State Highway, Major District Road, Other District Road, Municipal Local Lane).
- **Official Cadastral Ward Boundaries**: Municipal ward polygon shapefiles (e.g. Kochi Municipal Corporation Wards 1 to 74) to replace OpenStreetMap civic place centroid approximations.
- **Physical Defect Survey Data**: Real road distress survey records (GPS coordinates, defect class, distress area/dimensions, pavement age).
- **Official Public Works Rate Card**: Verified local PWD/CPWD Schedule of Rates (SoR) for cold-pour crack sealant, bituminous concrete tack coats, and pothole patch excavation to replace the synthetic rate card.
- **Target Folder**: `data/municipal_survey/`.

---

## 5. Real Street Photos with People & Vehicle Plates (for Privacy Blur Recall)

### Why it is needed:
To report empirical Recall ($\text{Recall} = \frac{\text{TP}}{\text{TP} + \text{FN}}$) and identify misses for face blurring (OpenCV YuNet deep model) and vehicle license plate blurring (morphological gradient filter), real test photos containing pedestrians and road vehicles are required from the researcher. Per project guidelines ("Never invent data, metrics or results" and "If a fix needs data I have not provided, stop that item, list exactly what you need in docs/NEEDS_FROM_ME.md, and continue with the rest"), this benchmark is paused awaiting real user photos rather than fabricating synthetic recall numbers.

### Required Specifications:
- **Face Test Photos**:
  - **Quantity**: 20 to 50 real street/sidewalk photos taken in daylight and twilight.
  - **Variety**: Walking pedestrians, standing bystanders, varying angles (profile, frontal), distances (2m to 20m).
  - **Target Folder**: `data/own/privacy/faces/`.
- **License Plate Test Photos**:
  - **Quantity**: 20 to 50 real road vehicle photos (two-wheelers, auto-rickshaws, cars, delivery trucks).
  - **Variety**: Indian standard high-security registration plates (HSRP), yellow commercial plates, white private plates.
  - **Target Folder**: `data/own/privacy/plates/`.
- **Ground Truth Annotation**:
  - Optional `manifest.json` in each directory mapping filename to integer count of visible faces/plates (e.g. `{"img_01.jpg": 2}`). If omitted, the benchmark script defaults to 1 expected instance per photo.
- **Execution Script**:
  ```bash
  python scripts/evaluate_privacy_recall.py --face-dir data/own/privacy/faces --plate-dir data/own/privacy/plates
  ```

---

## Current Status Summary

| Evaluation Target | Current Repo Status | Data Nature | Blocking Blocker | Once Provided, Run: |
|---|---|---|---|---|
| **Pothole Detection mAP** | Paused (labeled synthetic / audit) | Real dataset audited | Needs Item 1 | `scripts/evaluate_detector.py` |
| **Local Transfer Adaptation** | Paused (0 local annotations) | Awaiting data | Needs Item 2 | `scripts/transfer_adaptation.py` |
| **Video MOTA Tracking** | Demo status (`is_demo_only: true`) | Synthetic sequence | Needs Item 3 | `scripts/video_processor.py` |
| **Face & Plate Blur Recall** | **Paused** (Awaiting real user photos) | Awaiting real photos | Needs Item 5 | `scripts/evaluate_privacy_recall.py` |
| **Knapsack Prioritization** | **Complete & Verified** | **SIMULATED DATA** (30 segments) | Needs Item 4 for real city | `scripts/compare_prioritization.py` |
| **Monte Carlo Sensitivity** | **Complete & Verified** (500 trials) | **SIMULATED DATA** (±30% weights) | None (Scripted) | `scripts/sensitivity_analysis.py` |
| **Cost Uncertainty Stability** | **Complete & Verified** (200 trials) | **SIMULATED DATA** (log-normal) | None (Scripted) | `scripts/cost_uncertainty_simulation.py` |
| **Spatial Ward Equity & Gini** | **Complete & Verified** (3 zones) | **SIMULATED DATA** (OSM zones) | Needs Item 4 for real wards | `scripts/equity_check.py` |
| **Report Fusion Economics** | **Complete & Verified** (25m clustering) | **SIMULATED DATA** (50 tickets) | None (Scripted) | `scripts/report_fusion.py` |
| **Privacy YuNet & Pipeline FPS** | **Complete & Verified** (CPU benchmark) | **REAL MEASUREMENT** (CPU/ONNX) | None (Scripted) | `scripts/benchmark_fps.py` |
| **Crack mAP@50 (D00/D10/D20)** | **Complete & Verified** (1,632 images) | **REAL MEASUREMENT** (RDD2022 val) | None (Evaluated) | `results/detection_metrics.json` |

---
*Documented under Team WinterBorn scientific protocols. Updated October 2026.*
