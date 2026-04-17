"""Game Search page — AI-powered and keyword search with board preview."""

from __future__ import annotations

import io
import urllib.parse

import chess.pgn
import chess.svg
import json
import pandas as pd
from sqlalchemy import select
import streamlit as st

from app.services.game_search_service import (
    SearchPlanError,
    execute_sql_search,
    generate_search_plan,
    get_anthropic_model,
    is_anthropic_available,
    keyword_game_search,
)
from app.services.time_control import format_time_control
from app.storage.database import get_session
from app.storage.models import Game
from app.services.opening_book import opening_at_each_ply
from app.web.components.charts import opening_starburst_chart

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VISIBLE_COLUMNS = {
    "white_username", "black_username", "lichess_opening", "result_pgn", "load_game",
    "player", "opponent", "result", "opening",
}


def _column_config(df: pd.DataFrame) -> dict:
    cfg: dict = {
        "load_game": st.column_config.LinkColumn("Game", display_text="Load Game"),
    }
    for col in df.columns:
        if col not in VISIBLE_COLUMNS:
            cfg[col] = None
    return cfg


def _ensure_pgn(df: pd.DataFrame) -> pd.DataFrame:
    """Fill in pgn column from DB where missing."""
    if "game_id" not in df.columns:
        return df
    working = df.copy()
    if "pgn" not in working.columns:
        working["pgn"] = ""

    missing_mask = working["pgn"].fillna("").astype(str).str.strip() == ""
    missing_ids = working.loc[missing_mask, "game_id"].dropna().unique().tolist()
    if not missing_ids:
        return working

    with get_session() as session:
        rows = session.execute(
            select(Game.id, Game.pgn).where(Game.id.in_([str(g) for g in missing_ids]))
        ).all()
    db_map = {r.id: (r.pgn or "") for r in rows}

    for idx in working.index:
        if missing_mask.at[idx]:
            working.at[idx, "pgn"] = db_map.get(working.at[idx, "game_id"], "")

    return working


def _ensure_opening_plies(df: pd.DataFrame, depth: int = 5) -> pd.DataFrame:
    """Add opening_ply_1..depth columns, fetching from DB or parsing PGN."""
    ply_cols = [f"opening_ply_{i}" for i in range(1, depth + 1)]
    working = df.copy()
    for col in ply_cols:
        if col not in working.columns:
            working[col] = None

    # Fetch from DB when game_ids are available.
    if "game_id" in working.columns:
        need_mask = working["opening_ply_1"].isna() | (
            working["opening_ply_1"].astype(str).str.strip() == ""
        )
        ids = working.loc[need_mask, "game_id"].dropna().unique().tolist()
        if ids:
            with get_session() as session:
                rows = session.execute(
                    select(
                        Game.id,
                        Game.opening_ply_1, Game.opening_ply_2,
                        Game.opening_ply_3, Game.opening_ply_4,
                        Game.opening_ply_5,
                    ).where(Game.id.in_([str(g) for g in ids]))
                ).all()
            db_map = {r.id: r for r in rows}
            for idx in working.index:
                if not need_mask.at[idx]:
                    continue
                gid = str(working.at[idx, "game_id"])
                db_row = db_map.get(gid)
                if db_row:
                    for col in ply_cols:
                        val = getattr(db_row, col, None)
                        if val:
                            working.at[idx, col] = val

    # Parse PGN as fallback.
    if "pgn" in working.columns:
        for idx in working.index:
            if pd.notna(working.at[idx, "opening_ply_1"]) and str(
                working.at[idx, "opening_ply_1"]
            ).strip():
                continue
            pgn_text = str(working.at[idx, "pgn"] or "").strip()
            if not pgn_text:
                continue
            game = chess.pgn.read_game(io.StringIO(pgn_text))
            if game is None:
                continue
            board = game.board()
            for ply_i, move in enumerate(game.mainline_moves(), 1):
                if ply_i > depth:
                    break
                working.at[idx, f"opening_ply_{ply_i}"] = board.san(move)
                board.push(move)

    return working


