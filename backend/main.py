"""
WinterRoad backend (FastAPI)
Intelligent Road Damage Detection and Budget-Constrained Repair Prioritization.

Project: WinterRoad
Team: WinterBorn
Members: B K Kesavkrishnan, S Arun Kumar

Endpoints:
  GET    /api/health               Server status, loaded models, report count
  GET    /api/config               Central configuration parameters (single source of truth)
  GET    /api/segments             All damaged road segments
  POST   /api/detect               Upload road photo -> YOLO detections + privacy blur
  POST   /api/plan                 Optimal repair plan (0/1 knapsack vs baselines)
  DELETE /api/segments/{id}        Remove one segment
  POST   /api/reset                Reload segments from data/detections.csv

  Citizen Reports:
  POST   /api/report               Single-shot photo + GPS -> AI detection, privacy blur, SQLite
  GET    /api/reports              All saved reports (newest first)
  GET    /api/reports.csv          Export reports as CSV
  POST   /api/reports/{id}/status  Mark report as repaired
"""
import base64
import csv
import io
import json
import os
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timezone

import cv2
import numpy as np
import pandas as pd
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from PIL import Image, ImageOps
from pydantic import BaseModel

# Import centralized configuration and privacy modules
import sys
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from winterroad_config import (
    CONFIG, CODES, CLASS_NAME, CLASS_WEIGHT_MAP, UNIT_COST_MAP,
    FIXED_COST, IMG_AREA_M2, ROAD_TYPES, DISCRETIZATION_UNIT,
    PRIVACY, RATE_LIMIT, GPS_VALIDATION, compute_severity,
    compute_repair_cost, compute_traffic_weight, compute_risk
)
from privacy import detect_and_blur_privacy

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_CSV = os.path.join(BASE, "data", "detections.csv")
DB_PATH = os.environ.get("DB_PATH", os.path.join(BASE, "data", "reports.db"))
UPLOADS = os.environ.get("UPLOAD_DIR", os.path.join(BASE, "data", "uploads"))
os.makedirs(UPLOADS, exist_ok=True)
MAX_UPLOAD_MB = 15

# UI Color palette for OpenCV annotations (BGR format)
# D00 (blue), D10 (purple), D20 (orange), D40 (red)
COLORS_BGR = {
    0: (235, 99, 37),
    1: (237, 58, 124),
    2: (12, 88, 234),
    3: (38, 38, 220)
}

app = FastAPI(title="WinterRoad API", version="2.0", description="WinterRoad Municipal Road Maintenance API")
_cors = dict(allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
try:
    app.add_middleware(CORSMiddleware, allow_private_network=True, **_cors)
except TypeError:
    app.add_middleware(CORSMiddleware, **_cors)

@app.middleware("http")
async def allow_private_network(request: Request, call_next):
    response = await call_next(request)
    response.headers["Access-Control-Allow-Private-Network"] = "true"
    return response

# ---------------- Authentication & Security ----------------
import hashlib
import hmac
import secrets

# Load .env file if present
_env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
if os.path.exists(_env_path):
    with open(_env_path, "r", encoding="utf-8") as _ef:
        for _line in _ef:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip())

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD_ENV = os.environ.get("ADMIN_PASSWORD", "")
ADMIN_PASSWORD_HASH_ENV = os.environ.get("ADMIN_PASSWORD_HASH", "")

SALT = b"winterroad_demo_salt_2026"

def hash_password(pwd: str) -> str:
    """Computes PBKDF2-HMAC-SHA256 password hash (600,000 iterations per OWASP recommendation)."""
    return hashlib.pbkdf2_hmac("sha256", pwd.encode("utf-8"), SALT, 600000).hex()

# Precompute expected hash for demo admin credentials (loaded from .env)
EXPECTED_ADMIN_HASH = (
    ADMIN_PASSWORD_HASH_ENV if ADMIN_PASSWORD_HASH_ENV
    else (hash_password(ADMIN_PASSWORD_ENV) if ADMIN_PASSWORD_ENV else "")
)

def verify_password(plain_pwd: str) -> bool:
    """Verifies plain password against PBKDF2 or standard SHA256."""
    pbkdf2_hash = hash_password(plain_pwd)
    sha256_hash = hashlib.sha256(plain_pwd.encode("utf-8")).hexdigest()
    return (
        hmac.compare_digest(pbkdf2_hash, EXPECTED_ADMIN_HASH) or
        hmac.compare_digest(sha256_hash, EXPECTED_ADMIN_HASH)
    )

_active_sessions = {}
_sessions_lock = threading.Lock()

def create_admin_session(username: str) -> str:
    token = secrets.token_hex(24)
    with _sessions_lock:
        _active_sessions[token] = {
            "username": username,
            "role": "admin",
            "created_at": time.time()
        }
    return token

def check_admin_auth(request: Request):
    """Enforces admin authentication on protected endpoints. Returns session dict or raises 401/403."""
    token = None
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
    elif request.headers.get("X-Admin-Token"):
        token = request.headers.get("X-Admin-Token").strip()
    elif request.cookies.get("winterroad_token"):
        token = request.cookies.get("winterroad_token").strip()

    if not token:
        raise HTTPException(status_code=401, detail="Authentication required. Please log in as an administrator.")

    with _sessions_lock:
        session = _active_sessions.get(token)
        if not session or (time.time() - session["created_at"] > 86400):
            if token in _active_sessions:
                del _active_sessions[token]
            raise HTTPException(status_code=401, detail="Invalid or expired session. Please log in again.")
        if session.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Forbidden: Admin role required.")
        return session

