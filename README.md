# Woodland Chess

A Streamlit chess analytics app for club and personal game history, opening analysis, and Stockfish-powered game review.

Pages:
- **My History** — rating trend, recent games, opening distribution
- **Game Search** — AI-powered and keyword search across all games
- **Game Analysis** — move-by-move board with eval chart, best-move arrows, and accuracy stats

---

## Setup

```bash
# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Install dependencies (includes all scripts)
pip install -e .
```

### Environment variables

Create a `.env` file in the project root (or set these in your shell / Railway dashboard):

| Variable | Required | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | No | local SQLite | PostgreSQL connection string (`postgresql+psycopg://...`) |
| `CHESS_COM_USERNAMES` | Yes (for sync) | — | Comma-separated Chess.com usernames to track |
| `CHESS_COM_USER_AGENT` | No | built-in | Custom User-Agent string for Chess.com API requests |
| `INGEST_MONTH_LIMIT` | No | `0` | Limit sync to last N months; `0` means full history |
| `ANTHROPIC_API_KEY` | No | — | Enables AI-powered natural-language game search |
| `ANTHROPIC_MODEL` | No | `claude-3-haiku-20240307` | Claude model for AI search |
| `STOCKFISH_PATH` | No | auto-detected | Full path to Stockfish binary; auto-detected from `PATH` if omitted |
| `ANALYSIS_DEPTH` | No | `20` | Stockfish search depth per position |
| `ANALYSIS_THREADS` | No | `1` | CPU threads Stockfish uses per game |
| `AUTH_ENABLED` | No | `false` | Enable login-gated access |
| `AUTH_BOOTSTRAP_ADMIN_EMAIL` | No | — | Admin account created on first startup when auth is enabled |
| `AUTH_BOOTSTRAP_ADMIN_PASSWORD` | No | — | Password for the bootstrap admin |
| `AUTH_SIGNING_KEY` | No | — | Secret key for signing session tokens (use a long random string in production) |
| `AUTH_TOKEN_TTL_SECONDS` | No | `604800` | Session cookie lifetime in seconds (default 7 days) |

### Run the app

```bash
streamlit run streamlit_app.py
```

---

## Ingest: Syncing games from Chess.com

```bash
.venv/bin/python -m app.ingest.run_sync
```

Fetches all archives for the configured usernames and upserts games into the database. Safe to re-run — already-stored games are updated, not duplicated.

**Options:**

| Flag | Description |
|---|---|
| `--usernames alice,bob` | Override `CHESS_COM_USERNAMES`; comma-separated |

**Examples:**

```bash
# Sync usernames from .env
.venv/bin/python -m app.ingest.run_sync

# Sync specific usernames without changing .env
.venv/bin/python -m app.ingest.run_sync --usernames christophersw,opponent1
```

**When to run:**
- After first setup to populate the database
- On a schedule (e.g. nightly cron) to pick up new games
- Manually after a tournament or active play session

---

## Stockfish analysis

Analysis is a two-step process: first **enqueue** the games you want analyzed, then **run a worker** to process them. The two steps can be combined into one command.

### Step 1 — Enqueue unanalyzed games

```bash
.venv/bin/python -m app.ingest.run_analysis_worker --enqueue-only
```

Scans the database for games with PGN that have not yet been analyzed and creates a job queue entry for each one. Safe to re-run — already-queued or completed games are skipped.

**Options:**

| Flag | Description |
|---|---|
| `--enqueue-limit N` | Only enqueue up to N games (useful for a trial run) |
| `--depth N` | Stockfish search depth to request (default `20`); stored on the job |

### Step 2 — Run the worker

```bash
.venv/bin/python -m app.ingest.run_analysis_worker --no-poll
```

Claims jobs from the queue one at a time, runs Stockfish on each game's PGN, and saves per-move centipawn evals, best-move arrows, accuracy scores, and blunder/mistake/inaccuracy counts to the database.

