import re
from typing import List, Match, Tuple


# The optional emphasis stars are part of the raw marker so replacement cannot
# leave a Markdown emphasis residue behind.
SCREENSHOT_MARKER_RE = re.compile(
    r"\*?Screenshot-(?:\[(?P<bracket_mm>\d{2}):(?P<bracket_ss>\d{2})\]|(?P<legacy_mm>\d{2}):(?P<legacy_ss>\d{2}))\*?"
)


def find_screenshot_markers(markdown: str) -> List[Match[str]]:
    """Find complete supported screenshot markers in Markdown occurrence order."""
    return list(SCREENSHOT_MARKER_RE.finditer(markdown))


def extract_screenshot_timestamps(markdown: str) -> List[Tuple[str, int]]:
    results: List[Tuple[str, int]] = []
    for match in find_screenshot_markers(markdown):
        mm = match.group("bracket_mm") or match.group("legacy_mm")
        ss = match.group("bracket_ss") or match.group("legacy_ss")
        results.append((match.group(0), int(mm) * 60 + int(ss)))
    return results
