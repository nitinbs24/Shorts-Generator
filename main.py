"""
main.py — Pipeline Orchestrator for YouTube Shorts Automation Ventures.

Entry point for both channels. Called by GitHub Actions and locally for testing.

Usage:
    python main.py --channel a              # Run full pipeline for Channel A
    python main.py --channel b              # Run full pipeline for Channel B
    python main.py --channel a --dry-run    # Stop before video assembly & upload
    python main.py --channel b --dry-run

Pipeline steps:
    1.  Fetch topic
    2.  Generate auto script + Veo prompt (Gemini)
    3.  Content safety check (Channel B only)
    4.  Generate TTS voiceover (edge-tts)
    5.  Store Veo entry in database
    6.  Mark topic as used
    -- dry-run stops here --
    7.  Fetch stock footage (Pexels)
    8.  Assemble video (MoviePy + FFmpeg)
    9.  Generate & burn captions (Whisper)
    10. Upload to YouTube
"""

import argparse
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# ── Logging setup ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("main")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_env() -> None:
    """Load .env file for local development. No-op in GitHub Actions (secrets are env vars)."""
    try:
        from dotenv import load_dotenv
        if load_dotenv():
            logger.info("Loaded environment from .env file")
    except ImportError:
        pass  # python-dotenv not required in CI


def _get_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _tmp_path(filename: str) -> str:
    """Return a cross-platform temp file path."""
    from shared.config import TMP_DIR
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    return str(TMP_DIR / filename)


def _fetch_topic(channel: str) -> str:
    """Dispatch topic fetching to the correct channel engine."""
    if channel == "a":
        from channel_a.topic_fetcher import fetch_topic
        return fetch_topic()
    else:
        from channel_b.config import fetch_topic  # type: ignore[attr-defined]
        return fetch_topic()


def _get_channel_config(channel: str):
    """Import and return the config module for the given channel."""
    if channel == "a":
        import channel_a.config as cfg
    else:
        import channel_b.config as cfg
    return cfg


def _generate_scripts(channel: str, topic: str) -> tuple[str, str]:
    """Dispatch script generation to the correct channel module."""
    if channel == "a":
        from channel_a.script_gen import generate_scripts
    else:
        from channel_b.script_gen import generate_scripts
    return generate_scripts(topic)


# ── Pipeline ──────────────────────────────────────────────────────────────────

