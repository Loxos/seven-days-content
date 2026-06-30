"""Reading and writing the content tree the gallery serves.

Layout (relative to CONTENT_DIR):
    day-0/ day-1/ ... each with index.html, statement.md, meta.json
    diary.md     the artist's running, first-person journal (the arc)
    index.html   the generated gallery (see gallery.py)
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class DayMeta:
    day: int
    title: str
    blurb: str
    created_at: str
    model: str | None = None


def _day_dirs(content_dir: Path) -> list[Path]:
    return sorted(
        (p for p in content_dir.glob("day-*") if p.is_dir() and p.name[4:].isdigit()),
        key=lambda p: int(p.name[4:]),
    )


def load_meta(day_dir: Path) -> DayMeta | None:
    f = day_dir / "meta.json"
    if not f.exists():
        return None
    d = json.loads(f.read_text(encoding="utf-8"))
    return DayMeta(
        day=int(d.get("day", int(day_dir.name[4:]))),
        title=d.get("title", day_dir.name),
        blurb=d.get("blurb", ""),
        created_at=d.get("created_at", ""),
        model=d.get("model"),
    )


def all_meta(content_dir: Path) -> list[DayMeta]:
    out = []
    for d in _day_dirs(content_dir):
        m = load_meta(d)
        if m:
            out.append(m)
    return out


def next_day(content_dir: Path) -> int:
    nums = [int(d.name[4:]) for d in _day_dirs(content_dir)]
    return (max(nums) + 1) if nums else 1


def read_diary(content_dir: Path) -> str:
    f = content_dir / "diary.md"
    return f.read_text(encoding="utf-8") if f.exists() else ""


def append_diary(content_dir: Path, day: int, entry: str) -> None:
    f = content_dir / "diary.md"
    header = f"\n\n## Day {day} — {datetime.now(timezone.utc).date().isoformat()}\n\n"
    prior = f.read_text(encoding="utf-8") if f.exists() else "# The artist's diary\n"
    f.write_text(prior + header + entry.strip() + "\n", encoding="utf-8")


def build_prior_context(content_dir: Path, max_days: int = 8) -> str:
    """A compact summary of prior work + the diary, for the prompt."""
    metas = all_meta(content_dir)[-max_days:]
    if not metas:
        return "(none yet — this is the very first piece)"
    lines = [f"- Day {m.day}: \"{m.title}\" — {m.blurb}" for m in metas]
    diary = read_diary(content_dir).strip()
    # keep the prompt bounded: only the tail of the diary
    if len(diary) > 4000:
        diary = "...\n" + diary[-4000:]
    return "Prior pieces:\n" + "\n".join(lines) + "\n\nYour diary so far:\n" + (diary or "(empty)")


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60] or "untitled"


def write_day(
    content_dir: Path,
    *,
    day: int,
    title: str,
    blurb: str,
    html: str,
    statement: str,
    model: str | None,
) -> Path:
    day_dir = content_dir / f"day-{day}"
    day_dir.mkdir(parents=True, exist_ok=True)
    (day_dir / "index.html").write_text(html, encoding="utf-8")
    (day_dir / "statement.md").write_text(statement.strip() + "\n", encoding="utf-8")
    meta = {
        "day": day,
        "title": title,
        "blurb": blurb,
        "slug": _slug(title),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "model": model,
    }
    (day_dir / "meta.json").write_text(
        json.dumps(meta, indent=2) + "\n", encoding="utf-8"
    )
    return day_dir
