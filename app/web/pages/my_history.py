import pandas as pd
import streamlit as st

from app.config import get_settings
from app.ingest.sync_service import ChessComSyncService
from app.services.history_service import HistoryFilters, HistoryService
from app.services.time_control import format_time_control
from app.web.components.auth import require_auth
from app.web.components.charts import elo_trend_chart, opening_pie_chart

require_auth()

settings = get_settings()
service = HistoryService()
sync_service = ChessComSyncService()

st.title("My History")
st.caption("Track rating trend, recent games, and opening usage.")

players = service.list_players()
default_player = players[0] if players else ""

with st.expander("Chess.com Sync", expanded=False):
    configured_usernames = settings.chess_usernames()
    st.write("Configured usernames:", ", ".join(configured_usernames) if configured_usernames else "none")
    if st.button("Sync configured users now", disabled=not configured_usernames):
        results = []
        overall = st.progress(0, text="Preparing sync...")
        total_users = len(configured_usernames)

        for idx, username in enumerate(configured_usernames, start=1):
            user_progress = st.progress(0, text=f"{username}: preparing archives...")

            def progress_callback(cb_username: str, current: int, total: int, stats):
                if total <= 0:
                    user_progress.progress(
                        100,
                        text=f"{cb_username}: no archives in scope (inserted={stats.inserted}, updated={stats.updated})",
                    )
                    return

                pct = int((current / total) * 100)
                user_progress.progress(
                    pct,
                    text=(
                        f"{cb_username}: archive {current}/{total} "
                        f"(inserted={stats.inserted}, updated={stats.updated})"
                    ),
                )

            result = sync_service.sync_player(username, progress_callback=progress_callback)
            results.append(result)

            overall.progress(
                int((idx / total_users) * 100),
                text=f"Completed {idx}/{total_users} users",
            )

        for result in results:
            st.success(
                f"{result.username}: archives={result.archives_scanned}, inserted={result.inserted}, updated={result.updated}"
            )
        players = service.list_players()
        default_player = players[0] if players else ""

if not players:
    st.warning("No players available yet. Configure CHESS_COM_USERNAMES and run sync.")
    st.stop()

c1, c2, c3 = st.columns([2, 1, 1])
with c1:
    selected_player = st.selectbox("Player", players, index=0)
with c2:
    lookback_days = st.selectbox("Lookback", [30, 60, 90, 180], index=2)
with c3:
    recent_limit = st.selectbox("Recent games", [10, 20, 30, 50], index=1)

filters = HistoryFilters(player=selected_player or default_player, lookback_days=lookback_days, recent_limit=recent_limit)

elo_df = service.get_elo_timeseries(filters)
recent_df = service.get_recent_games_with_eval(filters)
opening_df = service.get_opening_distribution(filters, moves_depth=5)

status_a, status_b, status_c = st.columns(3)
status_a.metric("Players Compared", len(players))
status_b.metric("Recent Games", len(recent_df))
status_c.metric("Openings Tracked", len(opening_df))

if settings.database_url:
    st.caption("Data source: configured database")
else:
    st.caption("Data source: local SQLite (woodland_chess.db)")

st.plotly_chart(elo_trend_chart(elo_df, filters.player), width='stretch', config={"displaylogo": False, "plotlyServerURL": ""})

left, right = st.columns([1.6, 1])
with left:
    st.subheader("Recent Games")
    if recent_df.empty:
        st.info("No recent games found for this filter.")
    else:
        display_df = recent_df.copy()
        if "time_control" in display_df.columns:
            display_df["time_control"] = display_df["time_control"].apply(format_time_control)
        cols = ["played_at", "opponent", "color", "result", "time_control", "stockfish_cp", "game_id"]
        display_cols = [c for c in cols if c in display_df.columns]

        header_cols = st.columns([*([1] * len(display_cols)), 1.2])
        for idx, col_name in enumerate(display_cols):
            if col_name == "game_id":
                continue
            header_cols[idx].markdown(f"**{col_name.replace('_', ' ').title()}**")
        header_cols[-1].markdown("**Open**")

        for row_idx, row in display_df.reset_index(drop=True).iterrows():
            row_cols = st.columns([*([1] * len(display_cols)), 1.2])
            for col_idx, col_name in enumerate(display_cols):
                if col_name == "game_id":
                    continue
                value = row.get(col_name, "")
                row_cols[col_idx].write("" if pd.isna(value) else str(value))

            game_id = row.get("game_id", "")
            can_open = pd.notna(game_id) and str(game_id).strip() != ""
            if row_cols[-1].button(
                "Open in Analysis",
                key=f"history_open_{row_idx}",
                width='content',
                disabled=not can_open,
            ):
                st.session_state["pending_game_id"] = str(game_id)
                st.switch_page("app/web/pages/game_analysis.py")

with right:
    st.plotly_chart(opening_pie_chart(opening_df), width='stretch', config={"displaylogo": False, "plotlyServerURL": ""})

st.caption("Use Open in Analysis on any row to open that game.")