def generate_ticket_code() -> str:
    """Generates an unguessable 6-char alphanumeric ticket code (e.g. WR-7F9K2M)."""
    alphabet = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
    code = "".join(secrets.choice(alphabet) for _ in range(6))
    return f"WR-{code}"

# ---------------- Rate Limiting ----------------
_rate_limit_lock = threading.Lock()
_ip_buckets = {"reports": {}, "track": {}, "login": {}}

def check_rate_limit(client_ip: str, bucket: str, max_per_min: int) -> bool:
    """Tracks per-IP request timestamps within 60s sliding window."""
    now = time.time()
    with _rate_limit_lock:
        b = _ip_buckets.setdefault(bucket, {})
        reqs = [t for t in b.get(client_ip, []) if now - t < 60]
        if len(reqs) >= max_per_min:
            return True
        reqs.append(now)
        b[client_ip] = reqs
        return False

def is_rate_limited(client_ip: str) -> bool:
    return check_rate_limit(client_ip, "reports", RATE_LIMIT.get("max_reports_per_minute", 5))

# ---------------- Model Management ----------------
_model = None
_pothole_model = None

def get_model():
    """Primary road damage model (RDD2022 YOLOv8s)."""
    global _model
    if _model is None:
        from ultralytics import YOLO
        path = os.environ.get("MODEL_PATH", os.path.join(BASE, "best.pt"))
        if not os.path.exists(path):
            from huggingface_hub import hf_hub_download
            path = hf_hub_download("dronefreak/rdd2022-yolov8s", "best.pt")
        _model = YOLO(path)
    return _model

def get_pothole_model():
    """Dedicated high-accuracy pothole detector."""
    global _pothole_model
    if _pothole_model is None:
        from ultralytics import YOLO
        path = os.environ.get("POTHOLE_MODEL_PATH", os.path.join(BASE, "pothole_best.pt"))
        if not os.path.exists(path):
            try:
                from huggingface_hub import hf_hub_download
                path = hf_hub_download("samdutse/pothole-yolov8", "best.pt")
            except Exception:
                path = None
        if path and os.path.exists(path):
            _pothole_model = YOLO(path)
    return _pothole_model

def class_index(name: str) -> int:
    n = name.lower()
    if "d00" in n or "long" in n:
        return 0
    if "d10" in n or "trans" in n:
        return 1
    if "d20" in n or "allig" in n:
        return 2
    return 3

def box_iou(b1, b2) -> float:
    """Intersection-over-Union between two boxes [x1, y1, x2, y2]."""
    x1, y1 = max(b1[0], b2[0]), max(b1[1], b2[1])
    x2, y2 = min(b1[2], b2[2]), min(b1[3], b2[3])
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    a1 = max(0.0, b1[2] - b1[0]) * max(0.0, b1[3] - b1[1])
    a2 = max(0.0, b2[2] - b2[0]) * max(0.0, b2[3] - b2[1])
    union = a1 + a2 - inter
    return inter / union if union > 0 else 0.0

