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

  Public photo reports (saved in the SQLite database data/reports.db)
  POST   /api/report            photo (+ optional lat, lon) -> YOLO result, saved as a new report
  GET    /api/reports           all saved reports (newest first)
  GET    /api/reports.csv       the same, as a CSV file
  POST   /api/reports/{id}/status   {"status": "repaired"} mark a report as fixed
"""
import base64
import csv
import io
import json
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from PIL import Image, ImageOps
from pydantic import BaseModel

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_CSV = os.path.join(BASE, "data", "detections.csv")
DB_PATH = os.environ.get("DB_PATH", os.path.join(BASE, "data", "reports.db"))
UPLOADS = os.environ.get("UPLOAD_DIR", os.path.join(BASE, "data", "uploads"))
os.makedirs(UPLOADS, exist_ok=True)
MAX_UPLOAD_MB = 15

# ---------------- settings (same numbers as the website) ----------------
CLASS_NAME = ["Longitudinal crack", "Transverse crack", "Alligator crack", "Pothole"]
CLASS_WEIGHT = [0.4, 0.5, 0.8, 1.0]
UNIT_COST = [600, 600, 1200, 2500]        # Rs per m2
FIXED_COST = 15000                        # Rs per site
IMG_AREA_M2 = 20
ROAD_TYPES = {"Highway": 30000, "Arterial": 15000, "Collector": 5000, "Local": 1000}

app = FastAPI(title="Gladiators API", version="1.0")
_cors = dict(allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
try:   # newer Starlette: allow the public website to reach a server on your own laptop
    app.add_middleware(CORSMiddleware, allow_private_network=True, **_cors)
except TypeError:
    app.add_middleware(CORSMiddleware, **_cors)


@app.middleware("http")
async def allow_private_network(request: Request, call_next):
    # lets the public website (https://...netlify.app) talk to this server on your own laptop
    response = await call_next(request)
    response.headers["Access-Control-Allow-Private-Network"] = "true"
    return response

# ---------------- model (loaded on first use) ----------------
_model = None


def get_model():
    global _model
    if _model is None:
        from ultralytics import YOLO
        path = os.environ.get("MODEL_PATH", os.path.join(BASE, "best.pt"))   # put weights here to work offline
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
    with db() as con:
        n = con.execute("SELECT COUNT(*) FROM reports").fetchone()[0]
    return {"status": "ok", "segments": len(SEGMENTS), "model_loaded": _model is not None, "reports": n}


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


# ---------------- public photo reports (SQLite database) ----------------
CODES = ["D00", "D10", "D20", "D40"]
_db_lock = threading.Lock()
REPORT_COLS = ["id", "created_at", "lat", "lon", "location_source", "gps_accuracy_m",
               "damage_code", "damage_type", "confidence", "severity", "size_factor",
               "detections", "photo_file", "annotated_file", "note", "status"]


def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with _db_lock, db() as con:
        con.execute("""CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            lat REAL, lon REAL,
            location_source TEXT,          -- 'photo GPS', 'phone GPS' or 'none'
            gps_accuracy_m REAL,
            damage_code TEXT,              -- most serious damage in the photo: D00/D10/D20/D40
            damage_type TEXT,
            confidence REAL,               -- 0..1, how sure YOLO is about that damage
            severity REAL,                 -- 0..10
            size_factor REAL,              -- 1 = average size (same as the planner)
            detections TEXT,               -- JSON list of every box YOLO found
            photo_file TEXT, annotated_file TEXT,
            note TEXT,
            status TEXT DEFAULT 'reported' -- 'reported' or 'repaired'
        )""")


init_db()


def exif_gps(img: Image.Image):
    """Latitude/longitude saved by the phone camera inside the photo, or None."""
    try:
        gps = img.getexif().get_ifd(0x8825)
        if not gps or 2 not in gps or 4 not in gps:
            return None

        def deg(v):
            d, m, s = (float(x) for x in v)
            return d + m / 60 + s / 3600

        lat, lon = deg(gps[2]), deg(gps[4])
        if gps.get(1, "N") in ("S", b"S"):
            lat = -lat
        if gps.get(3, "E") in ("W", b"W"):
            lon = -lon
        if abs(lat) < 0.0001 and abs(lon) < 0.0001:
            return None
        return round(lat, 6), round(lon, 6)
    except Exception:
        return None


def row_to_dict(r, request: Request = None):
    d = dict(r)
    d["detections"] = json.loads(d["detections"] or "[]")
    d["photo_url"] = f"/uploads/{d['photo_file']}" if d["photo_file"] else None
    d["annotated_url"] = f"/uploads/{d['annotated_file']}" if d["annotated_file"] else None
    return d


@app.post("/api/report")
async def create_report(request: Request,
                        file: UploadFile = File(...),
                        lat: float = Form(None), lon: float = Form(None),
                        accuracy: float = Form(None), note: str = Form("")):
    raw = await file.read()
    if len(raw) > MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(413, f"The photo is larger than {MAX_UPLOAD_MB} MB. Send a smaller photo.")
    try:
        original = Image.open(io.BytesIO(raw))
        gps = exif_gps(original)
        img = ImageOps.exif_transpose(original).convert("RGB")
    except Exception:
        raise HTTPException(400, "That file is not an image. Upload a JPG or PNG photo of the road.")

    # location: photo GPS first (exact spot of the photo), then the phone's current GPS
    if gps:
        lat, lon, src, accuracy = gps[0], gps[1], "photo GPS", None
    elif lat is not None and lon is not None:
        src = "phone GPS"
    else:
        lat = lon = accuracy = None
        src = "none"

    try:
        dets, jpg = run_detection(img)
    except Exception as e:
        raise HTTPException(503, f"The AI model could not run: {e}")

    boxes = [{"code": CODES[c], "type": CLASS_NAME[c], "confidence": cf, "area": a} for c, a, cf in dets]
    if not dets:
        return {"saved": False, "found": 0, "detections": [],
                "image": "data:image/jpeg;base64," + base64.b64encode(jpg).decode(),
                "lat": lat, "lon": lon, "location_source": src,
                "message": "No road damage found in this photo. Take a closer photo of the crack or pothole, in daylight."}

    # the most serious damage in the photo decides the report type
    main = max(dets, key=lambda d: (CLASS_WEIGHT[d[0]], d[2]))
    c = main[0]
    conf = max(cf for cc, a, cf in dets if cc == c)
    severity = round(min(10, sum(CLASS_WEIGHT[cc] * a for cc, a, _ in dets) * 20), 2)
    area_main = sum(a for cc, a, _ in dets if cc == c)
    size = round(min(2.0, max(0.5, area_main / 0.05)), 2)   # 5% of the photo = average size

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    key = f"{stamp}-{uuid.uuid4().hex[:6]}"
    photo_file, ann_file = f"{key}.jpg", f"{key}-ai.jpg"
    small = img.copy()
    small.thumbnail((1600, 1600))
    small.save(os.path.join(UPLOADS, photo_file), "JPEG", quality=85)
    with open(os.path.join(UPLOADS, ann_file), "wb") as f:
        f.write(jpg)

    with _db_lock, db() as con:
        cur = con.execute(
            """INSERT INTO reports (created_at, lat, lon, location_source, gps_accuracy_m, damage_code,
               damage_type, confidence, severity, size_factor, detections, photo_file, annotated_file, note)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (datetime.now(timezone.utc).isoformat(timespec="seconds"), lat, lon, src, accuracy,
             CODES[c], CLASS_NAME[c], conf, severity, size, json.dumps(boxes),
             photo_file, ann_file, (note or "")[:300]))
        rid = cur.lastrowid
        row = con.execute("SELECT * FROM reports WHERE id=?", (rid,)).fetchone()

    out = row_to_dict(row)
    out.update({"saved": True, "found": len(dets),
                "image": "data:image/jpeg;base64," + base64.b64encode(jpg).decode(),
                "message": f"{CLASS_NAME[c]} ({CODES[c]}) found. Saved as report #{rid}."})
    return out


