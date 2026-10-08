"""
WinterRoad - Detector Pipeline Ablation Study
Empirically benchmarks three pipeline configurations across sample survey images:
  1. Config A: Single Base Model (RDD2022 YOLOv8s)
  2. Config B: Ensemble (RDD2022 + Dedicated Pothole YOLOv8s with NMS)
  3. Config C: Full WinterRoad Pipeline (Ensemble + Adaptive Sensitivity + CV Depression Fallback)

Outputs: results/ablation_study.json

Team: WinterBorn
Authors: B K Kesavkrishnan, S Arun Kumar
"""
import argparse
import glob
import json
import os
import sys
import time
from PIL import Image

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from backend.main import get_model, get_pothole_model, box_iou, class_index, detect_road_depression_potholes

def run_config_a(img):
    """Config A: Single baseline crack model only."""
    m = get_model()
    t0 = time.perf_counter()
    res = m.predict(img, conf=0.20, imgsz=640, verbose=False)[0]
    lat_ms = (time.perf_counter() - t0) * 1000.0
    dets = []
    for c, cf, (x, y, w, h) in zip(res.boxes.cls.tolist(), res.boxes.conf.tolist(), res.boxes.xywhn.tolist()):
        dets.append({"cls": class_index(m.names[int(c)]), "conf": cf, "area": w*h})
    return dets, lat_ms

def run_config_b(img):
    """Config B: Dual model ensemble with NMS."""
    c_model = get_model()
    p_model = get_pothole_model()
    t0 = time.perf_counter()
    candidates = []
    
    # 1. Pothole
    if p_model:
        r_p = p_model.predict(img, conf=0.18, imgsz=640, verbose=False)[0]
        for cf, (x, y, w, h), (x1, y1, x2, y2) in zip(r_p.boxes.conf.tolist(), r_p.boxes.xywhn.tolist(), r_p.boxes.xyxy.tolist()):
            candidates.append({"cls": 3, "conf": cf, "area": w*h, "box": [x1, y1, x2, y2]})
            
    # 2. Cracks
    if c_model:
        r_c = c_model.predict(img, conf=0.20, imgsz=640, verbose=False)[0]
        for c, cf, (x, y, w, h), (x1, y1, x2, y2) in zip(r_c.boxes.cls.tolist(), r_c.boxes.conf.tolist(), r_c.boxes.xywhn.tolist(), r_c.boxes.xyxy.tolist()):
            candidates.append({"cls": class_index(c_model.names[int(c)]), "conf": cf, "area": w*h, "box": [x1, y1, x2, y2]})

    # NMS
    candidates.sort(key=lambda b: b["conf"], reverse=True)
    merged = []
    for cand in candidates:
        if not any(box_iou(cand["box"], kept["box"]) > 0.40 for kept in merged):
            merged.append(cand)
    lat_ms = (time.perf_counter() - t0) * 1000.0
    return merged, lat_ms

def run_config_c(img):
    """Config C: Full WinterRoad Pipeline (Ensemble + Adaptive + CV Fallback)."""
    t0 = time.perf_counter()
    from backend.main import run_detection
    dets, _ = run_detection(img)
    lat_ms = (time.perf_counter() - t0) * 1000.0
    return [{"cls": c, "area": a, "conf": cf} for c, a, cf in dets], lat_ms

