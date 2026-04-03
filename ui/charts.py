"""Chart builder functions and shared Plotly layout constants."""

import plotly.graph_objects as go

# ── Color palette ─────────────────────────────────────────────────────────────
COLORS = [
    "#3b82f6", "#22d3ee", "#f59e0b", "#10b981", "#f43f5e",
    "#60a5fa", "#34d399", "#fb923c", "#818cf8", "#e879f9",
    "#facc15", "#4ade80", "#f472b6", "#38bdf8", "#fb7185",
    "#a3e635", "#93c5fd", "#fbbf24",
]

_BG = "rgba(0,0,0,0)"  # transparent — CSS gradient on container handles it
_PLOT_BG = "#1b1e2e"
_GRID = dict(gridcolor="rgba(59,130,246,0.06)", zeroline=False)

_LAYOUT = dict(
    paper_bgcolor=_BG,
    plot_bgcolor=_PLOT_BG,
    font_color="#e2e8f0",
    height=310,
    margin=dict(t=78, b=20, l=42, r=16),
    showlegend=False,
)


def _title(text: str, subtitle: str) -> dict:
    """Build a Plotly title dict with subtitle using the native API (Plotly ≥ 5.14)."""
    return dict(
        text=text,
        font=dict(size=13, color="#e2e8f0"),
        subtitle=dict(
            text=subtitle,
            font=dict(size=10, color="#64748b"),
        ),
        x=0.02,
        xanchor="left",
        # y / yanchor intentionally omitted → Plotly auto-positions within margin
    )


# ── Chart builders ────────────────────────────────────────────────────────────

def pie(labels, values, text, subtitle) -> go.Figure:
    """Pie chart — percent on slices, full label+value on hover."""
    fig = go.Figure(go.Pie(
        labels=labels, values=values,
        marker_colors=COLORS,
        hovertemplate="%{label}: %{value} (%{percent})<extra></extra>",
        textinfo="percent",
        textposition="inside",
        textfont_size=9,
        insidetextorientation="radial",
    ))
    fig.update_layout(
        title=_title(text, subtitle),
        uniformtext=dict(minsize=9, mode="hide"),
        **_LAYOUT,
    )
    return fig


def bar_h(labels, values, text, subtitle) -> go.Figure:
    """Horizontal bar chart."""
    fig = go.Figure(go.Bar(
        x=values, y=labels, orientation="h",
        marker_color=COLORS[0],
        hovertemplate="%{x}<extra></extra>",
    ))
    fig.update_layout(
        title=_title(text, subtitle),
        xaxis=_GRID,
        yaxis=dict(**_GRID, tickfont=dict(size=9)),
        **_LAYOUT,
    )
    return fig


def grouped_bar(days, opened, closed, text, subtitle) -> go.Figure:
    """Grouped bar chart comparing two series (e.g. opened vs closed)."""
    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Criados", x=days, y=opened,
        marker_color=COLORS[0],
        hovertemplate="%{y}<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        name="Resolvidos", x=days, y=closed,
        marker_color="#22c55e",
        hovertemplate="%{y}<extra></extra>",
    ))
    fig.update_layout(
        barmode="group",
        title=_title(text, subtitle),
        xaxis=dict(**_GRID, tickfont=dict(size=8), tickangle=45),
        yaxis=_GRID,
        showlegend=True,
        legend=dict(
            font=dict(color="#94a3b8", size=9),
            bgcolor="rgba(0,0,0,0)",
            orientation="h",
            x=0.5, xanchor="center",
            y=-0.22, yanchor="top",
        ),
        margin=dict(t=78, b=48, l=42, r=16),
        paper_bgcolor=_BG, plot_bgcolor=_PLOT_BG, font_color="#e2e8f0", height=310,
    )
    return fig


def line(days, values, text, subtitle) -> go.Figure:
    """Line chart with markers."""
    fig = go.Figure(go.Scatter(
        x=days, y=values,
        mode="lines+markers",
        line_color=COLORS[1],
        marker=dict(size=4),
        hovertemplate="%{y}<extra></extra>",
    ))
    fig.update_layout(
        title=_title(text, subtitle),
        xaxis=dict(**_GRID, tickfont=dict(size=8), tickangle=45),
        yaxis=_GRID,
        **_LAYOUT,
    )
    return fig


def donut(labels, values, colors, text, subtitle) -> go.Figure:
    """Donut chart — percent on slices, full label+value on hover."""
    fig = go.Figure(go.Pie(
        labels=labels, values=values,
        hole=0.5,
        marker_colors=colors or COLORS,
        hovertemplate="%{label}: %{value} (%{percent})<extra></extra>",
        textinfo="percent",
        textposition="inside",
        textfont_size=9,
        insidetextorientation="radial",
    ))
    fig.update_layout(
        title=_title(text, subtitle),
        uniformtext=dict(minsize=9, mode="hide"),
        **_LAYOUT,
    )
    return fig


def bar_v(labels, values, colors, text, subtitle, yrange=None) -> go.Figure:
    """Vertical bar chart with optional y-axis range."""
    fig = go.Figure(go.Bar(
        x=labels, y=values,
        marker_color=colors,
        hovertemplate="%{y}<extra></extra>",
    ))
    yax = dict(**_GRID)
    if yrange:
        yax["range"] = yrange
    fig.update_layout(
        title=_title(text, subtitle),
        xaxis=_GRID,
        yaxis=yax,
        **_LAYOUT,
    )
    return fig


def csat_bar(labels, avgs, text, subtitle) -> go.Figure:
    """Bar chart for CSAT scores, coloured green/amber/red by threshold."""
    colors = [
        "#10b981" if v >= 4.5 else "#f59e0b" if v >= 3.5 else "#f43f5e"
        for v in avgs
    ]
    fig = go.Figure(go.Bar(
        x=labels, y=avgs,
        marker_color=colors,
        hovertemplate="CSAT: %{y:.1f}<extra></extra>",
    ))
    fig.update_layout(
        title=_title(text, subtitle),
        xaxis=_GRID,
        yaxis=dict(**_GRID, range=[0, 5.5]),
        **_LAYOUT,
    )
    return fig
