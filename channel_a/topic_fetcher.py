"""
channel_a/topic_fetcher.py — Trending topic engine for Channel A (TrendByte Shorts).

Primary source:  Google Trends RSS (daily trending, region=IN)
Fallback source: feedparser — BBC Top Stories + Reddit r/worldnews RSS feeds

Applies 30-day deduplication and blacklist filtering before returning a topic.
"""

import logging
import re

import feedparser

from channel_a.config import (
    PYTRENDS_GEO,
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


def _clean_topic(raw: str) -> str:
    """
    Sanitise a raw headline into a clean topic string.

    - Strips HTML tags and common entities
    - Removes leading/trailing whitespace
    - Collapses internal whitespace
    - Truncates to TOPIC_MAX_LENGTH characters
    - Returns empty string if result is too short (< 4 chars)
    """
    if not raw:
        return ""
    # Remove HTML tags
    text = re.sub(r"<[^>]+>", "", raw)
    # Decode common HTML entities
    text = (
        text.replace("&amp;", "&")
            .replace("&lt;", "<")
            .replace("&gt;", ">")
            .replace("&quot;", '"')
            .replace("&#39;", "'")
            .replace("&nbsp;", " ")
    )
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    # Truncate to max length at word boundary
    if len(text) > TOPIC_MAX_LENGTH:
        text = text[:TOPIC_MAX_LENGTH].rsplit(" ", 1)[0]
    return text if len(text) >= 4 else ""


def _fetch_from_google_trends() -> list[str]:
    """Fetch daily trending search topics from the official Google Trends RSS feed."""
    logger.info(f"Fetching trending topics from Google Trends RSS (geo={PYTRENDS_GEO})...")
    topics: list[str] = []
    try:
        url = f"https://trends.google.com/trending/rss?geo={PYTRENDS_GEO}"
        feed = feedparser.parse(url)
        for entry in feed.entries:
            topic = _clean_topic(entry.get("title", ""))
            if topic:
                topics.append(topic)
        logger.info(f"Google Trends RSS returned {len(topics)} topics")
    except Exception as exc:
        logger.warning(f"Google Trends RSS failed: {exc}")
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
    """

    # ── Attempt Google Trends RSS ─────────────────────────────────────────────
    candidates = _fetch_from_google_trends()

    # ── Fallback to BBC/Reddit RSS ────────────────────────────────────────────
    if not candidates:
        logger.info("Google Trends failed — falling back to secondary RSS feeds")
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
