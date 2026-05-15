# xtrack

Track X/Twitter posts by specific authors using Nitter RSS feeds.

## Install

Requires Python 3.12+. Run in a venv environment.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Commands

```bash
python -m src.cli add <username>     # Start tracking an author
python -m src.cli remove <username>  # Stop tracking an author
python -m src.cli list               # List tracked authors and post counts
python -m src.cli fetch [username]   # Fetch latest posts (all authors, or one)
python -m src.cli new [username]     # Show posts from the most recent fetch
python -m src.cli watch              # Fetch continuously every 15 minutes (-i to change)
```

## Configuration

| Env var | Default | Description |
|---|---|---|
| `XT_DATA_DIR` | `<cwd>/db` | Where CSV data is stored |
| `XT_NITTER_INSTANCES` | built-in list | Comma-separated Nitter instance URLs |
| `XT_USER_AGENT` | xtrack/0.1 | HTTP User-Agent for requests |
| `XT_REQUEST_TIMEOUT` | `30` | HTTP request timeout in seconds |

## Data format

Data lives in `db/` as CSV files:

```
db/
  authors.csv          # One row per tracked author
  posts/
    <username>.csv     # One file per author's posts
  removed/
    <username>.csv     # Posts of removed authors
```

**authors.csv** columns: `username`, `display_name`, `added_at`, `last_fetched_at`, `is_active`

**posts CSV** columns: `id`, `content`, `url`, `published_at`, `fetched_at`

When an author is removed, their row is deleted from `authors.csv` and their posts are moved to `removed/`.
