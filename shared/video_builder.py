"""
shared/video_builder.py — MoviePy + FFmpeg video assembler.

Composites stock footage clips with the TTS voiceover and background music into
a 1080×1920 (9:16) portrait MP4 ready for YouTube Shorts.

Public API:
    build_video(
        clip_paths,
        voiceover_path,
        output_path,
        music_dir=None,
    ) -> Path
"""

import logging
import os
import random
from pathlib import Path
from typing import Optional

from shared.config import (
    MAX_VIDEO_DURATION,
    MUSIC_DIR,
    MUSIC_VOLUME,
    TMP_DIR,
    VIDEO_FPS,
    VIDEO_HEIGHT,
    VIDEO_WIDTH,
    VOICEOVER_VOLUME,
)

logger = logging.getLogger(__name__)


# ── Lazy MoviePy import (avoids import-time FFmpeg check in dry-run mode) ─────

def _import_moviepy():
    """Import moviepy components lazily to avoid startup errors if FFmpeg is absent."""
    try:
        from moviepy.editor import (  # type: ignore
            AudioFileClip,
            ColorClip,
            CompositeAudioClip,
            CompositeVideoClip,
            VideoFileClip,
            concatenate_videoclips,
        )
        return (
            AudioFileClip,
            ColorClip,
            CompositeAudioClip,
            CompositeVideoClip,
            VideoFileClip,
            concatenate_videoclips,
        )
    except ImportError as exc:
        raise ImportError(
            "MoviePy is required for video assembly. "
            "Install it with: pip install moviepy==1.0.3"
        ) from exc


# ── Helpers ───────────────────────────────────────────────────────────────────

def _pick_background_music(music_dir: Path) -> Optional[Path]:
    """Pick a random MP3 from the music directory. Returns None if empty."""
    if not music_dir.exists():
        return None
    tracks = list(music_dir.glob("*.mp3"))
    if not tracks:
        logger.warning("No background music found in %s. Skipping music overlay.", music_dir)
        return None
    chosen = random.choice(tracks)  # noqa: S311
    logger.info("Background music selected: %s", chosen.name)
    return chosen


