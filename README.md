Gladiators: Budget-Constrained Road Maintenance Prioritization Hackathon Problem: HTH-CV-07 · Municipal Infrastructure Live Website: https://gladiators-roads.netlify.app Municipal road departments often have more damaged roads than they can afford to repair at once. Gladiators is designed to help them decide where limited repair money should be spent first. The system detects road damage from images, places the reported damage on a real-world map, considers traffic and nearby public facilities such as hospitals, schools and colleges, and then creates a repair plan based on the available budget. How it works Road Photo + GPS ↓ YOLOv8 Damage Detection ↓ Identify Street + Estimate Traffic ↓ Check Nearby Hospitals / Schools / Colleges ↓ Calculate Repair Priority ↓ 0/1 Knapsack Optimization ↓ Budget-Based Repair Plan What the system does

Detect road damage We use YOLOv8s trained/evaluated with the RDD2022 road-damage dataset. The system identifies four types of damage:
D00 — Longitudinal crack
D10 — Transverse crack
D20 — Alligator crack
D40 — Pothole
Put the damage on the map Each report can be associated with GPS coordinates from the image or directly from the website using "Report damage here." The location is then displayed on a real street map using OpenStreetMap. This allows road authorities to see where the problem actually exists, rather than looking at a list of images alone.
Calculate road priority Not every damaged road has the same impact. Gladiators considers the road type and nearby important public places when calculating priority. Traffic is currently estimated from the road class: Road type Traffic level Highway / Main road High Secondary / Tertiary road Medium Residential road Low
Additional priority is given when damaged roads are located near:

Hospitals — +60%
Schools — +40%
Colleges — +30% These values are configurable planning assumptions rather than measured risk values.
Optimize repairs within the budget The main problem is simple: There may be more roads to repair than the available budget can cover.
Gladiators treats each repair as an item with:

a repair cost
a calculated risk/priority value It then uses a 0/1 Knapsack algorithm to select the combination of repairs that maximizes the total risk addressed without exceeding the available budget. The system can therefore compare the optimized plan with a simple "fix the worst damage first" approach.
Generate a repair plan The final result can be viewed through:
Interactive map
Ranked damaged streets
Public-place priority lists
Area-wise summaries
Budget-based repair recommendations
Downloadable CSV dataset Repository Structure gladiators-road-repair/ │ ├── website/ │ └── index.html │ └── Project website and live road-damage planner │ ├── notebooks/ │ ├── road_damage_detection.ipynb │ │ └── RDD2022 training, validation and detections │ │ │ └── chennai_survey_to_dataset.ipynb │ └── GPS road photos → YOLO → survey dataset │ ├── optimizer/ │ └── optimizer.py │ └── Command-line budget optimizer │ ├── dashboard/ │ └── app.py │ └── Streamlit dashboard │ ├── backend/ │ └── main.py │ └── FastAPI backend │ └── data/ └── sample_detections_synthetic.csv └── Synthetic test data Running the Project Website The simplest option is to open: website/index.html in Chrome. The live version is also available at: https://gladiators-roads.netlify.app The My Location and Report Damage Here features require location access and work best through the HTTPS website on a phone. Optimizer cd optimizer pip install -r requirements.txt python optimizer.py --csv ../data/sample_detections_synthetic.csv --budget 500000 Dashboard cd dashboard pip install -r requirements.txt python -m streamlit run app.py Backend cd backend pip install -r requirements.txt python -m uvicorn main:app --reload Then open: http://127.0.0.1:8000 API documentation: http://127.0.0.1:8000/docs Notebooks The notebooks can be run through Google Colab. For model training, select a T4 GPU and execute the cells in order. The road-damage dataset can be accessed using the Roboflow API key where indicated in the notebook. Model Results The model was evaluated on 1,632 validation images from the Norway subset of RDD2022. Model mAP@50 Our YOLOv8s — 18 epochs on free Colab 0.138 Pretrained RDD2022 YOLOv8s — 640 px 0.240 Pretrained model — 1024 px 0.265
At 1024 px, the per-class results were: Damage type mAP@50 Longitudinal crack 0.445 Alligator crack 0.321 Transverse crack 0.293 Pothole 0.001

The results also show an important limitation: potholes are not being detected reliably by the current model. Data and Assumptions The project intentionally separates measured data from assumptions.

Road and public-place information comes from OpenStreetMap contributors.
Traffic level is currently estimated from road classification rather than live traffic counts.
Repair costs are approximate planning values and can be changed.
Damage displayed on the website is simulated until actual survey data is uploaded or a user reports damage with GPS.
sample_detections_synthetic.csv is synthetic data intended only for testing.
The pretrained model weights are licensed under AGPL-3.0. This means the current system should be viewed as a decision-support prototype, not as an official municipal road assessment system. Current Limitations There are a few areas we want to improve. Pothole detection The current RDD2022 Norway training data contains relatively few useful pothole examples, which is reflected in the very low pothole detection score. The next step is to fine-tune the model using Indian road images, particularly images from Tamil Nadu and other Indian cities. Traffic information Traffic is currently estimated from road classification. A production version could use actual traffic counts or reliable traffic datasets from the respective city. Repair costs The current repair costs are planning estimates. For real municipal deployment, they should be replaced with the city's official Schedule of Rates (SOR). Team Gladiators Built using: YOLOv8 · Ultralytics · PyTorch · Google Colab · pandas · NumPy · Streamlit · FastAPI · Leaflet · OpenStreetMap Our goal is not simply to find damaged roads. It is to help answer the more practical question: "Given the roads that need attention and the money available, where should we repair first to address the greatest amount of risk?"