import argparse
import logging
import sys
import time
from datetime import datetime, timezone

from .config import Config
from .db import (
    init_db,
    add_author,
    remove_author,
    list_authors,
    insert_posts,
    get_new_posts_since_last_fetch,
    update_last_fetched,
    update_display_name,
)
from .fetcher import fetch_posts_for_author, FetchError

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
)
logger = logging.getLogger("xtrack")


def _format_relative(when: str | None) -> str:
    if not when:
        return "unknown time"
    try:
        for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%a, %d %b %Y %H:%M:%S %z"):
            try:
                dt = datetime.strptime(when, fmt)
                break
            except ValueError:
                continue
        else:
            dt = datetime.fromisoformat(when)
    except (ValueError, TypeError):
        return when

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    diff = now - dt
    seconds = diff.total_seconds()
    if seconds < 60:
        return "just now"
    minutes = int(seconds / 60)
    if minutes == 1:
        return "1 minute ago"
    if minutes < 60:
        return f"{minutes} minutes ago"
    hours = int(minutes / 60)
    if hours == 1:
        return "1 hour ago"
    if hours < 24:
        return f"{hours} hours ago"
    days = int(hours / 24)
    if days == 1:
        return "1 day ago"
    return f"{days} days ago"


def cmd_add(config: Config, username: str) -> int:
    init_db(config.data_dir)
    username = username.lower().lstrip("@")

    # Fetch before adding: validates the username exists and seeds initial posts
    # in one step so the user doesn't need a separate fetch command.
    try:
        display_name, posts = fetch_posts_for_author(
            username, config.nitter_instances, config.user_agent, config.request_timeout
        )
    except FetchError as e:
        logger.error("Error: %s", e)
        return 1

    if not posts:
        logger.warning("Warning: @%s returned no posts (account may be private or doesn't exist)", username)

    inserted = add_author(config.data_dir, username, display_name)
    if not inserted:
        logger.info("@%s is already tracked.", username)
        return 0

    # Stamp author_username onto each post so insert_posts can group by author.
    for p in posts:
        p["author_username"] = username
    n = insert_posts(config.data_dir, posts)
    update_last_fetched(config.data_dir, username)

    logger.info("Added @%s (%s) — %d initial posts stored.", username, display_name or username, n)
    return 0


def cmd_remove(config: Config, username: str) -> int:
    init_db(config.data_dir)
    username = username.lower().lstrip("@")
    if remove_author(config.data_dir, username):
        logger.info("Removed @%s from tracking.", username)
    else:
        logger.error("Error: @%s is not currently tracked.", username)
        return 1
    return 0


def cmd_list(config: Config) -> int:
    init_db(config.data_dir)
    authors = list_authors(config.data_dir)
    if not authors:
        logger.info("No authors are currently tracked. Use 'xtrack add <username>' to add one.")
        return 0

    logger.info("%-20s %-20s %6s  %s", "USERNAME", "DISPLAY NAME", "POSTS", "ADDED")
    logger.info("-" * 65)
    for a in authors:
        logger.info(
            "%-20s %-20s %6d  %s",
            a["username"],
            a["display_name"] or "",
            a["post_count"],
            a["added_at"][:10] if a["added_at"] else "",
        )
    return 0


def cmd_fetch(config: Config, username: str | None) -> int:
    init_db(config.data_dir)
    authors = list_authors(config.data_dir)

    if username:
        username = username.lower().lstrip("@")
        authors = [a for a in authors if a["username"] == username]
        if not authors:
            logger.error("Error: @%s is not a tracked author.", username)
            return 1

    if not authors:
        logger.info("No tracked authors. Use 'xtrack add <username>' to add one.")
        return 0

    logger.info("Fetching %d author(s)...", len(authors))
    total_new = 0
    for a in authors:
        uname = a["username"]
        try:
            display_name, posts = fetch_posts_for_author(
                uname, config.nitter_instances, config.user_agent, config.request_timeout
            )
        except FetchError as e:
            logger.error("%s: ERROR — %s", uname, e)
            continue

        if display_name and display_name != a["display_name"]:
            update_display_name(config.data_dir, uname, display_name)

        for p in posts:
            p["author_username"] = uname
        n = insert_posts(config.data_dir, posts)
        update_last_fetched(config.data_dir, uname)
        total_new += n
        logger.info("%s: %d new posts (%d total)", uname, n, a["post_count"] + n)

    logger.info("Done — %d new posts.", total_new)
    return 0


def cmd_new(config: Config, username: str | None) -> int:
    init_db(config.data_dir)
    authors = list_authors(config.data_dir)

    if username:
        username = username.lower().lstrip("@")
        authors = [a for a in authors if a["username"] == username]
        if not authors:
            logger.error("Error: @%s is not a tracked author.", username)
            return 1

    found_any = False
    for a in authors:
        posts = get_new_posts_since_last_fetch(config.data_dir, a["username"])
        if not posts:
            continue
        found_any = True
        for p in posts:
            when = _format_relative(p["published_at"])
            logger.info("\n@%s — %s:", a["username"], when)
            logger.info("%s", p["content"])

    if not found_any:
        logger.info("No new posts. Run 'xtrack fetch' first.")

    return 0


def cmd_watch(config: Config, interval: int) -> int:
    logger.info("Watching every %d minutes. Press Ctrl+C to stop.", interval)
    try:
        while True:
            logger.info("[%s] Fetching...", datetime.now().strftime("%Y-%m-%d %H:%M"))
            cmd_fetch(config, None)
            logger.info("Sleeping %d minutes...", interval)
            time.sleep(interval * 60)
    except KeyboardInterrupt:
        logger.info("Stopped.")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="xtrack",
        description="Track X/Twitter posts by specific authors using Nitter RSS feeds",
    )
    sub = parser.add_subparsers(dest="command")

    p_add = sub.add_parser("add", help="Add an author to track")
    p_add.add_argument("username", help="X/Twitter username (with or without @)")

    p_remove = sub.add_parser("remove", help="Remove an author from tracking")
    p_remove.add_argument("username", help="X/Twitter username")

    sub.add_parser("list", help="List tracked authors")

    p_fetch = sub.add_parser("fetch", help="Fetch latest posts")
    p_fetch.add_argument("username", nargs="?", help="Fetch for a specific author only")

    p_new = sub.add_parser("new", help="Show posts from the most recent fetch")
    p_new.add_argument("username", nargs="?", help="Show new posts for a specific author")

    p_watch = sub.add_parser("watch", help="Run fetch on a recurring interval")
    p_watch.add_argument(
        "--interval", "-i", type=int, default=15,
        help="Minutes between fetches (default: 15, min: 5)",
    )

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    config = Config()

    if args.command == "add":
        sys.exit(cmd_add(config, args.username))
    elif args.command == "remove":
        sys.exit(cmd_remove(config, args.username))
    elif args.command == "list":
        sys.exit(cmd_list(config))
    elif args.command == "fetch":
        sys.exit(cmd_fetch(config, args.username))
    elif args.command == "new":
        sys.exit(cmd_new(config, args.username))
    elif args.command == "watch":
        if args.interval < 5:
            logger.warning("Minimum interval is 5 minutes. Using 5 minutes.")
            args.interval = 5
        sys.exit(cmd_watch(config, args.interval))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
