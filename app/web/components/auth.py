from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import streamlit as st

from app.config import get_settings
from app.services.auth_service import AuthService, AuthUser


AUTH_USER_ID_KEY = "auth_user_id"
AUTH_TOKEN_KEY = "auth_token"
AUTH_COOKIE_NAME = "woodland_auth"


def require_auth() -> AuthUser | None:
    """Render auth controls and return current user when auth is enabled."""
    settings = get_settings()
    if not settings.auth_enabled:
        return None

    service = AuthService()
    service.bootstrap_admin_if_needed()

    # Hydrate auth state from signed browser cookie.
    # st.context.cookies reads from the HTTP request headers at session start —
    # synchronous and available immediately on the first script run of any new
    # session, including URL-navigated sessions (new tab, new window, link clicks).
    if AUTH_USER_ID_KEY not in st.session_state:
        cookie_token = st.context.cookies.get(AUTH_COOKIE_NAME)
        if cookie_token:
            user_from_cookie = service.verify_login_token(str(cookie_token))
            if user_from_cookie is not None:
                st.session_state[AUTH_USER_ID_KEY] = user_from_cookie.id
                st.session_state[AUTH_TOKEN_KEY] = str(cookie_token)

    user = _current_user(service)
    if user is not None:
        token = st.session_state.get(AUTH_TOKEN_KEY)
        if not token:
            token = service.create_login_token(user.id)
            st.session_state[AUTH_TOKEN_KEY] = token
        _set_auth_cookie(str(token), int(settings.auth_token_ttl_seconds))
        _render_logged_in_sidebar(service, user)
        return user

    _render_login_sidebar(service)
    st.warning("Sign in to continue.")
    st.stop()


def _current_user(service: AuthService) -> AuthUser | None:
    user_id = st.session_state.get(AUTH_USER_ID_KEY)
    if user_id is None:
        return None
    user = service.get_user(int(user_id))
    if user is None:
        st.session_state.pop(AUTH_USER_ID_KEY, None)
    return user


def _render_login_sidebar(service: AuthService) -> None:
    with st.sidebar:
        st.subheader("Sign In")
        with st.form("login_form", clear_on_submit=False):
            email = st.text_input("Email", key="login_email")
            password = st.text_input("Password", type="password", key="login_password")
            submitted = st.form_submit_button("Sign In", use_container_width=True)

        if submitted:
            user = service.authenticate(email, password)
            if user is None:
                st.error("Invalid email or password.")
            else:
                st.session_state[AUTH_USER_ID_KEY] = user.id
                token = service.create_login_token(user.id)
                st.session_state[AUTH_TOKEN_KEY] = token
                _set_auth_cookie(token, int(get_settings().auth_token_ttl_seconds))
                st.rerun()


def _render_logged_in_sidebar(service: AuthService, user: AuthUser) -> None:
    with st.sidebar:
        st.caption(f"Signed in as {user.email} ({user.role})")
        if st.button("Sign Out", use_container_width=True):
            st.session_state.pop(AUTH_USER_ID_KEY, None)
            st.session_state.pop(AUTH_TOKEN_KEY, None)
            _clear_auth_cookie()
            st.rerun()

        if user.role == "admin":
            st.markdown("---")
            st.subheader("Invite Member")
            with st.form("create_member_form", clear_on_submit=True):
                new_email = st.text_input("Email", key="create_member_email")
                new_password = st.text_input("Temporary password", type="password", key="create_member_password")
                role = st.selectbox("Role", ["member", "admin"], index=0, key="create_member_role")
                create_submitted = st.form_submit_button("Create User", use_container_width=True)

            if create_submitted:
                try:
                    created = service.create_user(new_email, new_password, role=role)
                    st.success(f"Created user: {created.email} ({created.role})")
                except ValueError as exc:
                    st.error(str(exc))


def _set_auth_cookie(token: str, ttl_seconds: int) -> None:
    expires = (datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)).strftime(
        "%a, %d %b %Y %H:%M:%S GMT"
    )
    # Use json.dumps to safely encode the cookie string — prevents any injection.
    cookie_str = f"{AUTH_COOKIE_NAME}={token}; expires={expires}; path=/; SameSite=Lax"
    st.html(f"<script>document.cookie = {json.dumps(cookie_str)};</script>")


def _clear_auth_cookie() -> None:
    cookie_str = f"{AUTH_COOKIE_NAME}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/; SameSite=Lax"
    st.html(f"<script>document.cookie = {json.dumps(cookie_str)};</script>")
