"""Post to Bluesky via AT Protocol.

Reads social-queue.json, generates text, optionally attaches images,
and posts to Bluesky. Tracks posted items to avoid duplicates.

Usage:
    python -m scripts.post_bluesky                    # post all queued items
    python -m scripts.post_bluesky --dry-run           # preview without posting
    python -m scripts.post_bluesky --test "Hello!"     # post a test message
"""

import argparse
import hashlib
import json
import logging
import os
from datetime import datetime
from pathlib import Path

from atproto import Client

from scripts.config import DATA_DIR
from scripts.generate_post_text import generate_text

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

QUEUE_FILE = DATA_DIR / "social-queue.json"
POSTED_FILE = DATA_DIR / "social-posted.json"
ASSETS_DIR = DATA_DIR / "social-assets"


def get_client() -> Client:
    """Create authenticated Bluesky client."""
    handle = os.environ.get("BLUESKY_HANDLE", "")
    password = os.environ.get("BLUESKY_APP_PASSWORD", "")

    if not handle or not password:
        # Try .env file
        env_path = Path(__file__).parent.parent / ".env"
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                if "=" in line and not line.startswith("#"):
                    key, val = line.strip().split("=", 1)
                    if key == "BLUESKY_HANDLE":
                        handle = val
                    elif key == "BLUESKY_APP_PASSWORD":
                        password = val

    if not handle or not password:
        raise ValueError("BLUESKY_HANDLE and BLUESKY_APP_PASSWORD must be set in .env or environment")

    client = Client()
    client.login(handle, password)
    log.info(f"Logged in as {handle}")
    return client


def load_posted() -> dict:
    """Load the posted items tracker."""
    if POSTED_FILE.exists():
        with open(POSTED_FILE) as f:
            return json.load(f)
    return {}


def save_posted(posted: dict):
    """Save the posted items tracker."""
    POSTED_FILE.write_text(json.dumps(posted, indent=2))


def item_id(item: dict) -> str:
    """Generate a unique ID for a queue item."""
    key = f"{item.get('type', '')}-{item.get('team', '')}-{item.get('league', '')}"
    return hashlib.md5(key.encode()).hexdigest()[:12]


def build_facets(text: str):
    """Parse hashtags and URLs in text, create Bluesky facets for clickability."""
    import re
    from atproto import models

    facets = []
    # Hashtags
    for match in re.finditer(r"#(\w+)", text):
        tag = match.group(1)
        start = len(text[:match.start()].encode("utf-8"))
        end = len(text[:match.end()].encode("utf-8"))
        facets.append(models.AppBskyRichtextFacet.Main(
            index=models.AppBskyRichtextFacet.ByteSlice(byteStart=start, byteEnd=end),
            features=[models.AppBskyRichtextFacet.Tag(tag=tag)],
        ))
    # URLs (simple http/https or domain patterns)
    for match in re.finditer(r"(https?://\S+|wijnandb\.github\.io\S*)", text):
        url = match.group(0)
        full_url = url if url.startswith("http") else f"https://{url}"
        start = len(text[:match.start()].encode("utf-8"))
        end = len(text[:match.end()].encode("utf-8"))
        facets.append(models.AppBskyRichtextFacet.Main(
            index=models.AppBskyRichtextFacet.ByteSlice(byteStart=start, byteEnd=end),
            features=[models.AppBskyRichtextFacet.Link(uri=full_url)],
        ))
    return facets if facets else None


def compress_image(image_data: bytes, max_size: int = 950_000) -> bytes:
    """Compress image to fit Bluesky's 1MB limit."""
    if len(image_data) <= max_size:
        return image_data
    import subprocess, tempfile
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_in:
        tmp_in.write(image_data)
        tmp_in_path = tmp_in.name
    tmp_out_path = tmp_in_path.replace(".png", "-compressed.jpg")
    subprocess.run(["convert", tmp_in_path, "-quality", "85", "-resize", "1080x1080", tmp_out_path],
                   capture_output=True)
    with open(tmp_out_path, "rb") as f:
        compressed = f.read()
    os.unlink(tmp_in_path)
    os.unlink(tmp_out_path)
    return compressed


def post_with_image(client: Client, text: str, image_path: Path | None = None) -> str:
    """Post to Bluesky with auto-facets and image compression."""
    from atproto import models

    facets = build_facets(text)

    if image_path and image_path.exists():
        with open(image_path, "rb") as f:
            image_data = compress_image(f.read())
        upload = client.upload_blob(image_data)
        embed = models.AppBskyEmbedImages.Main(
            images=[models.AppBskyEmbedImages.Image(
                alt="Hair Length Index",
                image=upload.blob,
            )]
        )
        post = client.send_post(text=text, facets=facets, embed=embed)
    else:
        post = client.send_post(text=text, facets=facets)

    return post.uri


def post_queue(dry_run: bool = False):
    """Post all unposted items from the social queue."""
    if not QUEUE_FILE.exists():
        log.warning(f"No queue file found at {QUEUE_FILE}")
        return

    with open(QUEUE_FILE) as f:
        queue = json.load(f)

    posted = load_posted()
    client = None if dry_run else get_client()

    items = queue.get("items", [])
    posted_count = 0

    for item in items:
        if "bluesky" not in item.get("platforms", []):
            continue

        iid = item_id(item)
        if iid in posted:
            log.info(f"  Skipping (already posted): {item.get('team', 'summary')}")
            continue

        text = generate_text(item)

        # Check for rendered card
        image_path = None
        if item.get("render_card"):
            team_slug = item.get("team", "").lower().replace(" ", "-").replace(".", "")
            card_path = ASSETS_DIR / f"card-{team_slug}.png"
            if card_path.exists():
                image_path = card_path

        if dry_run:
            log.info(f"\n[DRY RUN] Would post to Bluesky:")
            log.info(f"  Type: {item['type']}")
            log.info(f"  Team: {item.get('team', 'N/A')}")
            log.info(f"  Image: {image_path or 'none'}")
            log.info(f"  Text:\n{text}")
        else:
            try:
                uri = post_with_image(client, text, image_path)
                log.info(f"  Posted: {item.get('team', 'summary')} → {uri}")
                posted[iid] = {
                    "posted_at": datetime.now().isoformat(),
                    "type": item["type"],
                    "team": item.get("team", ""),
                    "uri": uri,
                }
                posted_count += 1
            except Exception as e:
                log.error(f"  Failed to post {item.get('team', '')}: {e}")

    if not dry_run:
        save_posted(posted)
        log.info(f"Posted {posted_count} items to Bluesky")


def post_test(message: str):
    """Post a simple test message."""
    client = get_client()
    post = client.send_post(text=message)
    log.info(f"Test post created: {post.uri}")


def main():
    parser = argparse.ArgumentParser(description="Post to Bluesky")
    parser.add_argument("--dry-run", action="store_true", help="Preview without posting")
    parser.add_argument("--test", type=str, help="Post a test message")
    args = parser.parse_args()

    if args.test:
        post_test(args.test)
    else:
        post_queue(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
