import streamlit as st

from app.services.analysis_service import AnalysisService
from app.services.time_control import format_time_control
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

st.subheader(f"{analysis.white} vs {analysis.black} — {analysis.result}")
details_parts = []
if analysis.date:
    details_parts.append(analysis.date)
if analysis.time_control:
    details_parts.append(format_time_control(analysis.time_control))
details_line = " · ".join(details_parts)
if analysis.url:
    details_line += f"  [View on Chess.com]({analysis.url})"
if details_line:
    st.caption(details_line)

# Build eval data for the linked chart
eval_data = None
if "ply" in analysis.moves.columns and "cp_eval" in analysis.moves.columns:
    eval_data = analysis.moves[["ply", "cp_eval"]].to_dict(orient="records")

render_svg_game_viewer(
    analysis.pgn,
    moves_df=analysis.moves,
    size=560,
    orientation="white",
    initial_ply="last",
    eval_data=eval_data,
)
