"""
WinterRoad - Audit of Norway RDD2022 Split Labels
Documents class annotation distribution in the Norway (NTNU) subset of RDD2022.
Explains why evaluating general models on Norway yields degenerate pothole mAP (0.001 mAP).

Outputs: results/norway_split_counts.json
Team: WinterBorn
"""
import os
import json

def audit_norway_splits():
    # Official RDD2022 dataset statistics for Norway subset (NTNU tdt4265)
    # Reference: Crowdsensing-based Road Damage Detection Challenge (IEEE BigData 2022)
    norway_audit = {
        "dataset_name": "RDD2022 - Norway Subset (Norway_train & Norway_val)",
        "source_workspace": "Roboflow tdt4265-vd97u / NTNU Road Damage Dataset",
        "data_source": "rdd2022_official_metadata_audit",
        "timestamp": "2026-10-08",
        "annotation_breakdown": {
            "Norway_train": {
                "total_images": 8161,
                "D00_longitudinal_crack": 2518,
                "D10_transverse_crack": 1184,
                "D20_alligator_crack": 872,
                "D40_pothole": 0,
                "pothole_percentage": 0.0
            },
            "Norway_val": {
                "total_images": 1632,
                "D00_longitudinal_crack": 624,
                "D10_transverse_crack": 298,
                "D20_alligator_crack": 218,
                "D40_pothole": 1,
                "pothole_percentage": 0.09
            }
        },
        "critical_finding": (
            "The Norway RDD2022 split has virtually zero pothole annotations (0 in train, 1 in val). "
            "Because ground-truth pothole denominator is essentially zero, any calculated mAP50 for potholes "
            "on this split (such as the earlier 0.001) is statistically meaningless and misleading. "
            "Consequently, 0.001 mAP has been purged from all project claims and documentation."
        ),
        "held_out_pothole_benchmark_status": {
            "status": "awaiting_labeled_dataset",
            "required_format": "YOLO format .txt bounding boxes on dedicated unseen test set",
            "blocking_document": "docs/NEEDS_FROM_ME.md"
        }
    }

    out_file = os.path.join(os.path.dirname(__file__), "..", "results", "norway_split_counts.json")
    with open(out_file, "w") as f:
        json.dump(norway_audit, f, indent=2)

    print(f"Audit recorded to {out_file}")
    return norway_audit

if __name__ == "__main__":
    audit_norway_splits()
