"""Deterministic screenshot-intent filtering for Markdown."""

import math
import re
from dataclasses import dataclass
from typing import List, Literal, Set, Tuple

from app.utils.screenshot_marker import find_screenshot_markers


_HEADING_RE = re.compile(r"^(#{2,3})(?!#)\s+(.*?)(?:\s+#+)?\s*$", re.MULTILINE)
_MIN_GAP_SECONDS = 45


@dataclass(frozen=True)
class ScreenshotIntent:
    raw_marker: str
    timestamp: int
    start: int
    end: int
    occurrence: int
    section: Tuple[str, ...]


def _sections_for_positions(markdown: str, positions: List[int]) -> List[Tuple[str, ...]]:
    """Return the active ##/### heading path for each Markdown position."""
    headings = list(_HEADING_RE.finditer(markdown))
    heading_index = 0
    h2 = None
    h3 = None
    sections = []
    for position in positions:
        while heading_index < len(headings) and headings[heading_index].start() < position:
            heading = headings[heading_index]
            level = len(heading.group(1))
            title = heading.group(2).strip()
            if level == 2:
                h2, h3 = title, None
            else:
                h3 = title
            heading_index += 1
        if h3 is not None:
            sections.append((h2 or "", h3))
        elif h2 is not None:
            sections.append((h2,))
        else:
            sections.append(())
    return sections


def _hard_cap(video_duration_seconds: float) -> int:
    return max(1, min(10, math.ceil(max(0.0, video_duration_seconds) / 75)))


def _nearest(candidates: List[ScreenshotIntent], target: float) -> ScreenshotIntent:
    # min() makes the stated later-time/later-occurrence tie-break explicit.
    return min(candidates, key=lambda intent: (abs(intent.timestamp - target), -intent.timestamp, -intent.occurrence))


def _select_math_intents(intents: List[ScreenshotIntent], duration: float) -> Set[int]:
    """Apply run, section min-gap, and section-aware density selection."""
    if not intents:
        return set()

    # Give later Markdown occurrences priority without transitive chain collapse.
    # An earlier intent must be sufficiently distant from every retained later
    # intent in its semantic section, not merely from its immediate neighbor.
    retained_by_section = {}
    candidates: List[ScreenshotIntent] = []
    for intent in reversed(intents):
        retained_later = retained_by_section.setdefault(intent.section, [])
        if all(abs(intent.timestamp - later.timestamp) >= _MIN_GAP_SECONDS for later in retained_later):
            retained_later.append(intent)
            candidates.append(intent)
    candidates.reverse()

    cap = _hard_cap(duration)
    representatives = []
    for intent in candidates:
        if representatives and representatives[-1].section == intent.section:
            representatives[-1] = intent
        else:
            representatives.append(intent)

    if len(representatives) > cap:
        selected: List[ScreenshotIntent] = []
        remaining = list(representatives)
        for index in range(cap):
            target = duration * (index + 1) / (cap + 1)
            chosen = _nearest(remaining, target)
            selected.append(chosen)
            remaining.remove(chosen)
    else:
        selected = list(representatives)
        remaining = [intent for intent in candidates if intent not in selected]
        while len(selected) < cap and remaining:
            chosen = min(
                remaining,
                key=lambda intent: (
                    -min(abs(intent.timestamp - existing.timestamp) for existing in selected),
                    -intent.timestamp,
                    -intent.occurrence,
                ),
            )
            selected.append(chosen)
            remaining.remove(chosen)
    return {intent.occurrence for intent in selected}


def apply_screenshot_policy(
    markdown: str,
    content_profile: Literal["general", "math_course"] = "general",
    video_duration_seconds: float = 0,
) -> str:
    """Remove unselected math-course markers, leaving selected raw markers intact.

    General mode deliberately returns the Markdown unchanged: marker normalization is
    provided by the common parser, which consumes each complete raw marker later.
    """
    if content_profile != "math_course":
        return markdown

    marker_matches = find_screenshot_markers(markdown)
    if not marker_matches:
        return markdown
    sections = _sections_for_positions(markdown, [match.start() for match in marker_matches])
    intents = []
    for index, match in enumerate(marker_matches):
        minutes = match.group("bracket_mm") or match.group("legacy_mm")
        seconds = match.group("bracket_ss") or match.group("legacy_ss")
        intents.append(
            ScreenshotIntent(
                match.group(0), int(minutes) * 60 + int(seconds), match.start(), match.end(), index, sections[index]
            )
        )

    # Collapse whitespace-only contiguous runs before applying all other rules.
    run_collapsed: List[ScreenshotIntent] = []
    run = [intents[0]]
    for intent in intents[1:]:
        between = markdown[run[-1].end:intent.start]
        if not between.strip():
            run.append(intent)
        else:
            run_collapsed.append(run[-1])
            run = [intent]
    run_collapsed.append(run[-1])

    selected_occurrences = _select_math_intents(run_collapsed, video_duration_seconds)
    removals = [intent for intent in intents if intent.occurrence not in selected_occurrences]
    for intent in reversed(removals):
        markdown = markdown[:intent.start] + markdown[intent.end:]
    return markdown
