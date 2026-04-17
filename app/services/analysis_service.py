from __future__ import annotations

from dataclasses import dataclass
import io

import chess.pgn
import pandas as pd
from sqlalchemy import select

from app.storage.database import get_session, init_db
from app.storage.models import Game


SAMPLE_PGN = """
[Event \"Casual Game\"]
[Site \"Chess.com\"]
[Date \"2026.04.16\"]
[Round \"-\"]
[White \"alice\"]
[Black \"bob\"]
[Result \"1-0\"]

1. e4 e5 2. Nf3 Nc6 3. Bc4 Bc5 4. c3 Nf6 5. d4 exd4 6. cxd4 Bb4+ 7. Nc3 Nxe4 8. O-O Bxc3 9. bxc3 d5 10. Ba3 dxc4 11. Re1 Bf5 12. Nd2 Qd5 13. f3 O-O-O 14. fxe4 Qa5 15. Nxc4 Qxc3 16. Rc1 Qxd4+ 17. Qxd4 Rxd4 18. exf5 Rhd8 19. Be7 R8d7 20. Bc5 R4d5 21. Re8+ Nd8 22. Bxa7 b6 23. Nxb6+ Kb7 24. Nxd5 Rxd5 25. Re7 Nc6 26. Rxf7 Nxa7 27. Rcxc7+ Kb6 28. Rxa7 Rd1+ 29. Kf2 Rd2+ 30. Ke3 Rxg2 31. Rfb7+ Kc5 32. Rxg7 Rxh2 33. Rxh7 Rb2 34. f6 Rb8 35. f7 Rf8 36. Re7 Kd6 37. Re8 Rxf7 38. Rxf7 1-0
""".strip()


@dataclass
class GameAnalysisData:
    game_id: str
    white: str
    black: str
    result: str
    pgn: str
    moves: pd.DataFrame


class AnalysisService:
    def __init__(self) -> None:
        init_db()

    def get_game_analysis(self, game_id: str) -> GameAnalysisData | None:
        if not game_id:
            return None

        pgn = self._pgn_for_game(game_id)
        game = chess.pgn.read_game(io.StringIO(pgn))
        if game is None:
            return None

        board = game.board()
        rows: list[dict] = []

        for ply, move in enumerate(game.mainline_moves(), start=1):
            san = board.san(move)
            board.push(move)
            cp_eval = ((ply % 10) - 5) * 22
            best_move = san
            rows.append(
                {
                    "ply": ply,
                    "san": san,
                    "fen": board.fen(),
                    "cp_eval": cp_eval,
                    "best_move": best_move,
                    "arrow_uci": move.uci(),
                }
            )

        return GameAnalysisData(
            game_id=game_id,
            white=game.headers.get("White", "White"),
            black=game.headers.get("Black", "Black"),
            result=game.headers.get("Result", "*"),
            pgn=pgn,
            moves=pd.DataFrame(rows),
        )

    @staticmethod
    def _pgn_for_game(game_id: str) -> str:
        with get_session() as session:
            row = session.scalar(select(Game.pgn).where(Game.id == game_id))
            if row:
                return row
        return SAMPLE_PGN