def _board_animation_html(pgn_text: str, max_ply: int = 10, interval_ms: int = 700) -> str:
    """Return self-contained HTML that animates the first max_ply half-moves frame by frame."""
    pgn_text = str(pgn_text or "").strip()
    if not pgn_text:
        return ""
    game = chess.pgn.read_game(io.StringIO(pgn_text))
    if game is None:
        return ""
    board = game.board()
    frames: list[str] = [chess.svg.board(board, size=360)]  # starting position
    last_move = None
    for i, move in enumerate(game.mainline_moves(), start=1):
        last_move = move
        board.push(move)
        frames.append(chess.svg.board(board, lastmove=last_move, size=360))
        if i >= max_ply:
            break
    if len(frames) <= 1:
        return frames[0] if frames else ""

    # Get opening names for each ply from the Lichess book.
    ply_names = opening_at_each_ply(pgn_text, max_ply=max_ply)
    # Pad to match frame count if needed.
    while len(ply_names) < len(frames):
        ply_names.append(ply_names[-1] if ply_names else ("", "Starting Position"))

    frames_json = json.dumps(frames)
    labels_json = json.dumps([f"{eco} {name}".strip() for eco, name in ply_names])
    total = len(frames)
    return f"""
<style>
  #chess-anim {{ width: 360px; font-family: sans-serif; }}
  #board-frame svg {{ display: block; }}
  #anim-controls {{ margin-top: 8px; display: flex; gap: 8px; align-items: center; }}
  #btn-pp {{ padding: 3px 12px; cursor: pointer; font-size: 14px; }}
  #frame-label {{ font-size: 12px; color: #555; }}
  #anim-scrubber {{ flex: 1; cursor: pointer; }}
  #opening-label {{ margin-top: 4px; font-size: 13px; font-weight: 600; color: #333; min-height: 20px; }}
</style>
<div id="chess-anim">
  <div id="board-frame"></div>
  <div id="opening-label"></div>
  <div id="anim-controls">
    <button id="btn-pp" onclick="togglePlay()">&#9646;&#9646; Pause</button>
    <input id="anim-scrubber" type="range" min="0" max="{total - 1}" value="0"
           oninput="scrub(this.value)" />
    <span id="frame-label">Start</span>
  </div>
</div>
<script>
  const frames = {frames_json};
  const labels = {labels_json};
  let idx = 0, playing = true;
  let timer = setInterval(advance, {interval_ms});

  function render() {{
    document.getElementById('board-frame').innerHTML = frames[idx];
    document.getElementById('anim-scrubber').value = idx;
    document.getElementById('frame-label').textContent = idx === 0 ? 'Start' : 'Ply ' + idx;
    document.getElementById('opening-label').textContent = labels[idx] || '';
  }}

  function advance() {{
    idx = (idx + 1) % frames.length;
    render();
  }}

  function scrub(val) {{
    idx = parseInt(val);
    render();
  }}

  function togglePlay() {{
    playing = !playing;
    const btn = document.getElementById('btn-pp');
    if (playing) {{
      timer = setInterval(advance, {interval_ms});
      btn.innerHTML = '&#9646;&#9646; Pause';
    }} else {{
      clearInterval(timer);
      btn.innerHTML = '&#9654; Play';
    }}
  }}

  render();
</script>
"""


# ---------------------------------------------------------------------------
# Render results with board preview
# ---------------------------------------------------------------------------

def _render_results(results_df: pd.DataFrame) -> None:
    if results_df.empty:
        st.info("No games matched.")
        return

    enriched = _ensure_pgn(results_df)
    enriched = _ensure_opening_plies(enriched)

    # Prepare display table
    table_df = enriched.copy()
    if "time_control" in table_df.columns:
        table_df["time_control"] = table_df["time_control"].apply(format_time_control)
    if "game_id" in table_df.columns:
        table_df["load_game"] = table_df["game_id"].apply(
            lambda g: "/game-analysis?" + urllib.parse.urlencode({"game_id": g})
        )

    st.markdown("---")

    # Two-column layout: results table (left, wider) + board preview (right)
    table_col, board_col = st.columns([2, 1])

    with table_col:
        st.markdown("### Results")
        st.caption(f"Showing {len(enriched)} games. Click a row to preview.")
        table_event = st.dataframe(
            table_df,
            use_container_width=True,
            hide_index=True,
            column_config=_column_config(table_df),
            on_select="rerun",
            selection_mode="single-row",
            key="results_table",
        )

    # Determine which row was selected
    selected_row_idx = None
    if table_event and table_event.selection and table_event.selection.rows:
        selected_row_idx = table_event.selection.rows[0]

    with board_col:
        st.markdown("### Board Preview")
        if selected_row_idx is not None and selected_row_idx < len(enriched):
            row = enriched.iloc[selected_row_idx]
            pgn_text = str(row.get("pgn", ""))

            # Show game info
            opening = str(row.get("lichess_opening", row.get("opening", "")))
            white = str(row.get("white_username", ""))
            black = str(row.get("black_username", ""))
            result = str(row.get("result_pgn", row.get("result", "")))
            if opening:
                st.caption(f"**{opening}**")
            st.caption(f"{white} vs {black} — {result}")

            anim_html = _board_animation_html(pgn_text, max_ply=10, interval_ms=700)
            if anim_html:
                st.components.v1.html(anim_html, height=430)
            else:
                st.info("No PGN available for this game.")
        else:
            st.info("Select a row to preview its opening position.")

    # --- Starburst chart ---
    st.markdown("### Opening Star-burst")
    fig = opening_starburst_chart(enriched, depth=5)
    if fig is not None:
        st.plotly_chart(
            fig, use_container_width=True,
            config={"displaylogo": False, "plotlyServerURL": ""},
        )
    else:
        st.info("Not enough PGN data to build starburst.")


