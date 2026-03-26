"""Tests for the team registry — name resolution and data integrity."""

import pytest

from scripts.team_registry import ALIASES, TEAMS, resolve_team_name


class TestResolveTeamName:
    def test_canonical_name_unchanged(self):
        """A canonical name should resolve to itself."""
        assert resolve_team_name("Ajax") == "Ajax"
        assert resolve_team_name("PSV Eindhoven") == "PSV Eindhoven"
        assert resolve_team_name("Feyenoord") == "Feyenoord"

    def test_nec_alias(self):
        """NEC should resolve to N.E.C."""
        assert resolve_team_name("NEC") == "N.E.C."
        assert resolve_team_name("NEC Nijmegen") == "N.E.C."
        assert resolve_team_name("Nijmegen") == "N.E.C."

    def test_ajax_alias(self):
        """AFC Ajax should resolve to Ajax."""
        assert resolve_team_name("AFC Ajax") == "Ajax"
        assert resolve_team_name("Ajax Amsterdam") == "Ajax"
        # Canonical stays canonical
        assert resolve_team_name("Ajax") == "Ajax"

    def test_psv_alias(self):
        """PSV should resolve to PSV Eindhoven."""
        assert resolve_team_name("PSV") == "PSV Eindhoven"

    def test_feyenoord_alias(self):
        """Feyenoord Rotterdam should resolve to Feyenoord."""
        assert resolve_team_name("Feyenoord Rotterdam") == "Feyenoord"

    def test_unknown_name_passthrough(self):
        """Unknown names should pass through unchanged."""
        assert resolve_team_name("Real Madrid") == "Real Madrid"
        assert resolve_team_name("Bayern Munich") == "Bayern Munich"

    def test_eerste_divisie_aliases(self):
        """Eerste Divisie aliases should resolve correctly."""
        assert resolve_team_name("Cambuur") == "SC Cambuur"
        assert resolve_team_name("VVV") == "VVV-Venlo"
        assert resolve_team_name("Roda JC") == "Roda JC Kerkrade"
        assert resolve_team_name("Waalwijk") == "RKC Waalwijk"


class TestTeamsRegistry:
    def test_all_entries_have_valid_tuples(self):
        """Every TEAMS entry must have a (wf_id, slug, league) tuple."""
        for name, value in TEAMS.items():
            assert isinstance(value, tuple), f"{name}: value is not a tuple"
            assert len(value) == 3, f"{name}: tuple has {len(value)} elements, expected 3"
            wf_id, slug, league = value
            assert isinstance(wf_id, str), f"{name}: wf_id should be str, got {type(wf_id)}"
            assert wf_id.startswith("te"), f"{name}: wf_id '{wf_id}' should start with 'te'"
            assert isinstance(slug, str), f"{name}: slug should be str"
            assert len(slug) > 0, f"{name}: slug is empty"
            assert league in ("DED", "JE"), f"{name}: league '{league}' not in (DED, JE)"

    def test_aliases_point_to_canonical_names(self):
        """Every alias must resolve to a name that exists in TEAMS."""
        for alias, canonical in ALIASES.items():
            assert canonical in TEAMS, (
                f"Alias '{alias}' -> '{canonical}' but '{canonical}' is not in TEAMS"
            )

    def test_no_alias_is_also_canonical(self):
        """An alias key should not also be a canonical team name (would be ambiguous)."""
        for alias in ALIASES:
            # It's okay if an alias happens to match a canonical name
            # as long as it maps to itself. But if it maps elsewhere, that's a bug.
            if alias in TEAMS:
                assert ALIASES[alias] == alias, (
                    f"'{alias}' is both a canonical name and an alias to '{ALIASES[alias]}'"
                )

    def test_eredivisie_team_count(self):
        """Should have 18 Eredivisie teams (standard league size)."""
        ered_teams = [n for n, (_, _, league) in TEAMS.items() if league == "DED"]
        assert len(ered_teams) == 18, f"Expected 18 Eredivisie teams, got {len(ered_teams)}: {ered_teams}"

    def test_eerste_divisie_team_count(self):
        """Should have 16 Eerste Divisie teams."""
        je_teams = [n for n, (_, _, league) in TEAMS.items() if league == "JE"]
        assert len(je_teams) == 16, f"Expected 16 Eerste Divisie teams, got {len(je_teams)}: {je_teams}"
