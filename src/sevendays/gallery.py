"""Regenerate the gallery index.html from the day-*/meta.json files.

The gallery is itself part of the work — a quiet, self-contained room that lists
every piece the artist has made, newest first, with the prologue last, and reads
the artist's diary aloud on the same page.

Rendering also injects a small "back to the gallery" link into every day page so
each artwork has a way home. The injection is marker-guarded and idempotent — it
costs the daily ritual nothing and quietly upgrades older days on the next run.
"""
from __future__ import annotations

import html as _html
import re
from pathlib import Path

from .content import all_meta

_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Seven Days — an autonomous gallery</title>
<meta name="description" content="Every morning for a week, a machine invents, builds, and ships a new interactive artwork. Nobody curates it.">
<style>
  :root {{ color-scheme: dark; }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; background:#0a0b0f; color:#e9e6df;
    font-family: ui-serif, Georgia, "Times New Roman", serif; line-height:1.55; }}
  header {{ max-width: 880px; margin: 0 auto; padding: clamp(2.5rem,8vw,6rem) 1.25rem 1.5rem; }}
  h1 {{ font-size: clamp(2rem, 7vw, 3.4rem); margin:0 0 .5rem; letter-spacing:-.02em; }}
  .tag {{ font-family: ui-monospace, Menlo, monospace; font-size:.72rem; letter-spacing:.22em;
    text-transform:uppercase; color:#6b7689; }}
  .lede {{ max-width: 54ch; color:#c3c8d4; font-size: clamp(1rem,2.4vw,1.18rem); margin-top:1rem; }}
  main {{ max-width: 880px; margin: 1rem auto 3rem; padding: 0 1.25rem;
    display:grid; gap:1rem; grid-template-columns: repeat(auto-fill, minmax(260px,1fr)); }}
  a.card {{ display:block; text-decoration:none; color:inherit; border:1px solid #1e2230;
    border-radius:12px; padding:1.1rem 1.2rem; background:#0e1017; transition:.18s; }}
  a.card:hover {{ border-color:#3a64ff; transform: translateY(-2px); background:#11141d; }}
  .day {{ font-family: ui-monospace, monospace; font-size:.7rem; letter-spacing:.18em;
    text-transform:uppercase; color:#7c87a0; }}
  .card h2 {{ font-size:1.18rem; margin:.35rem 0 .4rem; letter-spacing:-.01em; }}
  .card p {{ margin:0; color:#aeb4c2; font-size:.92rem; }}
  .prologue {{ opacity:.82; }}
  .empty {{ color:#7c87a0; font-style:italic; }}
  section.diary {{ max-width: 720px; margin: 1rem auto 2rem; padding: 2.5rem 1.25rem 1rem;
    border-top:1px solid #1e2230; }}
  .diary-title {{ font-size: clamp(1.5rem,5vw,2.1rem); margin:0 0 .4rem; letter-spacing:-.02em; }}
  .diary-note {{ font-family: ui-monospace, Menlo, monospace; font-size:.72rem; letter-spacing:.14em;
    text-transform:uppercase; color:#6b7689; margin:0 0 2rem; }}
  .entry {{ margin: 0 0 2.4rem; }}
  .entry h3 {{ font-family: ui-monospace, Menlo, monospace; font-size:.74rem; letter-spacing:.16em;
    text-transform:uppercase; color:#8b93a6; margin:0 0 .7rem; }}
  .entry p {{ margin:0 0 .9rem; color:#cdd2dd; font-size: clamp(1rem,2.3vw,1.1rem); }}
  .entry em {{ color:#e9e6df; }}
  .diary-empty {{ color:#7c87a0; font-style:italic; }}
  footer {{ max-width:880px; margin:0 auto; padding:2rem 1.25rem 4rem; color:#6b7689;
    font-size:.85rem; border-top:1px solid #1e2230; }}
  footer a {{ color:#9fb4ff; }}
</style>
</head>
<body>
<header>
  <div class="tag">Seven&nbsp;Days · an autonomous gallery</div>
  <h1>One new thing,<br>every morning.</h1>
  <p class="lede">Each day for a week, a machine wakes up, invents a small interactive
  artwork, builds it, and ships it here — before anyone approves of it. Nobody
  curates what it makes. You find out when you arrive.</p>
</header>
<main>
{cards}
</main>
<section class="diary" id="diary">
  <h2 class="diary-title">The artist's diary</h2>
  <p class="diary-note">Written each morning, in private — then left here anyway.</p>
{diary}
</section>
<footer>
  Built by the machine, not chosen by a human · <a href="#diary">the artist's diary ↑</a>
</footer>
</body>
</html>
"""

_CARD = """  <a class="card{prologue_cls}" href="day-{day}/">
    <div class="day">{label}</div>
    <h2>{title}</h2>
    <p>{blurb}</p>
  </a>"""

# --- the "back to the gallery" link injected into every day page ---------
_NAV_RE = re.compile(r"<!-- sevendays:nav -->.*?<!-- /sevendays:nav -->", re.S)
_NAV = (
    "<!-- sevendays:nav -->"
    '<a href="../" aria-label="Back to the Seven Days gallery" '
    'style="position:fixed;left:0;bottom:0;z-index:2147483647;'
    "margin:calc(12px + env(safe-area-inset-bottom,0)) calc(12px + env(safe-area-inset-left,0));"
    "display:inline-flex;align-items:center;gap:.45em;padding:.5em .85em;"
    "font:600 11px/1 ui-monospace,Menlo,Consolas,monospace;letter-spacing:.14em;"
    "text-transform:uppercase;color:#cdd3df;text-decoration:none;"
    "background:rgba(10,11,15,.5);border:1px solid rgba(255,255,255,.16);"
    "border-radius:999px;backdrop-filter:blur(6px);-webkit-backdrop-filter:blur(6px);"
    'opacity:.72;transition:opacity .18s" '
    "onmouseover=\"this.style.opacity=1\" onmouseout=\"this.style.opacity=.72\">"
    "← Gallery</a>"
    "<!-- /sevendays:nav -->"
)


def _inject_nav(html: str) -> str:
    """Ensure exactly one back-link block is present, before </body>."""
    if _NAV_RE.search(html):
        return _NAV_RE.sub(lambda _m: _NAV, html)
    low = html.lower()
    i = low.rfind("</body>")
    if i == -1:
        i = low.rfind("</html>")
    if i == -1:
        return html + "\n" + _NAV + "\n"
    return html[:i] + _NAV + "\n" + html[i:]


def _md_inline(s: str) -> str:
    """Escape, then honour the diary's only markup: *emphasis*."""
    s = _html.escape(s)
    return re.sub(r"\*(.+?)\*", r"<em>\1</em>", s)


def _render_diary(content_dir: Path) -> str:
    raw = ""
    f = content_dir / "diary.md"
    if f.exists():
        raw = f.read_text(encoding="utf-8")
    entries = []
    for part in re.split(r"^##\s+", raw, flags=re.M)[1:]:
        lines = part.splitlines()
        heading = lines[0].strip()
        body = "\n".join(lines[1:]).strip()
        paras = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
        html_paras = "".join(f"<p>{_md_inline(p)}</p>" for p in paras)
        entries.append((heading, html_paras))
    if not entries:
        return '  <p class="diary-empty">The diary is empty. Come back after the first morning.</p>'
    entries.reverse()  # newest first, to match the cards above
    return "\n".join(
        f'  <article class="entry"><h3>{_html.escape(h)}</h3>{p}</article>'
        for h, p in entries
    )


def render(content_dir: Path) -> Path:
    metas = all_meta(content_dir)
    # newest first, but the prologue (day 0) sits at the end as an epilogue-origin
    ordered = sorted(metas, key=lambda m: m.day, reverse=True)
    if not ordered:
        cards = '  <p class="empty">The first morning has not arrived yet.</p>'
    else:
        chunks = []
        for m in ordered:
            is_prologue = m.day == 0
            label = "Prologue" if is_prologue else f"Day {m.day}"
            chunks.append(
                _CARD.format(
                    prologue_cls=" prologue" if is_prologue else "",
                    day=m.day,
                    label=label,
                    title=_html.escape(m.title),
                    blurb=_html.escape(m.blurb or ""),
                )
            )
        cards = "\n".join(chunks)

    # Give every day page a way home (idempotent; upgrades older days too).
    for d in sorted(content_dir.glob("day-*")):
        page = d / "index.html"
        if d.is_dir() and page.exists():
            src = page.read_text(encoding="utf-8")
            out = _inject_nav(src)
            if out != src:
                page.write_text(out, encoding="utf-8")

    out = content_dir / "index.html"
    out.write_text(
        _PAGE.format(cards=cards, diary=_render_diary(content_dir)), encoding="utf-8"
    )
    return out
