"""One-off script: populate football_data_id and api_football_id in Neon from team_registry."""

import logging
from scripts.db import get_connection
from scripts.team_registry import TEAMS, EXTERNAL_IDS

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def main():
    conn = get_connection()
    updated = 0

    for name, (wf_id, slug, league) in TEAMS.items():
        ext = EXTERNAL_IDS.get(name, {})
        fd_id = ext.get("fd")
        af_id = ext.get("af")

        if not fd_id and not af_id:
            continue

        sets = []
        vals = []
        if fd_id:
            sets.append("football_data_id = ?")
            vals.append(fd_id)
        if af_id:
            sets.append("api_football_id = ?")
            vals.append(af_id)

        vals.append(name)
        sql = f"UPDATE teams SET {', '.join(sets)} WHERE name = ?"
        cur = conn.execute(sql, vals)
        if cur.rowcount and cur.rowcount > 0:
            updated += 1
            log.info(f"  {name}: fd={fd_id}, af={af_id}")

    conn.commit()
    log.info(f"Updated {updated} teams with external IDs.")
    conn.close()


if __name__ == "__main__":
    main()
