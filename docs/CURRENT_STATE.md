# WinterRoad: Current State Audit (Pre-Modification)

**Project**: WinterRoad (formerly Gladiators)  
**Team**: WinterBorn  
**Authors**: B K Kesavkrishnan, S Arun Kumar  
**Audit Date**: October 2026  
**Branch**: `winterroad`

---

## 1. Executive Summary

This document captures the exact pre-modification state of the codebase across all directories (`backend/`, `optimizer/`, `dashboard/`, `website/`, `notebooks/`, and `data/`). The system is an end-to-end prototype combining deep learning object detection (YOLOv8) with a 0/1 knapsack budget optimizer for road maintenance prioritization. While the core architecture and concept are compelling, the codebase currently suffers from duplicated hardcoded parameters across multiple languages, lack of reproducible evaluation scripts, unverified detection metrics, fragile external API dependencies, missing privacy controls, and zero automated tests.

---

## 2. Component-by-Component Audit

### 2.1 Backend (`backend/`)

#### What Works
- **FastAPI Core**: Server starts properly with Uvicorn (`backend/main.py`), hosting REST endpoints (`/api/health`, `/api/segments`, `/api/detect`, `/api/plan`, `/api/report`, `/api/reports`, `/api/reports.csv`, `/api/reports/{id}/status`).
- **SQLite Persistence**: Stores citizen-submitted reports in SQLite (`backend/data/reports.db`), tracking submission timestamps, defect classification, confidence, severity, GPS coordinates, notes, and repair status.
- **Image Preprocessing & EXIF GPS**: Correctly extracts EXIF GPS tags (tag 0x8825) from uploaded smartphone photos using PIL.
- **Model Inference**:
  - Successfully interfaces with Ultralytics YOLOv8 models (`best.pt` for RDD2022 cracks, `pothole_best.pt` for potholes).
  - Annotates detected defects with colored bounding boxes and labels via OpenCV.
- **Dynamic Programming Knapsack**: Discretizes road segment repair costs (default step ₹1,000) and solves the 0/1 knapsack problem via dynamic programming.

#### What is Hardcoded
- **Weight and Rate Constants**: Duplicated directly in `backend/main.py` (lines 50–56):
  - Damage class weights: `D00: 0.4`, `D10: 0.5`, `D20: 0.8`, `D40: 1.0`.
  - Unit repair rates (₹/m²): `D00: 600`, `D10: 600`, `D20: 1200`, `D40: 2500`.
  - Fixed site mobilization cost: ₹15,000.
  - Image survey road area: 20 m².
  - Traffic levels: Highway (30,000 veh/day), Arterial (15,000 veh/day), Collector (5,000 veh/day), Local (1,000 veh/day).
- **Heuristic Formulas**:
  - Severity formula: `round(min(10, sum(CLASS_WEIGHT[c] * a for c, a in seg["dets"]) * 20), 2)` where 20 is an arbitrary scaling multiplier.
  - Traffic weight: `round(np.log10(ROAD_TYPES[seg["road"]]) / np.log10(30000), 2)`.
  - Defect size factor: `round(min(2.0, max(0.5, area_main / 0.05)), 2)` which assumes 5% of photo frame is standard defect size.
- **Bounding Box Colors**: Hardcoded BGR color palette for OpenCV drawing.

#### What is Fragile
- **In-Memory Segment Storage**: Segments loaded or created through `/api/detect` reside in a global Python list (`SEGMENTS`). Any server restart wipes in-memory uploads unless manually committed to a file.
- **Hugging Face Hub Dependency**: Fallback calls `hf_hub_download` synchronously. If internet connectivity drops or rate limits hit, unhandled exceptions occur.
- **Computer Vision Shadow/Crater Fallback (`detect_road_depression_potholes`)**: Uses naive Gaussian blur, global Otsu/mean thresholding, and contour aspect ratio checks. Prone to false positives from vehicle shadows, tree shadows, fresh asphalt patches, or oil slicks.
- **Missing Privacy Protection**: Uploaded images are stored raw in `backend/data/uploads/` and served publicly via `/uploads/` without blurring human faces or vehicle license plates.
- **No Rate Limiting**: The `/api/report` and `/api/detect` endpoints lack request throttling, allowing potential denial-of-service through large image uploads.
- **Non-Standard CORS Headers**: Adds `Access-Control-Allow-Private-Network` via a custom middleware that can fail on older or non-standard browsers.

#### What is Untested
- Zero automated unit tests or integration tests for API endpoints.
- No stress testing under concurrent user submissions.
- Edge cases in knapsack (zero budget, segments costing more than budget, non-numeric IDs) are not tested.

---

### 2.2 Optimizer (`optimizer/optimizer.py`)

#### What Works
- **CLI Tooling**: Command-line interface accepting `--csv` and `--budget` flags.
- **Optimization Algorithms**:
  - 0/1 knapsack dynamic programming algorithm.
  - "Worst-first" greedy heuristic baseline.
- **Outputs**: Generates CSV files (`repair_plan.csv`, `unfunded.csv`), a Folium interactive map (`map.html`), and a Matplotlib comparison graph (`budget_curve.png`).
- **Explanation Generation**: Produces basic explanatory text for unfunded segments (`reason()` function).

#### What is Hardcoded
- Duplicates all class weights, unit repair costs, fixed site cost, and traffic levels directly inside `optimizer.py`.
- Discretization unit fixed at ₹1,000 (`unit=1000`).
- Synthetic segments generator uses fixed seed and hardcoded Kochi coordinates (`(9.9312, 76.2673)`).
- Matplotlib script has fixed budget increments (`np.arange(1, 21) * 1e5`).

