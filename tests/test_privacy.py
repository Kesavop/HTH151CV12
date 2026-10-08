"""
Tests for WinterRoad Privacy Module
Verifies YuNet face detector loading, blank image handling, and blur functionality.
"""
import os
import sys
import unittest
import numpy as np
from PIL import Image

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from privacy import detect_and_blur_privacy, get_face_detector

class TestPrivacyModule(unittest.TestCase):
    def test_detector_loads(self):
        detector = get_face_detector()
        self.assertIsNotNone(detector, "YuNet model should load successfully")

    def test_blank_image(self):
        # A 640x480 black image should not fail and should find 0 faces/plates
        img = Image.new("RGB", (640, 480), color=(0, 0, 0))
        out_img, stats = detect_and_blur_privacy(img)
        self.assertEqual(out_img.size, (640, 480))
        self.assertEqual(stats["faces_blurred"], 0)
        self.assertEqual(stats["plates_blurred"], 0)
        self.assertFalse(stats["privacy_protected"])

    def test_image_dimensions_preserved(self):
        img = Image.new("RGB", (320, 240), color=(128, 128, 128))
        out_img, stats = detect_and_blur_privacy(img)
        self.assertEqual(out_img.size, (320, 240))

if __name__ == "__main__":
    unittest.main()
