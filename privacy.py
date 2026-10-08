"""
WinterRoad - Privacy Protection Module
Detects and blurs human faces and vehicle license plates before storing or displaying images.
Complies with citizen privacy standards for research prototypes.

Uses OpenCV YuNet deep neural network for robust face detection (MIT license).
Uses morphological gradient and rectangular aspect-ratio filters for license plate candidate blurring.

Team: WinterBorn
Authors: B K Kesavkrishnan, S Arun Kumar
"""
import os
import cv2
import numpy as np
from PIL import Image

# Path to YuNet ONNX model (OpenCV Model Zoo, MIT License)
DEFAULT_YUNET_PATH = os.path.join(os.path.dirname(__file__), "data", "models", "face_detection_yunet_2023mar.onnx")

_yunet_detector = None

def get_face_detector(model_path=None):
    """Initializes or returns cached cv2.FaceDetectorYN instance."""
    global _yunet_detector
    if _yunet_detector is not None:
        return _yunet_detector
    
    path = model_path or DEFAULT_YUNET_PATH
    if os.path.exists(path):
        try:
            _yunet_detector = cv2.FaceDetectorYN.create(
                model=path,
                config="",
                input_size=(640, 640),
                score_threshold=0.55,
                nms_threshold=0.3,
                top_k=5000
            )
            return _yunet_detector
        except Exception:
            return None
    return None

def blur_roi(img_bgr, x1, y1, x2, y2, kernel_size=51):
    """Applies strong Gaussian blur to a rectangular region of interest."""
    h, w = img_bgr.shape[:2]
    x1, y1 = max(0, int(x1)), max(0, int(y1))
    x2, y2 = min(w, int(x2)), min(h, int(y2))
    if x2 <= x1 or y2 <= y1:
        return img_bgr
    roi = img_bgr[y1:y2, x1:x2]
    if roi.size == 0:
        return img_bgr
    # Ensure kernel size is odd and fits roi
    max_k = min(roi.shape[0], roi.shape[1])
    if max_k % 2 == 0:
        max_k -= 1
    k = max(3, min(kernel_size, max_k))
    if k >= 3 and k % 2 == 1:
        blurred = cv2.GaussianBlur(roi, (k, k), 30)
        img_bgr[y1:y2, x1:x2] = blurred
    return img_bgr

def detect_and_blur_privacy(image: Image.Image, model_path: str = None):
    """
    Scans image for potential human faces and vehicle license plates,
    applying Gaussian blurring. Returns (blurred_image, stats).

    Face detection: cv2.FaceDetectorYN (YuNet ONNX).
    Plate detection: Sobel horizontal gradient + morphological closing + aspect ratio 2.0-5.8.
    """
    img_np = np.array(image.convert("RGB"))
    img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
    h, w = img_bgr.shape[:2]

    blurred_faces = 0
    blurred_plates = 0

    # 1. Human Face Detection via YuNet Deep Model
    detector = get_face_detector(model_path)
    if detector is not None:
        try:
            detector.setInputSize((w, h))
            _, faces = detector.detect(img_bgr)
            if faces is not None:
                for face in faces:
                    fx, fy, fw, fh = int(face[0]), int(face[1]), int(face[2]), int(face[3])
                    # Expand by 15% to cover chin, forehead, ears
                    pad_w = int(fw * 0.15)
                    pad_h = int(fh * 0.20)
                    fx1 = max(0, fx - pad_w)
                    fy1 = max(0, fy - pad_h)
                    fx2 = min(w, fx + fw + pad_w)
                    fy2 = min(h, fy + fh + pad_h)
                    img_bgr = blur_roi(img_bgr, fx1, fy1, fx2, fy2, kernel_size=51)
                    blurred_faces += 1
        except Exception:
            pass

    # 2. License Plate Candidate Detection (aspect ratio 2.0 - 5.8, horizontal character gradients)
    try:
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        sobelx = cv2.Sobel(gray, cv2.CV_16S, 1, 0, ksize=3)
        abs_sobel = cv2.convertScaleAbs(sobelx)
        blurred_gray = cv2.GaussianBlur(abs_sobel, (7, 7), 0)
        _, thresh = cv2.threshold(blurred_gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (17, 3))
        closed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for cnt in contours:
            area = cv2.contourArea(cnt)
            # Plates typically occupy between 0.05% and 4% of street photos
            if 0.0005 * (w * h) <= area <= 0.04 * (w * h):
                x, y, bw, bh = cv2.boundingRect(cnt)
                aspect = float(bw) / max(1.0, float(bh))
                if 2.0 <= aspect <= 5.8:
                    # Pad plate region slightly by 10%
                    pad_x = int(bw * 0.10)
                    pad_y = int(bh * 0.10)
                    px1 = max(0, x - pad_x)
                    py1 = max(0, y - pad_y)
                    px2 = min(w, x + bw + pad_x)
                    py2 = min(h, y + bh + pad_y)
                    img_bgr = blur_roi(img_bgr, px1, py1, px2, py2, kernel_size=45)
                    blurred_plates += 1
    except Exception:
        pass

    blurred_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_RGB2BGR) # wait, RGB2BGR? No! cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    blurred_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    out_img = Image.fromarray(blurred_rgb)
    stats = {
        "faces_blurred": blurred_faces,
        "plates_blurred": blurred_plates,
        "privacy_protected": (blurred_faces + blurred_plates) > 0,
        "face_detector_engine": "OpenCV_YuNet_ONNX" if detector is not None else "unavailable",
        "data_source": "real"
    }
    return out_img, stats