def detect_road_depression_potholes(img: Image.Image):
    """Fallback CV analysis: detects dark recessed cavities characteristic of deep potholes."""
    try:
        w_orig, h_orig = img.size
        img_np = np.array(img)
        if img_np.ndim == 2:
            gray = img_np
        elif img_np.shape[2] == 4:
            gray = cv2.cvtColor(img_np, cv2.COLOR_RGBA2GRAY)
        else:
            gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)

        blurred = cv2.GaussianBlur(gray, (9, 9), 0)
        mean_val = float(np.mean(blurred))
        std_val = float(np.std(blurred))
        if std_val < 8:
            return []

        thresh_val = max(10, mean_val - 1.25 * std_val)
        _, thresh = cv2.threshold(blurred, thresh_val, 255, cv2.THRESH_BINARY_INV)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        opened = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
        closed = cv2.morphologyEx(opened, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        img_area = float(w_orig * h_orig)
        found = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if 0.015 * img_area <= area <= 0.40 * img_area:
                x, y, w, h = cv2.boundingRect(cnt)
                aspect = float(w) / max(1.0, float(h))
                if 0.35 <= aspect <= 2.8:
                    if x > 5 and y > 5 and (x + w) < (w_orig - 5) and (y + h) < (h_orig - 5):
                        roi = gray[y:y+h, x:x+w]
                        if np.mean(roi) < mean_val - 15:
                            found.append({
                                "cls": 3,
                                "conf": 0.45,
                                "area": round((w * h) / img_area, 4),
                                "box": [float(x), float(y), float(x + w), float(y + h)],
                                "source": "cv_depression"
                            })
        if found:
            found.sort(key=lambda b: b["area"], reverse=True)
            return [found[0]]
        return []
    except Exception:
        return []

def annotate_boxes(img: Image.Image, boxes):
    """Draws color-coded bounding boxes and labels."""
    w_orig, h_orig = img.size
    img_np = np.array(img)
    if img_np.ndim == 2:
        img_np = cv2.cvtColor(img_np, cv2.COLOR_GRAY2RGB)
    elif img_np.shape[2] == 4:
        img_np = cv2.cvtColor(img_np, cv2.COLOR_RGBA2RGB)
    img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)

    for b in boxes:
        cls_id = b["cls"]
        color = COLORS_BGR.get(cls_id, (38, 38, 220))
        x1, y1, x2, y2 = [int(v) for v in b["box"]]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w_orig - 1, x2), min(h_orig - 1, y2)

        cv2.rectangle(img_bgr, (x1, y1), (x2, y2), color, 3)
        label = f"{CODES[cls_id]} {CLASS_NAME[cls_id]} {int(b['conf'] * 100)}%"
        font_scale = max(0.5, min(1.0, w_orig / 1000.0))
        thickness = 2 if font_scale > 0.6 else 1
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness)
        y_text = max(y1, th + 8)
        cv2.rectangle(img_bgr, (x1, y_text - th - 6), (x1 + tw + 8, y_text + 4), color, -1)
        cv2.putText(img_bgr, label, (x1 + 4, y_text - 2), cv2.FONT_HERSHEY_SIMPLEX, font_scale, (255, 255, 255), thickness, cv2.LINE_AA)

    _, buf = cv2.imencode(".jpg", img_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
    return buf.tobytes()

def run_detection(img: Image.Image):
    """
    Multi-model ensemble pipeline:
    1. Dedicated YOLOv8 pothole model
    2. Primary RDD2022 YOLOv8 model for cracks
    3. NMS box merging
    4. Adaptive second chance & CV fallback
    Returns (detections, annotated JPEG bytes).
    """
    raw_candidates = []

    # Dedicated pothole model
    try:
        p_model = get_pothole_model()
        if p_model is not None:
            r_p = p_model.predict(img, conf=0.18, imgsz=640, verbose=False)[0]
            for cf, (x, y, w, h), (x1, y1, x2, y2) in zip(
                    r_p.boxes.conf.tolist(), r_p.boxes.xywhn.tolist(), r_p.boxes.xyxy.tolist()):
                raw_candidates.append({
                    "cls": 3,
                    "conf": round(float(cf), 3),
                    "area": round(float(w * h), 4),
                    "box": [float(x1), float(y1), float(x2), float(y2)],
                    "source": "pothole_model"
                })
    except Exception as e:
        print("Pothole model prediction warning:", e)

    # General crack model
    try:
        c_model = get_model()
        if c_model is not None:
            r_c = c_model.predict(img, conf=0.20, imgsz=1024, verbose=False)[0]
            for c, cf, (x, y, w, h), (x1, y1, x2, y2) in zip(
                    r_c.boxes.cls.tolist(), r_c.boxes.conf.tolist(),
                    r_c.boxes.xywhn.tolist(), r_c.boxes.xyxy.tolist()):
                cls_idx = class_index(c_model.names[int(c)])
                raw_candidates.append({
                    "cls": cls_idx,
                    "conf": round(float(cf), 3),
                    "area": round(float(w * h), 4),
                    "box": [float(x1), float(y1), float(x2), float(y2)],
                    "source": "crack_model"
                })
    except Exception as e:
        print("Crack model prediction warning:", e)

    # NMS filtering
    raw_candidates.sort(key=lambda b: (CLASS_WEIGHT_MAP.get(b["cls"], 0.5) * b["conf"]), reverse=True)
    merged_boxes = []
    for cand in raw_candidates:
        if not any(box_iou(cand["box"], kept["box"]) > 0.40 for kept in merged_boxes):
            merged_boxes.append(cand)

    # Adaptive pothole pass
    if not merged_boxes:
        try:
            p_model = get_pothole_model()
            if p_model is not None:
                r_p2 = p_model.predict(img, conf=0.10, imgsz=640, verbose=False)[0]
                for cf, (x, y, w, h), (x1, y1, x2, y2) in zip(
                        r_p2.boxes.conf.tolist(), r_p2.boxes.xywhn.tolist(), r_p2.boxes.xyxy.tolist()):
                    merged_boxes.append({
                        "cls": 3,
                        "conf": round(float(cf), 3),
                        "area": round(float(w * h), 4),
                        "box": [float(x1), float(y1), float(x2), float(y2)],
                        "source": "pothole_model_sensitive"
                    })
        except Exception:
            pass

    # CV fallback
    if not merged_boxes:
        cv_boxes = detect_road_depression_potholes(img)
        if cv_boxes:
            merged_boxes.extend(cv_boxes)

    jpg_bytes = annotate_boxes(img, merged_boxes)
    dets = [[b["cls"], b["area"], b["conf"]] for b in merged_boxes]
    return dets, jpg_bytes

# ---------------- In-Memory Data Store ----------------
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
            SEGMENTS.append({
                "id": str(sid),
                "road": road,
                "source": "csv",
                "dets": [[int(c), float(a)] for c, a in zip(g.cls, g.area)]
            })
        SOURCE = "detections.csv"
    else:
        SOURCE = "empty"

def next_id():
    nums = [int(s["id"].split("-")[-1]) for s in SEGMENTS if s["id"].split("-")[-1].isdigit()]
    return f"SEG-{(max(nums) + 1) if nums else 1:02d}"

load_csv()

def score_segment(seg):
    sev = compute_severity(seg["dets"])
    cost = compute_repair_cost(seg["dets"])
    tw = compute_traffic_weight(seg["road"])
    risk = compute_risk(sev, tw)
    level = "Low" if sev <= 3.0 else "Medium" if sev <= 6.0 else "High"
    return {
        "id": seg["id"],
        "road": seg["road"],
        "severity": sev,
        "cost": cost,
        "traffic_w": tw,
        "risk": risk,
        "level": level
    }

def solve_knapsack(costs, values, budget, unit=DISCRETIZATION_UNIT):
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

def solve_worst_first(rows, budget):
    chosen, spent = [], 0
    for i in sorted(range(len(rows)), key=lambda i: -rows[i]["severity"]):
        if spent + rows[i]["cost"] <= budget:
            chosen.append(i)
            spent += rows[i]["cost"]
    return chosen

# ---------------- Database (SQLite) ----------------
_db_lock = threading.Lock()
REPORT_COLS = [
    "id", "ticket_code", "created_at", "lat", "lon", "location_source", "gps_accuracy_m",
    "location_mismatch", "mismatch_distance_m", "damage_code", "damage_type",
    "confidence", "severity", "size_factor", "detections", "photo_file",
    "annotated_file", "note", "status", "verified_at", "admin_notes"
]

def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with _db_lock, db() as con:
        con.execute("""CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_code TEXT UNIQUE,
            created_at TEXT NOT NULL,
            lat REAL, lon REAL,
            location_source TEXT,
            gps_accuracy_m REAL,
            location_mismatch INTEGER DEFAULT 0,
            mismatch_distance_m REAL DEFAULT 0,
            damage_code TEXT,
            damage_type TEXT,
            confidence REAL,
            severity REAL,
            size_factor REAL,
            detections TEXT,
            photo_file TEXT, annotated_file TEXT,
            note TEXT,
            status TEXT DEFAULT 'received',
            verified_at TEXT,
            admin_notes TEXT
        )""")
        # Safe migration if table exists without new columns
        cur = con.execute("PRAGMA table_info(reports)")
        existing_cols = [c[1] for c in cur.fetchall()]
        if "ticket_code" not in existing_cols:
            con.execute("ALTER TABLE reports ADD COLUMN ticket_code TEXT")
        if "location_mismatch" not in existing_cols:
            con.execute("ALTER TABLE reports ADD COLUMN location_mismatch INTEGER DEFAULT 0")
        if "mismatch_distance_m" not in existing_cols:
            con.execute("ALTER TABLE reports ADD COLUMN mismatch_distance_m REAL DEFAULT 0")
        if "verified_at" not in existing_cols:
            con.execute("ALTER TABLE reports ADD COLUMN verified_at TEXT")
        if "admin_notes" not in existing_cols:
            con.execute("ALTER TABLE reports ADD COLUMN admin_notes TEXT")

        # Backfill any missing ticket codes for existing reports
        rows = con.execute("SELECT id FROM reports WHERE ticket_code IS NULL OR ticket_code = ''").fetchall()
        for r in rows:
            con.execute("UPDATE reports SET ticket_code=? WHERE id=?", (generate_ticket_code(), r[0]))

        # Normalize legacy status labels
        con.execute("UPDATE reports SET status='received' WHERE status='reported'")
        con.execute("UPDATE reports SET status='fixed' WHERE status='repaired'")

init_db()

def exif_gps(img: Image.Image):
    """Extract EXIF latitude/longitude if present."""
    try:
        gps = img.getexif().get_ifd(0x8825)
        if not gps or 2 not in gps or 4 not in gps:
            return None
        def deg(v):
            return float(v[0]) + float(v[1]) / 60.0 + float(v[2]) / 3600.0
        lat = deg(gps[2]) * (-1.0 if gps.get(1, "N") in ("S", b"S") else 1.0)
        lon = deg(gps[4]) * (-1.0 if gps.get(3, "E") in ("W", b"W") else 1.0)
        if abs(lat) < 0.0001 and abs(lon) < 0.0001:
            return None
        return round(lat, 6), round(lon, 6)
    except Exception:
        return None

def haversine_distance(lat1, lon1, lat2, lon2) -> float:
    """Distance in meters between two lat/lon coordinates."""
    R = 6371000.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dp = np.radians(lat2 - lat1)
    dl = np.radians(lon2 - lon1)
    a = np.sin(dp / 2.0)**2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2.0)**2
    return float(2.0 * R * np.arcsin(np.sqrt(a)))

