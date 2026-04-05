"""One-off: merge ghost teams created by football-data.org into canonical teams.

Ghost teams were created because FD uses different team names/IDs than our registry.
This script:
1. Maps each ghost team to its canonical counterpart
2. Reassigns matches (deleting duplicates where both sources have the same match)
3. Deletes the ghost team
"""

import logging
from scripts.db import get_connection

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# ghost_id → canonical_id
MERGE_MAP = {
    # DED ghosts
    1103: 10,   # Go Ahead Eagles (FD fd=718) → Go Ahead Eagles (id=10)
    1104: 3,    # SBV Excelsior (FD fd=670) → Excelsior (id=3)
    1105: 14,   # NAC Breda (FD fd=681) → NAC Breda (id=14)
    1106: 18,   # Telstar 1963 (FD fd=1912) → Telstar (id=18)
    # BL ghosts
    1107: 258,  # 1. FC Union Berlin (FD fd=28) → 1. FC Union Berlin (id=258)
    1108: 256,  # 1. FC Heidenheim 1846 (FD fd=44) → 1. FC Heidenheim 1846 (id=256)
    # SA ghosts
    1109: 304,  # US Cremonese (FD fd=457) → US Cremonese (id=304)
    1110: 295,  # Como 1907 (FD fd=7397) → Como 1907 (id=295)
    1111: 300,  # AC Pisa 1909 (FD fd=487) → Pisa SC (id=300)
    # LL ghosts
    1112: 288,  # Real Oviedo (FD fd=1048) → Real Oviedo (id=288)
    # L1 ghosts
    1113: 312,  # Le Havre AC (FD fd=533) → Havre AC (id=312)
    1114: 309,  # FC Lorient (FD fd=525) → FC Lorient (id=309)
    # CL/European ghosts
    1124: 38,   # Galatasaray SK (FD fd=610) → Galatasaray (id=38)
}

# Also fix: NEC (id=13, canonical N.E.C.) got a ghost "NEC" somewhere
# Team 10 was already fixed to Go Ahead Eagles above


def main():
    conn = get_connection()
    total_reassigned = 0
    total_deleted_dupes = 0
    total_ghosts_removed = 0

    for ghost_id, canonical_id in MERGE_MAP.items():
        # Check ghost exists
        ghost = conn.execute("SELECT name FROM teams WHERE id = ?", (ghost_id,)).fetchone()
        canonical = conn.execute("SELECT name FROM teams WHERE id = ?", (canonical_id,)).fetchone()
        if not ghost:
            log.info(f"  Ghost {ghost_id} not found, skipping")
            continue
        log.info(f"Merging {ghost['name']} (id={ghost_id}) → {canonical['name']} (id={canonical_id})")

        # Find matches that would be duplicates after reassignment
        # (same date + same opponent, different team IDs from different sources)
        for role, other_role in [("home_team_id", "away_team_id"), ("away_team_id", "home_team_id")]:
            # Delete FD matches that already exist as WF matches for the canonical team
            dupes = conn.execute(f"""
                SELECT m_ghost.id FROM matches m_ghost
                JOIN matches m_canon ON m_canon.date = m_ghost.date
                    AND m_canon.{other_role} = m_ghost.{other_role}
                    AND m_canon.{role} = ?
                WHERE m_ghost.{role} = ?
            """, (canonical_id, ghost_id)).fetchall()

            if dupes:
                dupe_ids = [d["id"] for d in dupes]
                for did in dupe_ids:
                    conn.execute("DELETE FROM matches WHERE id = ?", (did,))
                total_deleted_dupes += len(dupe_ids)
                log.info(f"  Deleted {len(dupe_ids)} duplicate matches")

            # Reassign remaining (non-duplicate) matches
            result = conn.execute(
                f"UPDATE matches SET {role} = ? WHERE {role} = ?",
                (canonical_id, ghost_id)
            )
            if hasattr(result, 'rowcount') and result.rowcount:
                total_reassigned += result.rowcount
                log.info(f"  Reassigned {result.rowcount} matches ({role})")

        # Delete ghost team
        conn.execute("DELETE FROM teams WHERE id = ?", (ghost_id,))
        total_ghosts_removed += 1
        conn.commit()

    # Also update FD IDs on canonical teams with the correct values from ghosts
    fd_corrections = {
        10: 718,    # Go Ahead Eagles
        3: 670,     # Excelsior
        14: 681,    # NAC Breda
        18: 1912,   # Telstar
        258: 28,    # 1. FC Union Berlin
        256: 44,    # 1. FC Heidenheim
        304: 457,   # US Cremonese
        295: 7397,  # Como 1907
        300: 487,   # Pisa SC (AC Pisa 1909)
        288: 1048,  # Real Oviedo
        312: 533,   # Havre AC (Le Havre AC)
        309: 525,   # FC Lorient
        38: 610,    # Galatasaray
    }
    for team_id, correct_fd_id in fd_corrections.items():
        conn.execute("UPDATE teams SET football_data_id = ? WHERE id = ?", (correct_fd_id, team_id))
    conn.commit()
    log.info(f"Updated {len(fd_corrections)} teams with correct FD IDs")

    log.info(f"\nDone: {total_ghosts_removed} ghosts removed, {total_deleted_dupes} dupes deleted, {total_reassigned} matches reassigned")
    conn.close()


if __name__ == "__main__":
    main()
