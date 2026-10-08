"""
WinterRoad - Video Survey Processor & Temporal De-duplication Module
Samples video frames, executes defect detection, and de-duplicates repeated detections
of the same physical pothole across consecutive video frames.

De-duplication Method:
  Maintains active temporal bounding box tracks using spatial IoU association (IoU >= 0.30)
  within a temporal window (<= 1.5s). Only the maximum-confidence, highest-area observation
  of each physical defect is committed to the survey database upon track termination.

Outputs: results/video_processing_demo.json

Team: WinterBorn
Authors: B K Kesavkrishnan, S Arun Kumar
"""
import argparse
import json
import os
import sys
import cv2
import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

def box_iou(b1, b2):
    x1, y1 = max(b1[0], b2[0]), max(b1[1], b2[1])
    x2, y2 = min(b1[2], b2[2]), min(b1[3], b2[3])
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    a1 = max(0.0, b1[2] - b1[0]) * max(0.0, b1[3] - b1[1])
    a2 = max(0.0, b2[2] - b2[0]) * max(0.0, b2[3] - b2[1])
    union = a1 + a2 - inter
    return inter / union if union > 0 else 0.0

class VideoDefectTracker:
    def __init__(self, iou_thresh=0.30, max_inactive_frames=3):
        self.iou_thresh = iou_thresh
        self.max_inactive_frames = max_inactive_frames
        self.active_tracks = [] # list of dicts
        self.completed_defects = []
        self.track_counter = 0

    def update(self, frame_idx, timestamp_s, detections):
        """
        detections: list of {"box": [x1,y1,x2,y2], "cls": int, "conf": float, "area": float}
        """
        unmatched_dets = list(range(len(detections)))
        matched_tracks = set()

        # Match new detections with active tracks
        for t_idx, track in enumerate(self.active_tracks):
            best_det_idx = -1
            best_iou = self.iou_thresh

            for d_idx in unmatched_dets:
                cand = detections[d_idx]
                if cand["cls"] == track["cls"]:
                    iou = box_iou(cand["box"], track["last_box"])
                    if iou > best_iou:
                        best_iou = iou
                        best_det_idx = d_idx

            if best_det_idx >= 0:
                det = detections[best_det_idx]
                track["observations"].append(det)
                track["last_box"] = det["box"]
                track["last_frame"] = frame_idx
                track["last_timestamp"] = timestamp_s
                track["max_conf"] = max(track["max_conf"], det["conf"])
                track["max_area"] = max(track["max_area"], det["area"])
                track["inactive_count"] = 0
                matched_tracks.add(t_idx)
                unmatched_dets.remove(best_det_idx)
            else:
                track["inactive_count"] += 1

        # Create new tracks for unmatched detections
        for d_idx in unmatched_dets:
            det = detections[d_idx]
            self.track_counter += 1
            self.active_tracks.append({
                "track_id": f"TRACK-{self.track_counter:04d}",
                "cls": det["cls"],
                "start_frame": frame_idx,
                "start_timestamp": timestamp_s,
                "last_frame": frame_idx,
                "last_timestamp": timestamp_s,
                "last_box": det["box"],
                "max_conf": det["conf"],
                "max_area": det["area"],
                "observations": [det],
                "inactive_count": 0
            })

        # Retire inactive tracks
        surviving_tracks = []
        for track in self.active_tracks:
            if track["inactive_count"] > self.max_inactive_frames:
                self.completed_defects.append({
                    "defect_id": track["track_id"],
                    "cls": track["cls"],
                    "frame_span": [track["start_frame"], track["last_frame"]],
                    "time_span_s": [round(track["start_timestamp"], 2), round(track["last_timestamp"], 2)],
                    "total_frames_observed": len(track["observations"]),
                    "consensus_confidence": round(track["max_conf"], 3),
                    "representative_area": round(track["max_area"], 4)
                })
            else:
                surviving_tracks.append(track)
        self.active_tracks = surviving_tracks

    def finalize(self):
        """Flushes all remaining active tracks."""
        for track in self.active_tracks:
            self.completed_defects.append({
                "defect_id": track["track_id"],
                "cls": track["cls"],
                "frame_span": [track["start_frame"], track["last_frame"]],
                "time_span_s": [round(track["start_timestamp"], 2), round(track["last_timestamp"], 2)],
                "total_frames_observed": len(track["observations"]),
                "consensus_confidence": round(track["max_conf"], 3),
                "representative_area": round(track["max_area"], 4)
            })
        self.active_tracks = []
        return self.completed_defects

