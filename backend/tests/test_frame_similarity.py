import importlib.util
import io
import pathlib
import sys
import unittest

import numpy as np
from PIL import Image, ImageDraw


MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "app" / "utils" / "frame_similarity.py"
spec = importlib.util.spec_from_file_location("frame_similarity", MODULE_PATH)
frame_similarity = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = frame_similarity
spec.loader.exec_module(frame_similarity)
MAX_DHASH_DISTANCE = frame_similarity.MAX_DHASH_DISTANCE
MAX_NORMALIZED_GRAYSCALE_MEAN_DELTA = frame_similarity.MAX_NORMALIZED_GRAYSCALE_MEAN_DELTA
compare_frames = frame_similarity.compare_frames
frames_are_similar = frame_similarity.frames_are_similar


class TestFrameSimilarity(unittest.TestCase):
    def test_minor_jpeg_encoding_variation_is_same_visual_state(self):
        pixels = np.tile(np.arange(256, dtype=np.uint8), (128, 1))
        original = Image.fromarray(pixels, mode="L")
        encoded = io.BytesIO()
        original.save(encoded, format="JPEG", quality=95)
        encoded.seek(0)
        reencoded = Image.open(encoded).copy()

        metrics = compare_frames(original, reencoded)

        self.assertLessEqual(metrics.dhash_distance, MAX_DHASH_DISTANCE)
        self.assertLessEqual(
            metrics.normalized_grayscale_mean_delta,
            MAX_NORMALIZED_GRAYSCALE_MEAN_DELTA,
        )
        self.assertTrue(frames_are_similar(original, reencoded))

    def test_added_formula_and_page_scale_change_are_not_similar(self):
        blank = Image.new("L", (320, 180), 255)
        formula = blank.copy()
        ImageDraw.Draw(formula).rectangle((80, 50, 240, 120), fill=0)
        next_page = Image.new("L", (320, 180), 0)

        self.assertFalse(frames_are_similar(blank, formula))
        self.assertFalse(frames_are_similar(blank, next_page))


if __name__ == "__main__":
    unittest.main()
