"""Post to Reddit via PRAW.

Reads social-queue.json, generates Reddit-formatted text (markdown tables,
detailed stats), and posts to relevant subreddits. Tracks posted items.

Reddit API setup:
1. Go to https://www.reddit.com/prefs/apps
2. Create a "script" type app
3. Set redirect URI to http://localhost:8080
4. Save client_id and client_secret to .env

Usage:
    python -m scripts.post_reddit                     # post all queued items
    python -m scripts.post_reddit --dry-run            # preview without posting
    python -m scripts.post_reddit --test "Hello!"      # post a test to own profile
"""

import argparse
import hashlib
import json
import logging
import os
from datetime import datetime
from pathlib import Path

import praw

from scripts.config import DATA_DIR

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

QUEUE_FILE = DATA_DIR / "social-queue.json"
POSTED_FILE = DATA_DIR / "reddit-posted.json"

# Subreddit routing per league
SUBREDDIT_MAP = {
    "DED": ["Eredivisie"],
    "JE": ["Eredivisie"],
    "PL": ["PremierLeague"],
    "BL": ["Bundesliga"],
    "LL": ["LaLiga"],
    "SA": ["CalcioItaliano"],
    "L1": ["Ligue1"],
}

# All football events also go to r/soccer for big events
BIG_EVENT_TYPES = {"barber_alert", "weekly_summary"}

URL = "https://wijnandb.github.io/hair-length-index/"


def get_client() -> praw.Reddit:
    """Create authenticated Reddit client."""
    client_id = os.environ.get("REDDIT_CLIENT_ID", "")
    client_secret = os.environ.get("REDDIT_CLIENT_SECRET", "")
    username = os.environ.get("REDDIT_USERNAME", "")
    password = os.environ.get("REDDIT_PASSWORD", "")

    if not all([client_id, client_secret, username, password]):
        # Try .env file
        env_path = Path(__file__).parent.parent / ".env"
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                if "=" in line and not line.startswith("#"):
                    key, val = line.strip().split("=", 1)
                    if key == "REDDIT_CLIENT_ID":
                        client_id = val
                    elif key == "REDDIT_CLIENT_SECRET":
                        client_secret = val
                    elif key == "REDDIT_USERNAME":
                        username = val
                    elif key == "REDDIT_PASSWORD":
                        password = val

    if not all([client_id, client_secret, username, password]):
        raise ValueError(
            "REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USERNAME, "
            "REDDIT_PASSWORD must be set in .env or environment"
        )

    reddit = praw.Reddit(
        client_id=client_id,
        client_secret=client_secret,
        username=username,
        password=password,
        user_agent="HairLengthIndex/1.0 (by /u/{})".format(username),
    )
    log.info(f"Logged in as /u/{reddit.user.me()}")
    return reddit


def load_posted() -> dict:
    if POSTED_FILE.exists():
        with open(POSTED_FILE) as f:
            return json.load(f)
    return {}


def save_posted(posted: dict):
    POSTED_FILE.write_text(json.dumps(posted, indent=2))


def item_id(item: dict, subreddit: str) -> str:
    key = f"reddit-{subreddit}-{item.get('type', '')}-{item.get('team', '')}-{item.get('league', '')}"
    return hashlib.md5(key.encode()).hexdigest()[:12]