# ---------------------------------------------------------------------------
# Page layout
# ---------------------------------------------------------------------------

st.title("Game Search")
st.caption("Search your games and preview openings.")

anthropic_available = is_anthropic_available()
if anthropic_available:
    st.success(f"AI SQL parsing enabled ({get_anthropic_model()}).")
    search_mode = st.radio("Search mode", ["AI-Powered Search", "Keyword Search"], horizontal=True)
else:
    st.warning("ANTHROPIC_API_KEY not configured. Keyword search only.")
    search_mode = "Keyword Search"

# ---- AI-Powered Search ----
if search_mode == "AI-Powered Search":
    st.markdown("### AI-Powered Search")
    st.caption("Describe the games you want. The app converts it into validated SQL.")

    with st.form("ai_search_form", clear_on_submit=False):
        query = st.text_input(
            "Search Query",
            key="ai_search_query",
            placeholder="e.g., last 30 days losses as black in sicilian openings",
            label_visibility="collapsed",
        )
        submitted = st.form_submit_button("Search", use_container_width=True)

    if submitted and query.strip():
        try:
            with st.spinner("Generating and executing SQL..."):
                plan = generate_search_plan(query)
                rows = execute_sql_search(plan.sql_query)
            st.session_state["ai_results"] = rows
            st.session_state["ai_sql"] = plan.sql_query
            st.session_state["ai_reasoning"] = plan.reasoning
            st.session_state.pop("ai_error", None)
        except SearchPlanError as exc:
            st.session_state["ai_error"] = str(exc)
            st.session_state["ai_results"] = []
            st.session_state["ai_sql"] = exc.candidate_sql
            st.session_state["ai_reasoning"] = exc.reasoning
        except Exception as exc:
            st.session_state["ai_error"] = str(exc)
            st.session_state["ai_results"] = []

    if st.session_state.get("ai_reasoning"):
        st.caption(f"Reasoning: {st.session_state['ai_reasoning']}")
    if st.session_state.get("ai_sql"):
        st.code(st.session_state["ai_sql"], language="sql")
    if st.session_state.get("ai_error"):
        st.error(st.session_state["ai_error"])

    saved_rows = st.session_state.get("ai_results", [])
    if saved_rows:
        df = pd.DataFrame(saved_rows)
        if "id" in df.columns:
            df = df.rename(columns={"id": "game_id"})
        _render_results(df)
    elif st.session_state.get("ai_search_query") and not st.session_state.get("ai_error"):
        st.info("No games matched that query.")

# ---- Keyword Search ----
else:
    st.markdown("### Keyword Search")
    with st.form("keyword_search_form", clear_on_submit=False):
        keyword = st.text_input(
            "Keyword",
            key="kw_search_query",
            placeholder="e.g., sicilian, 15+10, win, opponent name",
            label_visibility="collapsed",
        )
        submitted = st.form_submit_button("Search", use_container_width=True)

    if submitted and keyword.strip():
        result_df = keyword_game_search(keyword.strip(), limit=200)
        st.session_state["kw_results"] = result_df.to_dict(orient="records")
        st.session_state.pop("kw_error", None)

    saved_kw = st.session_state.get("kw_results", [])
    if saved_kw:
        _render_results(pd.DataFrame(saved_kw))
    elif st.session_state.get("kw_search_query") and not st.session_state.get("kw_error"):
        st.info("No games matched that keyword.")
