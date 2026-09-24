"""
Gladiators backend (FastAPI)

Run:   python -m uvicorn main:app --reload
Open:  http://127.0.0.1:8000        (website)
Docs:  http://127.0.0.1:8000/docs   (try every API here)

Endpoints
  GET    /api/health            is the server up, is the model loaded
  GET    /api/segments          all damaged road segments
  POST   /api/detect            upload a road photo + road type -> YOLO detections, new segment
  POST   /api/plan              {"budget": 500000} -> optimal repair plan (0/1 knapsack)
  DELETE /api/segments/{id}     remove one segment
  POST   /api/reset             reload segments from data/detections.csv
"""
import base64
import io
import os

import numpy as np
import pandas as pd
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from PIL import Image
from pydantic import BaseModel

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_CSV = os.path.join(BASE, "data", "detections.csv")

# ---------------- settings (same numbers as the website) ----------------
CLASS_NAME = ["Longitudinal crack", "Transverse crack", "Alligator crack", "Pothole"]
CLASS_WEIGHT = [0.4, 0.5, 0.8, 1.0]
UNIT_COST = [600, 600, 1200, 2500]        # Rs per m2
FIXED_COST = 15000                        # Rs per site
IMG_AREA_M2 = 20
ROAD_TYPES = {"Highway": 30000, "Arterial": 15000, "Collector": 5000, "Local": 1000}

