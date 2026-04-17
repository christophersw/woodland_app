from __future__ import annotations

import io
import json
from uuid import uuid4

import chess
import chess.pgn
import chess.svg
import pandas as pd
import streamlit as st


def render_svg_game_viewer(
    pgn: str,
    moves_df: pd.DataFrame,
    size: int = 560,
    orientation: str = "white",
    initial_ply: int | str = "last",
) -> None:
    """Full-game SVG viewer with play/pause, scrubber, move list, and best-move arrows.

    ``moves_df`` must have columns: ply, san, fen, arrow_uci (UCI of best move).
    """
    viewer_id = f"svg-{uuid4().hex}"
    game = chess.pgn.read_game(io.StringIO(pgn))
    if game is None:
        st.warning("Could not parse PGN.")
        return

    flipped = orientation == "black"

    # -- Build SVG frames for each position -----------------------------------
    board = game.board()
    moves_played: list[chess.Move] = list(game.mainline_moves())

    # Build a lookup from ply → arrow_uci
    arrow_map: dict[int, str] = {}
    san_list: list[str] = []
    if not moves_df.empty:
        for _, row in moves_df.iterrows():
            p = int(row["ply"])
            arrow_map[p] = str(row.get("arrow_uci", "") or "")
            san_list.append(str(row.get("san", "")))
    else:
        for move in moves_played:
            san_list.append(board.san(move))
        board = game.board()  # reset

    frames: list[str] = []

    # Frame 0: starting position (no arrows, no lastmove)
    frames.append(
        chess.svg.board(board, size=size, flipped=flipped)
    )

    board = game.board()  # reset
    for ply_i, move in enumerate(moves_played, start=1):
        board.push(move)
        # Best-move arrow for this ply
        arrows: list[chess.svg.Arrow] = []
        uci_str = arrow_map.get(ply_i, "")
        if uci_str and len(uci_str) >= 4:
            try:
                from_sq = chess.parse_square(uci_str[:2])
                to_sq = chess.parse_square(uci_str[2:4])
                arrows.append(chess.svg.Arrow(from_sq, to_sq, color="#3b82f680"))
            except ValueError:
                pass

        frames.append(
            chess.svg.board(
                board,
                size=size,
                lastmove=move,
                arrows=arrows,
                flipped=flipped,
            )
        )

    total_frames = len(frames)  # 0..N where 0=start, 1=after move 1, etc.

    if isinstance(initial_ply, int) and 0 <= initial_ply < total_frames:
        start_ply = initial_ply
    else:
        start_ply = total_frames - 1

    # -- Build move list HTML (numbered moves) --------------------------------
    move_spans: list[str] = []
    for i, san in enumerate(san_list):
        ply = i + 1
        if ply % 2 == 1:
            move_no = (ply + 1) // 2
            move_spans.append(
                f'<span class="move-num">{move_no}.</span>'
            )
        move_spans.append(
            f'<span class="move" data-ply="{ply}" onclick="goTo({ply})">{san}</span>'
        )
    moves_html = " ".join(move_spans)

    # -- Serialize SVG frames as JSON -----------------------------------------
    frames_json = json.dumps(frames)

    html = f"""
    <style>
      #{viewer_id} {{
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        max-width: {size + 40}px;
      }}
      #{viewer_id} .board-wrap {{ text-align: center; }}
      #{viewer_id} .board-wrap svg {{ display: block; margin: 0 auto; }}
      #{viewer_id} .controls {{
        display: flex; align-items: center; gap: 6px;
        padding: 8px 0; justify-content: center;
      }}
      #{viewer_id} .controls button {{
        background: #374151; color: #fff; border: none; border-radius: 4px;
        padding: 5px 10px; cursor: pointer; font-size: 14px; min-width: 32px;
      }}
      #{viewer_id} .controls button:hover {{ background: #4b5563; }}
      #{viewer_id} .controls input[type=range] {{ flex: 1; max-width: 280px; }}
      #{viewer_id} .ply-label {{
        font-size: 13px; color: #9ca3af; min-width: 70px; text-align: center;
      }}
      #{viewer_id} .move-list {{
        max-height: 180px; overflow-y: auto; padding: 6px 4px;
        font-size: 13px; line-height: 1.8; border: 1px solid #374151;
        border-radius: 6px; margin-top: 6px; background: #111827;
      }}
      #{viewer_id} .move-list .move-num {{ color: #6b7280; margin-left: 4px; }}
      #{viewer_id} .move-list .move {{
        cursor: pointer; padding: 1px 4px; border-radius: 3px; color: #d1d5db;
      }}
      #{viewer_id} .move-list .move:hover {{ background: #1f2937; }}
      #{viewer_id} .move-list .move.active {{
        background: #2563eb; color: #fff; font-weight: 600;
      }}
    </style>

    <div id="{viewer_id}">
      <div class="board-wrap" id="{viewer_id}-board"></div>
      <div class="controls">
        <button onclick="goTo(0)" title="Start">&#x23EE;</button>
        <button onclick="goTo(Math.max(0, currentPly-1))" title="Back">&#x25C0;</button>
        <button id="{viewer_id}-playbtn" onclick="togglePlay()" title="Play/Pause">&#x25B6;</button>
        <button onclick="goTo(Math.min({total_frames - 1}, currentPly+1))" title="Forward">&#x25B6;&#xFE0E;</button>
        <button onclick="goTo({total_frames - 1})" title="End">&#x23ED;</button>
        <input type="range" id="{viewer_id}-slider" min="0" max="{total_frames - 1}"
               value="{start_ply}" oninput="goTo(parseInt(this.value))">
        <span class="ply-label" id="{viewer_id}-label"></span>
      </div>
      <div class="move-list" id="{viewer_id}-moves">{moves_html}</div>
    </div>

    <script>
    (function() {{
      const frames = {frames_json};
      const totalFrames = frames.length;
      let currentPly = {start_ply};
      let playing = false;
      let timer = null;

      const boardEl = document.getElementById('{viewer_id}-board');
      const slider = document.getElementById('{viewer_id}-slider');
      const label = document.getElementById('{viewer_id}-label');
      const playBtn = document.getElementById('{viewer_id}-playbtn');
      const movesEl = document.getElementById('{viewer_id}-moves');
      const allMoveSpans = movesEl.querySelectorAll('.move');

      window.currentPly = currentPly;

      function render() {{
        boardEl.innerHTML = frames[currentPly];
        slider.value = currentPly;
        if (currentPly === 0) {{
          label.textContent = 'Start';
        }} else {{
          const moveNum = Math.ceil(currentPly / 2);
          const side = currentPly % 2 === 1 ? '' : '...';
          label.textContent = moveNum + '.' + side + ' (ply ' + currentPly + ')';
        }}
        // highlight active move in list
        allMoveSpans.forEach(s => s.classList.remove('active'));
        if (currentPly > 0) {{
          const active = movesEl.querySelector('.move[data-ply="' + currentPly + '"]');
          if (active) {{
            active.classList.add('active');
            active.scrollIntoView({{ block: 'nearest' }});
          }}
        }}
      }}

      window.goTo = function(ply) {{
        currentPly = Math.max(0, Math.min(totalFrames - 1, ply));
        window.currentPly = currentPly;
        render();
      }};

      window.togglePlay = function() {{
        if (playing) {{
          clearInterval(timer);
          playing = false;
          playBtn.innerHTML = '\\u25B6';
        }} else {{
          if (currentPly >= totalFrames - 1) currentPly = 0;
          playing = true;
          playBtn.innerHTML = '\\u23F8';
          timer = setInterval(() => {{
            if (currentPly >= totalFrames - 1) {{
              clearInterval(timer);
              playing = false;
              playBtn.innerHTML = '\\u25B6';
              return;
            }}
            currentPly++;
            window.currentPly = currentPly;
            render();
          }}, 800);
        }}
      }};

      render();
    }})();
    </script>
    """

    # Height: board + controls + move list
    st.components.v1.html(html, height=size + 280)


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
