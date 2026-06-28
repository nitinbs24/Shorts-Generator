"""
shared/config.py — Shared constants used across the entire pipeline.
"""

import os
import tempfile
from pathlib import Path

# ── Directory layout ──────────────────────────────────────────────────────────
ROOT_DIR   = Path(__file__).parent.parent
DATA_DIR   = ROOT_DIR / "data"
ASSETS_DIR = ROOT_DIR / "assets"
MUSIC_DIR  = ASSETS_DIR / "music"

# Temp directory — works on both Windows and Linux (GitHub Actions)
TMP_DIR = Path(tempfile.gettempdir())

# ── Database ──────────────────────────────────────────────────────────────────
DB_PATH = DATA_DIR / "ventures.db"

# ── Video settings ────────────────────────────────────────────────────────────
VIDEO_WIDTH      = 1080
VIDEO_HEIGHT     = 1920          # 9:16 portrait
VIDEO_FPS        = 30
MAX_VIDEO_DURATION = 59          # seconds (YouTube Shorts limit)

# ── Audio mix ─────────────────────────────────────────────────────────────────
VOICEOVER_VOLUME = 1.0           # 100 % — primary track
MUSIC_VOLUME     = 0.2           # 20 % — background music

# ── Retry defaults ────────────────────────────────────────────────────────────
DEFAULT_RETRY_ATTEMPTS = 3
DEFAULT_RETRY_MIN_WAIT = 2       # seconds
DEFAULT_RETRY_MAX_WAIT = 8       # seconds
