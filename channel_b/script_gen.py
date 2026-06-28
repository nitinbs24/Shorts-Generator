"""
channel_b/script_gen.py — Gemini script generator for Channel B (Rhymie Kids).

Generates two outputs per topic:
    auto_script  — AABB rhyming song for children aged 2-8
    veo_prompt   — Veo video generation prompt for the manual Veo workflow

Also provides generate_auto_script_strict() — a stricter fallback used by
main.py when the standard script fails the content safety check.
"""

import logging
import os

from google import genai
from google.genai import types

from channel_b.config import GEMINI_MAX_TOKENS, GEMINI_TEMPERATURE
from shared.retry import with_retry

logger = logging.getLogger(__name__)

# ── Prompt templates ──────────────────────────────────────────────────────────

_AUTO_SCRIPT_SYSTEM = (
    "You are a children's rhyme writer for kids aged 2-8. "
    "Write warm, playful, age-appropriate content only. "
    "Every line should be simple, joyful, and easy for a toddler to understand."
)

_AUTO_SCRIPT_USER = """Topic: {topic}

Write a fun rhyming song using AABB rhyme scheme.
4-6 couplets, 8 lines maximum. Simple vocabulary only — words a 2-year-old knows.
Use lots of repetition. End with a singalong line the whole family can join in.
Plain text only. No stage directions. No titles."""

_STRICT_SCRIPT_USER = """Topic: {topic}

Write a simple, happy rhyming song for babies and toddlers.
AABB rhyme scheme. Exactly 4 couplets (8 lines).
Use ONLY: colours, animals, shapes, happy sounds (moo, quack, woof, meow).
No conflict, no scary elements, no negative emotions.
Every line must be under 8 words. Plain text only."""

_VEO_PROMPT_USER = """Topic: {topic}

Write a Veo video generation prompt for a children's YouTube Short.
The video must be bright, colourful, and completely child-safe.
Specify: cheerful visual style, camera angle, vivid colour palette, 
happy mood, gentle motion, simple background, 9:16 portrait format.
Suitable for children aged 2-8. Under 80 words. Vivid and specific."""


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
    Generate a children's rhyming song script for Channel B.

    Args:
        topic: The topic string from the topic bank.

    Returns:
        Plain text rhyming script (4-6 couplets, 8 lines max).
    """
    prompt = f"{_AUTO_SCRIPT_SYSTEM}\n\n{_AUTO_SCRIPT_USER.format(topic=topic)}"
    script = _generate(prompt)
    logger.info(f"Auto script generated: topic='{topic}' length={len(script)} chars")
    return script


@with_retry(attempts=3, min_wait=2, max_wait=8)
def generate_auto_script_strict(topic: str) -> str:
    """
    Stricter fallback script generator — used when the standard script fails safety check.

    Uses a more constrained prompt: 4 couplets, simple sounds only, no negatives.

    Args:
        topic: The topic string from the topic bank.

    Returns:
        Plain text rhyming script (4 couplets, very simple vocabulary).
    """
    prompt = f"{_AUTO_SCRIPT_SYSTEM}\n\n{_STRICT_SCRIPT_USER.format(topic=topic)}"
    script = _generate(prompt)
    logger.info(f"Strict script generated: topic='{topic}' length={len(script)} chars")
    return script


@with_retry(attempts=3, min_wait=2, max_wait=8)
def generate_veo_prompt(topic: str) -> str:
    """
    Generate a child-safe Veo video prompt for Channel B's manual Veo workflow.

    Args:
        topic: The topic string from the topic bank.

    Returns:
        Veo video generation prompt (under 80 words, child-safe).
    """
    veo_prompt = _generate(_VEO_PROMPT_USER.format(topic=topic))
    logger.info(f"Veo prompt generated: topic='{topic}' length={len(veo_prompt)} chars")
    return veo_prompt


def generate_scripts(topic: str) -> tuple[str, str]:
    """
    Generate both the auto script and Veo prompt for a given topic.

    Args:
        topic: The topic string from the topic bank.

    Returns:
        Tuple of (auto_script, veo_prompt).
    """
    auto_script = generate_auto_script(topic)
    veo_prompt  = generate_veo_prompt(topic)
    return auto_script, veo_prompt
