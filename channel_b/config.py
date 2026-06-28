"""
channel_b/config.py — Constants, settings, and topic selection for Channel B (Rhymie Kids).
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Channel identity ──────────────────────────────────────────────────────────
CHANNEL_ID   = "B"
CHANNEL_NAME = "Rhymie Kids"

# ── Text-to-speech ────────────────────────────────────────────────────────────
TTS_VOICE = "en-US-AnaNeural"    # Child-friendly voice
TTS_RATE  = "-5%"                # Slightly slower — easier for children to follow
TTS_PITCH = "+5Hz"               # Slightly higher pitch — warmer, child-friendly

# ── YouTube metadata ──────────────────────────────────────────────────────────
YOUTUBE_CATEGORY_ID = "27"       # Education
TITLE_FORMAT        = "The {topic} Song! | Kids Rhymes #Shorts #Nursery"
DESCRIPTION_TEMPLATE = (
    "🎵 {topic} — a fun rhyming song for little ones!\n\n"
    "#Shorts #Nursery #KidsRhymes #ChildrenSongs #Learning\n\n"
    "New songs every day — subscribe for more fun rhymes!"
)

# ── Scheduling (UTC) ──────────────────────────────────────────────────────────
UPLOAD_SCHEDULE = ["07:00", "16:00"]   # GitHub Actions cron: 0 7 * * * / 0 16 * * *

# ── Gemini script generation ──────────────────────────────────────────────────
GEMINI_TEMPERATURE = 0.6         # Lower = more consistent, age-appropriate output
GEMINI_MAX_TOKENS  = 500

# ── Topic bank ────────────────────────────────────────────────────────────────
TOPIC_BANK_PATH = Path(__file__).parent / "topic_bank.json"
TOPIC_DEDUP_DAYS = 30            # Skip topics used in the last 30 days

_topic_bank_cache: list[dict] | None = None


def _load_topic_bank() -> list[dict]:
    """Load and cache the topic bank JSON."""
    global _topic_bank_cache
    if _topic_bank_cache is None:
        with open(TOPIC_BANK_PATH, encoding="utf-8") as f:
            _topic_bank_cache = json.load(f)
    return _topic_bank_cache


def fetch_topic() -> str:
    """
    Select the next topic from the topic bank using round-robin logic.

    Picks the first topic (in bank order) not used in the last TOPIC_DEDUP_DAYS days.
    If all topics have been used recently, picks the one used least recently (full cycle reset).

    Returns:
        Topic string from the bank.
    """
    from shared.db import is_topic_used, is_blacklisted

    bank = _load_topic_bank()

    # First pass: find a topic not used recently and not blacklisted
    for entry in bank:
        topic = entry["topic"]
        if is_blacklisted("B", topic):
            logger.debug(f"Skipping blacklisted topic: {topic}")
            continue
        if not is_topic_used("B", topic, days=TOPIC_DEDUP_DAYS):
            logger.info(f"Selected topic (fresh): {topic}")
            return topic

    # All topics used — full cycle complete, take the first non-blacklisted entry
    logger.info("Full topic bank cycle complete — restarting from beginning")
    for entry in bank:
        topic = entry["topic"]
        if not is_blacklisted("B", topic):
            logger.info(f"Selected topic (cycle reset): {topic}")
            return topic

    raise RuntimeError("No valid topics available in topic bank (all blacklisted?)")
