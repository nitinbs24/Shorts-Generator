# 📱 Youtube Shorts Generator

> Dual-channel automated YouTube Shorts at zero recurring cost.

**TrendByte Shorts** (Channel A) · **Rhymie Kids** (Channel B)

---

## Overview

YouTube Shorts Automation Ventures is a fully automated, dual-channel YouTube Shorts publishing system built and operated by a single person. It runs two independent content channels from a single Python monorepo, producing **4 AI-generated Shorts every day** without manual intervention — plus **2 additional premium Shorts** via a guided manual workflow using Gemini Pro's Veo video generation.

The entire infrastructure runs at **£0/month** using free-tier services: GitHub Actions for scheduling, Streamlit Cloud for the dashboard, and free API tiers for Gemini, Pexels, and YouTube.

---

## The Two Channels

### 📺 Channel A — TrendByte Shorts

| Property | Detail |
|---|---|
| **Theme** | Trending news, viral science facts, tech events, pop culture |
| **Audience** | General public, ages 16–35 |
| **Tone** | Punchy, energetic, fast-paced |
| **Script format** | Hook → 3 punchy facts → punchline · under 70 words |
| **Voice** | `en-US-GuyNeural` (energetic) |
| **Video style** | Real stock footage from Pexels · fast cuts |
| **Captions** | Bold white text · word-by-word highlight · centered |
| **Upload schedule** | 8:00 AM UTC and 6:00 PM UTC daily |
| **Topic source** | Google Trends (pytrends) + BBC/Reddit RSS |

### 🧒 Channel B — Rhymie Kids

| Property | Detail |
|---|---|
| **Theme** | Animals, colors, numbers, shapes, nature — evergreen children's topics |
| **Audience** | Children aged 2–8, discovered by parents |
| **Tone** | Warm, playful, repetitive, singalong-friendly |
| **Script format** | AABB rhyme scheme · 4–6 couplets · 8 lines max |
| **Voice** | `en-US-AnaNeural` (child voice) |
| **Video style** | Colorful cartoon-style clips or bright nature footage |
| **Captions** | Large rounded font · rainbow-colored words |
| **Upload schedule** | 7:00 AM UTC and 4:00 PM UTC daily |
| **Topic source** | Local JSON topic bank (100+ topics, rotating daily) |

---

## How It Works

The system runs two parallel tracks each day:

### 🤖 Automated Track (no operator input required)

```
GitHub Actions cron trigger
        │
        ▼
Topic fetched (Trends API / topic bank)
        │
        ▼
Script generated via Gemini 1.5 Pro
        │
        ├── Channel B safety check (Gemini validates age-appropriateness)
        │
        ▼
Text-to-speech voiceover (edge-tts)
        │
        ▼
Stock footage downloaded (Pexels API)
        │
        ▼
Video assembled — 9:16 portrait (MoviePy + FFmpeg)
        │
        ├── Captions transcribed (Whisper) + burned onto video
        │
        ▼
Uploaded to YouTube via Data API v3
        │
        ▼
Run logged to SQLite database
```

### 🎬 Manual Veo Track (~10 minutes/day operator effort)

```
Operator opens Streamlit dashboard
        │
        ▼
Copies today's pre-generated Veo prompt
        │
        ▼
Pastes into Gemini app → generates AI video → downloads MP4
        │
        ▼
Drops MP4 into dashboard upload slot
        │
        ▼
Clicks "Merge Audio" → FFmpeg adds TTS voiceover
        │
        ▼
Clicks "Upload to YouTube" → Short published
```

**Total daily output: 4 automated + 2 Veo = 6 Shorts across both channels.**

---

## Tech Stack

| Component | Technology |
|---|---|
| **Orchestrator** | Python 3.11, argparse |
| **Script generation** | Gemini 1.5 Pro (`google-generativeai`) |
| **Text-to-speech** | `edge-tts` (Microsoft Azure neural voices) |
| **Topic engine (Ch. A)** | `pytrends`, `feedparser` (BBC + Reddit RSS) |
| **Topic engine (Ch. B)** | Local JSON topic bank |
| **Stock footage** | Pexels Video API |
| **Video assembly** | MoviePy 1.0.3, FFmpeg 6.x |
| **Captions** | OpenAI Whisper (local, base model) |
| **Upload** | YouTube Data API v3 (OAuth 2.0) |
| **Database** | SQLite 3 |
| **Dashboard** | Streamlit 1.35+ |
| **Scheduling** | GitHub Actions cron |
| **Secrets** | GitHub Secrets (zero secrets in code) |

