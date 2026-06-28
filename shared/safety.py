"""
shared/safety.py — Gemini content-safety validator for Channel B (Rhymie Kids).

Runs ONLY for Channel B scripts before TTS generation. Sends the script to
Gemini with a structured safety prompt. Raises ValueError if the script contains
any content deemed inappropriate for children aged 2-8.

Usage:
    from shared.safety import is_safe
    is_safe("The friendly cat goes meow meow")   # Returns True or raises ValueError
"""

import json
import logging
import os
import re

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

SAFETY_PROMPT = """You are a child safety reviewer for content aimed at kids aged 2-8.
Review the following script carefully.

Check for ANY of these issues:
- Violence, aggression, or conflict between characters
- Adult themes, romantic content, or suggestive language
- Scary or threatening content (monsters, danger, death)
- Inappropriate language or slurs
- Personal data requests (names, addresses, phone numbers)
- Commercial persuasion aimed at children
- Any content that could distress or confuse a young child

Respond with ONLY valid JSON in this exact format:
{{"safe": true, "reason": "Content is appropriate for children aged 2-8."}}
or
{{"safe": false, "reason": "Specific issue found: ..."}}

Script to review:
\"\"\"
{script}
\"\"\"
"""


def _parse_safety_response(response_text: str) -> dict:
    """Extract JSON from Gemini's response, handling markdown code fences."""
    text = response_text.strip()

    # Strip markdown code fences if present
    if "```" in text:
        # Extract content between first and last ```
        matches = re.findall(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
        if matches:
            text = matches[0].strip()

    return json.loads(text)


def is_safe(script: str) -> bool:
    """
    Validate a Channel B script for child-safe content.

    Args:
        script: The generated script text to validate.

    Returns:
        True if the script is safe.

    Raises:
        ValueError:   If the script contains inappropriate content.
        RuntimeError: If the Gemini API call fails or returns unparseable output.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError("GEMINI_API_KEY environment variable is not set.")

    client = genai.Client(api_key=api_key)

    logger.info("Running content safety check on Channel B script...")

    try:
        response = client.models.generate_content(
            model="gemini-1.5-pro",
            contents=SAFETY_PROMPT.format(script=script),
            config=types.GenerateContentConfig(temperature=0.1, max_output_tokens=200),
        )
        result = _parse_safety_response(response.text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Safety check returned unparseable JSON: {response.text}"
        ) from exc
    except Exception as exc:
        raise RuntimeError(f"Safety check API call failed: {exc}") from exc

    if not result.get("safe", False):
        reason = result.get("reason", "No reason provided")
        logger.warning(f"Safety check FAILED: {reason}")
        raise ValueError(f"Unsafe content detected: {reason}")

    logger.info(f"Safety check PASSED: {result.get('reason', 'OK')}")
    return True
