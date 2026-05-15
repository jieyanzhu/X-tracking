# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

`xtrack` — a Python CLI tool that tracks X/Twitter posts by specific authors using Nitter RSS feeds. Data is stored as local CSV files.

## Commands

```bash
# Run the CLI (development — no formal package install)
python -m src.cli <command> [args]

# Verify imports work after changes
python -c "from src.fetcher import fetch_posts_for_author; from src.db import init_db; print('OK')"
```

There is no test suite, linter, or type checker configured yet.

## Architecture

Four modules with clear separation of concerns:

- **`src/cli.py`** — argparse entry point. Commands: `add`, `remove`, `list`, `fetch`, `new`, `watch`. Each command is a standalone function (`cmd_add`, `cmd_remove`, etc.) that takes a `Config` object plus command-specific args and returns an exit code.
- **`src/config.py`** — `Config` class reads all settings from environment variables. No config files. Default Nitter instances are hardcoded; Nitter URLs must not have trailing slashes.
- **`src/db.py`** — CSV-backed persistence. `authors.csv` tracks active authors; `posts/<username>.csv` stores per-author posts; `removed/<username>.csv` holds posts from removed authors. Posts are deduplicated by `id` on insert. The `new` command relies on `get_new_posts_since_last_fetch`, which returns only posts from the most recent `fetched_at` timestamp.
- **`src/fetcher.py`** — Fetches RSS feeds from Nitter instances via `httpx` + `feedparser`. Instances are tried in random order for load distribution. Returns `(display_name, list[post_dict])` on success. Raises `FetchError` only when all instances fail; an empty feed (private/protected account) returns an empty list, not an error.

## Key design decisions

- **No database** — CSV files are the source of truth. The `authors.csv` file is fully rewritten on every mutation (read → modify in memory → write). Post CSVs are append-only with header-on-create.
- **No async** — everything is synchronous despite using `httpx` (synchronous client).
- **No package install** — the project has no `setup.py` or `pyproject.toml`. Import paths use relative imports (`from .config import Config`), so the code must be run as a module (`python -m src.cli`).
- **Dependencies**: `feedparser>=0.6` for RSS parsing, `httpx>=0.27` for HTTP requests.
