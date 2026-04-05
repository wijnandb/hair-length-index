"""Database module — Postgres (Neon) with SQLite fallback for the Hair Length Index."""

import os
import sqlite3
from pathlib import Path

from scripts.config import DB_PATH

# Check for Postgres connection
DATABASE_URL = os.environ.get("DATABASE_URL")


class DictRow(dict):
    """Dict that also supports index-based access, mimicking sqlite3.Row."""
    def __init__(self, keys, values):
        super().__init__(zip(keys, values))
        self._keys = keys

    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)

    def keys(self):
        return self._keys


class PgConnectionWrapper:
    """Wraps psycopg2 connection to provide sqlite3-compatible interface.

    Key differences handled:
    - Returns DictRow instead of psycopg2 tuples
    - Uses %s placeholders (auto-converted from ?)
    - Provides execute/fetchone/fetchall on connection directly
    """

    def __init__(self, pg_conn):
        self._conn = pg_conn

    def execute(self, sql, params=None):
        sql = _pg_sql(sql)
        cur = self._conn.cursor()
        cur.execute(sql, params or ())
        return _PgCursorWrapper(cur)

    def commit(self):
        self._conn.commit()

    def close(self):
        self._conn.close()


class _PgCursorWrapper:
    """Wraps psycopg2 cursor to return DictRow objects."""

    def __init__(self, cursor):
        self._cursor = cursor

    @property
    def lastrowid(self):
        return self._cursor.fetchone()[0] if self._cursor.description else None

    @property
    def rowcount(self):
        return self._cursor.rowcount

    def fetchone(self):
        row = self._cursor.fetchone()
        if row is None or not self._cursor.description:
            return None
        keys = [d[0] for d in self._cursor.description]
        return DictRow(keys, row)

    def fetchall(self):
        rows = self._cursor.fetchall()
        if not rows or not self._cursor.description:
            return []
        keys = [d[0] for d in self._cursor.description]
        return [DictRow(keys, r) for r in rows]


def _pg_sql(sql: str) -> str:
    """Convert SQLite-style ? placeholders to Postgres %s."""
    return sql.replace("?", "%s")