**Options:**

| Flag | Description |
|---|---|
| `--stockfish /path/to/sf` | Path to Stockfish binary; auto-detected from `PATH` if omitted |
| `--depth N` | Analysis depth per position (default `20`; higher = slower but more accurate) |
| `--threads N` | CPU threads Stockfish uses internally per game (default `1`) |
| `--limit N` | Stop after processing N games and exit |
| `--no-poll` | Exit when the queue is empty instead of waiting for new jobs |
| `--poll-interval N` | Seconds to wait between queue checks when polling (default `5`) |
| `--status` | Print job counts by status and exit |

### Combined: enqueue + analyze in one command

```bash
.venv/bin/python -m app.ingest.run_analysis_worker --enqueue --no-poll
```

### Check queue status

```bash
.venv/bin/python -m app.ingest.run_analysis_worker --status
```

Output example:
```
  completed     1450
  pending       7127
  failed           3
```

### Run multiple workers in parallel

Each worker safely claims its own jobs via `SELECT FOR UPDATE SKIP LOCKED` (PostgreSQL) so there are no duplicate analyses. On a machine with 8 cores:

```bash
for i in 1 2 3 4; do
  .venv/bin/python -m app.ingest.run_analysis_worker --threads 2 --no-poll &
done
wait
```

### Worker crash recovery

If a worker is killed mid-job, its jobs are left in `running` state. On the next startup the worker automatically resets any jobs that have been `running` for more than 10 minutes back to `pending` so they will be retried.

### Depth guidance

| Depth | Speed | Use case |
|---|---|---|
| `12–15` | Fast (~1–2s/move) | Quick bulk pass across thousands of games |
| `18–20` | Medium (~3–6s/move) | Default; good balance of accuracy and speed |
| `22+` | Slow (10s+/move) | Deep review of specific important games |

---

## Routing

| Page | URL |
|---|---|
| My History | `/my-history` |
| Game Analysis | `/game-analysis?game_id=<id>` |
| Game Search | `/game-search` |

---

## Authentication

Auth is disabled by default. Enable it by setting:

```env
AUTH_ENABLED=true
AUTH_BOOTSTRAP_ADMIN_EMAIL=you@example.com
AUTH_BOOTSTRAP_ADMIN_PASSWORD=your-password
AUTH_SIGNING_KEY=long-random-secret-string
```

On first startup with auth enabled, the admin account is created automatically if no users exist. Admins can invite new members from the sidebar. Sessions are persisted via a signed browser cookie so direct game links (`/game-analysis?game_id=...`) work across tabs and browser restarts.

---

## Deploy to Railway

1. Push this repo to GitHub.
2. In Railway, create a new project → **Deploy from GitHub repo**.
3. Attach a **PostgreSQL** plugin and Railway will inject `DATABASE_URL` automatically.
4. Add environment variables in the Railway dashboard (see table above).
5. Deploy. Railway uses `railway.toml` (Nixpacks builder) which:
   - Installs `stockfish` via Nix (available on PATH automatically)
   - Runs `pip install .`
   - Starts Streamlit on `0.0.0.0:$PORT`

**Notes:**
- Do not set `PORT` manually — Railway injects it automatically.
- Always set a strong `AUTH_SIGNING_KEY` in production.
- Run the sync script against your Railway database from your local machine by setting `DATABASE_URL` in your shell before running `run_sync`.

---

## Architecture notes

- If no `DATABASE_URL` is set, the app uses a local SQLite file (`woodland_chess.db`).
- Demo/placeholder data is only shown when the database has no player or game rows.
- The `Game` table stores one row per unique game. `GameParticipant` stores each tracked player's perspective on that game (color, result, rating, blunder counts), so games between two tracked players appear correctly in both players' history.
- Stockfish analysis results are stored in `GameAnalysis` (per-game accuracy/blunder summary) and `MoveAnalysis` (per-move eval, best move, CPL, classification).
