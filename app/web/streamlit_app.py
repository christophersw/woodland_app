import streamlit as st

from app.config import get_settings
from app.services.auth_service import AuthService
from app.storage.database import init_db
from app.web.components.auth import (
    is_authenticated,
    login_page,
    logout_page,
    render_admin_sidebar,
)


def main() -> None:
    st.set_page_config(page_title="Woodland Chess", page_icon="♟", layout="wide")
    init_db()

    settings = get_settings()
    if settings.auth_enabled:
        AuthService().bootstrap_admin_if_needed()

    # Always register all pages so that direct URL navigation (e.g. from
    # LinkColumn clicks opening a new tab) resolves correctly. Auth is enforced
    # inside each page via require_auth(), not by hiding pages from the router.
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

    authenticated = not settings.auth_enabled or is_authenticated()

    if settings.auth_enabled:
        if authenticated:
            _logout = st.Page(logout_page, title="Sign Out", icon="🚪", url_path="logout")
            pages: dict | list = {
                "": [history_page, analysis_page, search_page],
                "Account": [_logout],
            }
        else:
            _login = st.Page(login_page, title="Sign In", icon="🔑", url_path="login")
            pages = {
                "": [history_page, analysis_page, search_page],
                "Account": [_login],
            }
    else:
        pages = [history_page, analysis_page, search_page]

    nav = st.navigation(pages, position="sidebar")
    render_admin_sidebar()
    nav.run()
