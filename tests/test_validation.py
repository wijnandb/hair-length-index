"""Tests for data validation checks."""

import sqlite3

import pytest

from scripts.db import init_db, upsert_match, upsert_team
from scripts.validate_data import (
    ValidationResult,
    check_competition_limits,
    check_cup_elimination,
    check_same_day_matches,
)


@pytest.fixture
def db():
    """In-memory SQLite database for testing."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    init_db(conn)
    return conn


@pytest.fixture
def team_a(db):
    return upsert_team(db, name="Team A", short_name="TMA", country="NL", current_league="DED")


@pytest.fixture
def team_b(db):
    return upsert_team(db, name="Team B", short_name="TMB", country="NL", current_league="DED")


def _insert_match(db, home_id, away_id, match_date, home_goals, away_goals,
                  comp_id="DED", comp_name="Eredivisie", comp_type="LEAGUE",
                  season="2025-26", decided_in="REGULAR", result_final=None,
                  source_id=None):
    """Helper to insert a match for validation tests."""
    if home_goals > away_goals:
        result = "H"
    elif away_goals > home_goals:
        result = "A"
    else:
        result = "D"

    if result_final is None:
        result_final = result

    if source_id is None:
        source_id = f"val-{match_date}-{home_id}-{away_id}"

    upsert_match(
        db, source="test", source_match_id=source_id,
        date=match_date, home_team_id=home_id, away_team_id=away_id,
        home_goals_90min=home_goals, away_goals_90min=away_goals,
        home_goals_final=home_goals, away_goals_final=away_goals,
        decided_in=decided_in, result_90min=result, result_final=result_final,
        competition_id=comp_id, competition_name=comp_name,
        competition_type=comp_type, season=season,
    )


class TestCompetitionLimits:
    def test_knvb_over_seven_flagged(self, db, team_a, team_b):
        """KNVB Beker > 7 matches per team per season should be flagged as error."""
        for i in range(8):
            _insert_match(db, team_a, team_b, f"2025-10-{10 + i:02d}",
                          2, 1, comp_id="KNVB", comp_name="KNVB Beker",
                          comp_type="DOMESTIC_CUP", source_id=f"knvb-{i}")

        result = ValidationResult()
        check_competition_limits(db, "DED", result)
        assert len(result.errors) > 0
        assert any("KNVB" in e and "max 7" in e for e in result.errors)

    def test_knvb_within_limit_ok(self, db, team_a, team_b):
        """KNVB Beker <= 7 matches should not trigger errors."""
        for i in range(5):
            _insert_match(db, team_a, team_b, f"2025-10-{10 + i:02d}",
                          2, 1, comp_id="KNVB", comp_name="KNVB Beker",
                          comp_type="DOMESTIC_CUP", source_id=f"knvb-ok-{i}")

        result = ValidationResult()
        check_competition_limits(db, "DED", result)
        knvb_errors = [e for e in result.errors if "KNVB" in e]
        assert len(knvb_errors) == 0


class TestCupElimination:
    def test_multiple_cup_losses_flagged(self, db, team_a, team_b):
        """A team losing twice in the same cup season should be flagged."""
        # First loss
        _insert_match(db, team_a, team_b, "2025-10-15",
                      0, 2, comp_id="KNVB", comp_name="KNVB Beker",
                      comp_type="DOMESTIC_CUP", source_id="cup-loss-1")
        # Second loss (impossible in knockout)
        _insert_match(db, team_a, team_b, "2025-11-20",
                      1, 3, comp_id="KNVB", comp_name="KNVB Beker",
                      comp_type="DOMESTIC_CUP", source_id="cup-loss-2")

        result = ValidationResult()
        check_cup_elimination(db, "DED", result)
        assert len(result.errors) > 0
        assert any("cup losses" in e for e in result.errors)

    def test_single_cup_loss_ok(self, db, team_a, team_b):
        """A single cup loss is normal (knocked out)."""
        _insert_match(db, team_a, team_b, "2025-10-15",
                      2, 0, comp_id="KNVB", comp_name="KNVB Beker",
                      comp_type="DOMESTIC_CUP", source_id="cup-win-1")
        _insert_match(db, team_a, team_b, "2025-11-20",
                      0, 1, comp_id="KNVB", comp_name="KNVB Beker",
                      comp_type="DOMESTIC_CUP", source_id="cup-loss-only")

        result = ValidationResult()
        check_cup_elimination(db, "DED", result)
        cup_loss_errors = [e for e in result.errors if "cup losses" in e]
        assert len(cup_loss_errors) == 0


class TestSameDayMatches:
    def test_same_day_flagged(self, db, team_a, team_b):
        """A team playing twice on the same day should be flagged."""
        _insert_match(db, team_a, team_b, "2025-10-15",
                      2, 0, comp_id="DED", comp_name="Eredivisie",
                      source_id="same-day-1")
        # Need a different opponent for same day (unique constraint: date+home+away)
        team_c = upsert_team(db, name="Team C", short_name="TMC", country="NL", current_league="DED")
        _insert_match(db, team_a, team_c, "2025-10-15",
                      1, 1, comp_id="KNVB", comp_name="KNVB Beker",
                      comp_type="DOMESTIC_CUP", source_id="same-day-2")

        result = ValidationResult()
        check_same_day_matches(db, "DED", result)
        assert len(result.errors) > 0
        assert any("plays twice" in e for e in result.errors)

    def test_different_days_ok(self, db, team_a, team_b):
        """Matches on different days should not be flagged."""
        _insert_match(db, team_a, team_b, "2025-10-15",
                      2, 0, source_id="diff-day-1")
        _insert_match(db, team_a, team_b, "2025-10-22",
                      1, 0, source_id="diff-day-2")

        result = ValidationResult()
        check_same_day_matches(db, "DED", result)
        assert len(result.errors) == 0
