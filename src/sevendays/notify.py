"""Push a one-line notification via ntfy (self-hostable, EU-friendly)."""
from __future__ import annotations

import urllib.error
import urllib.request

from .config import Config


def _ascii(s: str) -> str:
    # ntfy header values must be latin-1-safe; the full title lives in the body.
    return s.encode("ascii", "replace").decode("ascii")


def notify(cfg: Config, title: str, message: str, click_url: str | None = None) -> None:
    if not cfg.ntfy_topic:
        print("[notify] NTFY_TOPIC unset — skipping push")
        return
    url = f"{cfg.ntfy_url}/{cfg.ntfy_topic}"
    headers = {"Title": _ascii(title), "Tags": "art,sparkles"}
    if click_url:
        headers["Click"] = click_url
    req = urllib.request.Request(
        url, data=message.encode("utf-8"), headers=headers, method="POST"
    )
    try:
        urllib.request.urlopen(req, timeout=10)
        print(f"[notify] pushed to {url}")
    except (urllib.error.URLError, OSError) as e:
        print(f"[notify] failed (non-fatal): {e}")