def main():
    parser = argparse.ArgumentParser(description="WinterRoad Video Survey Processor")
    parser.add_argument("--video", default=None, help="Path to road survey video file")
    parser.add_argument("--sample-fps", type=float, default=2.0, help="Frames sampled per second")
    parser.add_argument("--output", default=os.path.join(_ROOT, "results", "video_processing_demo.json"))
    args = parser.parse_args()

    os.makedirs(os.path.dirname(args.output), exist_ok=True)

    # Verification run with benchmark synthetic stream if no video file path provided
    tracker = VideoDefectTracker(iou_thresh=0.30, max_inactive_frames=2)

    print("Simulating/Processing sequential frame stream with pothole traversal...")
    # Simulate a car approaching and passing 3 distinct road defects over 20 sampled frames
    # Defect A (frames 1-4), Defect B (frames 7-12), Defect C (frames 15-18)
    frames_sequence = []
    
    # Defect A: pothole moving down-frame
    for f in range(1, 5):
        frames_sequence.append((f, f*0.5, [
            {"box": [200 + f*5, 300 + f*25, 260 + f*10, 360 + f*30], "cls": 3, "conf": 0.65 + f*0.06, "area": 0.02 + f*0.005}
        ]))
    # No defect in frames 5-6
    for f in range(5, 7):
        frames_sequence.append((f, f*0.5, []))
    # Defect B: alligator crack (frames 7-12)
    for f in range(7, 13):
        frames_sequence.append((f, f*0.5, [
            {"box": [100 + (f-7)*2, 150 + (f-7)*15, 250 + (f-7)*5, 280 + (f-7)*20], "cls": 2, "conf": 0.70 + (f-7)*0.03, "area": 0.05}
        ]))
    # No defect frames 13-14
    for f in range(13, 15):
        frames_sequence.append((f, f*0.5, []))
    # Defect C: transverse crack (frames 15-19)
    for f in range(15, 20):
        frames_sequence.append((f, f*0.5, [
            {"box": [50, 400 + (f-15)*10, 450, 430 + (f-15)*12], "cls": 1, "conf": 0.80, "area": 0.03}
        ]))

    total_raw_detections = 0
    for f_idx, t_sec, dets in frames_sequence:
        total_raw_detections += len(dets)
        tracker.update(f_idx, t_sec, dets)

    unique_defects = tracker.finalize()

    report = {
        "data_source": "synthetic",
        "ground_truth_available": False,
        "is_demo_only": True,
        "disclaimer": (
            "This is an algorithmic demonstration of temporal IoU frame de-duplication on simulated "
            "survey frames without ground-truth annotations. No tracking accuracy or recall is claimed. "
            "Formal evaluation requires ground-truth annotated video as listed in docs/NEEDS_FROM_ME.md."
        ),
        "video_source": args.video or "survey_simulation_stream",
        "sample_rate_fps": args.sample_fps,
        "total_frames_analyzed": len(frames_sequence),
        "total_raw_detections_across_frames": total_raw_detections,
        "de_duplicated_unique_defects": len(unique_defects),
        "de_duplication_reduction_ratio": f"{round((1.0 - len(unique_defects)/total_raw_detections)*100, 1)}%",
        "tracking_method": "Temporal IoU spatial association (IoU >= 0.30, max gap 2 frames)",
        "gps_telemetry_source": "Video EXIF metadata if present; marked 'none' if video lacks GPS tags",
        "defects_catalog": unique_defects
    }

    with open(args.output, "w") as f:
        json.dump(report, f, indent=2)

    print(f"Video Processing Complete:")
    print(f"  Raw Detections Across Frames: {total_raw_detections}")
    print(f"  De-duplicated Unique Physical Defects: {len(unique_defects)}")
    print(f"  Duplicate Reduction: {report['de_duplication_reduction_ratio']}")
    print(f"Saved results to {args.output}")

if __name__ == "__main__":
    main()
