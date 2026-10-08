"""
WinterRoad - Privacy Blurring Recall Evaluation Benchmark
Measures empirical face-blur recall and license plate-blur recall on real photos.
Identifies and reports misses (False Negatives) and True Positives.

Usage:
  python scripts/evaluate_privacy_recall.py --face-dir data/own/privacy/faces --plate-dir data/own/privacy/plates

Outputs:
  - results/privacy_recall_benchmark.json

Team: WinterBorn
Authors: B K Kesavkrishnan, S Arun Kumar
"""
import argparse
import json
import os
import sys
from PIL import Image

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

import privacy

def evaluate_directory(dir_path, defect_type="face"):
    """
    Evaluates photos in dir_path.
    Expects photos containing at least one real face or plate.
    If a metadata manifest.json exists in dir_path, uses exact expected counts.
    Otherwise assumes 1 expected instance per image unless filename indicates otherwise.
    """
    if not os.path.exists(dir_path):
        return None

    valid_exts = {".jpg", ".jpeg", ".png", ".webp"}
    img_files = [f for f in sorted(os.listdir(dir_path)) if os.path.splitext(f.lower())[1] in valid_exts]
    if not img_files:
        return None

    manifest_path = os.path.join(dir_path, "manifest.json")
    manifest = {}
    if os.path.exists(manifest_path):
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

    total_expected = 0
    total_detected = 0
    true_positives = 0
    false_negatives = 0
    missed_images = []
    details = []

    for fname in img_files:
        fpath = os.path.join(dir_path, fname)
        expected = manifest.get(fname, 1) # Default: 1 instance expected
        total_expected += expected

        try:
            im = Image.open(fpath)
            _, stats = privacy.detect_and_blur_privacy(im)
            detected = stats["faces_blurred"] if defect_type == "face" else stats["plates_blurred"]
            total_detected += detected

            tp = min(expected, detected)
            fn = max(0, expected - detected)
            true_positives += tp
            false_negatives += fn

            if fn > 0:
                missed_images.append({
                    "filename": fname,
                    "expected": expected,
                    "detected": detected,
                    "missed_count": fn
                })

            details.append({
                "filename": fname,
                "expected": expected,
                "detected": detected,
                "status": "pass" if fn == 0 else "missed"
            })
        except Exception as e:
            missed_images.append({
                "filename": fname,
                "expected": expected,
                "detected": 0,
                "error": str(e)
            })
            false_negatives += expected

    recall = round((true_positives / max(1, total_expected)) * 100.0, 2)
    return {
        "images_evaluated": len(img_files),
        "total_ground_truth_instances": total_expected,
        "total_detected_instances": total_detected,
        "true_positives": true_positives,
        "false_negatives_misses": false_negatives,
        "recall_pct": recall,
        "missed_images": missed_images,
        "details": details
    }

def main():
    parser = argparse.ArgumentParser(description="WinterRoad Privacy Blurring Recall Benchmark")
    parser.add_argument("--face-dir", default=os.path.join(_ROOT, "data", "own", "privacy", "faces"))
    parser.add_argument("--plate-dir", default=os.path.join(_ROOT, "data", "own", "privacy", "plates"))
    parser.add_argument("--outdir", default=os.path.join(_ROOT, "results"))
    args = parser.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    out_json = os.path.join(args.outdir, "privacy_recall_benchmark.json")

    print("Evaluating Privacy Blurring Recall...")
    face_results = evaluate_directory(args.face_dir, "face")
    plate_results = evaluate_directory(args.plate_dir, "plate")

    # Check if user photos were provided
    if face_results is None and plate_results is None:
        print("  Status: Awaiting User Photos")
        print(f"  Target directories empty or missing:")
        print(f"    - Faces:  {args.face_dir}")
        print(f"    - Plates: {args.plate_dir}")
        print("  Per project protocol, evaluation paused pending user data.")

        # Run smoke test on library baseline samples to verify algorithm executes
        library_samples = [
            (".venv/lib/python3.13/site-packages/matplotlib/mpl-data/sample_data/grace_hopper.jpg", 1, 0),
            (".venv/lib/python3.13/site-packages/ultralytics/assets/zidane.jpg", 3, 0),
            (".venv/lib/python3.13/site-packages/ultralytics/assets/bus.jpg", 2, 0)
        ]
        smoke_details = []
        smoke_tp = 0
        smoke_expected = 0
        for rel_path, exp_faces, exp_plates in library_samples:
            full_p = os.path.join(_ROOT, rel_path)
            if os.path.exists(full_p):
                im = Image.open(full_p)
                _, st = privacy.detect_and_blur_privacy(im)
                det_f = st["faces_blurred"]
                det_p = st["plates_blurred"]
                smoke_expected += exp_faces
                smoke_tp += min(exp_faces, det_f)
                smoke_details.append({
                    "sample": os.path.basename(rel_path),
                    "expected_faces": exp_faces,
                    "detected_faces": det_f,
                    "detected_plates": det_p
                })

        summary = {
            "status": "awaiting_user_data",
            "protocol_note": "Awaiting user-provided real photos in data/own/privacy/faces/ and data/own/privacy/plates/.",
            "documented_in": "docs/NEEDS_FROM_ME.md",
            "engine": "OpenCV YuNet ONNX (face) + Sobel gradient morphology (plate)",
            "library_smoke_test": {
                "images_tested": len(smoke_details),
                "expected_faces": smoke_expected,
                "detected_faces": smoke_tp,
                "smoke_recall_pct": round(smoke_tp / max(1, smoke_expected) * 100.0, 1),
                "samples": smoke_details
            }
        }
    else:
        summary = {
            "status": "completed",
            "data_source": "real_user_photos",
            "faces": face_results or {"status": "no_face_images_provided"},
            "plates": plate_results or {"status": "no_plate_images_provided"}
        }

    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"Saved benchmark results to {out_json}")
    if summary.get("status") == "completed":
        if face_results:
            print(f"  Face Blur Recall:  {face_results['recall_pct']}% (Misses: {face_results['false_negatives_misses']})")
        if plate_results:
            print(f"  Plate Blur Recall: {plate_results['recall_pct']}% (Misses: {plate_results['false_negatives_misses']})")

if __name__ == "__main__":
    main()
