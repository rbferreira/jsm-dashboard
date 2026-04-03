"""Dashboard global CSS — injected once at startup via inject_styles()."""

import streamlit as st

# Accent: #3b82f6 (blue-500)  Shadow accent: rgba(59,130,246,*)
_CSS = """
<style>
/* ── Hide Streamlit chrome ─────────────────────────────────────────────── */
[data-testid="stToolbar"]       { display: none !important; }
[data-testid="stDecoration"]    { display: none !important; }
[data-testid="stStatusWidget"]  { display: none !important; }
[data-testid="stSidebar"]       { display: none !important; }
[data-testid="collapsedControl"]{ display: none !important; }

/* ── Page breathing room ───────────────────────────────────────────────── */
.block-container {
    padding-top: 2rem !important;
    padding-bottom: 0.5rem !important;
    overflow: visible !important;
}

/* ── Chart cards ───────────────────────────────────────────────────────── */
[data-testid="stPlotlyChart"] {
    background: linear-gradient(145deg, #1e2235 0%, #181b28 100%);
    border: 1px solid rgba(59, 130, 246, 0.1);
    border-radius: 14px;
    padding: 0 !important;
    overflow: hidden !important;
    box-shadow:
        0 4px 20px rgba(0, 0, 0, 0.3),
        0 1px 3px rgba(0, 0, 0, 0.15),
        inset 0 1px 0 rgba(255, 255, 255, 0.03);
    transition: box-shadow 0.25s ease, transform 0.25s ease;
}
[data-testid="stPlotlyChart"]:hover {
    box-shadow:
        0 8px 32px rgba(59, 130, 246, 0.12),
        0 2px 6px rgba(0, 0, 0, 0.25),
        inset 0 1px 0 rgba(255, 255, 255, 0.05);
    transform: translateY(-2px);
}
[data-testid="stPlotlyChart"] > div {
    overflow: hidden !important;
}

/* ── Period pill radio buttons ─────────────────────────────────────────── */
div[data-testid="stRadio"] > div {
    flex-direction: row !important;
    gap: 3px !important;
    background: linear-gradient(145deg, #1e2235 0%, #1a1d2e 100%);
    padding: 3px !important;
    border-radius: 10px;
    width: fit-content;
    box-shadow:
        0 2px 8px rgba(0, 0, 0, 0.2),
        inset 0 1px 0 rgba(255, 255, 255, 0.03);
}
div[data-testid="stRadio"] label {
    padding: 5px 14px !important;
    border-radius: 7px !important;
    color: #94a3b8 !important;
    font-size: 0.85rem !important;
    cursor: pointer;
    transition: all 0.2s ease;
    margin-bottom: 0 !important;
}
div[data-testid="stRadio"] label:hover {
    color: #cbd5e1 !important;
    background: rgba(59, 130, 246, 0.06) !important;
}
div[data-testid="stRadio"] label:has(input:checked) {
    background: linear-gradient(135deg, #2563eb 0%, #3b82f6 100%) !important;
    color: #ffffff !important;
    box-shadow: 0 2px 8px rgba(59, 130, 246, 0.3);
}
div[data-testid="stRadio"] input[type="radio"] { display: none !important; }
div[data-testid="stRadio"] > label              { display: none !important; }

/* ── Selectbox ─────────────────────────────────────────────────────────── */
div[data-testid="stSelectbox"] > label { display: none !important; }
div[data-testid="stSelectbox"] > div > div {
    background: linear-gradient(145deg, #1e2235 0%, #1a1d2e 100%) !important;
    border-color: rgba(59, 130, 246, 0.1) !important;
    border-radius: 10px !important;
    min-height: 36px !important;
    color: #e2e8f0 !important;
    font-size: 0.85rem !important;
    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.15);
    transition: border-color 0.2s ease, box-shadow 0.2s ease;
}
div[data-testid="stSelectbox"] > div > div:hover {
    border-color: rgba(59, 130, 246, 0.25) !important;
}

/* ── Date input — match overall theme ──────────────────────────────────── */
div[data-testid="stDateInput"] > label {
    font-size: 0.8rem !important;
    color: #94a3b8 !important;
}
div[data-testid="stDateInput"] > div > div > input {
    background: linear-gradient(145deg, #1e2235 0%, #1a1d2e 100%) !important;
    border-color: rgba(59, 130, 246, 0.1) !important;
    border-radius: 10px !important;
    color: #e2e8f0 !important;
    font-size: 0.85rem !important;
    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.15);
}

/* ── Refresh button — blue pill style like selected radio ──────────────── */
div[data-testid="stButton"] > button {
    background: linear-gradient(135deg, #2563eb 0%, #3b82f6 100%) !important;
    border: none !important;
    border-radius: 7px !important;
    color: #ffffff !important;
    font-size: 0.85rem !important;
    height: 34px;
    box-shadow: 0 2px 8px rgba(59, 130, 246, 0.3);
    transition: all 0.2s ease;
}
div[data-testid="stButton"] > button:hover {
    box-shadow: 0 4px 14px rgba(59, 130, 246, 0.4);
    transform: translateY(-1px);
}
div[data-testid="stButton"] > button:active {
    transform: translateY(0px) scale(0.97);
}

/* ── Tabs — subtle glow on active ──────────────────────────────────────── */
[data-testid="stTabs"] button {
    transition: all 0.2s ease;
}
[data-testid="stTabs"] button[aria-selected="true"] {
    text-shadow: 0 0 10px rgba(59, 130, 246, 0.35);
}

/* ── Divider ───────────────────────────────────────────────────────────── */
hr {
    border-color: rgba(59, 130, 246, 0.08) !important;
    margin: 0.6rem 0 !important;
}

</style>
"""


def inject_styles() -> None:
    """Inject the dashboard global CSS into the Streamlit page."""
    st.markdown(_CSS, unsafe_allow_html=True)
