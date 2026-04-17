from __future__ import annotations

import json
from uuid import uuid4

import streamlit as st


def render_pgn_viewer(
    pgn: str,
    size: int = 560,
    orientation: str = "white",
    board_theme: str = "blue",
    initial_ply: int | str = "last",
) -> None:
    viewer_id = f"lpv-{uuid4().hex}"
    safe_pgn = json.dumps(pgn)
    safe_orientation = "black" if orientation == "black" else "white"
    safe_theme = board_theme if board_theme in {"blue", "green", "brown"} else "blue"
    safe_initial_ply: int | str
    if isinstance(initial_ply, int) and initial_ply >= 0:
        safe_initial_ply = initial_ply
    else:
        safe_initial_ply = "last"

    initial_ply_js = json.dumps(safe_initial_ply)

    # Uses the official lichess-org/pgn-viewer package for move tree, controls,
    # and board playback UI.
    html_payload = f"""
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@lichess-org/pgn-viewer@2.6.0/dist/lichess-pgn-viewer.css" />

        <style>
            #{viewer_id} {{ width: min({size + 180}px, 100%); }}
            #{viewer_id} .lpv__board {{ width: {size}px; max-width: 100%; }}

            #{viewer_id}.theme-blue cg-board square.light {{ background: #d8e3ef; }}
            #{viewer_id}.theme-blue cg-board square.dark {{ background: #7b96b2; }}

            #{viewer_id}.theme-green cg-board square.light {{ background: #e2eadf; }}
            #{viewer_id}.theme-green cg-board square.dark {{ background: #6f8f5f; }}

            #{viewer_id}.theme-brown cg-board square.light {{ background: #f0d9b5; }}
            #{viewer_id}.theme-brown cg-board square.dark {{ background: #b58863; }}
        </style>

        <div id="{viewer_id}" class="theme-{safe_theme}"></div>

        <script nomodule>
            document.getElementById('{viewer_id}').innerHTML = '<p>Modern chess viewer requires module-enabled browser support.</p>';
        </script>

        <script type="module">
            import LichessPgnViewer from 'https://cdn.jsdelivr.net/npm/@lichess-org/pgn-viewer@2.6.0/+esm';

            const target = document.getElementById('{viewer_id}');
            const pgn = {safe_pgn};

            LichessPgnViewer(target, {{
                pgn,
                orientation: '{safe_orientation}',
                showClocks: false,
                showMoves: 'auto',
                scrollToMove: true,
                initialPly: {initial_ply_js},
            }});
        </script>
        """

    st.components.v1.html(html_payload, height=size + 220)
