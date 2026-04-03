"""Reusable UI helper functions (pure Python / HTML — no Streamlit imports)."""

from math import floor


def top_n(d: dict, n: int = 12) -> dict:
    """Return the top-n items by value, collapsing the rest into 'Outros'."""
    items = sorted(d.items(), key=lambda x: x[1], reverse=True)
    if len(items) <= n:
        return dict(items)
    top = dict(items[:n])
    outros = sum(v for _, v in items[n:])
    if outros:
        top["Outros"] = outros
    return top


def trunc(s: str, n: int = 20) -> str:
    """Truncate a string to at most n characters, appending an ellipsis if cut."""
    return s if len(s) <= n else s[:n] + "\u2026"


def render_stars(avg: float) -> str:
    """Return an HTML star-rating string for a 0–5 average score."""
    full = floor(avg)
    half = 1 if (avg - full) >= 0.25 else 0
    empty = 5 - full - half
    fs = '<span style="color:#f59e0b">\u2605</span>'
    es = '<span style="color:#374151">\u2605</span>'
    hs = (
        '<span style="position:relative;display:inline-block">'
        '<span style="color:#374151">\u2605</span>'
        '<span style="position:absolute;left:0;top:0;overflow:hidden;width:50%;color:#f59e0b">\u2605</span>'
        "</span>"
    )
    return fs * full + (hs if half else "") + es * empty


def kpi_card(label: str, value: str, color: str = "#e2e8f0", extra: str = "") -> str:
    """Return an HTML string for a single KPI metric card."""
    extra_html = (
        f'<div style="font-size:0.72rem;color:#94a3b8;margin-top:auto">{extra}</div>'
        if extra
        else ""
    )
    return (
        f'<div style="'
        f"background:linear-gradient(145deg, #1e2235 0%, #181b28 100%);"
        f"border:1px solid rgba(59,130,246,0.1);"
        f"border-radius:14px;"
        f"padding:1rem 1.25rem;"
        f"min-width:0;overflow:hidden;"
        f"display:flex;flex-direction:column;"
        f"height:110px;box-sizing:border-box;"
        f"box-shadow:0 4px 20px rgba(0,0,0,0.25), 0 1px 3px rgba(0,0,0,0.12), inset 0 1px 0 rgba(255,255,255,0.03);"
        f"transition:box-shadow 0.25s ease, transform 0.25s ease;"
        f'">'
        f'<div style="font-size:0.7rem;color:#94a3b8;text-transform:uppercase;'
        f'letter-spacing:0.6px;margin-bottom:0.4rem;line-height:1.3">{label}</div>'
        f'<div style="font-size:1.9rem;font-weight:700;line-height:1;color:{color};'
        f'text-shadow:0 0 12px {color}1a">{value}</div>'
        f"{extra_html}"
        f"</div>"
    )


def col_toggle_html(current: int = 4) -> str:
    """Return HTML for the 3/4 column layout toggle buttons."""
    cls3 = "col-btn active" if current == 3 else "col-btn"
    cls4 = "col-btn active" if current == 4 else "col-btn"
    return (
        '<div class="col-toggle-wrap">'
        '<div class="col-toggle-bg">'
        f'<span class="{cls3}" id="col-3">▦ 3 col</span>'
        f'<span class="{cls4}" id="col-4">▦ 4 col</span>'
        '</div>'
        '</div>'
    )
