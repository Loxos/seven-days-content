"""The daily run: read the past → invent → validate → publish → notify.

One invocation = one morning. Idempotent enough to retry: the day number is
derived from what already exists, and writes are confined to CONTENT_DIR.
"""
from __future__ import annotations

import re

from . import content, gallery, git_ops, guardrails, notify, prompt
from .config import Config
from .llm import LLMError, generate


def _blurb(statement: str, limit: int = 150) -> str:
    """A one-liner for the gallery card, derived from the statement."""
    lines = [ln.strip() for ln in statement.splitlines()]
    body = [ln for ln in lines if ln and not ln.startswith("#")]
    text = re.sub(r"[*_`>#]", "", " ".join(body)).strip()
    if len(text) > limit:
        text = text[:limit].rsplit(" ", 1)[0] + "…"
    return text or "An interactive piece."


def run() -> int:
    cfg = Config.from_env()
    print(f"[engine] provider={cfg.provider} model={cfg.model} content_dir={cfg.content_dir}")
    git_ops.ensure_content_repo(cfg)
    cfg.content_dir.mkdir(parents=True, exist_ok=True)

    day = cfg.day_override or content.next_day(cfg.content_dir)
    if day > cfg.total_days:
        print(f"[engine] day {day} > {cfg.total_days}: the season is complete. Nothing to make.")
        return 0
    print(f"[engine] composing day {day} of {cfg.total_days}")

    prior = content.build_prior_context(cfg.content_dir)
    brief = prompt.build(day, cfg.total_days, prior)

    parsed = None
    last_err = ""
    for attempt in range(1, 3):
        try:
            raw = generate(cfg, brief.system, brief.user, max_tokens=cfg.max_html_bytes // 12 + 4000)
            candidate = prompt.parse(raw)
        except (LLMError, prompt.ParseError) as e:
            last_err = str(e)
            print(f"[engine] attempt {attempt} failed to generate/parse: {e}")
            continue
        ok, msg = guardrails.validate(candidate["html"], cfg.max_html_bytes)
        if ok:
            parsed = candidate
            print(f"[engine] attempt {attempt} passed validation")
            break
        last_err = msg
        print(f"[engine] attempt {attempt} rejected by guardrails: {msg}")

    if parsed is None:
        print(f"[engine] giving up after retries: {last_err}")
        return 1

    blurb = _blurb(parsed["statement"])
    content.write_day(
        cfg.content_dir,
        day=day,
        title=parsed["title"],
        blurb=blurb,
        html=parsed["html"],
        statement=parsed["statement"],
        model=None if cfg.provider == "stub" else cfg.model,
    )
    content.append_diary(cfg.content_dir, day, parsed["diary"])
    gallery.render(cfg.content_dir)
    print(f"[engine] wrote day-{day}: {parsed['title']!r}")

    git_ops.commit_and_push(cfg, f"Day {day}: {parsed['title']}")

    link = f"{cfg.base_url}/day-{day}/"
    notify.notify(
        cfg,
        title=f"Seven Days · Day {day} is live",
        message=f"{parsed['title']}\n\n{blurb}\n\n{link}",
        click_url=link,
    )
    print(f"[engine] done. live at {link}")
    return 0
