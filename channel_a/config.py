"""
channel_a/config.py — Constants and settings for Channel A (TrendByte Shorts).
"""

# ── Channel identity ──────────────────────────────────────────────────────────
CHANNEL_ID   = "A"
CHANNEL_NAME = "TrendByte Shorts"

# ── Text-to-speech ────────────────────────────────────────────────────────────
TTS_VOICE = "en-US-GuyNeural"    # Energetic male voice
TTS_RATE  = "+10%"               # Slightly faster delivery
TTS_PITCH = "+0Hz"               # Default pitch

# ── YouTube metadata ──────────────────────────────────────────────────────────
YOUTUBE_CATEGORY_ID = "25"       # News & Politics
TITLE_FORMAT        = "Did you know {topic}? #Shorts #Trending #Facts"
DESCRIPTION_TEMPLATE = (
    "🔥 {topic}\n\n"
    "#Shorts #Trending #Facts #DidYouKnow #Viral\n\n"
    "New Shorts every day — subscribe for daily facts!"
)

# ── Scheduling (UTC) ──────────────────────────────────────────────────────────
UPLOAD_SCHEDULE = ["08:00", "18:00"]   # GitHub Actions cron: 0 8 * * * / 0 18 * * *

# ── Gemini script generation ──────────────────────────────────────────────────
GEMINI_TEMPERATURE  = 0.8        # Higher = more varied output
GEMINI_MAX_TOKENS   = 500        # auto script (300) + Veo prompt (200)

# ── Topic fetching ────────────────────────────────────────────────────────────
PYTRENDS_GEO        = "IN"       # India — large English-trending market
TOPIC_MAX_LENGTH    = 60         # characters
TOPIC_DEDUP_DAYS    = 30         # rolling deduplication window
