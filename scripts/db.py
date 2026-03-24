"""Database module — SQLite schema and helpers for the Hair Length Index."""

import sqlite3
from pathlib import Path

from scripts.config import DB_PATH


def get_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    """Get a SQLite connection with row factory enabled."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """Create all tables if they don't exist."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS teams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            short_name TEXT,
            country TEXT,
            football_data_id INTEGER UNIQUE,
            api_football_id INTEGER,
            crest_url TEXT,
            current_league TEXT
        );

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
            UNIQUE(source, source_match_id)
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

        -- Indexes for common query patterns
        CREATE INDEX IF NOT EXISTS idx_matches_home_team ON matches(home_team_id, date);
        CREATE INDEX IF NOT EXISTS idx_matches_away_team ON matches(away_team_id, date);
        CREATE INDEX IF NOT EXISTS idx_matches_date ON matches(date);
        CREATE INDEX IF NOT EXISTS idx_matches_competition ON matches(competition_id, season);

        -- Cross-source dedup index
        CREATE INDEX IF NOT EXISTS idx_matches_dedup
            ON matches(date, home_team_id, away_team_id);
    """)
    conn.commit()


def upsert_team(conn: sqlite3.Connection, **kwargs) -> int:
    """Insert or update a team by football_data_id. Returns the internal team ID."""
    fd_id = kwargs.get("football_data_id")
    if fd_id is not None:
        row = conn.execute(
            "SELECT id FROM teams WHERE football_data_id = ?", (fd_id,)
        ).fetchone()
        if row:
            # Update fields
            updates = []
            values = []
            for key in ("name", "short_name", "country", "crest_url", "current_league"):
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
    cursor = conn.execute(
        f"INSERT INTO teams ({', '.join(cols)}) VALUES ({placeholders})", values
    )
    conn.commit()
    return cursor.lastrowid


def find_team_by_name(conn: sqlite3.Connection, name: str) -> sqlite3.Row | None:
    """Find a team by exact name or short_name."""
    row = conn.execute(
        "SELECT * FROM teams WHERE name = ? OR short_name = ?", (name, name)
    ).fetchone()
    return row


def find_team_by_api_football_id(conn: sqlite3.Connection, api_id: int) -> sqlite3.Row | None:
    """Find a team by its API-Football ID."""
    return conn.execute(
        "SELECT * FROM teams WHERE api_football_id = ?", (api_id,)
    ).fetchone()


def set_api_football_id(conn: sqlite3.Connection, team_id: int, api_football_id: int) -> None:
    """Set the API-Football ID for a team."""
    conn.execute(
        "UPDATE teams SET api_football_id = ? WHERE id = ?",
        (api_football_id, team_id),
    )
    conn.commit()


def get_teams_missing_cup_data(conn: sqlite3.Connection, league: str, season: str) -> list[sqlite3.Row]:
    """Get teams that don't have cup match data for a given season."""
    return conn.execute(
        """
        SELECT t.* FROM teams t
        WHERE t.current_league = ?
        AND NOT EXISTS (
            SELECT 1 FROM matches m
            WHERE (m.home_team_id = t.id OR m.away_team_id = t.id)
            AND m.competition_type IN ('DOMESTIC_CUP', 'SUPER_CUP')
            AND m.season = ?
        )
        ORDER BY t.name
        """,
        (league, season),
    ).fetchall()


def upsert_match(conn: sqlite3.Connection, **kwargs) -> int | None:
    """Insert a match, ignoring duplicates (same source + source_match_id)."""
    cols = [k for k in kwargs if kwargs[k] is not None]
    placeholders = ", ".join("?" for _ in cols)
    values = [kwargs[k] for k in cols]
    try:
        cursor = conn.execute(
            f"INSERT OR IGNORE INTO matches ({', '.join(cols)}) VALUES ({placeholders})",
            values,
        )
        conn.commit()
        return cursor.lastrowid if cursor.rowcount > 0 else None
    except sqlite3.IntegrityError:
        return None


def get_team_matches(
    conn: sqlite3.Connection, team_id: int, order: str = "DESC"
) -> list[sqlite3.Row]:
    """Get all matches for a team, ordered by date."""
    return conn.execute(
        f"""
        SELECT * FROM matches
        WHERE home_team_id = ? OR away_team_id = ?
        ORDER BY date {order}, id {order}
        """,
        (team_id, team_id),
    ).fetchall()


def get_all_teams(conn: sqlite3.Connection, league: str | None = None) -> list[sqlite3.Row]:
    """Get all teams, optionally filtered by current league."""
    if league:
        return conn.execute(
            "SELECT * FROM teams WHERE current_league = ? ORDER BY name", (league,)
        ).fetchall()
    return conn.execute("SELECT * FROM teams ORDER BY name").fetchall()


def update_data_source(conn: sqlite3.Connection, source: str, competition_id: str,
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
