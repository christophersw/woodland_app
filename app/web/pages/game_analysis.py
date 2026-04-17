import streamlit as st

from app.services.analysis_service import AnalysisService
from app.web.components.charts import eval_timeline_chart
from app.web.components.game_board import render_pgn_viewer


service = AnalysisService()

st.title("Game Analysis")
st.caption("UI build: board-v4-lichess-pgn-viewer")

query_params = st.query_params
game_id = query_params.get("game_id", "")

if isinstance(game_id, list):
    game_id = game_id[0] if game_id else ""

if not game_id:
    st.warning("Missing game_id. Open this page with /game-analysis?game_id=<id>.")
    st.stop()

analysis = service.get_game_analysis(game_id)
if analysis is None or analysis.moves.empty:
    st.error("Game analysis not found for the requested game_id.")
    st.stop()

state_key = f"selected_ply_{analysis.game_id}"
if state_key not in st.session_state:
    st.session_state[state_key] = int(analysis.moves["ply"].max())

selected_ply = int(st.session_state[state_key])

meta_a, meta_b, meta_c = st.columns(3)
meta_a.metric("Game ID", analysis.game_id)
meta_b.metric("Players", f"{analysis.white} vs {analysis.black}")
meta_c.metric("Result", analysis.result)

left, right = st.columns([1.1, 1])
with left:
    st.subheader("PGN Viewer")
    render_pgn_viewer(
        analysis.pgn,
        size=560,
        orientation="white",
        board_theme="brown",
        initial_ply=selected_ply,
    )
    st.caption(f"Playback and move tree are powered by lichess-org/pgn-viewer. Current chart-selected ply: {selected_ply}")

with right:
    st.subheader("Evaluation")
    selection = st.plotly_chart(
        eval_timeline_chart(analysis.moves, selected_ply=selected_ply),
        use_container_width=True,
        key=f"eval_chart_{analysis.game_id}",
        on_select="rerun",
        selection_mode=["points"],
        config={"displaylogo": False, "plotlyServerURL": ""},
    )

    points = (selection or {}).get("selection", {}).get("points", [])
    if points:
        clicked_x = points[0].get("x")
        if clicked_x is not None:
            clicked_ply = int(clicked_x)
            if clicked_ply != st.session_state[state_key]:
                st.session_state[state_key] = clicked_ply
                st.rerun()
