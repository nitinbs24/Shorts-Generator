"""
shared/tts.py — Text-to-speech voiceover generation using edge-tts.

Wraps edge-tts's async API in a synchronous interface. Retries up to 3 times
on network failure before raising RuntimeError.

Usage:
    from shared.tts import generate_voiceover
    generate_voiceover("Hello world", "en-US-GuyNeural", "/tmp/voice.mp3")
"""

import asyncio
import logging
import sys
import time
from pathlib import Path

import edge_tts

logger = logging.getLogger(__name__)

# Fix asyncio event loop on Windows (required for edge-tts)
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


async def _synthesise(
    text: str,
    voice: str,
    output_path: str,
    rate: str = "+0%",
    pitch: str = "+0Hz",
) -> None:
    """Async edge-tts synthesis — saves MP3 to output_path."""
    communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
    await communicate.save(output_path)


def generate_voiceover(
    text: str,
    voice: str,
    output_path: str,
    rate: str = "+0%",
    pitch: str = "+0Hz",
    max_attempts: int = 3,
) -> str:
    """
    Generate a TTS voiceover MP3 from text.

    Args:
        text:         The script text to synthesise.
        voice:        edge-tts voice name (e.g. 'en-US-GuyNeural').
        output_path:  Destination file path for the MP3.
        rate:         Speech rate adjustment (e.g. '+10%', '-5%').
        pitch:        Pitch adjustment (e.g. '+0Hz', '+5Hz').
        max_attempts: Number of retry attempts on network failure.

    Returns:
        The absolute path to the generated MP3 file.

    Raises:
        RuntimeError: If all attempts fail.
    """
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    for attempt in range(1, max_attempts + 1):
        try:
            logger.info(f"TTS attempt {attempt}/{max_attempts}: voice={voice} chars={len(text)}")
            asyncio.run(_synthesise(text, voice, str(output_path), rate, pitch))
            logger.info(f"Voiceover saved: {output_path}")
            return str(output_path)

        except Exception as exc:
            logger.warning(f"TTS attempt {attempt} failed: {exc}")
            if attempt == max_attempts:
                raise RuntimeError(
                    f"TTS generation failed after {max_attempts} attempts: {exc}"
                ) from exc
            wait = 2 ** attempt
            logger.info(f"Retrying in {wait}s...")
            time.sleep(wait)
