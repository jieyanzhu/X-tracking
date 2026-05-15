import logging
import random
import feedparser
import httpx

logger = logging.getLogger(__name__)


class FetchError(Exception):
    pass


def fetch_posts_for_author(
    username: str,
    instances: list[str],
    user_agent: str,
    timeout: int = 30,
) -> tuple[str | None, list[dict]]:
    """Fetch RSS feed for a username. Returns (display_name, list of post dicts).

    Tries instances in random order. Returns empty list (not error) if author has
    no posts or the account is private/protected.
    """
    shuffled = list(instances)
    random.shuffle(shuffled)

    for instance in shuffled:
        url = f"{instance}/{username}/rss"
        try:
            resp = httpx.get(
                url,
                headers={"User-Agent": user_agent, "Accept": "application/rss+xml, application/xml, text/xml"},
                timeout=timeout,
                follow_redirects=True,
            )
            if resp.status_code != 200:
                logger.warning("%s returned HTTP %s", instance, resp.status_code)
                continue
            if len(resp.content) < 100:
                logger.warning("%s returned short response (%d bytes)", instance, len(resp.content))
                continue

            posts, display_name = _parse_rss(resp.content)
            if not posts:
                logger.warning("%s returned empty/parseable feed for %s", instance, username)
                continue

            return display_name, posts
        except httpx.RequestError as e:
            logger.warning("%s failed: %s", instance, e)
            continue

    raise FetchError(f"All instances failed for @{username}")


def _parse_rss(content: bytes) -> tuple[list[dict], str | None]:
    feed = feedparser.parse(content)
    display_name = None
    if feed.feed.get("title"):
        display_name = feed.feed.title

    posts = []
    for entry in feed.entries:
        post_id = entry.get("guid") or entry.get("link") or ""
        if not post_id:
            continue

        content_text = entry.get("description") or entry.get("title") or ""
        url = entry.get("link") or ""
        published = entry.get("published") or None

        posts.append({
            "id": str(post_id),
            "content": content_text,
            "url": str(url),
            "published_at": published,
        })

    return posts, display_name
