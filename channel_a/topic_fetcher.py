"""
channel_a/topic_fetcher.py — Trending topic engine for Channel A (TrendByte Shorts).

Primary source:  pytrends — Google Trends daily trending searches (region=IN)
Fallback source: feedparser — BBC Top Stories + Reddit r/worldnews RSS feeds

Applies 30-day deduplication and blacklist filtering before returning a topic.
"""

import logging
import re
import time

import feedparser
from pytrends.request import TrendReq

from channel_a.config import (
    PYTRENDS_GEO,
    PYTRENDS_LANGUAGE,
    TOPIC_DEDUP_DAYS,
    TOPIC_MAX_LENGTH,
)
from shared.db import is_blacklisted, is_topic_used

logger = logging.getLogger(__name__)

RSS_FEEDS = [
    "http://feeds.bbci.co.uk/news/rss.xml",          # BBC Top Stories
    "https://www.reddit.com/r/worldnews/.rss",         # Reddit r/worldnews
    "http://feeds.bbci.co.uk/news/technology/rss.xml", # BBC Technology (bonus)
]

PYTRENDS_MAX_RETRIES = 3
PYTRENDS_RETRY_WAIT  = 60   # seconds — pytrends rate limit cooldown


def _clean_topic(raw: str) -> str:
    """Normalise a raw topic string: strip special chars, trim to max length."""
    cleaned = re.sub(r"[^\w\s\-]", "", raw)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:TOPIC_MAX_LENGTH]


def _fetch_from_pytrends() -> list[str]:
    """Fetch daily trending search topics from Google Trends for the configured region."""
    logger.info(f"Fetching trending topics from pytrends (geo={PYTRENDS_GEO})...")
    pytrends = TrendReq(hl=PYTRENDS_LANGUAGE, tz=330)   # tz=330 = IST (UTC+5:30)
    df = pytrends.trending_searches(pn="india")
    topics = [_clean_topic(t) for t in df[0].tolist() if t]
    logger.info(f"pytrends returned {len(topics)} topics")
    return topics


def _fetch_from_rss() -> list[str]:
    """Fetch headline topics from BBC and Reddit RSS feeds as fallback."""
    logger.info("Fetching topics from RSS feeds...")
    topics: list[str] = []

    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:10]:
                topic = _clean_topic(entry.get("title", ""))
                if topic:
                    topics.append(topic)
            logger.debug(f"RSS {url}: {len(feed.entries)} entries parsed")
        except Exception as exc:
            logger.warning(f"RSS feed failed ({url}): {exc}")

    logger.info(f"RSS feeds returned {len(topics)} total topics")
    return topics


def _is_valid_topic(topic: str, channel: str = "A") -> bool:
    """Return True if the topic passes dedup and blacklist checks."""
    if not topic:
        return False
    if is_topic_used(channel, topic, days=TOPIC_DEDUP_DAYS):
        logger.debug(f"Skipping (used in last {TOPIC_DEDUP_DAYS}d): {topic}")
        return False
    if is_blacklisted(channel, topic):
        logger.debug(f"Skipping (blacklisted): {topic}")
        return False
    return True


def fetch_topic() -> str:
    """
    Fetch a valid, deduplicated trending topic for Channel A.

    Tries pytrends first (with retries on rate-limit), then falls back to RSS.
    Applies deduplication and blacklist filtering before returning.

    Returns:
        A clean topic string (max 60 characters).

    Raises:
        RuntimeError: If no valid topic can be found from any source.
    """
    candidates: list[str] = []

    # ── Attempt pytrends ──────────────────────────────────────────────────────
    for attempt in range(1, PYTRENDS_MAX_RETRIES + 1):
        try:
            candidates = _fetch_from_pytrends()
            break
        except Exception as exc:
            logger.warning(f"pytrends attempt {attempt}/{PYTRENDS_MAX_RETRIES} failed: {exc}")
            if attempt < PYTRENDS_MAX_RETRIES:
                logger.info(f"Waiting {PYTRENDS_RETRY_WAIT}s before retry...")
                time.sleep(PYTRENDS_RETRY_WAIT)

    # ── Fallback to RSS ───────────────────────────────────────────────────────
    if not candidates:
        logger.info("pytrends failed — falling back to RSS feeds")
        candidates = _fetch_from_rss()

    # ── Filter and return first valid topic ───────────────────────────────────
    for topic in candidates:
        if _is_valid_topic(topic, channel="A"):
            logger.info(f"Topic selected: '{topic}'")
            return topic

    raise RuntimeError(
        "No valid trending topics found after deduplication and blacklist filtering. "
        "All candidates have been used in the last 30 days or are blacklisted."
    )