app = FastAPI(title="Gladiators API", version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ---------------- model (loaded on first use) ----------------
_model = None


def get_model():
    global _model
    if _model is None:
        from ultralytics import YOLO
        path = os.path.join(BASE, "best.pt")            # put weights here to work offline
        if not os.path.exists(path):
            from huggingface_hub import hf_hub_download
            path = hf_hub_download("dronefreak/rdd2022-yolov8s", "best.pt")
        _model = YOLO(path)
    return _model


def class_index(name):
    n = name.lower()
    if "d00" in n or "long" in n:
        return 0
    if "d10" in n or "trans" in n:
        return 1
    if "d20" in n or "allig" in n:
        return 2
    return 3


def run_detection(img: Image.Image):
    """Returns (detections, annotated JPEG bytes). detections = [[cls, area, conf], ...]"""
    model = get_model()
    r = model.predict(img, conf=0.25, imgsz=1024, verbose=False)[0]
    dets = []
    for c, cf, (x, y, w, h) in zip(r.boxes.cls.tolist(), r.boxes.conf.tolist(), r.boxes.xywhn.tolist()):
        dets.append([class_index(model.names[int(c)]), round(w * h, 4), round(cf, 3)])
    plotted = r.plot()[:, :, ::-1]                       # BGR -> RGB
    buf = io.BytesIO()
    Image.fromarray(plotted).save(buf, format="JPEG", quality=85)
    return dets, buf.getvalue()


# ---------------- data store (in memory, seeded from CSV) ----------------
SEGMENTS = []
SOURCE = "empty"


def load_csv():
    global SEGMENTS, SOURCE
    SEGMENTS = []
    if os.path.exists(DATA_CSV):
        d = pd.read_csv(DATA_CSV)
        for sid, g in d.groupby("segment", sort=True):
            road = str(g.road_type.iloc[0])
            if road not in ROAD_TYPES:
                continue
            SEGMENTS.append({"id": str(sid), "road": road, "source": "csv",
                             "dets": [[int(c), float(a)] for c, a in zip(g.cls, g.area)]})
        SOURCE = "detections.csv"
    else:
        SOURCE = "empty"


def next_id():
    nums = [int(s["id"].split("-")[-1]) for s in SEGMENTS if s["id"].split("-")[-1].isdigit()]
    return f"SEG-{(max(nums) + 1) if nums else 1:02d}"


load_csv()


# ---------------- scoring + optimizer ----------------
def score(seg):
    sev = round(min(10, sum(CLASS_WEIGHT[c] * a for c, a in seg["dets"]) * 20), 2)
    cost = int(round(FIXED_COST + sum(UNIT_COST[c] * a * IMG_AREA_M2 * 10 for c, a in seg["dets"])))
    tw = round(np.log10(ROAD_TYPES[seg["road"]]) / np.log10(30000), 2)
    level = "Low" if sev <= 3 else "Medium" if sev <= 6 else "High"
    return {"id": seg["id"], "road": seg["road"], "severity": sev, "cost": cost,
            "traffic_w": tw, "risk": round(sev * tw, 2), "level": level}


def knapsack(costs, values, budget, unit=1000):
    c = np.ceil(np.array(costs) / unit).astype(int)
    B = int(budget // unit)
    dp = np.zeros(B + 1)
    keep = np.zeros((len(c), B + 1), bool)
    for i in range(len(c)):
        if c[i] > B:
            continue
        cand = np.full(B + 1, -1.0)
        cand[c[i]:] = dp[:B + 1 - c[i]] + values[i]
        keep[i] = cand > dp
        dp = np.maximum(dp, cand)
    chosen, b = [], B
    for i in range(len(c) - 1, -1, -1):
        if keep[i][b]:
            chosen.append(i)
            b -= c[i]
    return chosen


def worst_first(rows, budget):
    chosen, spent = [], 0
    for i in sorted(range(len(rows)), key=lambda i: -rows[i]["severity"]):
        if spent + rows[i]["cost"] <= budget:
            chosen.append(i)
            spent += rows[i]["cost"]
    return chosen


# ---------------- API ----------------
class PlanRequest(BaseModel):
    budget: float = 500000


@app.get("/api/health")
def health():
    return {"status": "ok", "segments": len(SEGMENTS), "model_loaded": _model is not None}


@app.get("/api/segments")
def segments():
    return {"source": SOURCE, "count": len(SEGMENTS), "segments": SEGMENTS}


@app.post("/api/detect")
async def detect(file: UploadFile = File(...), road_type: str = Form("Arterial")):
    if road_type not in ROAD_TYPES:
        raise HTTPException(400, f"road_type must be one of {list(ROAD_TYPES)}")
    try:
        img = Image.open(io.BytesIO(await file.read())).convert("RGB")
    except Exception:
        raise HTTPException(400, "That file is not an image. Upload a JPG or PNG road photo.")
    try:
        dets, jpg = run_detection(img)
    except Exception as e:
        raise HTTPException(500, f"Model could not run: {e}")
    result = {"found": len(dets),
              "detections": [{"class": CLASS_NAME[c], "code": ["D00", "D10", "D20", "D40"][c],
                              "area": a, "conf": cf} for c, a, cf in dets],
              "image": "data:image/jpeg;base64," + base64.b64encode(jpg).decode()}
    if dets:
        seg = {"id": next_id(), "road": road_type, "source": "upload",
               "dets": [[c, a] for c, a, _ in dets]}
        SEGMENTS.append(seg)
        result["segment"] = seg
        result["score"] = score(seg)
    return result


@app.post("/api/plan")
def plan(req: PlanRequest):
    rows = [score(s) for s in SEGMENTS]
    if not rows:
        return {"budget": req.budget, "plan": [], "risk_removed_pct": 0, "worst_first_pct": 0}
    total = sum(r["risk"] for r in rows) or 1
    opt = knapsack([r["cost"] for r in rows], [r["risk"] for r in rows], req.budget)
    grd = worst_first(rows, req.budget)
    chosen = sorted((rows[i] for i in opt), key=lambda r: -r["risk"])
    for k, r in enumerate(chosen, 1):
        r["priority"] = k
    return {"budget": req.budget,
            "segments_repaired": len(opt),
            "cost_used": sum(rows[i]["cost"] for i in opt),
            "risk_removed_pct": round(sum(rows[i]["risk"] for i in opt) / total * 100, 1),
            "worst_first_segments": len(grd),
            "worst_first_pct": round(sum(rows[i]["risk"] for i in grd) / total * 100, 1),
            "plan": chosen}


@app.delete("/api/segments/{seg_id}")
def delete_segment(seg_id: str):
    before = len(SEGMENTS)
    SEGMENTS[:] = [s for s in SEGMENTS if s["id"] != seg_id]
    if len(SEGMENTS) == before:
        raise HTTPException(404, f"No segment called {seg_id}")
    return {"deleted": seg_id, "count": len(SEGMENTS)}


@app.post("/api/reset")
def reset():
    load_csv()
    return {"source": SOURCE, "count": len(SEGMENTS)}


# website (must be last so /api routes win)
app.mount("/", StaticFiles(directory=os.path.join(BASE, "static"), html=True), name="static")
