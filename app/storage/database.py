from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.storage.models import Base


settings = get_settings()


def _normalize_database_url(database_url: str) -> str:
    if database_url.startswith("postgresql+psycopg://"):
        return database_url
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql+psycopg://", 1)
    return database_url


def _engine():
    if settings.database_url:
        return create_engine(_normalize_database_url(settings.database_url), pool_pre_ping=True)
    return create_engine("sqlite+pysqlite:///woodland_chess.db", pool_pre_ping=True)


ENGINE = _engine()
SessionLocal = sessionmaker(bind=ENGINE, autoflush=False, autocommit=False)


def init_db() -> None:
    Base.metadata.create_all(ENGINE)
    _run_lightweight_migrations()


def _run_lightweight_migrations() -> None:
    inspector = inspect(ENGINE)

    if inspector.has_table("games"):
        existing = {col["name"] for col in inspector.get_columns("games")}
        column_defs = {
            "white_username": "VARCHAR(120)",
            "black_username": "VARCHAR(120)",
            "white_rating": "INTEGER",
            "black_rating": "INTEGER",
            "result_pgn": "VARCHAR(16)",
            "winner_username": "VARCHAR(120)",
            "lichess_opening": "VARCHAR(200)",
            "opening_ply_1": "VARCHAR(32)",
            "opening_ply_2": "VARCHAR(32)",
            "opening_ply_3": "VARCHAR(32)",
            "opening_ply_4": "VARCHAR(32)",
            "opening_ply_5": "VARCHAR(32)",
        }
        missing_columns = {name: ddl for name, ddl in column_defs.items() if name not in existing}

        if missing_columns:
            with ENGINE.begin() as conn:
                for name, ddl in missing_columns.items():
                    conn.execute(text(f"ALTER TABLE games ADD COLUMN {name} {ddl}"))

        # Backfill winner_username from result_pgn + white/black_username.
        if "winner_username" in missing_columns or "winner_username" in existing:
            with ENGINE.begin() as conn:
                conn.execute(text(
                    "UPDATE games SET winner_username = "
                    "CASE WHEN result_pgn = '1-0' THEN white_username "
                    "WHEN result_pgn = '0-1' THEN black_username "
                    "ELSE NULL END "
                    "WHERE winner_username IS NULL AND result_pgn IS NOT NULL"
                ))



def get_session() -> Session:
    return SessionLocal()
