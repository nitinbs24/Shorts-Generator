"""
dashboard/styles.py — Design token system and custom CSS for the Ventures Dashboard.

Injected via st.markdown(DASHBOARD_CSS, unsafe_allow_html=True) in app.py.
"""

DASHBOARD_CSS = """
<style>
/* ── Google Fonts ─────────────────────────────────────────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

/* ── Design Tokens ────────────────────────────────────────────────────────── */
:root {
    --bg-primary:     #0d1117;
    --bg-secondary:   #161b22;
    --bg-card:        #1c2230;
    --bg-hover:       #21293a;
    --border:         #30363d;
    --border-focus:   #58a6ff;

    --text-primary:   #e6edf3;
    --text-secondary: #8b949e;
    --text-muted:     #6e7681;

    --accent-a:       #f7931a;   /* TrendByte — orange */
    --accent-a-dim:   rgba(247,147,26,0.15);
    --accent-b:       #a78bfa;   /* Rhymie Kids — purple */
    --accent-b-dim:   rgba(167,139,250,0.15);
    --accent-blue:    #58a6ff;

    --success:        #3fb950;
    --success-dim:    rgba(63,185,80,0.15);
    --warning:        #d29922;
    --warning-dim:    rgba(210,153,34,0.15);
    --error:          #f85149;
    --error-dim:      rgba(248,81,73,0.15);

    --radius:         10px;
    --radius-sm:      6px;
    --shadow:         0 4px 24px rgba(0,0,0,0.4);
}

/* ── Global ───────────────────────────────────────────────────────────────── */
html, body, [class*="css"] {
    font-family: 'Inter', sans-serif !important;
    background-color: var(--bg-primary) !important;
    color: var(--text-primary) !important;
}
.stApp { background-color: var(--bg-primary); }

/* ── Sidebar ──────────────────────────────────────────────────────────────── */
[data-testid="stSidebar"] {
    background-color: var(--bg-secondary) !important;
    border-right: 1px solid var(--border) !important;
    padding-top: 1rem;
}
[data-testid="stSidebar"] .stRadio label {
    font-size: 0.9rem;
    color: var(--text-secondary);
    padding: 0.4rem 0.8rem;
    border-radius: var(--radius-sm);
    transition: all 0.15s ease;
}
[data-testid="stSidebar"] .stRadio label:hover {
    background: var(--bg-hover);
    color: var(--text-primary);
}

/* ── Logo / Brand ─────────────────────────────────────────────────────────── */
.ventures-logo {
    font-size: 1.6rem;
    font-weight: 700;
    letter-spacing: -0.5px;
    background: linear-gradient(135deg, var(--accent-a), var(--accent-b));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 0.2rem;
}
.ventures-version {
    font-size: 0.72rem;
    color: var(--text-muted);
    font-family: 'JetBrains Mono', monospace;
}

/* ── KPI Cards ────────────────────────────────────────────────────────────── */
.kpi-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 1.2rem 1.4rem;
    box-shadow: var(--shadow);
    transition: transform 0.2s ease, box-shadow 0.2s ease;
    position: relative;
    overflow: hidden;
}
.kpi-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 32px rgba(0,0,0,0.5);
}
.kpi-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
}
.kpi-card.channel-a::before { background: var(--accent-a); }
.kpi-card.channel-b::before { background: var(--accent-b); }
.kpi-card.neutral::before   { background: var(--accent-blue); }
.kpi-label { font-size: 0.78rem; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 0.5rem; }
.kpi-value { font-size: 2rem; font-weight: 700; color: var(--text-primary); line-height: 1; }
.kpi-sub   { font-size: 0.78rem; color: var(--text-muted); margin-top: 0.4rem; }

/* ── Status Badges ────────────────────────────────────────────────────────── */
.badge {
    display: inline-block;
    padding: 0.2em 0.7em;
    border-radius: 999px;
    font-size: 0.72rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
}
.badge-success  { background: var(--success-dim);  color: var(--success); }
.badge-pending  { background: var(--warning-dim);  color: var(--warning); }
.badge-failed   { background: var(--error-dim);    color: var(--error); }
.badge-a        { background: var(--accent-a-dim); color: var(--accent-a); }
.badge-b        { background: var(--accent-b-dim); color: var(--accent-b); }

/* ── Section Headers ──────────────────────────────────────────────────────── */
.section-header {
    font-size: 0.78rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--text-muted);
    border-bottom: 1px solid var(--border);
    padding-bottom: 0.5rem;
    margin-bottom: 1rem;
}

/* ── Error Banner ─────────────────────────────────────────────────────────── */
.error-banner {
    background: var(--error-dim);
    border: 1px solid var(--error);
    border-radius: var(--radius);
    padding: 0.9rem 1.2rem;
    color: var(--error);
    font-size: 0.88rem;
    margin-bottom: 1rem;
}

/* ── Veo Step Tracker ─────────────────────────────────────────────────────── */
.step-row {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    font-size: 0.85rem;
    padding: 0.35rem 0;
    color: var(--text-secondary);
}
.step-dot {
    width: 10px; height: 10px;
    border-radius: 50%;
    flex-shrink: 0;
}
.step-dot.done    { background: var(--success); }
.step-dot.active  { background: var(--warning); box-shadow: 0 0 0 3px var(--warning-dim); }
.step-dot.waiting { background: var(--bg-hover); border: 1px solid var(--border); }

/* ── Tables ───────────────────────────────────────────────────────────────── */
[data-testid="stDataFrame"] {
    border-radius: var(--radius);
    overflow: hidden;
    border: 1px solid var(--border) !important;
}

/* ── Buttons ──────────────────────────────────────────────────────────────── */
.stButton > button {
    background: var(--accent-blue) !important;
    color: var(--bg-primary) !important;
    border: none !important;
    border-radius: var(--radius-sm) !important;
    font-weight: 600 !important;
    padding: 0.5rem 1.4rem !important;
    transition: opacity 0.2s ease !important;
}
.stButton > button:hover { opacity: 0.85 !important; }

/* ── Inputs ───────────────────────────────────────────────────────────────── */
.stTextInput > div > div > input,
.stTextArea textarea {
    background: var(--bg-card) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius-sm) !important;
    color: var(--text-primary) !important;
}
.stTextInput > div > div > input:focus,
.stTextArea textarea:focus {
    border-color: var(--border-focus) !important;
    box-shadow: 0 0 0 2px rgba(88,166,255,0.15) !important;
}

/* ── Code / Script blocks ─────────────────────────────────────────────────── */
.stCode, .stCodeBlock {
    background: var(--bg-card) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius) !important;
    font-family: 'JetBrains Mono', monospace !important;
}

/* ── Hide Streamlit chrome ────────────────────────────────────────────────── */
#MainMenu, footer, [data-testid="stToolbar"] { visibility: hidden; }
</style>
"""
