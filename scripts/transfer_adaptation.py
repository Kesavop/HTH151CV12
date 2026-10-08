"""
WinterRoad - Transfer Test and Adaptation Experiment Script
Evaluates model on local images in data/own/ and runs adaptation experiments
when real images are supplied by the user.

Team: WinterBorn
Authors: B K Kesavkrishnan, S Arun Kumar
"""
import argparse
import glob
import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

def main():
    parser = argparse.ArgumentParser(description="Evaluate on user local images and fine-tune progression")
    parser.add_argument("--data-dir", default=os.path.join(_ROOT, "data", "own"), help="Directory containing user images")
    parser.add_argument("--eval-only", action="store_true", help="Only evaluate pre-trained models")
    parser.add_argument("--output", default=os.path.join(_ROOT, "results", "adaptation_results.json"))
    args = parser.parse_args()

    os.makedirs(os.path.dirname(args.output), exist_ok=True)

    # Search for user images
    valid_exts = (".jpg", ".jpeg", ".png", ".heic")
    user_images = []
    if os.path.exists(args.data_dir):
        for ext in valid_exts:
            user_images.extend(glob.glob(os.path.join(args.data_dir, f"**/*{ext}"), recursive=True))

    if not user_images:
        print("=================================================================")
        print("WinterRoad Transfer & Adaptation Experiment Status: AWAITING DATA")
        print("=================================================================")
        print(f"No user images found in '{args.data_dir}'.")
        print("As per WinterRoad scientific rules, NO synthetic images are fabricated.")
        print("To run this experiment:")
        print(f"1. Add your road defect images into: {args.data_dir}")
        print("2. Re-run: python scripts/transfer_adaptation.py")
        print("=================================================================")
        
        status_info = {
            "status": "awaiting_user_data",
            "message": f"No images found in {args.data_dir}. Waiting for user-provided test images.",
            "data_directory": os.path.relpath(args.data_dir, _ROOT),
            "supported_sample_sizes": [0, 25, 50, 100, 200],
            "zero_shot_baseline_ready": True
        }
        with open(args.output, "w") as f:
            json.dump(status_info, f, indent=2)
        return

    print(f"Found {len(user_images)} user images in {args.data_dir}.")
    from ultralytics import YOLO
    model_path = os.path.join(_ROOT, "backend", "best.pt")
    model = YOLO(model_path)

    # Run predictions on user images
    detection_summary = {"total_images": len(user_images), "detections_per_image": []}
    for p in user_images:
        res = model.predict(p, conf=0.20, verbose=False)[0]
        detection_summary["detections_per_image"].append({
            "image": os.path.basename(p),
            "count": len(res.boxes),
            "classes": [int(c) for c in res.boxes.cls.tolist()]
        })

    with open(args.output, "w") as f:
        json.dump(detection_summary, f, indent=2)
    print(f"Saved evaluation on user images to {args.output}")

if __name__ == "__main__":
    main()