def row_to_dict(r):
    d = dict(r)
    d["detections"] = json.loads(d.get("detections") or "[]")
    d["photo_url"] = f"/uploads/{d['photo_file']}" if d.get("photo_file") else None
    d["annotated_url"] = f"/uploads/{d['annotated_file']}" if d.get("annotated_file") else None
    d["location_mismatch"] = bool(d.get("location_mismatch", 0))
    d["mismatch_distance_m"] = float(d.get("mismatch_distance_m", 0) or 0)
    d["ticket_code"] = d.get("ticket_code") or f"WR-{d['id']:06d}"
    d["status"] = d.get("status") or "received"
    d["admin_notes"] = d.get("admin_notes") or ""
    return d

# ---------------- API Routes ----------------
class PlanRequest(BaseModel):
    budget: float = 500000.0

@app.get("/api/config")
def get_configuration():
    """Single source of truth configuration for UI and API clients."""
    return CONFIG

@app.get("/api/health")
def health():
    with db() as con:
        n = con.execute("SELECT COUNT(*) FROM reports").fetchone()[0]
    return {
        "status": "ok",
        "project": "WinterRoad",
        "team": "WinterBorn",
        "segments": len(SEGMENTS),
        "model_loaded": (_model is not None or _pothole_model is not None),
        "reports": n,
        "disclaimer": "WinterRoad is an academic research prototype, not a certified safety system. Defect severity is a visual 2D proxy from bounding box area, not measured cavity depth."
    }

@app.get("/api/segments")
def segments():
    return {"source": SOURCE, "count": len(SEGMENTS), "segments": SEGMENTS}

