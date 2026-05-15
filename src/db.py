import csv
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

AUTHORS_FILE = "authors.csv"
POSTS_DIR = "posts"
AUTHORS_FIELDS = ["username", "display_name", "added_at", "last_fetched_at", "is_active"]
POSTS_FIELDS = ["id", "content", "url", "published_at", "fetched_at"]


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _authors_path(data_dir: str) -> Path:
    return Path(data_dir) / AUTHORS_FILE


def _posts_dir(data_dir: str) -> Path:
    return Path(data_dir) / POSTS_DIR


def _posts_path(data_dir: str, username: str) -> Path:
    return _posts_dir(data_dir) / f"{username}.csv"


def _read_authors(data_dir: str) -> list[dict]:
    path = _authors_path(data_dir)
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _write_authors(data_dir: str, authors: list[dict]) -> None:
    path = _authors_path(data_dir)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=AUTHORS_FIELDS)
        w.writeheader()
        for row in authors:
            w.writerow({k: row.get(k, "") for k in AUTHORS_FIELDS})


def _read_posts(data_dir: str, username: str) -> list[dict]:
    path = _posts_path(data_dir, username)
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _append_posts(data_dir: str, username: str, posts: list[dict]) -> None:
    path = _posts_path(data_dir, username)
    exists = path.exists()
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=POSTS_FIELDS)
        if not exists:
            w.writeheader()
        for p in posts:
            w.writerow({k: p.get(k, "") for k in POSTS_FIELDS})


def init_db(data_dir: str) -> None:
    posts_dir = _posts_dir(data_dir)
    posts_dir.mkdir(parents=True, exist_ok=True)
    authors_path = _authors_path(data_dir)
    if not authors_path.exists():
        authors_path.write_text(",".join(AUTHORS_FIELDS) + "\n", encoding="utf-8")


def add_author(data_dir: str, username: str, display_name: str | None = None) -> bool:
    """Insert or reactivate an author. Returns True if newly inserted, False if already active."""
    authors = _read_authors(data_dir)
    for a in authors:
        if a["username"] == username:
            if a["is_active"] == "1":
                return False
            a["is_active"] = "1"
            if display_name:
                a["display_name"] = display_name
            _write_authors(data_dir, authors)
            return True
    authors.append({
        "username": username,
        "display_name": display_name or "",
        "added_at": _now(),
        "last_fetched_at": "",
        "is_active": "1",
    })
    _write_authors(data_dir, authors)
    return True


def _removed_dir(data_dir: str) -> Path:
    return Path(data_dir) / "removed"


def remove_author(data_dir: str, username: str) -> bool:
    """Remove an author from authors.csv and move their posts to removed/. """
    authors = _read_authors(data_dir)
    new_authors = [a for a in authors if a["username"] != username]
    if len(new_authors) == len(authors):
        return False
    _write_authors(data_dir, new_authors)

    posts_path = _posts_path(data_dir, username)
    if posts_path.exists():
        dest_dir = _removed_dir(data_dir)
        dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.move(str(posts_path), str(dest_dir / f"{username}.csv"))
    return True


def list_authors(data_dir: str, active_only: bool = True) -> list[dict]:
    authors = _read_authors(data_dir)
    result = []
    for a in authors:
        if active_only and a["is_active"] != "1":
            continue
        post_count = get_post_count(data_dir, a["username"])
        result.append({
            "username": a["username"],
            "display_name": a["display_name"],
            "added_at": a["added_at"],
            "last_fetched_at": a["last_fetched_at"],
            "is_active": int(a["is_active"]),
            "post_count": post_count,
        })
    return result


def insert_posts(data_dir: str, posts: list[dict]) -> int:
    """Batch insert posts. Returns count of newly inserted."""
    if not posts:
        return 0
    now = _now()
    by_author: dict[str, list[dict]] = {}
    for p in posts:
        p["fetched_at"] = now
        by_author.setdefault(p["author_username"], []).append(p)

    inserted = 0
    for username, author_posts in by_author.items():
        existing = _read_posts(data_dir, username)
        existing_ids = {p["id"] for p in existing}
        new_posts = [p for p in author_posts if p["id"] not in existing_ids]
        if new_posts:
            _append_posts(data_dir, username, new_posts)
            inserted += len(new_posts)
    return inserted


def get_posts(
    data_dir: str,
    author: str | None = None,
    limit: int = 50,
) -> list[dict]:
    if author:
        posts = _read_posts(data_dir, author)
    else:
        posts = []
        authors = _read_authors(data_dir)
        for a in authors:
            posts.extend(_read_posts(data_dir, a["username"]))

    posts.sort(
        key=lambda p: p.get("published_at") or p.get("fetched_at") or "",
        reverse=True,
    )
    return posts[:limit]


def get_new_posts_since_last_fetch(
    data_dir: str, author: str
) -> list[dict]:
    """Posts fetched in the most recent fetch cycle for this author."""
    posts = _read_posts(data_dir, author)
    if not posts:
        return []
    max_fetched = max(p.get("fetched_at", "") for p in posts)
    if not max_fetched:
        return []
    result = [p for p in posts if p.get("fetched_at") == max_fetched]
    result.sort(
        key=lambda p: p.get("published_at") or p.get("fetched_at") or "",
        reverse=True,
    )
    return result


def update_last_fetched(data_dir: str, username: str) -> None:
    authors = _read_authors(data_dir)
    for a in authors:
        if a["username"] == username:
            a["last_fetched_at"] = _now()
            _write_authors(data_dir, authors)
            return


def update_display_name(data_dir: str, username: str, display_name: str) -> None:
    authors = _read_authors(data_dir)
    for a in authors:
        if a["username"] == username:
            a["display_name"] = display_name
            _write_authors(data_dir, authors)
            return


def get_post_count(data_dir: str, author: str | None = None) -> int:
    if author:
        posts = _read_posts(data_dir, author)
        return len(posts)
    total = 0
    authors = _read_authors(data_dir)
    for a in authors:
        total += len(_read_posts(data_dir, a["username"]))
    return total
