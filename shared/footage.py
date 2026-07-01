"""
shared/footage.py — Pexels Video API integration.

Downloads royalty-free portrait-orientation stock clips for the video assembler.

Public API:
    fetch_clips(topic, count=3, output_dir=None) -> list[Path]
        Returns a list of downloaded MP4 file paths, sorted by resolution (best first).
        Falls back to a broader category keyword if fewer than 2 clips are returned.
"""

import logging
import os
import re
import requests
from pathlib import Path
from typing import Optional

from shared.config import TMP_DIR
from shared.retry import with_retry

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

PEXELS_BASE_URL = "https://api.pexels.com/videos/search"
PEXELS_PER_PAGE = 10          # fetch enough to pick best ones
TARGET_ORIENTATION = "portrait"

# Broad fallback terms when specific topic yields no results
_CATEGORY_FALLBACKS: list[str] = [
    "nature",
    "city",
    "people",
    "technology",
    "abstract",
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_api_key() -> str:
    """Retrieve Pexels API key from environment."""
    key = os.environ.get("PEXELS_API_KEY", "")
    if not key:
        raise EnvironmentError(
            "PEXELS_API_KEY is not set. "
            "Add it to your .env file or GitHub Secrets."
        )
    return key


def _best_video_file(video_files: list[dict]) -> Optional[dict]:
    """Return the highest-resolution portrait video file from the Pexels file list."""
    portrait_files = [
        f for f in video_files
        if f.get("width", 0) < f.get("height", 1)  # portrait = width < height
    ]
    if not portrait_files:
        # Fall back to any file
        portrait_files = video_files

    # Sort descending by height (resolution)
    portrait_files.sort(key=lambda f: f.get("height", 0), reverse=True)
    return portrait_files[0] if portrait_files else None


def _sanitize_filename(text: str) -> str:
    """Convert topic text into a safe filename prefix."""
    safe = re.sub(r"[^\w\s-]", "", text.lower())
    return re.sub(r"\s+", "_", safe.strip())[:40]


def _download_clip(url: str, output_path: Path) -> Path:
    """Stream-download a video clip to disk. Returns the output path."""
    logger.info("Downloading clip → %s", output_path.name)
    with requests.get(url, stream=True, timeout=60) as resp:
        resp.raise_for_status()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as fh:
            for chunk in resp.iter_content(chunk_size=8192):
                fh.write(chunk)
    return output_path


def _search_pexels(query: str, api_key: str) -> list[dict]:
    """Search Pexels for portrait videos and return the raw video list."""
    params = {
        "query": query,
        "orientation": TARGET_ORIENTATION,
        "per_page": PEXELS_PER_PAGE,
        "size": "medium",  # medium = HD (720p+), not 4K
    }
    headers = {"Authorization": api_key}
    resp = requests.get(PEXELS_BASE_URL, params=params, headers=headers, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    return data.get("videos", [])


# ── Public API ────────────────────────────────────────────────────────────────

@with_retry(attempts=3, min_wait=2, max_wait=8)
def fetch_clips(
    topic: str,
    count: int = 3,
    output_dir: Optional[Path] = None,
) -> list[Path]:
    """
    Fetch and download `count` portrait MP4 clips from Pexels for `topic`.

    Falls back to a broader category keyword if < 2 clips are found for the
    original topic.

    Args:
        topic:      The search keyword/topic string.
        count:      Maximum number of clips to download (default 3).
        output_dir: Directory to save clips. Defaults to a sub-folder in TMP_DIR.

    Returns:
        List of Path objects pointing to downloaded MP4 files.

    Raises:
        EnvironmentError: If PEXELS_API_KEY is not configured.
        RuntimeError:     If no clips are found for topic or any fallback.
    """
    api_key = _get_api_key()
    safe_prefix = _sanitize_filename(topic)
    dest_dir = output_dir or (TMP_DIR / "footage" / safe_prefix)
    dest_dir.mkdir(parents=True, exist_ok=True)

    # ── Primary search ────────────────────────────────────────────────────────
    logger.info("Pexels search: '%s'", topic)
    videos = _search_pexels(topic, api_key)

    # ── Fallback: broaden to category keyword ─────────────────────────────────
    if len(videos) < 2:
        for fallback_query in _CATEGORY_FALLBACKS:
            logger.warning(
                "Only %d clip(s) for '%s'. Trying fallback: '%s'",
                len(videos), topic, fallback_query,
            )
            videos = _search_pexels(fallback_query, api_key)
            if len(videos) >= 2:
                logger.info("Fallback '%s' returned %d clips.", fallback_query, len(videos))
                break

    if not videos:
        raise RuntimeError(
            f"No Pexels clips found for topic '{topic}' or any fallback keyword."
        )

    # ── Select best clips (sorted by duration proximity to target) ────────────
    # Prefer clips ≥ 5 seconds
    usable = [v for v in videos if v.get("duration", 0) >= 5]
    if not usable:
        usable = videos  # accept all if nothing is ≥ 5s

    selected = usable[:count]
    downloaded: list[Path] = []

    for idx, video in enumerate(selected):
        video_files = video.get("video_files", [])
        best_file = _best_video_file(video_files)
        if not best_file:
            logger.warning("Skipping video id=%s — no suitable file found.", video.get("id"))
            continue

        video_url = best_file.get("link", "")
        if not video_url:
            continue

        clip_path = dest_dir / f"{safe_prefix}_{idx:02d}.mp4"
        try:
            _download_clip(video_url, clip_path)
            downloaded.append(clip_path)
            logger.info("Clip %d/%d saved → %s", idx + 1, len(selected), clip_path.name)
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to download clip %d: %s", idx, exc)

    if not downloaded:
        raise RuntimeError(f"All clip downloads failed for topic '{topic}'.")

    logger.info("fetch_clips complete: %d clip(s) downloaded.", len(downloaded))
    return downloaded
