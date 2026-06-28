"""
channel_a/script_gen.py — Gemini script generator for Channel A (TrendByte Shorts).

Generates two outputs per topic:
    auto_script  — 45-second punchy script for the automated video pipeline
    veo_prompt   — Veo video generation prompt for the manual Veo workflow

Both functions use the @with_retry decorator for resilience against API rate limits.
"""

import logging
import os

from google import genai
from google.genai import types

from channel_a.config import GEMINI_MAX_TOKENS, GEMINI_TEMPERATURE
from shared.retry import with_retry

logger = logging.getLogger(__name__)

# ── Prompt templates ──────────────────────────────────────────────────────────

_AUTO_SCRIPT_SYSTEM = (
    "You are a viral YouTube Shorts scriptwriter. "
    "Write punchy, fast-paced scripts for a general audience aged 16-35. "
    "Always hook the viewer in the very first sentence."
)

_AUTO_SCRIPT_USER = """Topic: {topic}

Write a 45-second YouTube Shorts script.
Structure: shocking hook (1 sentence) → 3 punchy facts → memorable punchline.
Under 70 words total. No hashtags in the script. Plain text only. No stage directions."""

_VEO_PROMPT_USER = """Topic: {topic}

Write a Veo video generation prompt for a YouTube Short about this topic.
Specify all of: visual style, camera angle, colour palette, mood, motion type, background setting, 9:16 portrait format.
Under 80 words. Vivid and specific — describe exactly what the viewer sees."""


# ── Model factory ─────────────────────────────────────────────────────────────

def _get_client() -> genai.Client:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError("GEMINI_API_KEY environment variable is not set.")
    return genai.Client(api_key=api_key)


def _generate(prompt: str) -> str:
    """Send a prompt to Gemini and return the response text."""
    client = _get_client()
    response = client.models.generate_content(
        model="gemini-1.5-pro",
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=GEMINI_TEMPERATURE,
            max_output_tokens=GEMINI_MAX_TOKENS,
        ),
    )
    return response.text.strip()


# ── Script generators ─────────────────────────────────────────────────────────

@with_retry(attempts=3, min_wait=2, max_wait=8)
def generate_auto_script(topic: str) -> str:
    """
    Generate a 45-second punchy script for Channel A's automated video pipeline.

    Args:
        topic: The trending topic string.

    Returns:
        Plain text script (under 70 words).
    """
    prompt = f"{_AUTO_SCRIPT_SYSTEM}\n\n{_AUTO_SCRIPT_USER.format(topic=topic)}"
    script = _generate(prompt)
    logger.info(f"Auto script generated: topic='{topic}' length={len(script)} chars")
    return script


@with_retry(attempts=3, min_wait=2, max_wait=8)
def generate_veo_prompt(topic: str) -> str:
    """
    Generate a Veo video prompt for Channel A's manual Veo workflow.

    Args:
        topic: The trending topic string.

    Returns:
        Veo video generation prompt (under 80 words).
    """
    veo_prompt = _generate(_VEO_PROMPT_USER.format(topic=topic))
    logger.info(f"Veo prompt generated: topic='{topic}' length={len(veo_prompt)} chars")
    return veo_prompt


def generate_scripts(topic: str) -> tuple[str, str]:
    """
    Generate both the auto script and Veo prompt for a given topic.

    Args:
        topic: The trending topic string.

    Returns:
        Tuple of (auto_script, veo_prompt).
    """
    auto_script = generate_auto_script(topic)
    veo_prompt  = generate_veo_prompt(topic)
    return auto_script, veo_prompt
