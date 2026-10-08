# Local User Images Directory (`data/own/`)

**Status**: Awaiting User Data  
**Purpose**: Transfer test and adaptation experiment for WinterRoad.

## Instructions
1. Place your own local road defect photos directly into this directory (or subfolders `data/own/images/` and `data/own/labels/` if annotated in YOLO format).
2. Accepted formats: `.jpg`, `.jpeg`, `.png`, `.heic`.
3. To evaluate pre-trained models on these images without fine-tuning:
   ```bash
   python scripts/transfer_adaptation.py --eval-only
   ```
4. To run the full adaptation experiment (fine-tuning with 0, 25, 50, 100, 200 local images) and plot performance vs. amount of local data:
   ```bash
   python scripts/transfer_adaptation.py --data-dir data/own
   ```
   This will output the empirical performance progression curve to `results/adaptation_curve.png` and `results/adaptation_results.json`.

> [!NOTE]
> Per the WinterRoad reproducibility guidelines, no synthetic data is fabricated for this experiment. The script requires real local images provided by the researcher.