---

## Folder Structure

```
Shorts-Generator/
│
├── main.py                        # Orchestrator — python main.py --channel a|b
├── requirements.txt               # All Python dependencies
├── oauth_setup.py                 # One-time YouTube OAuth token generator
├── .env.example                   # Environment variable template
│
├── channel_a/                     # TrendByte Shorts — Channel A module
│   ├── config.py                  # Constants: voice, schedule, title format, category
│   ├── topic_fetcher.py           # pytrends + RSS trending topic engine
│   └── script_gen.py              # Gemini prompt templates for Channel A
│
├── channel_b/                     # Rhymie Kids — Channel B module
│   ├── config.py                  # Constants: voice, schedule, title format, category
│   ├── topic_bank.json            # 100+ rotating children's topics by category
│   └── script_gen.py              # Gemini prompt templates for Channel B
│
├── shared/                        # Shared components used by both channels
│   ├── config.py                  # Shared constants (paths, resolution, audio mix)
│   ├── db.py                      # SQLite schema + all database helper functions
│   ├── retry.py                   # Exponential backoff decorator (tenacity)
│   ├── tts.py                     # edge-tts voiceover wrapper
│   ├── safety.py                  # Gemini content-safety validator (Channel B)
│   ├── footage.py                 # Pexels API clip downloader
│   ├── video_builder.py           # MoviePy + FFmpeg video assembler
│   ├── captions.py                # Whisper transcription + FFmpeg subtitle burn
│   └── uploader.py                # YouTube Data API v3 upload handler
│
├── dashboard/                     # Streamlit management dashboard
│   ├── app.py                     # Main Streamlit application
│   ├── styles.py                  # Custom CSS (design tokens, typography, colours)
│   ├── components.py              # Reusable UI component helpers
│   └── github_trigger.py          # GitHub Actions workflow_dispatch helper
│
├── tests/                         # Unit test suite
│   ├── test_db.py
│   ├── test_topic_fetcher.py
│   ├── test_script_gen.py
│   └── test_safety.py
│
├── data/
│   └── ventures.db                # SQLite database (git-ignored)
│
├── assets/
│   └── music/                     # Royalty-free background MP3s
│
├── docs/
│   ├── PRD.md                     # Product Requirements Document
│   ├── TRD.md                     # Technical Requirements Document
│   ├── UX Brief.md                # UI/UX Design Brief
│   └── Implementation Plan.md    # Phase-wise build plan with checklists
│
└── .github/workflows/
    ├── channel_a.yml              # Cron workflow: 08:00 + 18:00 UTC
    └── channel_b.yml              # Cron workflow: 07:00 + 16:00 UTC
```

---

## Quick Start

```bash
# 1. Clone the repo
git clone https://github.com/[username]/Shorts-Generator.git
cd Shorts-Generator

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Copy and fill in your API keys
cp .env.example .env
# Edit .env with your actual keys

# 4. Initialise the database
python -c "from shared.db import init_db; init_db()"

# 5. Run a dry-run pipeline (no YouTube upload)
python main.py --channel a --dry-run
python main.py --channel b --dry-run

# 6. Run the dashboard locally
streamlit run dashboard/app.py
```

---

## Success Metrics

| Metric | Month 1 Target | Month 3 Target |
|---|---|---|
| Pipeline success rate | > 90% of runs | > 97% of runs |
| Videos published/day | 4 auto + 2 Veo = 6 | 4 auto + 2 Veo = 6 |
| Operator daily time | < 15 min | < 10 min |
| Channel A subscribers | Baseline | > 500 |
| Channel B subscribers | Baseline | > 1,000 |
| Content safety violations (Ch. B) | 0 | 0 |
| Monthly cost | £0 | £0 |

---

*Confidential — Internal Use Only*
