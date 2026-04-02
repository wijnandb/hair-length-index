"""Tests for the streak computation engine."""

import sqlite3
from datetime import date, timedelta

import pytest

from scripts.compute_streaks import _team_result, find_last_streak
from scripts.config import get_hair_tier
from scripts.db import get_connection, init_db, upsert_match, upsert_team


@pytest.fixture
def db():
    """In-memory SQLite database for testing."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    init_db(conn)
    return conn


@pytest.fixture
def team_id(db):
    """Create a test team and return its ID."""
    return upsert_team(db, name="Test FC", short_name="TST", country="NL")


@pytest.fixture
def opponent_id(db):
    """Create an opponent team."""
    return upsert_team(db, name="Opponent FC", short_name="OPP", country="NL")


def _make_match(db, team_id, opponent_id, match_date, home_goals, away_goals,
                is_home=True, competition_id="DED", competition_name="Eredivisie",
                decided_in="REGULAR", match_id=None):
    """Helper to create a match."""
    if match_id is None:
        match_id = f"m-{match_date}-{home_goals}-{away_goals}-{is_home}"

    h_id = team_id if is_home else opponent_id
    a_id = opponent_id if is_home else team_id
    h_goals = home_goals if is_home else away_goals
    a_goals = away_goals if is_home else home_goals

    # Compute results
    if h_goals > a_goals:
        result = "H"
    elif a_goals > h_goals:
        result = "A"
    else:
        result = "D"

    upsert_match(
        db,
        source="test",
        source_match_id=match_id,
        date=str(match_date),
        home_team_id=h_id,
        away_team_id=a_id,
        home_goals_90min=h_goals,
        away_goals_90min=a_goals,
        home_goals_final=h_goals,
        away_goals_final=a_goals,
        decided_in=decided_in,
        result_90min=result,
        result_final=result,
        competition_id=competition_id,
        competition_name=competition_name,
        competition_type="LEAGUE",
        season="2025-26",
    )


def _make_matches(db, team_id, opponent_id, results_str, start_date=None):
    """Create matches from a string like 'WWWDLWWWWW'.

    Most recent match first in the string.
    """
    if start_date is None:
        start_date = date(2026, 1, 1)

    results = list(results_str)
    # results[0] is the most recent match
    for i, r in enumerate(results):
        match_date = start_date - timedelta(days=i * 7)  # weekly matches
        if r == "W":
            _make_match(db, team_id, opponent_id, match_date, 2, 0, is_home=(i % 2 == 0))
        elif r == "L":
            _make_match(db, team_id, opponent_id, match_date, 0, 1, is_home=(i % 2 == 0))
        elif r == "D":
            _make_match(db, team_id, opponent_id, match_date, 1, 1, is_home=(i % 2 == 0))


def _get_matches_desc(db, team_id):
    """Get matches sorted by date DESC."""
    return db.execute(
        "SELECT * FROM matches WHERE home_team_id = ? OR away_team_id = ? ORDER BY date DESC",
        (team_id, team_id),
    ).fetchall()


# === Basic streak tests ===

class TestFindLastStreak:
    def test_no_matches(self):
        result = find_last_streak([], team_id=1)
        assert result["found"] is False
        assert result["streak_length"] == 0

    def test_five_wins_in_a_row(self, db, team_id, opponent_id):
        _make_matches(db, team_id, opponent_id, "WWWWW")
        matches = _get_matches_desc(db, team_id)
        result = find_last_streak(matches, team_id)
        assert result["found"] is True
        assert result["streak_length"] == 5
        assert result["matches_since"] == 0  # streak is the most recent matches

    def test_streak_broken_by_draw(self, db, team_id, opponent_id):
        # Most recent first: D W W W W W (draw broke a 5-streak)
        _make_matches(db, team_id, opponent_id, "DWWWWW")
        matches = _get_matches_desc(db, team_id)
        result = find_last_streak(matches, team_id)
        assert result["found"] is True
        assert result["streak_length"] == 5
        assert result["matches_since"] == 1  # 1 match since the streak ended

    def test_streak_broken_by_loss(self, db, team_id, opponent_id):
        _make_matches(db, team_id, opponent_id, "WLWWWWW")
        matches = _get_matches_desc(db, team_id)
        result = find_last_streak(matches, team_id)
        assert result["found"] is True
        assert result["streak_length"] == 5
        assert result["matches_since"] == 2

    def test_no_streak_found(self, db, team_id, opponent_id):
        _make_matches(db, team_id, opponent_id, "WDWWWDWWWDL")
        matches = _get_matches_desc(db, team_id)
        result = find_last_streak(matches, team_id)
        assert result["found"] is False

    def test_longer_than_five(self, db, team_id, opponent_id):
        # "LWWWWWWWWD" = L then 8 W's then D (most recent first)
        _make_matches(db, team_id, opponent_id, "LWWWWWWWWD")
        matches = _get_matches_desc(db, team_id)
        result = find_last_streak(matches, team_id)
        assert result["found"] is True
        assert result["streak_length"] == 8

    def test_exactly_four_not_enough(self, db, team_id, opponent_id):
        _make_matches(db, team_id, opponent_id, "WWWWDWWWWL")
        matches = _get_matches_desc(db, team_id)
        result = find_last_streak(matches, team_id)
        assert result["found"] is False

    def test_finds_most_recent_streak(self, db, team_id, opponent_id):
        # Two streaks: recent one and older one
        _make_matches(db, team_id, opponent_id, "DWWWWWLWWWWWD",
                      start_date=date(2026, 3, 1))
        matches = _get_matches_desc(db, team_id)
        result = find_last_streak(matches, team_id)
        assert result["found"] is True
        assert result["streak_length"] == 5
        # The streak_end_date should be the more recent one
        assert result["streak_end_date"] >= "2026-02"  # recent streak

    def test_current_form(self, db, team_id, opponent_id):
        _make_matches(db, team_id, opponent_id, "WLDWWWWWDL")
        matches = _get_matches_desc(db, team_id)
        result = find_last_streak(matches, team_id)
        assert result["current_form"][:4] == ["W", "L", "D", "W"]

    def test_away_wins_count(self, db, team_id, opponent_id):
        """Away wins should count as wins for the team."""
        start = date(2026, 1, 1)
        for i in range(5):
            # team is away, scores 2, opponent (home) scores 0
            # _make_match swaps so: h_goals=0 (opponent), a_goals=2 (team) → result "A" → team wins
            _make_match(db, team_id, opponent_id,
                       start - timedelta(days=i * 7),
                       2, 0, is_home=False)  # away win: team scores 2
        matches = _get_matches_desc(db, team_id)
        result = find_last_streak(matches, team_id)
        assert result["found"] is True
        assert result["streak_length"] == 5

    def test_five_wins_then_draw(self, db, team_id, opponent_id):
        """W,W,W,W,W,D (most recent first) should find a 5x streak."""
        _make_matches(db, team_id, opponent_id, "WWWWWD")
        matches = _get_matches_desc(db, team_id)
        result = find_last_streak(matches, team_id)
        assert result["found"] is True
        assert result["streak_length"] == 5
        assert result["matches_since"] == 0  # streak is ongoing/most recent

    def test_no_five_streak_in_mixed(self, db, team_id, opponent_id):
        """W,W,W,D,W,W (most recent first) has no 5x streak."""
        _make_matches(db, team_id, opponent_id, "WWWDWW")
        matches = _get_matches_desc(db, team_id)
        result = find_last_streak(matches, team_id)
        assert result["found"] is False

    def test_cross_season_streak(self, db, team_id, opponent_id):
        """A streak that spans across two seasons should still be found."""
        # Create 6 wins spanning two seasons using _make_match which handles home/away correctly
        base = date(2025, 7, 15)  # mid-summer, season boundary
        for i in range(6):
            match_date = base - timedelta(days=i * 4)
            season = "2025-26" if match_date >= date(2025, 7, 1) else "2024-25"
            is_home = (i % 2 == 0)
            h_id = team_id if is_home else opponent_id
            a_id = opponent_id if is_home else team_id
            # Team always wins: if home, result=H; if away, result=A
            result_code = "H" if is_home else "A"
            h_goals = 2 if is_home else 0
            a_goals = 0 if is_home else 2
            upsert_match(
                db, source="test", source_match_id=f"xseason-{i}",
                date=str(match_date), home_team_id=h_id, away_team_id=a_id,
                home_goals_90min=h_goals, away_goals_90min=a_goals,
                home_goals_final=h_goals, away_goals_final=a_goals,
                decided_in="REGULAR", result_90min=result_code, result_final=result_code,
                competition_id="DED", competition_name="Eredivisie",
                competition_type="LEAGUE", season=season,
            )
        matches = _get_matches_desc(db, team_id)
        result = find_last_streak(matches, team_id)
        assert result["found"] is True
        assert result["streak_length"] == 6


# === _team_result tests ===

class TestTeamResult:
    def test_home_win(self, db, team_id, opponent_id):
        """Home win: result H, team is home -> W."""
        _make_match(db, team_id, opponent_id, date(2026, 1, 1), 3, 0, is_home=True)
        match = _get_matches_desc(db, team_id)[0]
        assert _team_result(match, team_id) == "W"

    def test_home_loss(self, db, team_id, opponent_id):
        """Home loss: result A, team is home -> L."""
        _make_match(db, team_id, opponent_id, date(2026, 1, 1), 0, 2, is_home=True)
        match = _get_matches_desc(db, team_id)[0]
        assert _team_result(match, team_id) == "L"

    def test_away_win(self, db, team_id, opponent_id):
        """Away win: result A, team is away -> W."""
        _make_match(db, team_id, opponent_id, date(2026, 1, 1), 2, 0, is_home=False)
        match = _get_matches_desc(db, team_id)[0]
        assert _team_result(match, team_id) == "W"

    def test_away_loss(self, db, team_id, opponent_id):
        """Away loss: result H, team is away -> L."""
        _make_match(db, team_id, opponent_id, date(2026, 1, 1), 0, 1, is_home=False)
        match = _get_matches_desc(db, team_id)[0]
        assert _team_result(match, team_id) == "L"

    def test_draw(self, db, team_id, opponent_id):
        """Draw: result D -> D regardless of home/away."""
        _make_match(db, team_id, opponent_id, date(2026, 1, 1), 1, 1, is_home=True)
        match = _get_matches_desc(db, team_id)[0]
        assert _team_result(match, team_id) == "D"
        assert _team_result(match, opponent_id) == "D"

    def test_result_final_field(self, db, team_id, opponent_id):
        """Can use result_final instead of result_90min."""
        pen_date = date(2026, 1, 1)
        upsert_match(
            db, source="test", source_match_id="pen-test",
            date=str(pen_date), home_team_id=team_id, away_team_id=opponent_id,
            home_goals_90min=1, away_goals_90min=1,
            home_goals_final=1, away_goals_final=1,
            home_goals_penalties=4, away_goals_penalties=3,
            decided_in="PENALTIES",
            result_90min="D", result_final="H",
            competition_id="KNVB", competition_name="KNVB Beker",
            competition_type="DOMESTIC_CUP", season="2025-26",
        )
        match = _get_matches_desc(db, team_id)[0]
        assert _team_result(match, team_id, "result_90min") == "D"
        assert _team_result(match, team_id, "result_final") == "W"


# === Cross-competition tests ===

class TestCrossCompetition:
    def test_mixed_competitions_count(self, db, team_id, opponent_id):
        """Wins across different competitions form a streak."""
        start = date(2026, 1, 1)
        comps = ["DED", "CL", "DED", "KNVB", "DED"]
        for i, comp in enumerate(comps):
            _make_match(db, team_id, opponent_id,
                       start - timedelta(days=i * 4),
                       3, 1, competition_id=comp, competition_name=comp)
        matches = _get_matches_desc(db, team_id)
        result = find_last_streak(matches, team_id)
        assert result["found"] is True
        assert len(result["competitions_in_streak"]) > 1


# === Penalty/AET tests ===

class TestPenaltyResults:
    def test_draw_90min_breaks_streak(self, db, team_id, opponent_id):
        """A match that went to pens is a draw after 90 min — breaks the streak."""
        start = date(2026, 1, 1)
        # 4 wins, then a penalty match (draw at 90), then more wins
        for i in range(4):
            _make_match(db, team_id, opponent_id,
                       start - timedelta(days=i * 7), 2, 0)

        # Penalty match: 1-1 at 90 min, team wins on pens
        pen_date = start - timedelta(days=28)
        h_id = team_id
        a_id = opponent_id
        upsert_match(
            db, source="test", source_match_id="pen-match",
            date=str(pen_date), home_team_id=h_id, away_team_id=a_id,
            home_goals_90min=1, away_goals_90min=1,
            home_goals_final=2, away_goals_final=2,
            home_goals_penalties=4, away_goals_penalties=3,
            decided_in="PENALTIES",
            result_90min="D",  # draw at 90 min
            result_final="H",  # home team won pens
            competition_id="KNVB", competition_name="KNVB Beker",
            competition_type="DOMESTIC_CUP", season="2025-26",
        )

        # 5 more wins before that
        for i in range(5):
            _make_match(db, team_id, opponent_id,
                       pen_date - timedelta(days=(i + 1) * 7), 3, 0,
                       match_id=f"old-{i}")

        matches = _get_matches_desc(db, team_id)

        # Official index (90 min): the penalty draw breaks the streak
        result_90 = find_last_streak(matches, team_id, result_field="result_90min")
        assert result_90["found"] is True
        assert result_90["streak_length"] == 5  # the 5 wins BEFORE the pen match

        # Fan index (final result): penalty win counts as win
        result_final = find_last_streak(matches, team_id, result_field="result_final")
        assert result_final["found"] is True
        assert result_final["streak_length"] >= 5


# === Hair tier tests ===

class TestHairTiers:
    def test_fresh_cut(self):
        assert get_hair_tier(0) == ("Fresh cut", "Clean buzzcut, fresh fade")
        assert get_hair_tier(14) == ("Fresh cut", "Clean buzzcut, fresh fade")

    def test_growing_back(self):
        name, _ = get_hair_tier(30)
        assert name == "Growing back"

    def test_caveman(self):
        name, _ = get_hair_tier(400)
        assert name == "Caveman"

    def test_sasquatch(self):
        name, _ = get_hair_tier(600)
        assert name == "Sasquatch"

    def test_lost_in_time(self):
        name, _ = get_hair_tier(None)
        assert name == "Lost in time"


# === Database tests ===

class TestDatabase:
    def test_init_db(self, db):
        tables = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        table_names = {t["name"] for t in tables}
        assert "teams" in table_names
        assert "matches" in table_names
        assert "data_sources" in table_names

    def test_upsert_team_idempotent(self, db):
        id1 = upsert_team(db, wf_slug="afc-ajax", name="Ajax", short_name="AJX")
        id2 = upsert_team(db, wf_slug="afc-ajax", name="AFC Ajax", short_name="AJX")
        assert id1 == id2
        # Name should be updated
        row = db.execute("SELECT name FROM teams WHERE id = ?", (id1,)).fetchone()
        assert row["name"] == "AFC Ajax"

    def test_upsert_match_dedup(self, db, team_id, opponent_id):
        kwargs = dict(
            source="test", source_match_id="m1", date="2026-01-01",
            home_team_id=team_id, away_team_id=opponent_id,
            home_goals_90min=2, away_goals_90min=0,
            home_goals_final=2, away_goals_final=0,
            decided_in="REGULAR", result_90min="H", result_final="H",
            competition_id="DED", competition_name="Eredivisie",
            competition_type="LEAGUE", season="2025-26",
        )
        r1 = upsert_match(db, **kwargs)
        r2 = upsert_match(db, **kwargs)  # duplicate
        assert r1 is not None
        assert r2 is None  # ignored
        count = db.execute("SELECT COUNT(*) FROM matches").fetchone()[0]
        assert count == 1
