"""Validation gates for a generated artifact.

Deliberately light — the creative-director prompt is the primary quality/safety
control. These checks only catch egregious mechanical failures so nothing broken
or wildly off-policy auto-ships: size bound, completeness, self-containment
(no external resource loads → keeps it EU-clean and offline-robust), an
interactivity signal, a conservative content backstop, and — when ``node`` is
available — a JS syntax check on inline scripts.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from html.parser import HTMLParser

# Tags that *load* an external resource (vs <a href> navigation, which is fine).
_LOADER_ATTR = {
    "script": "src", "link": "href", "img": "src", "iframe": "src",
    "source": "src", "video": "src", "audio": "src", "object": "data",
    "embed": "src", "track": "src",
}

# Conservative backstop only. Not a substitute for the prompt's content policy.
_BANNED = re.compile(r"\b(?:porn|nazi|kike|spic|chink|faggot)\b", re.I)


class _Inspector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.external: list[str] = []
        self.interactive = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        d = dict(attrs)
        loader = _LOADER_ATTR.get(tag)
        if loader:
            url = (d.get(loader) or "").strip().lower()
            if url.startswith(("http://", "https://", "//")):
                self.external.append(f"<{tag} {loader}={url[:60]}>")
        if tag in ("script", "canvas", "audio", "video"):
            self.interactive = True
        if any(k.startswith("on") for k in d):
            self.interactive = True


def validate(html: str, max_bytes: int) -> tuple[bool, str]:
    size = len(html.encode("utf-8"))
    if size > max_bytes:
        return False, f"too large: {size} > {max_bytes} bytes"
    low = html.lower()
    if "<!doctype html" not in low:
        return False, "missing <!doctype html>"
    if "</html>" not in low:
        return False, "missing </html> — likely truncated"
    if _BANNED.search(html):
        return False, "tripped content-policy backstop"

    insp = _Inspector()
    try:
        insp.feed(html)
    except Exception as e:  # noqa: BLE001 — malformed markup
        return False, f"HTML parse error: {e}"
    if insp.external:
        return False, f"not self-contained (external load): {insp.external[0]}"
    if not insp.interactive:
        return False, "no interactivity (no <script>/<canvas>/event handlers found)"

    return _js_syntax_ok(html)


def _js_syntax_ok(html: str) -> tuple[bool, str]:
    """Run `node --check` on each inline <script> body, if node is present."""
    node = shutil.which("node")
    if not node:
        return True, "ok (node unavailable — JS syntax check skipped)"
    for js in re.findall(r"<script(?:\s[^>]*)?>(.*?)</script>", html, re.S | re.I):
        if not js.strip():
            continue
        with tempfile.NamedTemporaryFile(
            "w", suffix=".js", delete=False, encoding="utf-8"
        ) as f:
            f.write(js)
            path = f.name
        try:
            r = subprocess.run(
                [node, "--check", path], capture_output=True, text=True, timeout=20
            )
        finally:
            os.unlink(path)
        if r.returncode != 0:
            last = (r.stderr or "").strip().splitlines()
            return False, f"JS syntax error: {last[-1] if last else 'unknown'}"
    return True, "ok"
