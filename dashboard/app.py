"""
dashboard/app.py — Ventures Dashboard main Streamlit application.

Run with:
    streamlit run dashboard/app.py

Tabs:
    Overview    — KPI cards, recent activity, error banner
    Channel A   — TrendByte Shorts history, stats, trigger, blacklist
    Channel B   — Rhymie Kids history, stats, trigger, blacklist
    Veo Studio  — Manual Veo workflow (upload MP4 → merge audio → publish)
"""

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

# ── Path setup (allow imports from project root) ──────────────────────────────
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

# ── Page config (must be first Streamlit call) ────────────────────────────────
st.set_page_config(
    page_title="Ventures Dashboard",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

from dashboard.styles import DASHBOARD_CSS
from dashboard.components import (
    render_kpi_card,
    render_upload_table,
    render_blacklist_editor,
    render_veo_panel,
    render_schedule_countdown,
    status_badge,
    channel_badge,
)
from dashboard.github_trigger import trigger_workflow, get_recent_runs
from shared.db import (
    init_db,
    get_today_uploads,
    get_upload_history,
    get_pending_veo,
)

# ── Inject CSS ────────────────────────────────────────────────────────────────
st.markdown(DASHBOARD_CSS, unsafe_allow_html=True)

# ── Init DB ───────────────────────────────────────────────────────────────────
init_db()


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<div class="ventures-logo">⚡ Ventures</div>', unsafe_allow_html=True)
    st.markdown('<div class="ventures-version">v1.0 · YouTube Shorts Automation</div>', unsafe_allow_html=True)
    st.divider()

    # Channel status dots
    today_a = get_today_uploads("A")
    today_b = get_today_uploads("B")
    success_a = sum(1 for u in today_a if u["status"] == "success")
    success_b = sum(1 for u in today_b if u["status"] == "success")

    st.markdown(
        f"""
        <div style="font-size:0.8rem; color: var(--text-secondary); margin-bottom:1rem;">
            <div style="margin-bottom:0.3rem;">
                <span style="color:{'var(--success)' if success_a > 0 else 'var(--text-muted)'}">●</span>
                &nbsp;<b style="color:var(--accent-a)">TrendByte</b> — {success_a} today
            </div>
            <div>
                <span style="color:{'var(--success)' if success_b > 0 else 'var(--text-muted)'}">●</span>
                &nbsp;<b style="color:var(--accent-b)">Rhymie Kids</b> — {success_b} today
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    page = st.radio(
        "Navigation",
        ["📊 Overview", "🔥 Channel A", "🌈 Channel B", "🎬 Veo Studio"],
        label_visibility="collapsed",
    )
    st.divider()
    st.caption("Local dashboard — reads from `data/ventures.db`")


# ─────────────────────────────────────────────────────────────────────────────
# PAGE: OVERVIEW
# ─────────────────────────────────────────────────────────────────────────────
if page == "📊 Overview":
    st.markdown("## 📊 Overview")
    st.caption(f"Last refreshed: {datetime.now(timezone.utc).strftime('%H:%M UTC')}")

    # ── Error banner ──────────────────────────────────────────────────────────
    all_today = get_today_uploads()
    failures = [u for u in all_today if u["status"] == "failed"]
    if failures:
        st.markdown(
            f'<div class="error-banner">⚠️ {len(failures)} pipeline failure(s) detected today. '
            'Check GitHub Actions logs for details.</div>',
            unsafe_allow_html=True,
        )

    # ── KPI Cards ─────────────────────────────────────────────────────────────
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        render_kpi_card("TrendByte — Today", str(success_a), "uploads successful", "channel-a")
    with col2:
        render_kpi_card("Rhymie Kids — Today", str(success_b), "uploads successful", "channel-b")

    # 7-day totals
    history_7 = get_upload_history(days=7)
    total_7   = sum(1 for u in history_7 if u["status"] == "success")
    fail_7    = sum(1 for u in history_7 if u["status"] == "failed")
    rate_7    = f"{round(total_7 / max(total_7 + fail_7, 1) * 100)}%" if history_7 else "—"

    with col3:
        render_kpi_card("Success Rate (7d)", rate_7, f"{total_7} successful / {fail_7} failed", "neutral")
    with col4:
        pending_veo = len(get_pending_veo())
        render_kpi_card("Veo Queue", str(pending_veo), "videos pending manual upload", "neutral")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Next scheduled runs ───────────────────────────────────────────────────
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown('<div class="section-header">⏱ Channel A Schedule</div>', unsafe_allow_html=True)
        st.caption(render_schedule_countdown("a"))
        st.caption("Runs: 08:00 & 18:00 UTC daily")
    with col_b:
        st.markdown('<div class="section-header">⏱ Channel B Schedule</div>', unsafe_allow_html=True)
        st.caption(render_schedule_countdown("b"))
        st.caption("Runs: 07:00 & 16:00 UTC daily")

    st.divider()

    # ── Recent activity ───────────────────────────────────────────────────────
    st.markdown('<div class="section-header">📋 Recent Uploads (Last 7 days)</div>', unsafe_allow_html=True)
    render_upload_table(history_7[:20])

    # ── GitHub Actions runs ───────────────────────────────────────────────────
    if os.environ.get("GITHUB_PAT"):
        st.divider()
        st.markdown('<div class="section-header">🔧 Recent GitHub Actions Runs</div>', unsafe_allow_html=True)
        col_ra, col_rb = st.columns(2)
        with col_ra:
            st.markdown(f"**Channel A** · [View all →](https://github.com/nitinbs24/Shorts-Generator/actions/workflows/channel_a.yml)")
            runs_a = get_recent_runs("a", limit=3)
            for r in runs_a:
                icon = "✅" if r["conclusion"] == "success" else ("❌" if r["conclusion"] == "failure" else "⟳")
                st.markdown(f"{icon} [{r['created_at'][:16]}]({r['html_url']}) — {r['status']}")
        with col_rb:
            st.markdown(f"**Channel B** · [View all →](https://github.com/nitinbs24/Shorts-Generator/actions/workflows/channel_b.yml)")
            runs_b = get_recent_runs("b", limit=3)
            for r in runs_b:
                icon = "✅" if r["conclusion"] == "success" else ("❌" if r["conclusion"] == "failure" else "⟳")
                st.markdown(f"{icon} [{r['created_at'][:16]}]({r['html_url']}) — {r['status']}")


# ─────────────────────────────────────────────────────────────────────────────
# CHANNEL PAGE (shared logic for A and B)
# ─────────────────────────────────────────────────────────────────────────────
def render_channel_page(channel: str) -> None:
    ch_label  = "A"  if channel == "a" else "B"
    ch_name   = "TrendByte Shorts" if channel == "a" else "Rhymie Kids"
    ch_color  = "#f7931a" if channel == "a" else "#a78bfa"
    ch_class  = "channel-a" if channel == "a" else "channel-b"
    ch_emoji  = "🔥" if channel == "a" else "🌈"

    st.markdown(
        f"## {ch_emoji} Channel {ch_label} — "
        f"<span style='color:{ch_color}'>{ch_name}</span>",
        unsafe_allow_html=True,
    )

    # ── Mini KPI row ──────────────────────────────────────────────────────────
    history_30 = get_upload_history(channel=ch_label, days=30)
    total_all  = get_upload_history(channel=ch_label)
    success_30 = sum(1 for u in history_30 if u["status"] == "success")
    fail_30    = sum(1 for u in history_30 if u["status"] == "failed")
    rate_30    = f"{round(success_30 / max(success_30 + fail_30, 1) * 100)}%"
    today_up   = get_today_uploads(ch_label)
    last_ok    = next((u for u in history_30 if u["status"] == "success"), None)
    last_ok_dt = last_ok["created_at"][:16] if last_ok else "Never"

    col1, col2, col3 = st.columns(3)
    with col1:
        render_kpi_card("Total Uploads (30d)", str(success_30), f"{fail_30} failed", ch_class)
    with col2:
        render_kpi_card("Success Rate (30d)", rate_30, "", ch_class)
    with col3:
        render_kpi_card("Last Successful Run", last_ok_dt, "", ch_class)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Manual trigger ────────────────────────────────────────────────────────
    st.markdown('<div class="section-header">🚀 Manual Trigger</div>', unsafe_allow_html=True)
    col_t1, col_t2 = st.columns([1, 3])
    with col_t1:
        if st.button(f"▶ Run Channel {ch_label} Now", key=f"trigger_{channel}"):
            ok, msg = trigger_workflow(channel)
            if ok:
                st.success(msg)
            else:
                st.error(msg)
    with col_t2:
        st.caption(render_schedule_countdown(channel))

    st.divider()

    # ── Filters ───────────────────────────────────────────────────────────────
    st.markdown('<div class="section-header">📋 Upload History</div>', unsafe_allow_html=True)
    col_f1, col_f2 = st.columns([1, 1])
    with col_f1:
        mode_filter = st.radio("Mode", ["All", "Auto", "Veo"], horizontal=True, key=f"mode_{channel}")
    with col_f2:
        day_filter = st.selectbox("Period", [7, 14, 30, 90], index=2, key=f"days_{channel}",
                                  format_func=lambda x: f"Last {x} days")

    filtered = get_upload_history(
        channel=ch_label,
        days=int(day_filter),
        mode=mode_filter.lower() if mode_filter != "All" else None,
    )
    render_upload_table(filtered)

    st.divider()

    # ── Blacklist editor ──────────────────────────────────────────────────────
    render_blacklist_editor(ch_label)


if page == "🔥 Channel A":
    render_channel_page("a")

elif page == "🌈 Channel B":
    render_channel_page("b")


# ─────────────────────────────────────────────────────────────────────────────
# PAGE: VEO STUDIO
# ─────────────────────────────────────────────────────────────────────────────
elif page == "🎬 Veo Studio":
    st.markdown("## 🎬 Veo Studio")
    st.caption("Complete the manual Veo workflow: generate video in Google Veo, upload here, merge TTS audio, and publish.")

    pending = get_pending_veo()

    if not pending:
        st.info("✅ No pending Veo entries. The pipeline will generate new entries on the next scheduled run.")
    else:
        # Group by channel
        ch_a_entries = [e for e in pending if e["channel"] == "A"]
        ch_b_entries = [e for e in pending if e["channel"] == "B"]

        tabs = []
        if ch_a_entries:
            tabs.append("🔥 TrendByte Shorts")
        if ch_b_entries:
            tabs.append("🌈 Rhymie Kids")

        if len(tabs) > 1:
            selected_tab = st.tabs(tabs)
            if ch_a_entries:
                with selected_tab[0]:
                    render_veo_panel(ch_a_entries[0], "a")
            if ch_b_entries:
                with selected_tab[-1]:
                    render_veo_panel(ch_b_entries[0], "b")
        elif ch_a_entries:
            render_veo_panel(ch_a_entries[0], "a")
        elif ch_b_entries:
            render_veo_panel(ch_b_entries[0], "b")

        if len(pending) > 1:
            st.divider()
            st.caption(f"Showing 1 entry per channel. {len(pending) - 1} more entries in queue.")

    st.divider()
    st.markdown('<div class="section-header">ℹ️ Veo Workflow Guide</div>', unsafe_allow_html=True)
    with st.expander("How to use Veo Studio", expanded=False):
        st.markdown("""
        1. **Copy the Veo Prompt** from the panel above
        2. Go to **[Google Veo](https://aitestkitchen.withgoogle.com/tools/video-fx)** and generate a video using the prompt
        3. Download the generated MP4 from Veo
        4. Come back here and **upload the MP4** in the file uploader above
        5. Click **"Merge Audio & Upload"** — the dashboard will:
           - Generate the TTS voiceover from the script
           - Merge the audio into the Veo video using FFmpeg
           - Upload the final video to YouTube as **Private**
        6. Go to YouTube Studio to review and **publish** when ready
        """)
