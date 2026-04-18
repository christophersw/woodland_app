import time

import pandas as pd
import streamlit as st
from sqlalchemy import func, select

from app.storage.database import get_session, init_db
from app.storage.models import AnalysisJob
from app.web.components.auth import require_auth

require_auth()

init_db()

st.title("Analysis Status")
st.caption("Live view of the Stockfish analysis job queue.")

auto_refresh = st.toggle("Auto-refresh every 10s", value=False)

def _get_counts() -> dict:
    with get_session() as s:
        rows = s.execute(
            select(AnalysisJob.status, func.count().label("n")).group_by(AnalysisJob.status)
        ).all()
        return {r.status: r.n for r in rows}


def _get_recent_jobs(limit: int = 50) -> pd.DataFrame:
    with get_session() as s:
        rows = s.execute(
            select(
                AnalysisJob.id,
                AnalysisJob.game_id,
                AnalysisJob.status,
                AnalysisJob.depth,
                AnalysisJob.worker_id,
                AnalysisJob.created_at,
                AnalysisJob.started_at,
                AnalysisJob.completed_at,
                AnalysisJob.retry_count,
                AnalysisJob.error_message,
            )
            .order_by(AnalysisJob.id.desc())
            .limit(limit)
        ).all()
        return pd.DataFrame([r._asdict() for r in rows]) if rows else pd.DataFrame()


counts = _get_counts()
total = sum(counts.values())
completed = counts.get("completed", 0)
pending = counts.get("pending", 0)
running = counts.get("running", 0)
failed = counts.get("failed", 0)

# Summary metrics
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total", total)
c2.metric("Completed", completed)
c3.metric("Pending", pending)
c4.metric("Running", running)
c5.metric("Failed", failed)

# Progress bar
if total > 0:
    pct = completed / total
    st.progress(pct, text=f"{pct:.1%} analyzed ({completed:,} / {total:,} games)")

st.markdown("---")

# Recent jobs table
st.subheader("Recent Jobs")
df = _get_recent_jobs(50)
if not df.empty:
    status_colors = {"completed": "✅", "running": "⏳", "pending": "🕐", "failed": "❌"}
    df["status"] = df["status"].map(lambda s: f"{status_colors.get(s, '')} {s}")
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
