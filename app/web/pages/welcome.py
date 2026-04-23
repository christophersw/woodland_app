"""Welcome tab — ELO trends, best recent games, and best games ever."""

from __future__ import annotations

from datetime import datetime, timedelta
from html import escape

import pandas as pd
import streamlit as st

from app.services.welcome_service import WelcomeService
from app.web.components.auth import require_auth
from app.web.components.charts import welcome_elo_chart

require_auth()

_service = WelcomeService()

# ── Helpers ──────────────────────────────────────────────────────────────────


def _fmt_accuracy(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:.1f}%"


def _fmt_acpl(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:.1f}"


def _fmt_wdl(win: float | None, draw: float | None, loss: float | None) -> str:
    if win is None or draw is None or loss is None:
        return "—"
    return f"W {win * 100:.0f}% · D {draw * 100:.0f}% · L {loss * 100:.0f}%"


def _open_link(game_id: str) -> str:
    safe_id = escape(str(game_id))
    return f"/game-analysis?game_id={safe_id}"


def _is_recent(played_at: object, days: int = 7) -> bool:
    cutoff = datetime.utcnow() - timedelta(days=days)
    if isinstance(played_at, pd.Timestamp):
        ts = played_at
        # Strip tz so comparison is always naive
        if ts.tzinfo is not None:
            ts = ts.tz_convert("UTC").tz_localize(None)
        return ts >= pd.Timestamp(cutoff)
    if isinstance(played_at, datetime):
        naive = played_at.replace(tzinfo=None) if played_at.tzinfo is not None else played_at
        return naive >= cutoff
    return False


# ── ELO metric cards ─────────────────────────────────────────────────────────


def _render_elo_metrics(elo_df: pd.DataFrame) -> None:
    """Show current ELO + 7-day delta for each club player."""
    cutoff_recent = pd.Timestamp(datetime.utcnow() - timedelta(days=7))
    players = sorted(elo_df["player"].unique())
    cols = st.columns(max(len(players), 1))
    for col, player in zip(cols, players):
        pdata = elo_df[elo_df["player"] == player].sort_values("date")
        current_rating = pdata["rating"].iloc[-1] if not pdata.empty else None
        old_data = pdata[pdata["date"] < cutoff_recent]
        old_rating = old_data["rating"].iloc[-1] if not old_data.empty else None
        delta: float | None = None
        if current_rating is not None and old_rating is not None:
            delta = current_rating - old_rating
        with col:
            st.metric(
                label=player,
                value=f"{int(current_rating)}" if current_rating is not None else "—",
                delta=f"{int(delta):+d}" if delta is not None else None,
                delta_color="normal",
            )


# ── Game tables ───────────────────────────────────────────────────────────────


_TABLE_CSS = """
<style>
.wc-table {
  width: 100%;
  border-collapse: collapse;
  font-family: 'EB Garamond', Georgia, serif;
  font-size: 0.95rem;
}
.wc-table thead tr {
  background: #EDE0C4;
  border-bottom: 2px solid #B8962E;
}
.wc-table thead th {
  font-family: 'DM Mono', monospace;
  font-size: 0.7rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #1E3D2F;
  padding: 0.55rem 0.75rem;
  text-align: left;
}
.wc-table tbody tr {
  border-bottom: 1px solid #EDE0C4;
  transition: background 0.15s;
}
.wc-table tbody tr:hover {
  background: rgba(245, 237, 216, 0.55);
}
.wc-table tbody tr.wc-recent {
  background: rgba(193, 127, 36, 0.12);
  border-left: 3px solid #C17F24;
}
.wc-table tbody tr.wc-recent:hover {
  background: rgba(193, 127, 36, 0.22);
}
.wc-table td {
  padding: 0.48rem 0.75rem;
  color: #1C1C1C;
  vertical-align: middle;
}
.wc-rank {
  font-family: 'DM Mono', monospace;
  font-size: 0.78rem;
  color: #7B4F2E;
  font-weight: 600;
}
.wc-acc {
  font-family: 'DM Mono', monospace;
  font-size: 0.88rem;
  font-weight: 700;
  color: #1E3D2F;
}
.wc-acpl {
  font-family: 'DM Mono', monospace;
  font-size: 0.88rem;
  font-weight: 700;
  color: #3A5C45;
}
.wc-wdl {
  font-family: 'DM Mono', monospace;
  font-size: 0.72rem;
  color: #4A4A4A;
}
.wc-date {
  font-family: 'DM Mono', monospace;
  font-size: 0.72rem;
  color: #7B4F2E;
}
.wc-badge-recent {
  display: inline-block;
  background: #C17F24;
  color: #FDFCFB;
  font-family: 'DM Mono', monospace;
  font-size: 0.6rem;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  border-radius: 3px;
  padding: 1px 5px;
  margin-left: 5px;
  vertical-align: middle;
}
.wc-open-btn {
  display: inline-block;
  border: 1px solid #B8962E;
  color: #1E3D2F;
  font-family: 'DM Mono', monospace;
  font-size: 0.68rem;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  border-radius: 3px;
  padding: 3px 10px;
  text-decoration: none;
  white-space: nowrap;
  transition: background 0.15s, color 0.15s;
}
.wc-open-btn:hover {
  background: #1C1C1C;
  color: #F5EDD8;
  border-color: #1C1C1C;
  text-decoration: none;
}
</style>
"""


