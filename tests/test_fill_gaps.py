"""Tests for fill_gaps — API-Football import and gap detection."""

import sqlite3

import pytest

from scripts.db import get_connection, init_db, upsert_match, upsert_team
from scripts.fill_gaps import (
    _compute_result,
    _league_id_to_code,
    _map_league_type,
    _map_status_to_decided_in,
    _season_label,
    find_gaps,
    import_api_football_fixture,
)


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    init_db(conn)
    return conn


@pytest.fixture
def team_psv(db):
    return upsert_team(
        db, football_data_id=674, name="PSV", short_name="PSV",
        country="NL", current_league="DED", api_football_id=197,
    )


@pytest.fixture
def team_ajax(db):
    return upsert_team(
        db, football_data_id=678, name="AFC Ajax", short_name="AJX",
        country="NL", current_league="DED", api_football_id=194,
    )


# === Helper function tests ===

class TestHelpers:
    def test_compute_result(self):
        assert _compute_result(3, 1) == "H"
        assert _compute_result(1, 3) == "A"
        assert _compute_result(2, 2) == "D"

    def test_map_status(self):
        assert _map_status_to_decided_in("FT") == "REGULAR"
        assert _map_status_to_decided_in("AET") == "EXTRA_TIME"
        assert _map_status_to_decided_in("PEN") == "PENALTIES"

    def test_map_league_type(self):
        assert _map_league_type("League") == "LEAGUE"
        assert _map_league_type("Cup") == "DOMESTIC_CUP"

    def test_season_label(self):
        assert _season_label(2025) == "2025-26"
        assert _season_label(2023) == "2023-24"

    def test_league_id_to_code(self):
        assert _league_id_to_code(88, "Eredivisie") == "DED"
        assert _league_id_to_code(90, "KNVB Beker") == "KNVB"
        assert _league_id_to_code(2, "Champions League") == "CL"
        assert _league_id_to_code(3, "Europa League") == "EL"
        assert _league_id_to_code(9999, "Unknown") == "AF_9999"


# === Fixture import tests ===

