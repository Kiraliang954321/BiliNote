"""Settled-frame selection for math-course screenshot intents."""

from dataclasses import dataclass
from typing import Callable, Optional

import numpy as np
from PIL import Image


@dataclass(frozen=True)
class StableFrameSelectorConfig:
    """Centralized parameters for the bounded final-frame search."""

    lookback_seconds: int = 2
    lookahead_seconds: int = 8
    sample_step_seconds: int = 1
    analysis_width: int = 320
    analysis_height: int = 180
    settled_motion_threshold: float = 0.03
    scene_cut_threshold: float = 0.18


DEFAULT_STABLE_FRAME_SELECTOR_CONFIG = StableFrameSelectorConfig()


def _grayscale_frame(frame: object, config: StableFrameSelectorConfig) -> np.ndarray:
    """Convert a Pillow image or array to the fixed analysis representation."""
    if isinstance(frame, Image.Image):
        image = frame.convert("L").resize(
            (config.analysis_width, config.analysis_height), Image.Resampling.BILINEAR
        )
        return np.asarray(image, dtype=np.float32) / 255.0

    array = np.asarray(frame)
    if not np.all(np.isfinite(array)):
        raise ValueError("frame contains non-finite pixels")
    if array.ndim == 3:
        # The synthetic loader contract also permits RGB/RGBA numpy frames.
        array = array[..., :3].astype(np.float32).mean(axis=2)
    elif array.ndim != 2:
        raise ValueError("frame must be a 2D grayscale or 3D color image")
    if np.issubdtype(array.dtype, np.floating) and array.size and array.min() >= 0 and array.max() <= 1:
        array = array * 255
    image = Image.fromarray(np.clip(array, 0, 255).astype(np.uint8), mode="L")
    image = image.resize((config.analysis_width, config.analysis_height), Image.Resampling.BILINEAR)
    return np.asarray(image, dtype=np.float32) / 255.0


def _motion_delta(first: np.ndarray, second: np.ndarray) -> float:
    return float(np.mean(np.abs(first - second)))


def _sharpness(frame: np.ndarray) -> float:
    """Horizontal plus vertical grayscale gradient energy."""
    return float(np.mean(np.abs(np.diff(frame, axis=1))) + np.mean(np.abs(np.diff(frame, axis=0))))


class StableFrameSelector:
    """Choose a local settled frame, falling back to the supplied intent on failure."""

    def __init__(
        self,
        frame_loader: Callable[[float], object],
        video_duration: float,
        config: StableFrameSelectorConfig = DEFAULT_STABLE_FRAME_SELECTOR_CONFIG,
    ) -> None:
        self.frame_loader = frame_loader
        self.video_duration = video_duration
        self.config = config

    def select(self, intent_timestamp: int) -> int:
        """Return the best local timestamp, or *exactly* the original intent on error."""
        original_timestamp = intent_timestamp
        try:
            if self.video_duration < 0:
                return original_timestamp
            start = max(0, intent_timestamp - self.config.lookback_seconds)
            end = min(intent_timestamp + self.config.lookahead_seconds, int(self.video_duration))
            timestamps = list(range(start, end + 1, self.config.sample_step_seconds))
            if len(timestamps) < 3:
                return original_timestamp

            frames = [_grayscale_frame(self.frame_loader(timestamp), self.config) for timestamp in timestamps]
            deltas = [_motion_delta(frames[index - 1], frames[index]) for index in range(1, len(frames))]

            # A cut from t to t+1 is a forward boundary only if t is at/after
            # the intent.  A lookback cut must not invalidate the intent scene.
            cutoff: Optional[int] = None
            for index, delta in enumerate(deltas):
                transition_start = timestamps[index]
                transition_end = timestamps[index + 1]
                if transition_start >= intent_timestamp and delta >= self.config.scene_cut_threshold:
                    cutoff = transition_end
                    break

            candidates = []
            for index in range(1, len(timestamps) - 1):
                timestamp = timestamps[index]
                if cutoff is not None and timestamp >= cutoff:
                    break
                previous_delta, next_delta = deltas[index - 1], deltas[index]
                motion_score = max(previous_delta, next_delta)
                settled = (
                    previous_delta <= self.config.settled_motion_threshold
                    and next_delta <= self.config.settled_motion_threshold
                )
                candidates.append((settled, motion_score, _sharpness(frames[index]), timestamp))

            if not candidates:
                return original_timestamp
            # settled, lower motion, higher sharpness, later time
            best = min(candidates, key=lambda item: (not item[0], item[1], -item[2], -item[3]))
            return best[3]
        except Exception:
            return original_timestamp


def select_stable_frame(
    frame_loader: Callable[[float], object],
    video_duration: float,
    intent_timestamp: int,
    config: StableFrameSelectorConfig = DEFAULT_STABLE_FRAME_SELECTOR_CONFIG,
) -> int:
    """Convenience API used by callers and synthetic unit tests."""
    return StableFrameSelector(frame_loader, video_duration, config).select(intent_timestamp)