def get_connection(db_path: Path = DB_PATH):
    """Get a database connection — Postgres if DATABASE_URL is set, else SQLite."""
    db_url = os.environ.get("DATABASE_URL")
    if db_url:
        import psycopg2
        pg_conn = psycopg2.connect(db_url)
        return PgConnectionWrapper(pg_conn)

    # SQLite fallback for local dev
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(conn) -> None:
    """Create tables if they don't exist. No-op for Postgres (tables already exist)."""
    if isinstance(conn, PgConnectionWrapper):
        return  # Neon tables created via migration

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS teams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            short_name TEXT,
            country TEXT,
            wf_slug TEXT UNIQUE,
            wf_id TEXT,
            football_data_id INTEGER,
            api_football_id INTEGER,
            crest_url TEXT,
            current_league TEXT
        );

        CREATE UNIQUE INDEX IF NOT EXISTS idx_teams_name_league
            ON teams(name, current_league) WHERE current_league IS NOT NULL;

        CREATE TABLE IF NOT EXISTS matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            source_match_id TEXT NOT NULL,
            date DATE NOT NULL,
            home_team_id INTEGER NOT NULL REFERENCES teams(id),
            away_team_id INTEGER NOT NULL REFERENCES teams(id),
            home_goals_90min INTEGER,
            away_goals_90min INTEGER,
            home_goals_final INTEGER,
            away_goals_final INTEGER,
            home_goals_penalties INTEGER,
            away_goals_penalties INTEGER,
            decided_in TEXT CHECK(decided_in IN ('REGULAR', 'EXTRA_TIME', 'PENALTIES')),
            result_90min TEXT CHECK(result_90min IN ('H', 'A', 'D')),
            result_final TEXT CHECK(result_final IN ('H', 'A', 'D')),
            competition_id TEXT NOT NULL,
            competition_name TEXT,
            competition_type TEXT CHECK(competition_type IN (
                'LEAGUE', 'DOMESTIC_CUP', 'CONTINENTAL', 'SUPER_CUP'
            )),
            round TEXT,
            season TEXT NOT NULL,
            UNIQUE(date, home_team_id, away_team_id)
        );

        CREATE TABLE IF NOT EXISTS data_sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            competition_id TEXT NOT NULL,
            season TEXT NOT NULL,
            last_fetched DATETIME,
            match_count INTEGER DEFAULT 0,
            status TEXT CHECK(status IN ('COMPLETE', 'PARTIAL', 'PENDING')) DEFAULT 'PENDING',
            UNIQUE(source, competition_id, season)
        );

        CREATE INDEX IF NOT EXISTS idx_matches_home_team ON matches(home_team_id, date);
        CREATE INDEX IF NOT EXISTS idx_matches_away_team ON matches(away_team_id, date);
        CREATE INDEX IF NOT EXISTS idx_matches_date ON matches(date);
        CREATE INDEX IF NOT EXISTS idx_matches_competition ON matches(competition_id, season);
    """)
    conn.commit()


def upsert_team(conn, **kwargs) -> int:
    """Insert or update a team. Looks up by football_data_id, api_football_id,
    wf_slug, or name (in that order). Returns the internal team ID."""
    updatable = (
        "name", "short_name", "country", "crest_url", "current_league",
        "wf_slug", "wf_id", "football_data_id", "api_football_id",
    )

    # Try to find existing team by external IDs (most specific first)
    row = None
    for lookup_key in ("football_data_id", "api_football_id", "wf_slug"):
        val = kwargs.get(lookup_key)
        if val is not None:
            row = conn.execute(
                f"SELECT id FROM teams WHERE {lookup_key} = ?", (val,)
            ).fetchone()
            if row:
                break

    if row:
        updates = []
        values = []
        for key in updatable:
            if key in kwargs and kwargs[key] is not None:
                updates.append(f"{key} = ?")
                values.append(kwargs[key])
        if updates:
            values.append(row["id"])
            conn.execute(
                f"UPDATE teams SET {', '.join(updates)} WHERE id = ?", values
            )
            conn.commit()
        return row["id"]

    # Insert new team
    cols = [k for k in kwargs if kwargs[k] is not None]
    placeholders = ", ".join("?" for _ in cols)
    values = [kwargs[k] for k in cols]

    if isinstance(conn, PgConnectionWrapper):
        col_str = ", ".join(cols)
        cursor = conn.execute(
            f"INSERT INTO teams ({col_str}) VALUES ({placeholders}) RETURNING id", values
        )
        conn.commit()
        return cursor.fetchone()["id"]
    else:
        cursor = conn.execute(
            f"INSERT INTO teams ({', '.join(cols)}) VALUES ({placeholders})", values
        )
        conn.commit()
        return cursor.lastrowid


def find_team_by_name(conn, name: str):
    """Find a team by exact name or short_name."""
    return conn.execute(
        "SELECT * FROM teams WHERE name = ? OR short_name = ?", (name, name)
    ).fetchone()


def find_team_by_football_data_id(conn, fd_id: int):
    """Find a team by football-data.org ID."""
    return conn.execute(
        "SELECT * FROM teams WHERE football_data_id = ?", (fd_id,)
    ).fetchone()


def find_team_by_api_football_id(conn, af_id: int):
    """Find a team by API-Football ID."""
    return conn.execute(
        "SELECT * FROM teams WHERE api_football_id = ?", (af_id,)
    ).fetchone()


def set_football_data_id(conn, team_id: int, fd_id: int) -> None:
    """Set the football-data.org ID for a team."""
    conn.execute("UPDATE teams SET football_data_id = ? WHERE id = ?", (fd_id, team_id))
    conn.commit()


def set_api_football_id(conn, team_id: int, af_id: int) -> None:
    """Set the API-Football ID for a team."""
    conn.execute("UPDATE teams SET api_football_id = ? WHERE id = ?", (af_id, team_id))
    conn.commit()


def upsert_match(conn, **kwargs) -> int | None:
    """Insert a match, ignoring duplicates (same date + home + away team)."""
    cols = [k for k in kwargs if kwargs[k] is not None]
    placeholders = ", ".join("?" for _ in cols)
    values = [kwargs[k] for k in cols]

    if isinstance(conn, PgConnectionWrapper):
        col_str = ", ".join(cols)
        try:
            cursor = conn.execute(
                f"INSERT INTO matches ({col_str}) VALUES ({placeholders}) "
                f"ON CONFLICT (date, home_team_id, away_team_id) DO NOTHING "
                f"RETURNING id", values
            )
            conn.commit()
            row = cursor.fetchone()
            return row["id"] if row else None
        except Exception:
            conn.commit()
            return None
    else:
        try:
            cursor = conn.execute(
                f"INSERT OR IGNORE INTO matches ({', '.join(cols)}) VALUES ({placeholders})",
                values,
            )
            conn.commit()
            return cursor.lastrowid if cursor.rowcount > 0 else None
        except sqlite3.IntegrityError:
            return None


def get_team_matches(conn, team_id: int, order: str = "DESC") -> list:
    """Get all matches for a team, ordered by date."""
    return conn.execute(
        f"""
        SELECT * FROM matches
        WHERE home_team_id = ? OR away_team_id = ?
        ORDER BY date {order}, id {order}
        """,
        (team_id, team_id),
    ).fetchall()


def get_all_teams(conn, league: str | None = None) -> list:
    """Get all teams, optionally filtered by current league."""
    if league:
        return conn.execute(
            "SELECT * FROM teams WHERE current_league = ? ORDER BY name", (league,)
        ).fetchall()
    return conn.execute("SELECT * FROM teams ORDER BY name").fetchall()


def update_data_source(conn, source: str, competition_id: str,
                       season: str, **kwargs) -> None:
    """Upsert a data source tracking record."""
    row = conn.execute(
        "SELECT id FROM data_sources WHERE source = ? AND competition_id = ? AND season = ?",
        (source, competition_id, season),
    ).fetchone()
    if row:
        updates = []
        values = []
        for key, val in kwargs.items():
            updates.append(f"{key} = ?")
            values.append(val)
        if updates:
            values.append(row["id"])
            conn.execute(
                f"UPDATE data_sources SET {', '.join(updates)} WHERE id = ?", values
            )
    else:
        cols = ["source", "competition_id", "season"] + list(kwargs.keys())
        values = [source, competition_id, season] + list(kwargs.values())
        placeholders = ", ".join("?" for _ in cols)
        conn.execute(
            f"INSERT INTO data_sources ({', '.join(cols)}) VALUES ({placeholders})",
            values,
        )
    conn.commit()