def run_pipeline(channel: str, dry_run: bool = False) -> None:
    """
    Execute the full (or dry-run) pipeline for the given channel.

    Args:
        channel:  'a' for TrendByte Shorts, 'b' for Rhymie Kids.
        dry_run:  If True, stops after TTS generation — no footage, video, or upload.
    """
    from shared.db import (
        init_db,
        log_upload,
        mark_topic_used,
        store_veo_entry,
        update_upload_status,
    )
    from shared.tts import generate_voiceover

    cfg     = _get_channel_config(channel)
    run_id  = _get_run_id()
    channel_label = channel.upper()

    logger.info("=" * 60)
    logger.info(f"Pipeline start: Channel {channel_label} | Run {run_id}")
    if dry_run:
        logger.info("MODE: DRY RUN (no video assembly or upload)")
    logger.info("=" * 60)

    # ── Step 1: Initialise database ───────────────────────────────────────────
    logger.info("Step 1/10 — Initialising database...")
    init_db()

    # ── Step 2: Fetch topic ───────────────────────────────────────────────────
    logger.info("Step 2/10 — Fetching topic...")
    topic = _fetch_topic(channel)
    logger.info(f"          Topic: '{topic}'")

    # ── Step 3: Generate scripts ──────────────────────────────────────────────
    logger.info("Step 3/10 — Generating scripts via Gemini...")
    auto_script, veo_prompt = _generate_scripts(channel, topic)
    logger.info(f"          Auto script: {len(auto_script)} chars")
    logger.info(f"          Veo prompt:  {len(veo_prompt)} chars")

    # ── Step 4: Content safety check (Channel B only) ─────────────────────────
    if channel == "b":
        logger.info("Step 4/10 — Running content safety check (Channel B)...")
        from shared.safety import is_safe
        from channel_b.script_gen import generate_auto_script_strict

        for safety_attempt in range(1, 3):
            try:
                is_safe(auto_script)
                break
            except ValueError as exc:
                logger.warning(f"          Safety check failed (attempt {safety_attempt}/2): {exc}")
                if safety_attempt == 2:
                    raise RuntimeError(
                        f"Script for '{topic}' failed safety check after 2 attempts."
                    ) from exc
                logger.info("          Regenerating with stricter prompt...")
                auto_script = generate_auto_script_strict(topic)
    else:
        logger.info("Step 4/10 — Safety check: skipped (Channel A)")

    # ── Step 5: Generate TTS voiceover ────────────────────────────────────────
    logger.info("Step 5/10 — Generating TTS voiceover...")
    voiceover_path = Path(_tmp_path(f"voiceover_{run_id}.mp3"))
    generate_voiceover(
        text=auto_script,
        voice=cfg.TTS_VOICE,
        output_path=str(voiceover_path),
        rate=cfg.TTS_RATE,
        pitch=cfg.TTS_PITCH,
    )
    logger.info(f"          Voiceover: {voiceover_path}")

    # ── Step 6: Store Veo entry + mark topic used ─────────────────────────────
    logger.info("Step 6/10 — Storing Veo entry and marking topic used...")
    veo_id = store_veo_entry(channel_label, topic, auto_script, veo_prompt)
    mark_topic_used(channel_label, topic)
    logger.info(f"          Veo entry ID: {veo_id}")
    logger.info(f"          Topic '{topic}' marked as used")

    # ── Dry-run exit ──────────────────────────────────────────────────────────
    if dry_run:
        logger.info("")
        logger.info("DRY RUN COMPLETE — pipeline outputs:")
        logger.info(f"  Script preview : {auto_script[:120].replace(chr(10), ' ')}...")
        logger.info(f"  Voiceover file : {voiceover_path}")
        logger.info(f"  Veo prompt     : {veo_prompt[:80].replace(chr(10), ' ')}...")
        logger.info("")
        return

    # ── Step 7: Fetch stock footage ───────────────────────────────────────────
    logger.info("Step 7/10 — Fetching stock footage from Pexels...")
    from shared.footage import fetch_clips
    clips = fetch_clips(topic, count=3)
    logger.info(f"           Downloaded {len(clips)} clips")

    # ── Step 8: Assemble video ────────────────────────────────────────────────
    logger.info("Step 8/10 — Assembling video (MoviePy + FFmpeg)...")
    from shared.video_builder import build_video
    no_subs_path = Path(_tmp_path(f"no_subs_{run_id}.mp4"))
    build_video(
        clip_paths=clips,
        voiceover_path=voiceover_path,
        output_path=no_subs_path,
    )
    logger.info(f"           Assembled (no captions): {no_subs_path.name}")

    # ── Step 9: Generate captions + burn ─────────────────────────────────────
    logger.info("Step 9/10 — Transcribing and burning captions (Whisper)...")
    from shared.captions import generate_captions, burn_captions
    srt_path   = Path(_tmp_path(f"captions_{run_id}.srt"))
    final_path = Path(_tmp_path(f"final_{run_id}.mp4"))
    generate_captions(voiceover_path=voiceover_path, output_srt=srt_path)
    burn_captions(
        video_path=no_subs_path,
        srt_path=srt_path,
        output_path=final_path,
    )
    logger.info(f"           Final video with captions: {final_path.name}")

    # ── Step 10: Upload to YouTube ────────────────────────────────────────────
    logger.info("Step 10/10 — Uploading to YouTube...")
    title       = cfg.TITLE_FORMAT.format(topic=topic)
    description = cfg.DESCRIPTION_TEMPLATE.format(topic=topic)
    upload_id   = log_upload(channel_label, "auto", title, topic)

    try:
        from shared.uploader import upload_short
        youtube_id = upload_short(
            video_path=final_path,
            title=title,
            description=description,
            category_id=int(cfg.YOUTUBE_CATEGORY_ID),
            channel_label=channel,
        )
        update_upload_status(upload_id, "success", youtube_id=youtube_id)
        logger.info("=" * 60)
        logger.info(f"UPLOAD SUCCESS — YouTube ID: {youtube_id}")
        logger.info(f"URL: https://youtu.be/{youtube_id}")
        logger.info(f"Title: {title}")
        logger.info("=" * 60)

    except Exception as exc:
        update_upload_status(upload_id, "failed", error_message=str(exc))
        logger.error(f"Upload failed: {exc}")
        raise


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="YouTube Shorts Automation — pipeline orchestrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --channel a             # Full Channel A pipeline
  python main.py --channel b             # Full Channel B pipeline
  python main.py --channel a --dry-run   # Test Phase 1 without video/upload
        """,
    )
    parser.add_argument(
        "--channel",
        choices=["a", "b"],
        required=True,
        help="Channel to run: 'a' (TrendByte Shorts) or 'b' (Rhymie Kids)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run topic → script → TTS → DB only. Skips footage, video, and upload.",
    )
    args = parser.parse_args()

    _load_env()

    try:
        run_pipeline(args.channel, args.dry_run)
    except Exception as exc:
        logger.error(f"Pipeline failed: {exc}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