def generate_reddit_text(item: dict) -> tuple[str, str]:
    """Generate Reddit title and body (markdown). Returns (title, body)."""
    item_type = item["type"]
    team = item.get("team", "")
    league_name = item.get("league_name", "")
    days = item.get("days_since", 0)
    days_str = f"{days:,}".replace(",", ".") if days else "?"

    if item_type == "barber_alert":
        title = f"✂️ {team} finally won 5 in a row! ({days_str} days waiting)"
        body = (
            f"**{team}** ({league_name}) has completed a 5-match winning streak "
            f"after waiting **{days_str} days**.\n\n"
            f"The Hair Length Index tracks how long since each club last won "
            f"5 matches in a row across all competitions.\n\n"
            f"[Full rankings and stats]({URL})\n\n"
            f"---\n*Data from the [Hair Length Index]({URL})*"
        )

    elif item_type == "bijna_bij_de_kapper":
        wins = item.get("consecutive_wins", 0)
        remaining = item.get("remaining", 0)
        title = f"👀 {team} on a {wins}-match winning streak — {remaining} more for 5 in a row ({days_str} days waiting)"

        matches_table = ""
        if item.get("streak_matches"):
            matches_table = "\n\n**The streak so far:**\n\n| Date | Opponent | Score | Comp |\n|------|----------|-------|------|\n"
            for m in item["streak_matches"]:
                ha = "H" if m.get("home_away") == "H" else "A"
                matches_table += f"| {m['date']} | {m['opponent']} ({ha}) | {m['score']} | {m.get('competition', '')} |\n"

        body = (
            f"**{team}** ({league_name}) has won **{wins} in a row** and needs "
            f"just **{remaining} more** to complete a 5-match streak.\n\n"
            f"They've been waiting **{days_str} days** since their last 5-in-a-row."
            f"{matches_table}\n\n"
            f"[Full rankings]({URL})\n\n"
            f"---\n*Data from the [Hair Length Index]({URL})*"
        )

    elif item_type == "countdown":
        title = f"🔥 {team} needs just ONE more win for 5 in a row! ({days_str} days waiting)"
        body = (
            f"**{team}** ({league_name}) has won **4 in a row**. "
            f"One more win and they complete a 5-match winning streak "
            f"after **{days_str} days** of waiting.\n\n"
            f"[Full rankings]({URL})\n\n"
            f"---\n*Data from the [Hair Length Index]({URL})*"
        )

    elif item_type == "close_call":
        was_on = item.get("was_on", 0)
        last = item.get("last_result", "L")
        result_word = {"L": "loss", "D": "draw"}.get(last, last)
        title = f"😩 {team} were {was_on} wins from a streak — then a {result_word}"
        body = (
            f"**{team}** ({league_name}) had won **{was_on} in a row** "
            f"but the streak was broken by a {result_word}.\n\n"
            f"They've now been waiting **{days_str} days** for 5 wins in a row.\n\n"
            f"[Full rankings]({URL})\n\n"
            f"---\n*Data from the [Hair Length Index]({URL})*"
        )

    elif item_type == "milestone":
        milestone = item.get("milestone", days)
        title = f"📅 {team}: exactly {milestone} days without winning 5 in a row"
        body = (
            f"**{team}** ({league_name}) has now gone exactly **{milestone} days** "
            f"without winning 5 matches in a row.\n\n"
            f"[Full rankings]({URL})\n\n"
            f"---\n*Data from the [Hair Length Index]({URL})*"
        )

    elif item_type == "derby_alert":
        opponent = item.get("opponent", "")
        rivalry = item.get("rivalry_name", "Derby")
        title = f"⚔️ {rivalry}: {team} vs {opponent} — {days_str} days without 5 in a row"
        body = (
            f"**{rivalry}** coming up! **{team}** faces **{opponent}**.\n\n"
            f"{team} has been waiting **{days_str} days** for a 5-match winning streak. "
            f"Can the derby be the start?\n\n"
            f"[Full rankings]({URL})\n\n"
            f"---\n*Data from the [Hair Length Index]({URL})*"
        )

    elif item_type == "weekly_summary":
        longest = item.get("longest", {})
        freshest = item.get("freshest", {})
        almost = item.get("almost", [])
        total = item.get("total_teams", 130)

        almost_rows = ""
        if almost:
            almost_rows = "\n\n**Almost there:**\n\n| Team | Wins in a row | League |\n|------|--------------|--------|\n"
            for a in almost:
                almost_rows += f"| {a['team']} | {a['wins']} | {a['league']} |\n"

        l_days = f"{longest.get('days', 0):,}".replace(",", ".")
        f_days = freshest.get("days", 0)

        title = f"📊 Hair Length Index — Weekly Update ({total} clubs, 7 leagues)"
        body = (
            f"# Hair Length Index — Weekly Update\n\n"
            f"Tracking how long since each club last won 5 in a row.\n\n"
            f"🧔 **Longest hair:** {longest.get('team', '?')} — {l_days} days ({longest.get('league', '')})\n\n"
            f"💇 **Freshest cut:** {freshest.get('team', '?')} — {f_days} days ({freshest.get('league', '')})"
            f"{almost_rows}\n\n"
            f"[Full interactive rankings]({URL})\n\n"
            f"---\n*{total} clubs across Eredivisie, Eerste Divisie, Premier League, "
            f"Bundesliga, La Liga, Serie A, and Ligue 1.*"
        )

    else:
        title = f"Hair Length Index update: {team}"
        body = f"Check the latest at {URL}"

    return title, body


def get_subreddits(item: dict) -> list[str]:
    """Determine which subreddits to post to."""
    league = item.get("league", "")
    subs = SUBREDDIT_MAP.get(league, [])

    # Big events also go to r/soccer
    if item["type"] in BIG_EVENT_TYPES:
        subs = ["soccer"] + subs

    return subs


def post_queue(dry_run: bool = False):
    """Post all unposted items from the social queue."""
    if not QUEUE_FILE.exists():
        log.warning(f"No queue file found at {QUEUE_FILE}")
        return

    with open(QUEUE_FILE) as f:
        queue = json.load(f)

    posted = load_posted()
    reddit = None if dry_run else get_client()

    items = queue.get("items", [])
    posted_count = 0

    for item in items:
        if "reddit" not in item.get("platforms", []):
            continue

        title, body = generate_reddit_text(item)
        subreddits = get_subreddits(item)

        for sub_name in subreddits:
            iid = item_id(item, sub_name)
            if iid in posted:
                log.info(f"  Skipping r/{sub_name} (already posted): {item.get('team', 'summary')}")
                continue

            if dry_run:
                log.info(f"\n[DRY RUN] Would post to r/{sub_name}:")
                log.info(f"  Title: {title}")
                log.info(f"  Body:\n{body[:300]}...")
            else:
                try:
                    subreddit = reddit.subreddit(sub_name)
                    submission = subreddit.submit(title=title, selftext=body)
                    log.info(f"  Posted to r/{sub_name}: {submission.url}")
                    posted[iid] = {
                        "posted_at": datetime.now().isoformat(),
                        "type": item["type"],
                        "team": item.get("team", ""),
                        "subreddit": sub_name,
                        "url": submission.url,
                    }
                    posted_count += 1
                except Exception as e:
                    log.error(f"  Failed to post to r/{sub_name}: {e}")

    if not dry_run:
        save_posted(posted)
        log.info(f"Posted {posted_count} items to Reddit")


def post_test(message: str):
    """Post a test to own profile."""
    reddit = get_client()
    sub = reddit.subreddit("u_" + str(reddit.user.me()))
    post = sub.submit(title="Hair Length Index Test", selftext=message)
    log.info(f"Test post: {post.url}")


def main():
    parser = argparse.ArgumentParser(description="Post to Reddit")
    parser.add_argument("--dry-run", action="store_true", help="Preview without posting")
    parser.add_argument("--test", type=str, help="Post a test message to own profile")
    args = parser.parse_args()

    if args.test:
        post_test(args.test)
    else:
        post_queue(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
