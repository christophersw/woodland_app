import io

import chess.pgn
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


def elo_trend_chart(df: pd.DataFrame, selected_player: str):
    fig = px.line(
        df,
        x="date",
        y="rating",
        color="player",
        title="ELO Trend (Daily Games)",
        markers=False,
    )
    fig.update_traces(opacity=0.35)
    fig.for_each_trace(
        lambda trace: trace.update(opacity=1.0, line=dict(width=3))
        if trace.name == selected_player
        else None
    )
    fig.update_layout(legend_title="Player", margin=dict(l=20, r=20, t=56, b=20))
    return fig


def opening_pie_chart(df: pd.DataFrame):
    fig = px.pie(
        df,
        names="opening",
        values="games",
        title="Recent Openings Distribution (Depth = 5 Ply)",
    )
    fig.update_traces(textposition="inside", textinfo="percent+label")
    return fig


def eval_timeline_chart(df: pd.DataFrame, selected_ply: int | None = None):
    fig = px.bar(df, x="ply", y="cp_eval", title="Engine Evaluation by Ply")

    if selected_ply is not None:
        colors = ["#4c78a8" if int(p) != selected_ply else "#e45756" for p in df["ply"].tolist()]
        fig.update_traces(marker_color=colors)

    fig.add_hline(y=0, line_dash="dot")
    fig.update_layout(yaxis_title="Centipawns", xaxis_title="Ply", clickmode="event+select")
    return fig


def opening_starburst_chart(df: pd.DataFrame, depth: int = 5):
    """Build a sunburst from opening ply data, with lichess opening labels on large segments."""
    if df.empty:
        return None

    depth = max(1, min(depth, 20))
    denorm_cols = [f"opening_ply_{i}" for i in range(1, depth + 1)]
    has_denorm = all(col in df.columns for col in denorm_cols)
    has_lichess = "lichess_opening" in df.columns

    # Collect per-game move sequences and lichess opening names.
    game_data: list[tuple[list[str], str]] = []
    for _, row in df.iterrows():
        plies: list[str] = []
        if has_denorm:
            for col in denorm_cols:
                val = row.get(col)
                if val is None:
                    break
                t = str(val).strip()
                if not t:
                    break
                plies.append(t)

        if not plies and "pgn" in df.columns:
            pgn = str(row.get("pgn") or "").strip()
            if pgn:
                game = chess.pgn.read_game(io.StringIO(pgn))
                if game is not None:
                    board = game.board()
                    for i, move in enumerate(game.mainline_moves(), 1):
                        plies.append(board.san(move))
                        board.push(move)
                        if i >= depth:
                            break

        if not plies:
            continue

        lichess = str(row.get("lichess_opening") or "").strip() if has_lichess else ""
        game_data.append((plies, lichess))

    if not game_data:
        return None

    # Build hierarchy nodes.
    nodes: dict[str, dict] = {}
    for plies, lichess in game_data:
        for d in range(1, min(len(plies), depth) + 1):
            nid = "/".join(plies[:d])
            pid = "/".join(plies[:d - 1]) if d > 1 else ""
            if nid not in nodes:
                nodes[nid] = {
                    "label": plies[d - 1],
                    "parent": pid,
                    "value": 0,
                    "lichess_names": [],
                }
            nodes[nid]["value"] += 1
            if lichess:
                nodes[nid]["lichess_names"].append(lichess)

    total = sum(n["value"] for n in nodes.values() if n["parent"] == "")

    ids, labels_arr, parents_arr, values_arr = [], [], [], []
    texts, hovertexts, customdata_arr = [], [], []

    for nid in sorted(nodes):
        n = nodes[nid]
        ids.append(nid)
        labels_arr.append(n["label"])
        parents_arr.append(n["parent"])
        values_arr.append(n["value"])

        # Dominant lichess opening name for this node.
        lnames = n["lichess_names"]
        if lnames:
            mode = pd.Series(lnames).mode()
            name = str(mode.iloc[0]) if not mode.empty else ""
        else:
            name = ""

        pct = n["value"] / total * 100 if total else 0
        # Show lichess name on segments >= 3% of total.
        if name and pct >= 3:
            short = name.split(" ", 1)[1] if " " in name else name
            texts.append(short)
        else:
            texts.append("")
        hovertexts.append(name or "")
        customdata_arr.append(name or "")

    fig = go.Figure(go.Sunburst(
        ids=ids,
        labels=labels_arr,
        parents=parents_arr,
        values=values_arr,
        text=texts,
        hovertext=hovertexts,
        customdata=customdata_arr,
        branchvalues="total",
        textinfo="label+text+percent parent",
        hovertemplate="<b>%{label}</b><br>Games: %{value}<br>%{hovertext}<extra></extra>",
        insidetextorientation="auto",
    ))
    fig.update_layout(
        title=f"Opening Star-burst (First {depth} Plies)",
        margin=dict(l=10, r=10, t=56, b=10),
    )
    return fig