class TestImportFixture:
    def _make_fixture(self, fixture_id=12345, status="FT",
                      home_id=197, home_name="PSV",
                      away_id=194, away_name="AFC Ajax",
                      goals_home=2, goals_away=1,
                      ft_home=2, ft_away=1,
                      et_home=None, et_away=None,
                      pen_home=None, pen_away=None,
                      league_id=90, league_name="KNVB Beker",
                      league_type="Cup", season=2025,
                      match_round="Quarter-finals",
                      date="2025-12-15T20:00:00+00:00"):
        """Build a realistic API-Football fixture object."""
        return {
            "fixture": {
                "id": fixture_id,
                "date": date,
                "status": {"short": status},
            },
            "league": {
                "id": league_id,
                "name": league_name,
                "type": league_type,
                "country": "Netherlands",
                "season": season,
                "round": match_round,
            },
            "teams": {
                "home": {"id": home_id, "name": home_name},
                "away": {"id": away_id, "name": away_name},
            },
            "goals": {"home": goals_home, "away": goals_away},
            "score": {
                "halftime": {"home": 1, "away": 0},
                "fulltime": {"home": ft_home, "away": ft_away},
                "extratime": {"home": et_home, "away": et_away} if et_home is not None else None,
                "penalty": {"home": pen_home, "away": pen_away} if pen_home is not None else None,
            },
        }

    def test_import_regular_cup_match(self, db, team_psv, team_ajax):
        """Import a normal cup match (no AET/pens)."""
        fixture = self._make_fixture()
        result = import_api_football_fixture(db, fixture)
        assert result is not None

        match = db.execute("SELECT * FROM matches WHERE source = 'api-football'").fetchone()
        assert match is not None
        assert match["competition_id"] == "KNVB"
        assert match["competition_type"] == "DOMESTIC_CUP"
        assert match["home_goals_90min"] == 2
        assert match["away_goals_90min"] == 1
        assert match["result_90min"] == "H"
        assert match["result_final"] == "H"
        assert match["decided_in"] == "REGULAR"
        assert match["season"] == "2025-26"
        assert match["round"] == "Quarter-finals"

    def test_import_penalty_match(self, db, team_psv, team_ajax):
        """Import a match decided on penalties."""
        fixture = self._make_fixture(
            status="PEN",
            goals_home=2, goals_away=2,  # After AET
            ft_home=1, ft_away=1,         # 90 min score
            et_home=1, et_away=1,          # Extra time goals
            pen_home=4, pen_away=3,        # PSV wins on pens
        )
        result = import_api_football_fixture(db, fixture)
        assert result is not None

        match = db.execute("SELECT * FROM matches WHERE source = 'api-football'").fetchone()
        assert match["decided_in"] == "PENALTIES"
        assert match["result_90min"] == "D"  # 1-1 after 90 min
        assert match["result_final"] == "H"  # PSV wins pens
        assert match["home_goals_90min"] == 1
        assert match["away_goals_90min"] == 1
        assert match["home_goals_penalties"] == 4
        assert match["away_goals_penalties"] == 3

    def test_import_aet_match(self, db, team_psv, team_ajax):
        """Import a match decided in extra time."""
        fixture = self._make_fixture(
            status="AET",
            goals_home=2, goals_away=1,
            ft_home=1, ft_away=1,
            et_home=1, et_away=0,
        )
        result = import_api_football_fixture(db, fixture)
        assert result is not None

        match = db.execute("SELECT * FROM matches WHERE source = 'api-football'").fetchone()
        assert match["decided_in"] == "EXTRA_TIME"
        assert match["result_90min"] == "D"  # 1-1 at 90 min
        assert match["result_final"] == "H"  # PSV wins in AET

    def test_dedup_across_imports(self, db, team_psv, team_ajax):
        """Same fixture imported twice should not duplicate."""
        fixture = self._make_fixture()
        r1 = import_api_football_fixture(db, fixture)
        r2 = import_api_football_fixture(db, fixture)
        assert r1 is not None
        assert r2 is None
        count = db.execute("SELECT COUNT(*) FROM matches WHERE source = 'api-football'").fetchone()[0]
        assert count == 1

    def test_skip_non_finished(self, db, team_psv, team_ajax):
        """Non-finished matches should be skipped."""
        fixture = self._make_fixture(status="NS")  # Not started
        result = import_api_football_fixture(db, fixture)
        assert result is None

    def test_import_champions_league(self, db, team_psv, team_ajax):
        """CL match should have competition_type CONTINENTAL."""
        fixture = self._make_fixture(
            league_id=2, league_name="Champions League", league_type="Cup"
        )
        result = import_api_football_fixture(db, fixture)
        assert result is not None

        match = db.execute("SELECT * FROM matches WHERE source = 'api-football'").fetchone()
        assert match["competition_type"] == "CONTINENTAL"
        assert match["competition_id"] == "CL"

    def test_import_creates_unknown_team(self, db):
        """Importing a match with unknown teams should create them."""
        fixture = self._make_fixture(
            home_id=9999, home_name="Unknown FC",
            away_id=9998, away_name="Mystery United",
        )
        result = import_api_football_fixture(db, fixture)
        assert result is not None

        # Check teams were created
        home = db.execute("SELECT * FROM teams WHERE api_football_id = 9999").fetchone()
        assert home is not None
        assert home["name"] == "Unknown FC"

        away = db.execute("SELECT * FROM teams WHERE api_football_id = 9998").fetchone()
        assert away is not None
        assert away["name"] == "Mystery United"


# === Gap detection tests ===

class TestGapDetection:
    def test_detect_missing_cups(self, db, team_psv, team_ajax):
        """Should detect missing cup data."""
        # Add a league match so teams exist with current_league
        upsert_match(
            db, source="football-data.org", source_match_id="league-1",
            date="2025-09-01", home_team_id=team_psv, away_team_id=team_ajax,
            home_goals_90min=2, away_goals_90min=0, home_goals_final=2, away_goals_final=0,
            decided_in="REGULAR", result_90min="H", result_final="H",
            competition_id="DED", competition_name="Eredivisie",
            competition_type="LEAGUE", season="2025-26",
        )

        gaps = find_gaps(db, "DED", ["2025-26"])
        assert "KNVB" in gaps
        assert "2025-26" in gaps["KNVB"]

    def test_no_gap_when_cups_present(self, db, team_psv, team_ajax):
        """No gap when cup matches exist."""
        upsert_match(
            db, source="api-football", source_match_id="cup-1",
            date="2025-10-15", home_team_id=team_psv, away_team_id=team_ajax,
            home_goals_90min=3, away_goals_90min=1, home_goals_final=3, away_goals_final=1,
            decided_in="REGULAR", result_90min="H", result_final="H",
            competition_id="KNVB", competition_name="KNVB Beker",
            competition_type="DOMESTIC_CUP", season="2025-26",
        )

        gaps = find_gaps(db, "DED", ["2025-26"])
        assert "KNVB" not in gaps

    def test_no_teams_no_gaps(self, db):
        """No teams = no gaps to detect."""
        gaps = find_gaps(db, "DED", ["2025-26"])
        assert gaps == {}