#### What is Fragile
- If segments have costs less than 1 unit or zero cost, indexing and rounding can misbehave.
- Missing standard heuristic baselines: Only compares against "Worst-First" (greedy by severity). Does not implement "Benefit-per-Cost" (greedy by risk/cost, the standard Knapsack heuristic) or "Complaint-Order" (first-come, first-served).
- Relies on headless Matplotlib (`Agg` backend), which works but lacks configurable styling or research-grade vector export.

#### What is Untested
- No unit tests validating knapsack against known analytical solutions or benchmark instances.
- No automated validation of CSV column format or NaN handling.

---

### 2.3 Dashboard (`dashboard/app.py`)

#### What Works
- **Streamlit Interface**: Interactive budget slider (₹1.0 L to ₹20.0 L).
- **Key Metrics (KPIs)**: Displays total damaged segments, total cost, allocated budget, segments repaired, and network risk removed.
- **Geographic Folium Integration**: Displays circle markers with popups detailing segment name, severity, traffic, and cost. Green indicates funded; red/orange/gray indicates unfunded.

#### What is Hardcoded
- Duplicates all settings (damage weights, rates, road types, center coordinates) for a third time.
- Hardcoded synthetic data generator if `detections.csv` is absent.

#### What is Fragile
- Expects `detections.csv` in the current working directory, failing if run from the project root instead of inside `dashboard/`.
- Streamlit-Folium bidirectional interaction triggers heavy re-renders when adjusting sliders.

#### What is Untested
- No automated UI or regression testing.

---

### 2.4 Website & Frontend (`website/index.html` & `backend/static/index.html`)

#### What Works
- **Leaflet GIS Map**: Full interactive mapping with street, satellite, and OSM tile layers.
- **Overpass API Integration**: Successfully downloads real road networks, hospital locations, school locations, and colleges for Indian cities.
- **Client-Side Planner**: Computes knapsack repair plans locally in JavaScript using Leaflet layers.
- **Citizen Reporting UI**: Drag-and-drop or file upload for road photos with note input and status alerts.

#### What is Hardcoded
- Duplicates all parameters a fourth time in JavaScript:
  - Road traffic speeds and daily volumes.
  - Defect weights and repair rates.
  - Critical facility proximity bonus values: Hospital +60% within 500m, School +40% within 300m, College +30% within 400m.
- Hardcoded list of public Overpass API mirrors.

#### What is Fragile
- **Overpass Rate Limits**: Public Overpass endpoints often throttle requests, timeout (HTTP 504), or return 429 errors when downloading dense urban areas.
- **Simulated Damage Injected Client-Side**: If no dataset is loaded, synthetic damage points are generated across OSM roads, which can be mistaken for real measured data if not clearly marked.
- **Geolocation Permission Flow**: Lacks a clear single-shot prompt on submission; does not validate distance between device GPS and EXIF GPS, allowing undetected location mismatches.
- **Privacy Notice Missing**: Does not disclose data collection policies or inform citizens that the system is a research prototype.

#### What is Untested
- No automated JavaScript test coverage for knapsack, distance calculations, or API fetch fallbacks.

---

### 2.5 Notebooks (`notebooks/`)

#### What Works
- **`road_damage_detection.ipynb`**: Documents training and validation steps for YOLOv8 on the RDD2022 dataset using Roboflow and Hugging Face.
- **`chennai_survey_to_dataset.ipynb`**: Documents an extraction pipeline converting geotagged smartphone photos into a structured survey dataset.

#### What is Hardcoded & Fragile
- Roboflow API keys are placeholders.
- Google Colab-specific paths (`/content/drive/MyDrive/...`).
- Hardcoded validation mAP metrics in markdown cells without automated verification scripts.
- No offline reproducibility: notebooks cannot be executed in an automated headless test suite without external cloud dependencies.

---

## 3. Summary of Gaps for Research Presentation

| Requirement | Current Status | Required Action for WinterRoad |
| :--- | :--- | :--- |
| **Project Identity & Credits** | Branded as "Gladiators", team Gladiators | Rename everywhere to "WinterRoad", team "WinterBorn" (B K Kesavkrishnan, S Arun Kumar). Create `docs/CREDITS.md`. |
| **Centralized Assumptions** | Duplicated across 4 files in Python & JS | Create single source of truth config (`winterroad_config.yaml` / `.json`) and write `docs/ASSUMPTIONS.md`. |
| **Detection Metrics & Speed** | Reported as static text in README & Notebook | Build automated evaluation script saving precision, recall, mAP per class, and FPS benchmark to `results/detection_metrics.json`. |
| **Prioritization Benchmarks** | Only compares Knapsack vs Worst-First | Implement Complaint-Order, Worst-First, Benefit-per-Cost Greedy, and Knapsack with budget sweep and plain reasons. |
| **Sensitivity Analysis** | None | Implement weight variation study testing stability and knapsack advantage; export plots and tables to `results/`. |
| **Live Citizen Location** | Generic location toggle | Implement single-shot permission on submit, EXIF vs device GPS distance mismatch flagging, manual map fallback, rate limiting. |
| **Privacy & Safety** | Raw images saved and served; no disclaimers | Add automatic face & license-plate blurring; add prominent research prototype disclaimers. |
| **Research Extensions** | None | Uncertainty-aware prioritization, cost Monte Carlo stability, report fusion, spatial equity analysis, PDF work order generation. |
| **Automated Tests** | Zero tests | Build test suite for optimizer, cost models, risk scores, and data loading. |

This audit serves as the baseline for all subsequent WinterRoad enhancements.
