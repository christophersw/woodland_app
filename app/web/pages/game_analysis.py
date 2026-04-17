import streamlit as st

from app.services.analysis_service import AnalysisService
from app.web.components.charts import eval_timeline_chart
from app.web.components.game_board import render_svg_game_viewer


service = AnalysisService()

st.title("Game Analysis")
st.caption("Full-game SVG board with best-move arrows and eval chart.")

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

meta_a, meta_b, meta_c = st.columns(3)
meta_a.metric("Game ID", analysis.game_id)
meta_b.metric("Players", f"{analysis.white} vs {analysis.black}")
meta_c.metric("Result", analysis.result)

left, right = st.columns([1.1, 1])
with left:
    st.subheader("Board")
    render_svg_game_viewer(
        analysis.pgn,
        moves_df=analysis.moves,
        size=560,
        orientation="white",
        initial_ply="last",
    )

with right:
    st.subheader("Evaluation")
    st.plotly_chart(
        eval_timeline_chart(analysis.moves),
        use_container_width=True,
        key=f"eval_chart_{analysis.game_id}",
        config={"displaylogo": False, "plotlyServerURL": ""},
    )