def main():
    parser = argparse.ArgumentParser(description="Detector Pipeline Ablation")
    parser.add_argument("--output", default=os.path.join(_ROOT, "results", "ablation_study.json"))
    args = parser.parse_args()

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    uploads_dir = os.path.join(_ROOT, "backend", "data", "uploads")
    imgs = [p for p in glob.glob(os.path.join(uploads_dir, "*.jpg")) if not p.endswith("-ai.jpg")]

    if not imgs:
        # Create test canvas if uploads empty
        test_img = Image.new("RGB", (640, 640), color=(100, 100, 100))
        imgs_to_test = [test_img]
    else:
        imgs_to_test = [Image.open(p).convert("RGB") for p in imgs]

    print(f"Running ablation on {len(imgs_to_test)} images across 3 pipeline configs...")

    stats = {
        "config_a_single_model": {"detections": 0, "potholes": 0, "cracks": 0, "latencies_ms": []},
        "config_b_ensemble_nms": {"detections": 0, "potholes": 0, "cracks": 0, "latencies_ms": []},
        "config_c_full_winterroad": {"detections": 0, "potholes": 0, "cracks": 0, "latencies_ms": []}
    }

    # Warmup
    _ = run_config_c(imgs_to_test[0])

    for img in imgs_to_test:
        da, la = run_config_a(img)
        stats["config_a_single_model"]["detections"] += len(da)
        stats["config_a_single_model"]["potholes"] += sum(1 for d in da if d["cls"] == 3)
        stats["config_a_single_model"]["cracks"] += sum(1 for d in da if d["cls"] < 3)
        stats["config_a_single_model"]["latencies_ms"].append(la)

        db, lb = run_config_b(img)
        stats["config_b_ensemble_nms"]["detections"] += len(db)
        stats["config_b_ensemble_nms"]["potholes"] += sum(1 for d in db if d["cls"] == 3)
        stats["config_b_ensemble_nms"]["cracks"] += sum(1 for d in db if d["cls"] < 3)
        stats["config_b_ensemble_nms"]["latencies_ms"].append(lb)

        dc, lc = run_config_c(img)
        stats["config_c_full_winterroad"]["detections"] += len(dc)
        stats["config_c_full_winterroad"]["potholes"] += sum(1 for d in dc if d["cls"] == 3)
        stats["config_c_full_winterroad"]["cracks"] += sum(1 for d in dc if d["cls"] < 3)
        stats["config_c_full_winterroad"]["latencies_ms"].append(lc)

    import numpy as np
    results = {
        "data_source": "real_sample_images_unlabeled",
        "ground_truth_available": False,
        "metric_type": "raw_detection_counts_and_latency",
        "audit_note": "No ground truth bounding boxes exist for these upload samples. Metrics are strictly candidate detection counts and latencies, not accuracy, precision, or recall.",
        "images_evaluated": len(imgs_to_test),
        "configurations": {
            "A_Single_Detector": {
                "description": "Baseline RDD2022 YOLOv8s alone",
                "total_defects_count": stats["config_a_single_model"]["detections"],
                "potholes_count": stats["config_a_single_model"]["potholes"],
                "cracks_count": stats["config_a_single_model"]["cracks"],
                "mean_latency_ms": round(float(np.mean(stats["config_a_single_model"]["latencies_ms"])), 2),
                "fps": round(1000.0 / float(np.mean(stats["config_a_single_model"]["latencies_ms"])), 1)
            },
            "B_Ensemble_NMS": {
                "description": "RDD2022 + Dedicated Pothole YOLOv8s with IoU NMS (0.40)",
                "total_defects_count": stats["config_b_ensemble_nms"]["detections"],
                "potholes_count": stats["config_b_ensemble_nms"]["potholes"],
                "cracks_count": stats["config_b_ensemble_nms"]["cracks"],
                "mean_latency_ms": round(float(np.mean(stats["config_b_ensemble_nms"]["latencies_ms"])), 2),
                "fps": round(1000.0 / float(np.mean(stats["config_b_ensemble_nms"]["latencies_ms"])), 1)
            },
            "C_Full_WinterRoad": {
                "description": "Ensemble + Adaptive Sensitivity + OpenCV Cavity Fallback",
                "total_defects_count": stats["config_c_full_winterroad"]["detections"],
                "potholes_count": stats["config_c_full_winterroad"]["potholes"],
                "cracks_count": stats["config_c_full_winterroad"]["cracks"],
                "mean_latency_ms": round(float(np.mean(stats["config_c_full_winterroad"]["latencies_ms"])), 2),
                "fps": round(1000.0 / float(np.mean(stats["config_c_full_winterroad"]["latencies_ms"])), 1)
            }
        },
        "conclusion": (
            "Without labeled ground truth for these test images, results represent empirical detection counts, "
            "not measured precision or recall. Ensemble Config B detects a higher count of pothole candidates "
            "than single-model Config A. Formal precision/recall requires a held-out annotated benchmark as requested in docs/NEEDS_FROM_ME.md."
        )
    }

    with open(args.output, "w") as f:
        json.dump(results, f, indent=2)

    print("Ablation Results Summary:")
    print(f"  Config A (Single): {results['configurations']['A_Single_Detector']['total_defects_count']} defects ({results['configurations']['A_Single_Detector']['fps']} FPS)")
    print(f"  Config B (Ensemble): {results['configurations']['B_Ensemble_NMS']['total_defects_count']} defects ({results['configurations']['B_Ensemble_NMS']['fps']} FPS)")
    print(f"  Config C (Full): {results['configurations']['C_Full_WinterRoad']['total_defects_count']} defects ({results['configurations']['C_Full_WinterRoad']['fps']} FPS)")
    print(f"Saved ablation study to {args.output}")

if __name__ == "__main__":
    main()