@app.post("/api/detect")
async def detect(file: UploadFile = File(...), road_type: str = Form("Arterial")):
    if road_type not in ROAD_TYPES:
        raise HTTPException(400, f"road_type must be one of {list(ROAD_TYPES)}")
    try:
        raw = await file.read()
        img = Image.open(io.BytesIO(raw)).convert("RGB")
    except Exception:
        raise HTTPException(400, "File is not a valid image. Upload a JPG or PNG road photo.")

    # Apply privacy blurring (faces & license plates)
    blurred_img, _ = detect_and_blur_privacy(img)

    try:
        dets, jpg = run_detection(blurred_img)
    except Exception as e:
        raise HTTPException(500, f"Model detection failure: {e}")

    result = {
        "found": len(dets),
        "detections": [{
            "class": CLASS_NAME[c],
            "code": CODES[c],
            "area": a,
            "conf": cf
        } for c, a, cf in dets],
        "image": "data:image/jpeg;base64," + base64.b64encode(jpg).decode()
    }
    if dets:
        seg = {
            "id": next_id(),
            "road": road_type,
            "source": "upload",
            "dets": [[c, a] for c, a, _ in dets]
        }
        SEGMENTS.append(seg)
        result["segment"] = seg
        result["score"] = score_segment(seg)
    return result

# ---------------- Admin Authentication Routes ----------------
class LoginRequest(BaseModel):
    username: str
    password: str

@app.post("/api/auth/login")
def auth_login(req: LoginRequest, request: Request, response: Response):
    """Admin authentication endpoint. Protected against brute-force with rate limiting."""
    client_ip = request.client.host if request.client else "unknown"
    if check_rate_limit(client_ip, "login", 5):
        raise HTTPException(429, "Too many login attempts. Please wait 60 seconds before retrying.")

    if req.username == ADMIN_USERNAME and verify_password(req.password):
        token = create_admin_session(req.username)
        response.set_cookie("winterroad_token", token, httponly=False, samesite="lax", max_age=86400)
        return {
            "authenticated": True,
            "access_token": token,
            "token_type": "bearer",
            "username": req.username,
            "role": "admin"
        }
    raise HTTPException(status_code=401, detail="Invalid administrator username or password.")

@app.post("/api/auth/logout")
def auth_logout(request: Request, response: Response):
    """Revokes active admin session."""
    token = None
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
    elif request.headers.get("X-Admin-Token"):
        token = request.headers.get("X-Admin-Token").strip()
    elif request.cookies.get("winterroad_token"):
        token = request.cookies.get("winterroad_token").strip()
    if token:
        with _sessions_lock:
            _active_sessions.pop(token, None)
    response.delete_cookie("winterroad_token")
    return {"status": "logged_out"}

@app.get("/api/auth/me")
def auth_me(request: Request):
    """Verifies active session and returns role."""
    session = check_admin_auth(request)
    return {
        "authenticated": True,
        "username": session["username"],
        "role": session["role"]
    }