def _crop_to_portrait(clip, target_w: int = VIDEO_WIDTH, target_h: int = VIDEO_HEIGHT):
    """
    Crop and resize a clip to the target portrait resolution (1080×1920).

    Strategy:
    - Scale so height = 1920 (preserving aspect), then centre-crop width to 1080.
    - If the clip is already taller than wide, scale width to 1080 first.
    """
    orig_w, orig_h = clip.size

    # Scale so the shorter dimension fills the target
    scale_by_h = target_h / orig_h
    scale_by_w = target_w / orig_w
    scale = max(scale_by_h, scale_by_w)

    new_w = int(orig_w * scale)
    new_h = int(orig_h * scale)
    resized = clip.resize((new_w, new_h))

    # Centre-crop
    x1 = max(0, (new_w - target_w) // 2)
    y1 = max(0, (new_h - target_h) // 2)
    cropped = resized.crop(x1=x1, y1=y1, width=target_w, height=target_h)
    return cropped


def _loop_clips_to_duration(
    clip_paths: list[Path],
    target_duration: float,
    VideoFileClip,
    concatenate_videoclips,
    ColorClip,
) -> object:
    """
    Load clips, concatenate/loop them until they reach `target_duration`.
    Returns a single composed video clip.
    """
    loaded = []
    for path in clip_paths:
        try:
            vc = VideoFileClip(str(path), audio=False)
            cropped = _crop_to_portrait(vc)
            loaded.append(cropped)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not load clip %s: %s", path.name, exc)

    if not loaded:
        logger.warning("No valid clips loaded — using black placeholder.")
        return ColorClip(
            size=(VIDEO_WIDTH, VIDEO_HEIGHT),
            color=(0, 0, 0),
            duration=target_duration,
        ).set_fps(VIDEO_FPS)

    # Concatenate once
    combined = concatenate_videoclips(loaded, method="compose")
    total_duration = combined.duration

    # Loop if shorter than voiceover
    if total_duration < target_duration:
        repeats = int(target_duration / total_duration) + 1
        clips_looped = (loaded * repeats)
        combined = concatenate_videoclips(clips_looped, method="compose")

    # Trim to exact target duration
    combined = combined.subclip(0, min(target_duration, combined.duration))
    combined = combined.set_fps(VIDEO_FPS)
    return combined


# ── Public API ────────────────────────────────────────────────────────────────

def build_video(
    clip_paths: list[Path],
    voiceover_path: Path,
    output_path: Path,
    music_dir: Optional[Path] = None,
) -> Path:
    """
    Assemble the final Short from clips + voiceover + optional background music.

    Args:
        clip_paths:     List of paths to portrait stock-footage MP4 clips.
        voiceover_path: Path to the TTS MP3 voiceover file.
        output_path:    Destination path for the assembled MP4.
        music_dir:      Directory containing background music MP3 files.
                        Defaults to assets/music/.

    Returns:
        Path to the assembled MP4 file.

    Raises:
        FileNotFoundError: If voiceover_path does not exist.
        RuntimeError:      If video encoding fails.
    """
    if not voiceover_path.exists():
        raise FileNotFoundError(f"Voiceover not found: {voiceover_path}")

    effective_music_dir = music_dir or MUSIC_DIR

    (
        AudioFileClip,
        ColorClip,
        CompositeAudioClip,
        CompositeVideoClip,
        VideoFileClip,
        concatenate_videoclips,
    ) = _import_moviepy()

    logger.info("Loading voiceover: %s", voiceover_path.name)
    voiceover = AudioFileClip(str(voiceover_path)).volumex(VOICEOVER_VOLUME)

    # Clamp voiceover to MAX_VIDEO_DURATION
    vo_duration = min(voiceover.duration, MAX_VIDEO_DURATION)
    if voiceover.duration > MAX_VIDEO_DURATION:
        logger.warning(
            "Voiceover (%0.1fs) exceeds %ds limit — trimming.",
            voiceover.duration,
            MAX_VIDEO_DURATION,
        )
        voiceover = voiceover.subclip(0, MAX_VIDEO_DURATION)

    # ── Build video track ─────────────────────────────────────────────────────
    logger.info("Compositing %d clip(s) to %.1fs…", len(clip_paths), vo_duration)
    video_track = _loop_clips_to_duration(
        clip_paths, vo_duration, VideoFileClip, concatenate_videoclips, ColorClip
    )
    video_track = video_track.set_duration(vo_duration)

    # ── Build audio track ─────────────────────────────────────────────────────
    audio_tracks = [voiceover]
    music_path = _pick_background_music(effective_music_dir)
    if music_path:
        try:
            bg_music = (
                AudioFileClip(str(music_path))
                .volumex(MUSIC_VOLUME)
                .subclip(0, vo_duration)
                .audio_fadein(1.5)
                .audio_fadeout(1.5)
            )
            audio_tracks.append(bg_music)
            logger.info("Background music mixed at %.0f%% volume.", MUSIC_VOLUME * 100)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not load background music %s: %s — skipping.", music_path.name, exc)

    composite_audio = CompositeAudioClip(audio_tracks)
    final_clip = video_track.set_audio(composite_audio)

    # ── Encode output ─────────────────────────────────────────────────────────
    output_path.parent.mkdir(parents=True, exist_ok=True)
    logger.info("Encoding → %s  (H.264, AAC, %dfps)…", output_path.name, VIDEO_FPS)

    try:
        final_clip.write_videofile(
            str(output_path),
            fps=VIDEO_FPS,
            codec="libx264",
            audio_codec="aac",
            bitrate="5000k",
            audio_bitrate="192k",
            preset="fast",
            ffmpeg_params=["-crf", "23"],
            logger=None,  # suppress moviepy's verbose ffmpeg output
        )
    except Exception as exc:
        raise RuntimeError(f"Video encoding failed: {exc}") from exc
    finally:
        # Release file handles
        final_clip.close()
        voiceover.close()

    logger.info("Video assembled successfully → %s", output_path)
    return output_path
