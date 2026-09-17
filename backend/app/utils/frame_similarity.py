"""Conservative, dependency-light frame similarity helpers for visual sampling."""
from __future__ import annotations

from dataclasses import dataclass
from os import PathLike
from typing import Union

import numpy as np
from PIL import Image

# The math-course visual sampling rule is intentionally centralized here.
DHASH_WIDTH = 9
DHASH_HEIGHT = 8
GRAYSCALE_COMPARISON_SIZE = (64, 64)
MAX_DHASH_DISTANCE = 2
MAX_NORMALIZED_GRAYSCALE_MEAN_DELTA = 0.006

ImageSource = Union[Image.Image, str, PathLike[str]]


@dataclass(frozen=True)
class FrameSimilarity:
    """Metrics used by the frozen adjacent-frame similarity rule."""

    dhash_distance: int
    normalized_grayscale_mean_delta: float

    @property
    def is_same_visual_state(self) -> bool:
        return (
            self.dhash_distance <= MAX_DHASH_DISTANCE
            and self.normalized_grayscale_mean_delta <= MAX_NORMALIZED_GRAYSCALE_MEAN_DELTA
        )


def _open_image(source: ImageSource) -> Image.Image:
    if isinstance(source, (str, PathLike)):
        with Image.open(source) as image:
            return image.copy()
    return source


def _grayscale_pixels(source: ImageSource, size: tuple[int, int]) -> np.ndarray:
    image = _open_image(source)
    return np.asarray(
        image.convert("L").resize(size, Image.Resampling.LANCZOS), dtype=np.float32
    ) / 255.0


def calculate_dhash(source: ImageSource) -> int:
    """Return the standard 64-bit horizontal difference hash for an image."""
    pixels = _grayscale_pixels(source, (DHASH_WIDTH, DHASH_HEIGHT))
    bits = pixels[:, 1:] > pixels[:, :-1]
    value = 0
    for bit in bits.ravel():
        value = (value << 1) | int(bit)
    return value


def hamming_distance(first_hash: int, second_hash: int) -> int:
    return (first_hash ^ second_hash).bit_count()


def normalized_grayscale_mean_delta(first: ImageSource, second: ImageSource) -> float:
    """Return mean absolute grayscale pixel difference normalized to [0, 1]."""
    first_pixels = _grayscale_pixels(first, GRAYSCALE_COMPARISON_SIZE)
    second_pixels = _grayscale_pixels(second, GRAYSCALE_COMPARISON_SIZE)
    return float(np.mean(np.abs(first_pixels - second_pixels)))


def compare_frames(first: ImageSource, second: ImageSource) -> FrameSimilarity:
    """Calculate the complete frozen similarity metrics for two frames."""
    return FrameSimilarity(
        dhash_distance=hamming_distance(calculate_dhash(first), calculate_dhash(second)),
        normalized_grayscale_mean_delta=normalized_grayscale_mean_delta(first, second),
    )


def frames_are_similar(first: ImageSource, second: ImageSource) -> bool:
    """Whether both conservative visual-state thresholds are satisfied."""
    return compare_frames(first, second).is_same_visual_state
