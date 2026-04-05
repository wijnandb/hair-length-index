"""Tests for scripts.fetch_standings module."""

import json
from unittest.mock import MagicMock, patch

import pytest

from scripts.fetch_standings import (
    FD_TO_INTERNAL,
    INTERNAL_TO_FD,
    STANDINGS_LEAGUES,
    _season_label,
    fetch_standings,
)


def test_fd_to_internal_mapping():
    """All football-data.org codes map to internal codes."""
    assert FD_TO_INTERNAL["DED"] == "DED"
    assert FD_TO_INTERNAL["PL"] == "PL"
    assert FD_TO_INTERNAL["BL1"] == "BL"
    assert FD_TO_INTERNAL["SA"] == "SA"
    assert FD_TO_INTERNAL["PD"] == "LL"
    assert FD_TO_INTERNAL["FL1"] == "L1"


def test_internal_to_fd_mapping():
    """Internal codes reverse-map to football-data.org codes."""
    assert INTERNAL_TO_FD["DED"] == "DED"
    assert INTERNAL_TO_FD["BL"] == "BL1"
    assert INTERNAL_TO_FD["LL"] == "PD"
    assert INTERNAL_TO_FD["L1"] == "FL1"


def test_season_label():
    assert _season_label(2025) == "2025-26"
    assert _season_label(2024) == "2024-25"


def test_standings_leagues_complete():
    """All expected leagues are in the fetch list."""
    assert set(STANDINGS_LEAGUES) == {"DED", "PL", "BL1", "SA", "PD", "FL1"}


def _mock_api_response():
    """Return a realistic football-data.org standings response."""
    return {
        "season": {"startDate": "2025-08-08"},
        "standings": [
            {
                "type": "TOTAL",
                "table": [
                    {
                        "position": 1,
                        "team": {"id": 674, "name": "PSV"},
                        "playedGames": 29,
                        "won": 22,
                        "draw": 4,
                        "lost": 3,
                        "goalsFor": 71,
                        "goalsAgainst": 22,
                        "goalDifference": 49,
                        "points": 70,
                    },
                    {
                        "position": 2,
                        "team": {"id": 678, "name": "AFC Ajax"},
                        "playedGames": 29,
                        "won": 20,
                        "draw": 5,
                        "lost": 4,
                        "goalsFor": 68,
                        "goalsAgainst": 30,
                        "goalDifference": 38,
                        "points": 65,
                    },
                ],
            },
            {
                "type": "HOME",
                "table": [],
            },
        ],
    }


def test_fetch_standings_parses_response():
    """fetch_standings correctly parses the API response into our schema."""
    client = MagicMock()
    client._get.return_value = _mock_api_response()

    result = fetch_standings(client, "DED")

    assert result is not None
    assert result["league"] == "DED"
    assert result["season"] == "2025-26"
    assert "generated_at" in result
    assert len(result["table"]) == 2

    psv = result["table"][0]
    assert psv["position"] == 1
    assert psv["team"] == "PSV"
    assert psv["team_id"] == 674
    assert psv["played"] == 29
    assert psv["won"] == 22
    assert psv["drawn"] == 4
    assert psv["lost"] == 3
    assert psv["goals_for"] == 71
    assert psv["goals_against"] == 22
    assert psv["goal_difference"] == 49
    assert psv["points"] == 70


def test_fetch_standings_uses_total_type():
    """Selects TOTAL standings, not HOME or AWAY."""
    client = MagicMock()
    client._get.return_value = _mock_api_response()

    result = fetch_standings(client, "DED")
    # Should have 2 teams from TOTAL, not 0 from HOME
    assert len(result["table"]) == 2


def test_fetch_standings_maps_league_code():
    """BL1 maps to internal code BL."""
    client = MagicMock()
    client._get.return_value = _mock_api_response()

    result = fetch_standings(client, "BL1")
    assert result["league"] == "BL"


def test_fetch_standings_empty_response():
    """Returns None when no standings data."""
    client = MagicMock()
    client._get.return_value = {"standings": []}

    result = fetch_standings(client, "DED")
    assert result is None
