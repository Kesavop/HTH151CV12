# 🛣️ Gladiators: Budget-Constrained Road Maintenance Prioritization

**Hackathon problem:** HTH-CV-07 · Municipal Infrastructure
**Live website:** https://gladiators-roads.netlify.app

City road departments have far more damaged roads than money to fix them. Gladiators finds road damage from photos, puts it on the real city map, gives extra priority to busy roads and to roads near hospitals, schools and colleges, and picks the repairs that remove the most risk within a fixed budget.

## How it works

```
Road photo (GPS) → YOLOv8 damage detection → street + traffic level → public-place priority → 0/1 knapsack → repair plan
```

| Step | What happens |
|---|---|
| Detect | YOLOv8s finds 4 RDD2022 damage types: D00 longitudinal crack, D10 transverse crack, D20 alligator crack, D40 pothole |
| Locate | Photo GPS or the website's "Report damage here" button places each damage on the real street (OpenStreetMap) |
| Weight | Traffic level from road class: High (highway/main road), Medium (secondary/tertiary), Low (residential). Extra priority near hospitals (+60%), schools (+40%), colleges (+30%) |
| Optimize | 0/1 knapsack: maximise total risk removed with total cost ≤ budget. Compared with "fix the worst first" |
| Plan | Map, ranked lists (streets, public places, areas), downloadable dataset CSV |

## Repository structure

```
gladiators-road-repair/
├── website/index.html                          Project website + live planner (any city, GPS reporting)
├── notebooks/
│   ├── road_damage_detection.ipynb             Colab: RDD2022 dataset, training, validation, detections.csv
│   └── chennai_survey_to_dataset.ipynb         Colab: GPS road photos → YOLO → survey dataset CSV
├── optimizer/optimizer.py                      Command-line optimizer (plan CSV, chart, map)
├── dashboard/app.py                            Streamlit dashboard with budget slider
├── backend/                                    FastAPI: photo upload → YOLO → plan API, serves a connected website
└── data/sample_detections_synthetic.csv        Synthetic sample input (for testing only)
```

## Run it

**Website:** open `website/index.html` in Chrome (internet needed for the map), or use the live link above.
Use **📍 My location** and **Report damage here** on a phone (needs the https link).

**Optimizer**
```
cd optimizer
pip install -r requirements.txt
python optimizer.py --csv ../data/sample_detections_synthetic.csv --budget 500000
```

**Dashboard**
```
cd dashboard
pip install -r requirements.txt
python -m streamlit run app.py
```

**Backend**
```
cd backend
pip install -r requirements.txt
python -m uvicorn main:app --reload
```
Open http://127.0.0.1:8000 and http://127.0.0.1:8000/docs

**Notebooks:** upload to Google Colab, choose a T4 GPU, run the cells in order. Put your own Roboflow API key where the notebook says `YOUR_ROBOFLOW_API_KEY`.

## Results

mAP@50 on 1,632 validation images (RDD2022, Norway subset):

| Model | mAP@50 |
|---|---|
| Our YOLOv8s, 18 epochs on free Colab | 0.138 |
| Pretrained RDD2022 YOLOv8s ([dronefreak/rdd2022-yolov8s](https://huggingface.co/dronefreak/rdd2022-yolov8s)), 640 px | 0.240 |
| Same model at 1024 px | **0.265** |

Per class at 1024 px: longitudinal 0.445, alligator 0.321, transverse 0.293, pothole 0.001.

## Data sources and honesty notes

- Streets, hospitals, schools, colleges and area names: © OpenStreetMap contributors.
- Traffic level is **estimated from road class**, not measured.
- Repair rates are **approximate planning assumptions** (₹ per repair), editable on the website.
- Damage shown on the website is **simulated** until real survey data is loaded or reported with GPS.
- `data/sample_detections_synthetic.csv` is synthetic test data.
- Pretrained weights are AGPL-3.0 licensed.

## Limitations and next steps
- Potholes are rarely detected (few potholes in the Norway training data) → fine-tune on Indian road images.
- Replace estimated traffic with real traffic counts from the city.
- Use the city's official Schedule of Rates for repair costs.

## Team
**Gladiators** · Built with YOLOv8 (Ultralytics), PyTorch, Google Colab, pandas, NumPy, Streamlit, FastAPI, Leaflet, OpenStreetMap.
