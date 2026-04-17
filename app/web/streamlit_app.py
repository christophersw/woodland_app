import streamlit as st

from app.storage.database import init_db
from app.web.components.auth import require_auth


def main() -> None:
    st.set_page_config(page_title="Woodland Chess", page_icon="♟", layout="wide")
    init_db()
    require_auth()

    history_page = st.Page(
        "app/web/pages/my_history.py",
        title="My History",
        icon="📈",
        url_path="my-history",
        default=True,
    )
    analysis_page = st.Page(
        "app/web/pages/game_analysis.py",
        title="Game Analysis",
        icon="🔎",
        url_path="game-analysis",
    )
    search_page = st.Page(
        "app/web/pages/game_search.py",
        title="Game Search",
        icon="🧠",
        url_path="game-search",
    )

    nav = st.navigation([history_page, analysis_page, search_page], position="sidebar")
    nav.run()
