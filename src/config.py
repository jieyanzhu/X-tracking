import os
from pathlib import Path

# Fallback Nitter mirrors used when XT_NITTER_INSTANCES env var is not set.
_DEFAULT_INSTANCES = [
    "https://nitter.net",
    "https://nitter.privacydev.net",
    "https://nitter.poast.org",
    "https://nitter.lacontrevoie.fr",
    "https://nitter.moomoo.me",
]


class Config:
    def __init__(self):
        self.nitter_instances = self._parse_instances()
        self.data_dir = self._resolve_data_dir()
        self.user_agent = os.environ.get(
            "XT_USER_AGENT",
            "Mozilla/5.0 (compatible; xtrack/0.1; +https://github.com/xtrack)",
        )
        self.request_timeout = int(os.environ.get("XT_REQUEST_TIMEOUT", "30"))

    def _parse_instances(self):
        val = os.environ.get("XT_NITTER_INSTANCES", "")
        if val:
            # Strip trailing slashes — RSS URLs are built as {instance}/{username}/rss
            return [u.strip().rstrip("/") for u in val.split(",") if u.strip()]
        return _DEFAULT_INSTANCES

    def _resolve_data_dir(self):
        env_dir = os.environ.get("XT_DATA_DIR", "")
        if env_dir:
            return env_dir
        return str(Path.cwd() / "db")
