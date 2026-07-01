"""
dashboard/components.py — Reusable Streamlit component helpers for the Ventures Dashboard.
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timezone


# ── KPI Cards ─────────────────────────────────────────────────────────────────

def render_kpi_card(label: str, value: str, sub: str = "", variant: str = "neutral") -> None:
    """Render a styled KPI metric card."""
    st.markdown(
        f"""
        <div class="kpi-card {variant}">
            <div class="kpi-label">{label}</div>
            <div class="kpi-value">{value}</div>
            {'<div class="kpi-sub">' + sub + '</div>' if sub else ''}
        </div>
        """,
        unsafe_allow_html=True,
    )


# ── Status Badges ──────────────────────────────────────────────────────────────

def status_badge(status: str) -> str:
    """Return an HTML badge string for an upload status."""
    mapping = {
        "success": ("badge-success", "✓ Success"),
        "failed":  ("badge-failed",  "✗ Failed"),
        "pending": ("badge-pending", "⟳ Pending"),
    }
    cls, label = mapping.get(status.lower(), ("badge-pending", status))
    return f'<span class="badge {cls}">{label}</span>'


def channel_badge(channel: str) -> str:
    """Return an HTML badge string for a channel label."""
    cls   = "badge-a" if channel.upper() == "A" else "badge-b"
    label = "TrendByte" if channel.upper() == "A" else "Rhymie Kids"
    return f'<span class="badge {cls}">{label}</span>'


# ── Upload History Table ───────────────────────────────────────────────────────

def render_upload_table(uploads: list[dict]) -> None:
    """Render the upload history as a formatted Streamlit dataframe."""
    if not uploads:
        st.info("No uploads found for the selected filters.")
        return

    df = pd.DataFrame(uploads)
    df["created_at"] = pd.to_datetime(df["created_at"]).dt.strftime("%b %d, %H:%M")
    df["youtube_url"] = df["youtube_id"].apply(
        lambda vid: f"https://youtu.be/{vid}" if vid else ""
    )

    display_df = df[["created_at", "channel", "mode", "title", "status", "youtube_url"]].copy()
    display_df.columns = ["Date", "Ch", "Mode", "Title", "Status", "URL"]

    st.dataframe(
        display_df,
        width='stretch',
        hide_index=True,
        column_config={
            "Status": st.column_config.TextColumn("Status"),
            "URL": st.column_config.LinkColumn("YouTube", display_text="▶ Watch"),
            "Title": st.column_config.TextColumn("Title", width="large"),
        },
    )


# ── Blacklist Editor ───────────────────────────────────────────────────────────

def render_blacklist_editor(channel: str) -> None:
    """Render a collapsible blacklist editor for a channel."""
    from shared.db import get_blacklist, add_to_blacklist, remove_from_blacklist

    with st.expander("🚫 Topic Blacklist", expanded=False):
        entries = get_blacklist(channel)

        if entries:
            st.markdown("**Blacklisted topics** (click × to remove):")
            cols = st.columns(4)
            for i, entry in enumerate(entries):
                with cols[i % 4]:
                    if st.button(f"× {entry['topic']}", key=f"bl_{entry['id']}_{channel}",
                                 help="Click to remove from blacklist"):
                        remove_from_blacklist(entry["id"])
                        st.rerun()
        else:
            st.caption("No blacklisted topics yet.")

        st.divider()
        new_topic = st.text_input(
            "Add topic to blacklist",
            placeholder="e.g. politics, violence...",
            key=f"bl_input_{channel}",
        )
        if st.button("Add to Blacklist", key=f"bl_add_{channel}"):
            if new_topic.strip():
                add_to_blacklist(channel, new_topic.strip())
                st.success(f"'{new_topic.strip()}' added to blacklist.")
                st.rerun()
            else:
                st.warning("Please enter a topic to blacklist.")


# ── Veo Panel ──────────────────────────────────────────────────────────────────

def render_veo_panel(entry: dict, channel: str) -> None:
    """Render the full Veo assistant panel for a single pending veo entry."""
    from shared.db import update_veo_status
    from shared.uploader import upload_short
    import tempfile, subprocess, os
    from pathlib import Path

    ch_name  = "TrendByte Shorts" if channel.upper() == "A" else "Rhymie Kids"
    ch_color = "#f7931a" if channel.upper() == "A" else "#a78bfa"

    st.markdown(f"### 🎬 Veo Entry — <span style='color:{ch_color}'>{ch_name}</span>", unsafe_allow_html=True)
    st.caption(f"Topic: **{entry['topic']}** · Created: {entry['created_at'][:10]}")

    # ── Step tracker ──────────────────────────────────────────────────────────
    status = entry.get("status", "pending")
    steps = [
        ("Script generated",   True),
        ("Veo prompt copied",  True),
        ("Veo video uploaded", status in ("downloaded", "uploaded")),
        ("Audio merged",       status == "uploaded"),
        ("Uploaded to YouTube", status == "uploaded"),
    ]
    st.markdown("#### Pipeline steps")
    for label, done in steps:
        dot_class = "done" if done else "waiting"
        st.markdown(
            f'<div class="step-row"><div class="step-dot {dot_class}"></div>{label}</div>',
            unsafe_allow_html=True,
        )

    st.divider()

    # ── Script + Prompt display ────────────────────────────────────────────────
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**📝 Auto Script (TTS)**")
        st.code(entry["script"], language=None)
    with col2:
        st.markdown("**🎨 Veo Prompt**")
        st.code(entry["veo_prompt"], language=None)

    st.divider()

    # ── Video upload + merge ───────────────────────────────────────────────────
    st.markdown("**Step 1 — Upload your Veo-generated MP4**")
    uploaded_file = st.file_uploader(
        "Upload Veo MP4",
        type=["mp4"],
        key=f"veo_upload_{entry['id']}",
        label_visibility="collapsed",
    )

    if uploaded_file:
        update_veo_status(entry["id"], "downloaded")

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as vf:
            vf.write(uploaded_file.read())
            veo_path = vf.name

        st.success("✅ Veo video received.")
        st.markdown("**Step 2 — Merge TTS audio + upload to YouTube**")

        voiceover_key = f"veo_voice_{entry['id']}"
        if st.button("🔀 Merge Audio & Upload to YouTube", key=voiceover_key):
            with st.spinner("Generating TTS voiceover..."):
                from shared.tts import generate_voiceover
                import channel_a.config as cfg_a
                import channel_b.config as cfg_b
                cfg = cfg_a if channel.upper() == "A" else cfg_b

                voice_path = Path(tempfile.mktemp(suffix=".mp3"))
                generate_voiceover(entry["script"], cfg.TTS_VOICE, str(voice_path))

            with st.spinner("Merging audio into video with FFmpeg..."):
                merged = Path(tempfile.mktemp(suffix=".mp4"))
                cmd = [
                    "ffmpeg", "-y",
                    "-i", veo_path,
                    "-i", str(voice_path),
                    "-map", "0:v:0", "-map", "1:a:0",
                    "-c:v", "copy", "-c:a", "aac",
                    "-shortest", str(merged),
                ]
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode != 0:
                    st.error(f"FFmpeg failed: {result.stderr[:500]}")
                    return

            with st.spinner("Uploading to YouTube..."):
                from channel_a.config import TITLE_FORMAT as title_a, DESCRIPTION_TEMPLATE as desc_a
                from channel_b.config import TITLE_FORMAT as title_b, DESCRIPTION_TEMPLATE as desc_b
                from channel_a.config import YOUTUBE_CATEGORY_ID as cat_a
                from channel_b.config import YOUTUBE_CATEGORY_ID as cat_b

                title_fmt  = title_a  if channel.upper() == "A" else title_b
                desc_fmt   = desc_a   if channel.upper() == "A" else desc_b
                cat_id     = cat_a    if channel.upper() == "A" else cat_b

                title = title_fmt.format(topic=entry["topic"]) + " (Veo)"
                desc  = desc_fmt.format(topic=entry["topic"])

                try:
                    yt_id = upload_short(
                        video_path=merged,
                        title=title,
                        description=desc,
                        category_id=int(cat_id),
                        channel_label=channel,
                        privacy="private",
                    )
                    update_veo_status(entry["id"], "uploaded")
                    st.success(f"🎉 Uploaded! [Watch on YouTube](https://youtu.be/{yt_id})")
                    st.balloons()
                except Exception as exc:
                    st.error(f"Upload failed: {exc}")

            # Cleanup temp files
            for p in [veo_path, str(voice_path), str(merged)]:
                try:
                    os.unlink(p)
                except OSError:
                    pass


# ── Schedule countdown ─────────────────────────────────────────────────────────

def render_schedule_countdown(channel: str) -> str:
    """Return a human-readable string for the next scheduled run."""
    from datetime import datetime, timezone
    now_utc = datetime.now(timezone.utc)
    hour = now_utc.hour

    schedules = {
        "a": [8, 18],
        "b": [7, 16],
    }
    run_hours = schedules.get(channel.lower(), [8])

    next_hours = [h for h in run_hours if h > hour]
    if next_hours:
        next_h = next_hours[0]
        wait_h = next_h - hour
        return f"Next run in ~{wait_h}h (at {next_h:02d}:00 UTC)"
    else:
        # After last run of the day
        next_h = run_hours[0]
        wait_h = 24 - hour + next_h
        return f"Next run in ~{wait_h}h (tomorrow at {next_h:02d}:00 UTC)"