@app.get("/api/reports")
def list_reports(limit: int = 500):
    with db() as con:
        rows = con.execute("SELECT * FROM reports ORDER BY id DESC LIMIT ?", (max(1, min(limit, 5000)),)).fetchall()
        total = con.execute("SELECT COUNT(*) FROM reports").fetchone()[0]
    return {"count": total, "reports": [row_to_dict(r) for r in rows]}


@app.get("/api/reports.csv")
def reports_csv():
    with db() as con:
        rows = con.execute("SELECT * FROM reports ORDER BY id").fetchall()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(REPORT_COLS)
    for r in rows:
        w.writerow([r[k] for k in REPORT_COLS])
    return Response(buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=gladiators_reports.csv"})


class StatusRequest(BaseModel):
    status: str


@app.post("/api/reports/{rid}/status")
def set_status(rid: int, req: StatusRequest):
    if req.status not in ("reported", "repaired"):
        raise HTTPException(400, "status must be 'reported' or 'repaired'")
    with _db_lock, db() as con:
        n = con.execute("UPDATE reports SET status=? WHERE id=?", (req.status, rid)).rowcount
    if not n:
        raise HTTPException(404, f"No report #{rid}")
    return {"id": rid, "status": req.status}


@app.on_event("startup")
def warm_up_model():
    # load YOLO in the background so the first photo does not wait for the download
    def load():
        try:
            get_model()
        except Exception as e:
            print("Model will load on first photo:", e)
    threading.Thread(target=load, daemon=True).start()


app.mount("/uploads", StaticFiles(directory=UPLOADS), name="uploads")


# website (must be last so /api routes win)
app.mount("/", StaticFiles(directory=os.path.join(BASE, "static"), html=True), name="static")