# ---------------- Citizen Public Endpoints (No Account Required) ----------------
@app.post("/api/citizen/report")
@app.post("/api/report")
async def create_report(
    request: Request,
    file: UploadFile = File(...),
    lat: float = Form(None),
    lon: float = Form(None),
    accuracy: float = Form(None),
    note: str = Form("")
):
    """
    Public citizen reporting endpoint:
    Accepts single-shot photo + optional GPS, executes privacy blurring,
    runs defect detection, assigns unguessable ticket code, and stores report.
    Never returns other citizens' data or admin credentials.
    """
    client_ip = request.client.host if request.client else "unknown"
    if check_rate_limit(client_ip, "reports", RATE_LIMIT.get("max_reports_per_minute", 5)):
        raise HTTPException(429, "Rate limit exceeded. Please wait a minute before submitting another report.")

    raw = await file.read()
    if len(raw) > MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(413, f"Photo exceeds {MAX_UPLOAD_MB} MB limit.")

    try:
        original = Image.open(io.BytesIO(raw))
        photo_gps = exif_gps(original)
        img = ImageOps.exif_transpose(original).convert("RGB")
    except Exception:
        raise HTTPException(400, "Invalid image format. Send a JPG or PNG road photo.")

    # Location resolution & Mismatch detection
    location_mismatch = 0
    mismatch_distance_m = 0.0

    if photo_gps and lat is not None and lon is not None:
        dist = haversine_distance(photo_gps[0], photo_gps[1], lat, lon)
        max_dist = GPS_VALIDATION.get("max_mismatch_distance_m", 150.0)
        if dist > max_dist:
            location_mismatch = 1
            mismatch_distance_m = round(dist, 1)
        final_lat, final_lon = photo_gps[0], photo_gps[1]
        src = "photo GPS"
    elif photo_gps:
        final_lat, final_lon = photo_gps[0], photo_gps[1]
        src = "photo GPS"
    elif lat is not None and lon is not None:
        final_lat, final_lon = lat, lon
        src = "device GPS"
    else:
        final_lat = final_lon = accuracy = None
        src = "none"

    # Privacy Protection: Blur faces and license plates before storing or serving
    blurred_img, priv_stats = detect_and_blur_privacy(img)

    try:
        dets, annotated_jpg = run_detection(blurred_img)
    except Exception as e:
        raise HTTPException(503, f"AI model execution error: {e}")

    boxes = [{"code": CODES[c], "type": CLASS_NAME[c], "confidence": cf, "area": a} for c, a, cf in dets]
    if not dets:
        return {
            "saved": False,
            "found": 0,
            "detections": [],
            "image": "data:image/jpeg;base64," + base64.b64encode(annotated_jpg).decode(),
            "lat": final_lat,
            "lon": final_lon,
            "location_source": src,
            "location_mismatch": bool(location_mismatch),
            "mismatch_distance_m": mismatch_distance_m,
            "message": "No road defect detected in this photo. Please submit a closer photo of the crack or pothole in daylight."
        }

    # Principal defect classification
    main_det = max(dets, key=lambda d: (CLASS_WEIGHT_MAP.get(d[0], 0.5), d[2]))
    c = main_det[0]
    conf = max(cf for cc, a, cf in dets if cc == c)
    sev = compute_severity([[cc, a] for cc, a, _ in dets])
    area_main = sum(a for cc, a, _ in dets if cc == c)
    size = round(min(2.0, max(0.5, area_main / 0.05)), 2)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    key = f"{stamp}-{uuid.uuid4().hex[:6]}"
    photo_file = f"{key}.jpg"
    ann_file = f"{key}-ai.jpg"

    small = blurred_img.copy()
    small.thumbnail((1600, 1600))
    small.save(os.path.join(UPLOADS, photo_file), "JPEG", quality=85)
    with open(os.path.join(UPLOADS, ann_file), "wb") as f:
        f.write(annotated_jpg)

    ticket_code = generate_ticket_code()

    with _db_lock, db() as con:
        cur = con.execute(
            """INSERT INTO reports (
                ticket_code, created_at, lat, lon, location_source, gps_accuracy_m,
                location_mismatch, mismatch_distance_m, damage_code, damage_type,
                confidence, severity, size_factor, detections, photo_file,
                annotated_file, note, status
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                ticket_code, datetime.now(timezone.utc).isoformat(timespec="seconds"),
                final_lat, final_lon, src, accuracy,
                location_mismatch, mismatch_distance_m,
                CODES[c], CLASS_NAME[c], conf, sev, size,
                json.dumps(boxes), photo_file, ann_file, (note or "")[:300],
                "received"
            )
        )
        rid = cur.lastrowid

    # Return sanitized citizen receipt (NO admin fields or raw server paths)
    return {
        "saved": True,
        "ticket_code": ticket_code,
        "report_id": rid,
        "status": "received",
        "damage_type": CLASS_NAME[c],
        "damage_code": CODES[c],
        "severity": sev,
        "location_mismatch": bool(location_mismatch),
        "tracking_url": f"/api/citizen/track/{ticket_code}",
        "message": f"Report received successfully. Assigned ticket code: {ticket_code}. Queued for engineering inspection.",
        "privacy": priv_stats
    }

@app.get("/api/citizen/track/{ticket_code}")
def track_ticket(ticket_code: str, request: Request):
    """
    Public ticket tracking endpoint:
    Look up defect status by random ticket code.
    Strictly sanitized: returns status progression only.
    Never exposes other citizens' records, private photos, or internal admin notes.
    """
    client_ip = request.client.host if request.client else "unknown"
    if check_rate_limit(client_ip, "track", 30):
        raise HTTPException(429, "Too many tracking lookups. Please wait a moment.")

    code_clean = ticket_code.strip().upper()
    with db() as con:
        row = con.execute(
            "SELECT id, ticket_code, status, created_at, damage_type, severity, verified_at FROM reports WHERE UPPER(ticket_code)=?",
            (code_clean,)
        ).fetchone()

    if not row:
        raise HTTPException(404, f"No road maintenance report found for ticket code '{ticket_code}'. Please verify the code.")

    status_map = {
        "received": {
            "step": 1,
            "label": "Report Received",
            "desc": "Your road damage report has been logged and queued for engineering verification."
        },
        "verified": {
            "step": 2,
            "label": "Defect Verified",
            "desc": "Inspected and confirmed by municipal PWD engineering review. Added to repair prioritization pool."
        },
        "scheduled": {
            "step": 3,
            "label": "Repair Scheduled",
            "desc": "Approved under municipal budget optimization; contractor work order generated."
        },
        "fixed": {
            "step": 4,
            "label": "Repair Completed",
            "desc": "Road surface restored, quality inspection approved, and ticket closed."
        },
        "rejected": {
            "step": 0,
            "label": "Not Actionable",
            "desc": "Report reviewed but could not be verified (duplicate, non-road surface, or outside municipal jurisdiction)."
        }
    }
    st_info = status_map.get(row["status"], status_map["received"])

    return {
        "ticket_code": row["ticket_code"],
        "status": row["status"],
        "status_step": st_info["step"],
        "status_label": st_info["label"],
        "status_description": st_info["desc"],
        "damage_type": row["damage_type"],
        "severity_score": round(float(row["severity"] or 0), 1),
        "submitted_at": row["created_at"],
        "verified_at": row["verified_at"]
    }

@app.get("/api/citizen/verified-potholes")
def get_verified_potholes():
    """
    Public road safety map data:
    Returns simple municipal counts and a list of VERIFIED potholes only.
    Coordinates are rounded to 4 decimals for civic privacy.
    Unverified reports and private citizen photos are NEVER included.
    """
    with db() as con:
        total_reported = con.execute("SELECT COUNT(*) FROM reports").fetchone()[0]
        total_verified = con.execute("SELECT COUNT(*) FROM reports WHERE status IN ('verified', 'scheduled', 'fixed')").fetchone()[0]
        total_fixed = con.execute("SELECT COUNT(*) FROM reports WHERE status = 'fixed'").fetchone()[0]

        rows = con.execute(
            "SELECT ticket_code, lat, lon, damage_type, severity, status, created_at FROM reports "
            "WHERE status IN ('verified', 'scheduled', 'fixed') AND lat IS NOT NULL AND lon IS NOT NULL"
        ).fetchall()

    public_features = []
    for r in rows:
        public_features.append({
            "ticket_code": r["ticket_code"],
            "lat": round(float(r["lat"]), 4),
            "lon": round(float(r["lon"]), 4),
            "damage_type": r["damage_type"],
            "severity": round(float(r["severity"] or 0), 1),
            "status": r["status"]
        })

    return {
        "counters": {
            "total_reported": total_reported,
            "total_verified": total_verified,
            "total_fixed": total_fixed
        },
        "verified_potholes": public_features
    }

# ---------------- Protected Admin Endpoints (Requires Admin Auth) ----------------
@app.post("/api/plan")
def plan(req: PlanRequest, request: Request):
    """Generates optimal budget-constrained repair plan. Protected: Admin role required."""
    check_admin_auth(request)
    rows = [score_segment(s) for s in SEGMENTS]
    if not rows:
        return {"budget": req.budget, "plan": [], "risk_removed_pct": 0, "worst_first_pct": 0}
    total = sum(r["risk"] for r in rows) or 1.0
    opt = solve_knapsack([r["cost"] for r in rows], [r["risk"] for r in rows], req.budget)
    grd = solve_worst_first(rows, req.budget)
    chosen = sorted((rows[i] for i in opt), key=lambda r: -r["risk"])
    for k, r in enumerate(chosen, 1):
        r["priority"] = k
    return {
        "budget": req.budget,
        "segments_repaired": len(opt),
        "cost_used": sum(rows[i]["cost"] for i in opt),
        "risk_removed_pct": round(sum(rows[i]["risk"] for i in opt) / total * 100.0, 1),
        "worst_first_segments": len(grd),
        "worst_first_pct": round(sum(rows[i]["risk"] for i in grd) / total * 100.0, 1),
        "plan": chosen
    }

@app.delete("/api/segments/{seg_id}")
def delete_segment(seg_id: str, request: Request):
    """Deletes road segment. Protected: Admin role required."""
    check_admin_auth(request)
    before = len(SEGMENTS)
    SEGMENTS[:] = [s for s in SEGMENTS if s["id"] != seg_id]
    if len(SEGMENTS) == before:
        raise HTTPException(404, f"No segment called {seg_id}")
    return {"deleted": seg_id, "count": len(SEGMENTS)}

@app.post("/api/reset")
def reset(request: Request):
    """Resets segments from detections.csv. Protected: Admin role required."""
    check_admin_auth(request)
    load_csv()
    return {"source": SOURCE, "count": len(SEGMENTS)}

@app.get("/api/reports")
def list_reports(request: Request, limit: int = 500):
    """Admin verification queue: returns complete report records with photos and GPS audits."""
    check_admin_auth(request)
    with db() as con:
        rows = con.execute("SELECT * FROM reports ORDER BY id DESC LIMIT ?", (max(1, min(limit, 5000)),)).fetchall()
        total = con.execute("SELECT COUNT(*) FROM reports").fetchone()[0]
    return {"count": total, "reports": [row_to_dict(r) for r in rows]}

@app.get("/api/reports/{rid}")
def get_report_detail(rid: int, request: Request):
    """Admin detail view for a specific report."""
    check_admin_auth(request)
    with db() as con:
        row = con.execute("SELECT * FROM reports WHERE id=?", (rid,)).fetchone()
    if not row:
        raise HTTPException(404, f"Report #{rid} not found.")
    return row_to_dict(row)

class AdminStatusUpdate(BaseModel):
    status: str
    admin_notes: str = ""

@app.post("/api/reports/{rid}/status")
@app.patch("/api/reports/{rid}/status")
def set_status(rid: int, req: AdminStatusUpdate, request: Request):
    """Admin endpoint to verify, schedule, or resolve defect reports."""
    check_admin_auth(request)
    valid_statuses = ("received", "verified", "scheduled", "fixed", "rejected", "reported", "repaired")
    if req.status not in valid_statuses:
        raise HTTPException(400, f"status must be one of {valid_statuses}")

    st_val = "received" if req.status == "reported" else ("fixed" if req.status == "repaired" else req.status)
    verified_time = datetime.now(timezone.utc).isoformat(timespec="seconds") if st_val in ("verified", "scheduled", "fixed") else None

    with _db_lock, db() as con:
        n = con.execute(
            "UPDATE reports SET status=?, verified_at=COALESCE(?, verified_at), admin_notes=? WHERE id=?",
            (st_val, verified_time, req.admin_notes, rid)
        ).rowcount
    if not n:
        raise HTTPException(404, f"No report #{rid}")
    return {"id": rid, "status": st_val, "updated": True}

@app.get("/api/admin/metrics")
def get_admin_metrics(request: Request):
    """Municipal analytics dashboard metrics."""
    check_admin_auth(request)
    with db() as con:
        total = con.execute("SELECT COUNT(*) FROM reports").fetchone()[0]
        by_status = dict(con.execute("SELECT status, COUNT(*) FROM reports GROUP BY status").fetchall())
        by_type = dict(con.execute("SELECT damage_type, COUNT(*) FROM reports GROUP BY damage_type").fetchall())
        mismatches = con.execute("SELECT COUNT(*) FROM reports WHERE location_mismatch = 1").fetchone()[0]
    return {
        "total_reports": total,
        "by_status": by_status,
        "by_type": by_type,
        "location_mismatches_flagged": mismatches
    }

@app.get("/api/reports.csv")
def reports_csv(request: Request):
    """Admin CSV export. Protected: Admin role required."""
    check_admin_auth(request)
    with db() as con:
        rows = con.execute("SELECT * FROM reports ORDER BY id").fetchall()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(REPORT_COLS)
    for r in rows:
        w.writerow([r[k] for k in REPORT_COLS])
    return Response(
        buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=winterroad_reports.csv"}
    )

@app.on_event("startup")
def warm_up_model():
    def load():
        try:
            get_model()
        except Exception as e:
            print("Crack model deferred load:", e)
        try:
            get_pothole_model()
        except Exception as e:
            print("Pothole model deferred load:", e)
    threading.Thread(target=load, daemon=True).start()

STATIC_DIR = os.path.join(BASE, "static")

def is_admin_authenticated(request: Request) -> bool:
    """Checks whether the incoming request possesses a valid active admin session."""
    token = None
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
    elif request.headers.get("X-Admin-Token"):
        token = request.headers.get("X-Admin-Token").strip()
    elif request.cookies.get("winterroad_token"):
        token = request.cookies.get("winterroad_token").strip()

    if not token:
        return False
    with _sessions_lock:
        session = _active_sessions.get(token)
        if not session or (time.time() - session["created_at"] > 86400):
            return False
        return session.get("role") == "admin"

ADMIN_NO_CACHE_HEADERS = {
    "Cache-Control": "no-cache, no-store, must-revalidate",
    "Pragma": "no-cache",
    "Expires": "0"
}

# ---------------- Public Citizen Multi-Page Routes ----------------
@app.get("/", response_class=FileResponse)
def page_landing():
    """Public landing page: project introduction and portal pathways."""
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))

@app.get("/report", response_class=FileResponse)
def page_report():
    """Citizen defect reporting page with photo upload and location capture."""
    return FileResponse(os.path.join(STATIC_DIR, "report.html"))

@app.get("/track", response_class=FileResponse)
def page_track():
    """Citizen ticket tracking page with sanitized milestone progression."""
    return FileResponse(os.path.join(STATIC_DIR, "track.html"))

@app.get("/map", response_class=FileResponse)
def page_map():
    """Public map of verified defects and municipal counters."""
    return FileResponse(os.path.join(STATIC_DIR, "map.html"))

# ---------------- Protected Municipal Admin Multi-Page Routes ----------------
@app.get("/admin/login")
def page_admin_login(request: Request):
    """Admin login page. If already authenticated, redirect directly to /admin."""
    if is_admin_authenticated(request):
        return RedirectResponse(url="/admin", status_code=303)
    return FileResponse(os.path.join(STATIC_DIR, "admin", "login.html"), headers=ADMIN_NO_CACHE_HEADERS)

@app.get("/admin")
@app.get("/admin/")
def page_admin_overview(request: Request):
    """Admin overview and live road damage map. Server-side redirect if unauthenticated."""
    if not is_admin_authenticated(request):
        return RedirectResponse(url="/admin/login", status_code=303)
    return FileResponse(os.path.join(STATIC_DIR, "admin", "index.html"), headers=ADMIN_NO_CACHE_HEADERS)

@app.get("/admin/reports")
def page_admin_reports(request: Request):
    """Admin defect verification queue. Server-side redirect if unauthenticated."""
    if not is_admin_authenticated(request):
        return RedirectResponse(url="/admin/login", status_code=303)
    return FileResponse(os.path.join(STATIC_DIR, "admin", "reports.html"), headers=ADMIN_NO_CACHE_HEADERS)

@app.get("/admin/planner")
def page_admin_planner(request: Request):
    """Admin budget knapsack optimizer and work order generator. Server-side redirect if unauthenticated."""
    if not is_admin_authenticated(request):
        return RedirectResponse(url="/admin/login", status_code=303)
    return FileResponse(os.path.join(STATIC_DIR, "admin", "planner.html"), headers=ADMIN_NO_CACHE_HEADERS)

@app.get("/admin/research")
def page_admin_research(request: Request):
    """Admin paper benchmarks and ablation experiments. Server-side redirect if unauthenticated."""
    if not is_admin_authenticated(request):
        return RedirectResponse(url="/admin/login", status_code=303)
    return FileResponse(os.path.join(STATIC_DIR, "admin", "research.html"), headers=ADMIN_NO_CACHE_HEADERS)

@app.get("/admin/equity")
def page_admin_equity(request: Request):
    """Admin ward allocations and multi-month rolling plan. Server-side redirect if unauthenticated."""
    if not is_admin_authenticated(request):
        return RedirectResponse(url="/admin/login", status_code=303)
    return FileResponse(os.path.join(STATIC_DIR, "admin", "equity.html"), headers=ADMIN_NO_CACHE_HEADERS)

@app.get("/admin/about")
def page_admin_about(request: Request):
    """Admin research provenance, assumptions, and licenses. Server-side redirect if unauthenticated."""
    if not is_admin_authenticated(request):
        return RedirectResponse(url="/admin/login", status_code=303)
    return FileResponse(os.path.join(STATIC_DIR, "admin", "about.html"), headers=ADMIN_NO_CACHE_HEADERS)

# ---------------- Static Asset Mounts ----------------
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/uploads", StaticFiles(directory=UPLOADS), name="uploads")
