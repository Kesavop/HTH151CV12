# WinterRoad - Road Defect Dataset Labeling Guide

**Team:** WinterBorn  
**Authors:** B K Kesavkrishnan, S Arun Kumar  
**Target:** Local Road Defect Transfer & Few-Shot Adaptation Benchmark (`data/own/`)

---

## 1. Directory Structure

Place all collected road images and their corresponding label files in `data/own/` following the standard YOLO format:

```
data/own/
├── images/
│   ├── train/          # Adaptation / fine-tuning images (N = 25, 50, 100, 200)
│   └── test/           # Held-out benchmark images (NEVER seen during training)
├── labels/
│   ├── train/          # YOLO .txt annotation files for train
│   └── test/           # YOLO .txt annotation files for test
└── data.yaml           # Dataset configuration file
```

---

## 2. Label Format (YOLO Darknet Normalized)

For every image (e.g., `IMG_0042.jpg`), there must be a text file with the identical base name (e.g., `IMG_0042.txt`) in the corresponding labels directory.

Each line in the `.txt` file represents one defect bounding box:
```
<class_id> <x_center> <y_center> <width> <height>
```
All coordinates are normalized floats in the range `[0.0, 1.0]` relative to image width and height.

### Class Index Mapping

| Class ID | Code | Defect Name | Visual Characteristics | Danger Weight |
|---|---|---|---|---|
| **0** | `D00` | Longitudinal Crack | Single crack running parallel to road direction | 0.40 |
| **1** | `D10` | Transverse Crack | Single crack running across road width | 0.50 |
| **2** | `D20` | Alligator Cracking | Interconnected web/mesh of fatigue cracks | 0.80 |
| **3** | `D40` | Pothole | Bowl-shaped cavity/depression with shadow/depth | 1.00 |

---

## 3. Strict Zero-Leakage Split Protocol

To preserve scientific validity and paper reproducibility:

1. **Spatial & Temporal Disjointness:**  
   Never split consecutive frames from the same video or camera burst between `train/` and `test/`. If 10 photos are captured along MG Road, assign all 10 to `train/` or all 10 to `test/`. Splitting consecutive frames creates visual background leakage that inflates test metrics.
2. **SHA-256 Checksum Verification:**  
   `scripts/evaluate_detector.py` automatically checks the SHA-256 hash of all images. If any image in `test/` matches an image in `train/`, evaluation halts immediately.
3. **Split Ratio:**  
   Recommend a 70% train / 30% test split, ensuring at least 30 diverse test images across both sunny, overcast, dry, and wet pavement conditions.

---

## 4. Annotation Best Practices

- **Tight Bounding Boxes:** Draw boxes snugly around the outer boundary of the defect. Avoid padding boxes with clean asphalt.
- **Pothole Depth:** For potholes with shadowed interiors, include the entire depression basin up to the pavement lip.
- **Alligator Cracking Clusters:** If an area contains many interconnected cracks spanning a continuous region, enclose the entire fatigue patch in a single `D20` box rather than dozens of micro-boxes.
- **Privacy Notice:** Do not intentionally capture pedestrian faces or vehicle license plates. Any inadvertent faces or plates will be blurred automatically by WinterRoad's YuNet privacy filter.

---

## 5. Recommended Free Annotation Tools

- **CVAT (Computer Vision Annotation Tool):** Web-based, open-source (`https://cvat.ai`). Export as `YOLO 1.1`.
- **LabelImg:** Lightweight desktop python tool (`pip install labelImg`). Set save format to `YOLO`.
- **Roboflow:** Free tier allows uploading, labeling, and downloading in YOLOv8 format with a single click.