def _accuracy_table_html(df: pd.DataFrame) -> str:
    rows_html = []
    for rank, (_, row) in enumerate(df.iterrows(), start=1):
        white = escape(str(row["white"]))
        black = escape(str(row["black"]))
        avg_acc = _fmt_accuracy(row.get("avg_accuracy"))
        w_acc = _fmt_accuracy(row.get("white_accuracy"))
        b_acc = _fmt_accuracy(row.get("black_accuracy"))
        wdl = _fmt_wdl(row.get("wdl_win"), row.get("wdl_draw"), row.get("wdl_loss"))
        played = row.get("played_at")
        date_str = played.strftime("%d %b %Y") if hasattr(played, "strftime") else str(played)[:10]
        link = _open_link(row["game_id"])
        rows_html.append(
            f"<tr>"
            f'<td class="wc-rank">#{rank}</td>'
            f"<td>&#9651; {white}</td>"
            f"<td>&#9650; {black}</td>"
            f'<td class="wc-acc">{avg_acc}</td>'
            f'<td class="wc-acc">{w_acc} / {b_acc}</td>'
            f'<td class="wc-wdl">{wdl}</td>'
            f'<td class="wc-date">{escape(date_str)}</td>'
            f'<td><a class="wc-open-btn" href="{link}" target="_blank">Open ↗</a></td>'
            f"</tr>"
        )
    header = (
        "<thead><tr>"
        "<th>#</th><th>White</th><th>Black</th>"
        "<th>Avg Acc</th><th>W / B Acc</th>"
        "<th>Avg WDL</th><th>Date</th><th></th>"
        "</tr></thead>"
    )
    return (
        _TABLE_CSS
        + f'<table class="wc-table">{header}<tbody>'
        + "".join(rows_html)
        + "</tbody></table>"
    )


def _acpl_table_html(df: pd.DataFrame, highlight_recent: bool = True) -> str:
    rows_html = []
    for rank, (_, row) in enumerate(df.iterrows(), start=1):
        white = escape(str(row["white"]))
        black = escape(str(row["black"]))
        avg_acpl = _fmt_acpl(row.get("avg_acpl"))
        w_acpl = _fmt_acpl(row.get("white_acpl"))
        b_acpl = _fmt_acpl(row.get("black_acpl"))
        avg_acc = _fmt_accuracy(
            (row["white_accuracy"] + row["black_accuracy"]) / 2
            if row.get("white_accuracy") is not None and row.get("black_accuracy") is not None
            else None
        )
        wdl = _fmt_wdl(row.get("wdl_win"), row.get("wdl_draw"), row.get("wdl_loss"))
        played = row.get("played_at")
        date_str = played.strftime("%d %b %Y") if hasattr(played, "strftime") else str(played)[:10]
        link = _open_link(row["game_id"])
        recent = highlight_recent and _is_recent(played)
        row_class = "wc-recent" if recent else ""
        recent_badge = '<span class="wc-badge-recent">New</span>' if recent else ""
        rows_html.append(
            f'<tr class="{row_class}">'
            f'<td class="wc-rank">#{rank}</td>'
            f"<td>&#9651; {white}</td>"
            f"<td>&#9650; {black}</td>"
            f'<td class="wc-acpl">{avg_acpl}</td>'
            f'<td class="wc-acpl">{w_acpl} / {b_acpl}</td>'
            f'<td class="wc-acc">{avg_acc}</td>'
            f'<td class="wc-wdl">{wdl}</td>'
            f'<td class="wc-date">{escape(date_str)}{recent_badge}</td>'
            f'<td><a class="wc-open-btn" href="{link}" target="_blank">Open ↗</a></td>'
            f"</tr>"
        )
    header = (
        "<thead><tr>"
        "<th>#</th><th>White</th><th>Black</th>"
        "<th>Avg ACPL</th><th>W / B ACPL</th>"
        "<th>Avg Acc</th><th>Avg WDL</th><th>Date</th><th></th>"
        "</tr></thead>"
    )
    return (
        _TABLE_CSS
        + f'<table class="wc-table">{header}<tbody>'
        + "".join(rows_html)
        + "</tbody></table>"
    )


# ── Page ──────────────────────────────────────────────────────────────────────

st.title("Woodland Chess Club")
st.caption("Club overview — ELO trends, best played games, and all-time records.")

# ── ELO Trends ───────────────────────────────────────────────────────────────

st.subheader("Member ELO Trends")
elo_df = _service.get_all_players_elo_timeseries(lookback_days=90)

if elo_df.empty:
    st.info("No rating data available yet.")
else:
    _render_elo_metrics(elo_df)
    st.caption("★ Larger dots mark games played in the last 7 days")
    fig = welcome_elo_chart(elo_df, recent_days=7)
    st.plotly_chart(fig, use_container_width=True)

st.divider()

# ── Best Recent Games (by Accuracy) ──────────────────────────────────────────

st.subheader("Best Played Games — Recent")
st.caption("Top 10 games from the last 30 days ranked by combined accuracy (Stockfish).")

recent_df = _service.get_best_recent_games_by_accuracy(limit=10, lookback_days=30)
if recent_df.empty:
    st.info("No analysed games found in the last 30 days.")
else:
    st.markdown(_accuracy_table_html(recent_df), unsafe_allow_html=True)

st.divider()

# ── Best Club Games Ever (by ACPL) ───────────────────────────────────────────

st.subheader("Best Club Games Ever")
st.caption(
    "All-time top 10 games by lowest combined Average Centipawn Loss (ACPL). "
    "Games played in the last 7 days are highlighted."
)

ever_df = _service.get_best_all_time_games_by_acpl(limit=10)
if ever_df.empty:
    st.info("No analysed games found.")
else:
    st.markdown(_acpl_table_html(ever_df, highlight_recent=True), unsafe_allow_html=True)
