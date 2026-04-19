import time
from datetime import datetime, timedelta, timezone

import pandas as pd
import streamlit as st
from sqlalchemy import delete, func, select

from app.storage.database import get_session, init_db
from app.storage.models import AnalysisJob, WorkerHeartbeat
from app.web.components.auth import require_auth

require_auth()
init_db()

_STALE_SECONDS = 120  # worker considered dead if no heartbeat for 2 minutes
def _prune_stale_heartbeats() -> int:
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=_STALE_SECONDS)
    with get_session() as s:
        result = s.execute(
            delete(WorkerHeartbeat).where(WorkerHeartbeat.last_seen < cutoff)
        )
        s.commit()
        return result.rowcount


title_col, cleanup_col = st.columns([8, 2])
title_col.title("Analysis Status")
title_col.caption("Live view of the Stockfish analysis job queue and worker health.")
if cleanup_col.button("Clean up", help="Remove all stale worker records"):
    pruned = _prune_stale_heartbeats()
    st.toast(f"Removed {pruned} stale worker record(s).")
    st.rerun()

auto_refresh = st.toggle("Auto-refresh every 10s", value=False)


def _get_counts() -> dict:
    with get_session() as s:
        rows = s.execute(
            select(AnalysisJob.status, func.count().label("n")).group_by(AnalysisJob.status)
        ).all()
        return {r.status: r.n for r in rows}


def _get_heartbeats() -> list:
    with get_session() as s:
        return s.execute(select(WorkerHeartbeat).order_by(WorkerHeartbeat.last_seen.desc())).scalars().all()


def _get_recent_jobs(limit: int = 50) -> pd.DataFrame:
    with get_session() as s:
        rows = s.execute(
            select(
                AnalysisJob.id,
                AnalysisJob.game_id,
                AnalysisJob.status,
                AnalysisJob.depth,
                AnalysisJob.worker_id,
                AnalysisJob.started_at,
                AnalysisJob.completed_at,
                AnalysisJob.retry_count,
                AnalysisJob.error_message,
            )
            .order_by(AnalysisJob.id.desc())
            .limit(limit)
        ).all()
        return pd.DataFrame([r._asdict() for r in rows]) if rows else pd.DataFrame()


# --- Worker health ---
st.subheader("Worker Health")
heartbeats = _get_heartbeats()
now = datetime.now(timezone.utc)

if not heartbeats:
    st.warning("No worker has ever connected. Start the analysis worker to begin processing.")
else:
    for hb in heartbeats:
        last_seen = hb.last_seen
        if last_seen.tzinfo is None:
            last_seen = last_seen.replace(tzinfo=timezone.utc)
        age_s = (now - last_seen).total_seconds()
        age_label = f"{int(age_s)}s ago" if age_s < 120 else f"{int(age_s // 60)}m ago"

        status_icon = {
            "analyzing": "⚙️",
            "idle": "💤",
            "starting": "🚀",
            "error": "❌",
            "stopped": "🛑",
        }.get(hb.status, "❓")

        if age_s > _STALE_SECONDS and hb.status not in ("stopped",):
            st.error(
                f"**{hb.worker_id}** — last seen {age_label}. "
                f"Worker may have crashed (status was: {hb.status})."
            )
        elif hb.status == "stopped":
            st.info(f"{status_icon} **{hb.worker_id}** — stopped cleanly, last seen {age_label}. "
                    f"Completed {hb.jobs_completed} / failed {hb.jobs_failed}.")
        elif hb.status == "idle":
            st.success(f"{status_icon} **{hb.worker_id}** — idle, last seen {age_label}. "
                       f"Completed {hb.jobs_completed} / failed {hb.jobs_failed}.")
        elif hb.status == "analyzing":
            st.success(
                f"{status_icon} **{hb.worker_id}** — analyzing `{hb.current_game_id}`, "
                f"last seen {age_label}. "
                f"Completed {hb.jobs_completed} / failed {hb.jobs_failed}."
            )
        else:
            st.warning(f"{status_icon} **{hb.worker_id}** — {hb.status}, last seen {age_label}.")

st.markdown("---")

# --- Queue metrics ---
st.subheader("Queue")
counts = _get_counts()
total = sum(counts.values())
completed = counts.get("completed", 0)
pending = counts.get("pending", 0)
running = counts.get("running", 0)
failed = counts.get("failed", 0)

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total", f"{total:,}")
c2.metric("Completed", f"{completed:,}")
c3.metric("Pending", f"{pending:,}")
c4.metric("Running", running)
c5.metric("Failed", failed)

if total > 0:
    pct = completed / total
    st.progress(pct, text=f"{pct:.1%} analyzed ({completed:,} / {total:,} games)")

st.markdown("---")

# --- Recent jobs table ---
st.subheader("Recent Jobs")
df = _get_recent_jobs(50)
if not df.empty:
    status_icons = {"completed": "✅", "running": "⏳", "pending": "🕐", "failed": "❌"}
    df["status"] = df["status"].map(lambda s: f"{status_icons.get(s, '')} {s}")
    df["duration_s"] = df.apply(
        lambda r: round((r["completed_at"] - r["started_at"]).total_seconds())
        if pd.notna(r.get("completed_at")) and pd.notna(r.get("started_at")) else None,
        axis=1,
    )
    display_cols = ["id", "status", "game_id", "depth", "worker_id", "duration_s", "retry_count", "error_message"]
    display_cols = [c for c in display_cols if c in df.columns]
    st.dataframe(
        df[display_cols],
        use_container_width=True,
        hide_index=True,
        column_config={
            "id": st.column_config.NumberColumn("Job", width="small"),
            "game_id": st.column_config.TextColumn("Game ID"),
            "depth": st.column_config.NumberColumn("Depth", width="small"),
            "worker_id": st.column_config.TextColumn("Worker"),
            "duration_s": st.column_config.NumberColumn("Duration (s)", width="small"),
            "retry_count": st.column_config.NumberColumn("Retries", width="small"),
            "error_message": st.column_config.TextColumn("Error"),
        },
    )
else:
    st.info("No jobs found. Run the analysis worker to populate the queue.")

if auto_refresh:
    time.sleep(10)
    st.rerun()
