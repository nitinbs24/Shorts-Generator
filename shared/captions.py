"""
shared/captions.py — Whisper transcription + FFmpeg subtitle burn.

Generates a .srt subtitle file from the TTS voiceover using OpenAI Whisper,
then burns the subtitles into the video via FFmpeg.

Caption style (per TRD §4.5):
    Font:       Arial Bold
    Colour:     White text, black outline (stroke)
    Alignment:  Centred
    Position:   MarginV=80 (near bottom)
    Font size:  18pt (ASS units ≈ 18)

Public API:
    generate_captions(voiceover_path, output_srt) -> Path
    burn_captions(video_path, srt_path, output_path) -> Path
"""

import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


# ── Whisper helpers ───────────────────────────────────────────────────────────

def _load_whisper_model(model_name: str = "base"):
    """Load a Whisper model, falling back to 'tiny' on OOM."""
    try:
        import whisper  # type: ignore
    except ImportError as exc:
        raise ImportError(
            "openai-whisper is required for caption generation. "
            "Install with: pip install openai-whisper"
        ) from exc

    try:
        logger.info("Loading Whisper model '%s'…", model_name)
        return whisper.load_model(model_name)
    except RuntimeError as exc:
        if "out of memory" in str(exc).lower() and model_name != "tiny":
            logger.warning("OOM loading '%s' model — falling back to 'tiny'.", model_name)
            return whisper.load_model("tiny")
        raise


def _transcribe_audio(model, audio_path: Path) -> dict:
    """Run Whisper transcription and return the result dict."""
    logger.info("Transcribing %s…", audio_path.name)
    result = model.transcribe(
        str(audio_path),
        language="en",
        word_timestamps=False,
        verbose=False,
    )
    return result


def _format_srt_timestamp(seconds: float) -> str:
    """Convert floating-point seconds to SRT timestamp format HH:MM:SS,mmm."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds - int(seconds)) * 1000))
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def _segments_to_srt(segments: list[dict]) -> str:
    """Convert Whisper segments to SRT format string."""
    srt_lines: list[str] = []
    for idx, seg in enumerate(segments, start=1):
        start = _format_srt_timestamp(seg["start"])
        end = _format_srt_timestamp(seg["end"])
        text = seg["text"].strip()
        srt_lines.append(f"{idx}\n{start} --> {end}\n{text}\n")
    return "\n".join(srt_lines)


# ── Public API ────────────────────────────────────────────────────────────────

def generate_captions(
    voiceover_path: Path,
    output_srt: Optional[Path] = None,
    model_name: str = "base",
) -> Path:
    """
    Transcribe the voiceover audio and write an SRT subtitle file.

    Args:
        voiceover_path: Path to the MP3 voiceover.
        output_srt:     Destination .srt file path. Defaults to same dir as voiceover.
        model_name:     Whisper model to use ('base' default, falls back to 'tiny' on OOM).

    Returns:
        Path to the generated .srt file.

    Raises:
        FileNotFoundError: If voiceover_path does not exist.
    """
    if not voiceover_path.exists():
        raise FileNotFoundError(f"Voiceover not found: {voiceover_path}")

    srt_path = output_srt or voiceover_path.with_suffix(".srt")

    model = _load_whisper_model(model_name)
    result = _transcribe_audio(model, voiceover_path)

    segments = result.get("segments", [])
    if not segments:
        logger.warning("Whisper returned no segments — SRT will be empty.")

    srt_content = _segments_to_srt(segments)
    srt_path.parent.mkdir(parents=True, exist_ok=True)
    srt_path.write_text(srt_content, encoding="utf-8")
    logger.info("SRT written → %s  (%d segments)", srt_path.name, len(segments))
    return srt_path


def burn_captions(
    video_path: Path,
    srt_path: Path,
    output_path: Path,
) -> Path:
    """
    Burn .srt subtitles into the video using FFmpeg's subtitles filter.

    Caption style: Arial Bold, white text, black stroke, centred, MarginV=80.

    Args:
        video_path:  Input MP4 (no subtitles).
        srt_path:    The .srt file to burn in.
        output_path: Output MP4 with baked-in captions.

    Returns:
        Path to the captioned video.

    Raises:
        FileNotFoundError: If video_path or srt_path is missing.
        RuntimeError:      If FFmpeg exits with a non-zero code.
    """
    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")
    if not srt_path.exists():
        raise FileNotFoundError(f"SRT file not found: {srt_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # On Windows, FFmpeg paths use forward slashes inside filter_complex
    # We escape colons and backslashes in the srt path for the subtitles filter
    srt_str = str(srt_path).replace("\\", "/").replace(":", "\\:")

    # Caption style matching TRD §4.5
    subtitle_filter = (
        f"subtitles='{srt_str}'"
        ":force_style="
        "'FontName=Arial,"
        "Bold=1,"
        "FontSize=18,"
        "PrimaryColour=&H00FFFFFF,"    # white text
        "OutlineColour=&H00000000,"   # black outline
        "Outline=2,"
        "Alignment=2,"                # bottom-centre
        "MarginV=80'"
    )

    cmd = [
        "ffmpeg",
        "-y",                     # overwrite output
        "-i", str(video_path),
        "-vf", subtitle_filter,
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-c:a", "copy",           # copy audio without re-encoding
        str(output_path),
    ]

    logger.info("Burning captions → %s", output_path.name)
    logger.debug("FFmpeg cmd: %s", " ".join(cmd))

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5-minute hard timeout
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("FFmpeg caption burn timed out after 5 minutes.") from exc

    if result.returncode != 0:
        raise RuntimeError(
            f"FFmpeg caption burn failed (exit {result.returncode}):\n"
            f"{result.stderr[-2000:]}"  # last 2 KB of stderr for diagnostics
        )

    logger.info("Captions burned successfully → %s", output_path.name)
    return output_path
