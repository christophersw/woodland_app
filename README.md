# Woodland Chess MVP

Two-page Streamlit MVP:
- My History
- Game Analysis
- Game Search

## Run

1. Create and activate a Python environment.
2. Install dependencies:
   pip install -e .
3. Start app:
   streamlit run streamlit_app.py

## Chess.com Sync

1. Configure environment values (either in shell or `.env`):
   - `CHESS_COM_USERNAMES=player1,player2`
   - `DATABASE_URL=postgresql+psycopg://...` (optional; defaults to local `woodland_chess.db`)
   - `INGEST_MONTH_LIMIT=24` (optional; set `0` for full history)
2. Run manual sync:
   python -m app.ingest.run_sync
3. Open My History and use the `Chess.com Sync` expander to trigger sync from UI.

## Routing

- My History: /my-history
- Game Analysis: /game-analysis?game_id=<id>
- Game Search: /game-search

## AI Game Search (Optional)

- Set `ANTHROPIC_API_KEY` in `.env` to enable natural-language to SQL game search.
- Optional: set `ANTHROPIC_MODEL` (defaults to `claude-3-haiku-20240307`).

## Authentication (Phase 6)

- Auth is optional and disabled by default.
- Enable with:
   - `AUTH_ENABLED=true`
   - `AUTH_BOOTSTRAP_ADMIN_EMAIL=you@example.com`
   - `AUTH_BOOTSTRAP_ADMIN_PASSWORD=your-password`
   - `AUTH_SIGNING_KEY=long-random-secret`
- On first startup with auth enabled, the admin user is auto-created if no users exist.
- Admins can create member/admin users from the sidebar `Invite Member` section.
- Auth is persisted in a signed browser cookie; game URLs remain clean and shareable (`/game-analysis?game_id=<id>`).

## Notes

- If no database URL is configured, the app uses local SQLite (`woodland_chess.db`).
- Demo data is used only when no player/game rows exist yet.
- Configure `DATABASE_URL` to point to Railway Postgres for shared real data.
