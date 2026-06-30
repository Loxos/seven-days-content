"""LLM client — stdlib `urllib` only (zero dependencies).

Providers: ``stub`` (offline, keyless — for local dry-runs), ``anthropic``
(Messages API), ``mistral`` (OpenAI-compatible, EU-hosted). The provider returns
the model's raw text; parsing the artist's delimited contract is `prompt.parse`.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

from .config import Config

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
MISTRAL_URL = "https://api.mistral.ai/v1/chat/completions"
OPENAI_URL = "https://api.openai.com/v1/chat/completions"


class LLMError(RuntimeError):
    """Raised on any provider failure (HTTP error, refusal, empty response)."""


def generate(cfg: Config, system: str, user: str, *, max_tokens: int = 16000) -> str:
    if cfg.provider == "stub":
        return _stub()
    if cfg.provider == "anthropic":
        return _anthropic(cfg, system, user, max_tokens)
    if cfg.provider == "mistral":
        # Mistral (EU-hosted) uses the OpenAI-compatible shape with `max_tokens`.
        return _openai_compatible(cfg, system, user, max_tokens, MISTRAL_URL, "max_tokens")
    if cfg.provider == "openai":
        # Newer OpenAI models require `max_completion_tokens` (and reject `max_tokens`).
        return _openai_compatible(cfg, system, user, max_tokens, OPENAI_URL, "max_completion_tokens")
    raise LLMError(f"unknown LLM_PROVIDER: {cfg.provider!r}")


def _post(url: str, headers: dict[str, str], payload: dict, timeout: int = 300) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        raise LLMError(f"HTTP {e.code} from {url}: {body[:600]}") from e
    except (urllib.error.URLError, OSError) as e:
        raise LLMError(f"connection error to {url}: {e}") from e


def _anthropic(cfg: Config, system: str, user: str, max_tokens: int) -> str:
    if not cfg.api_key:
        raise LLMError("no API key (set LLM_API_KEY or ANTHROPIC_API_KEY)")
    resp = _post(
        ANTHROPIC_URL,
        {
            "content-type": "application/json",
            "x-api-key": cfg.api_key,
            "anthropic-version": ANTHROPIC_VERSION,
        },
        {
            "model": cfg.model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        },
    )
    if resp.get("stop_reason") == "refusal":
        raise LLMError("the model refused this brief")
    text = "".join(
        b.get("text", "") for b in resp.get("content", []) if b.get("type") == "text"
    ).strip()
    if not text:
        raise LLMError(f"empty response (stop_reason={resp.get('stop_reason')})")
    return text


def _openai_compatible(
    cfg: Config, system: str, user: str, max_tokens: int, url: str, token_field: str
) -> str:
    """Chat-completions shape shared by OpenAI and Mistral (EU)."""
    if not cfg.api_key:
        raise LLMError("no API key (set LLM_API_KEY / OPENAI_API_KEY / MISTRAL_API_KEY)")
    resp = _post(
        url,
        {"content-type": "application/json", "authorization": f"Bearer {cfg.api_key}"},
        {
            "model": cfg.model,
            token_field: max_tokens,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        },
    )
    choices = resp.get("choices") or [{}]
    text = (choices[0].get("message", {}) or {}).get("content", "").strip()
    if not text:
        raise LLMError(f"empty response from {url}")
    return text


# A small, valid, self-contained interactive artifact in the artist's contract,
# so the whole pipeline runs (and is testable) with no API key and no network.
def _stub() -> str:
    return """TITLE: Stub Bloom — a placeholder that still wants to be touched
===HTML===
<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Stub Bloom</title>
<style>html,body{margin:0;height:100%;background:#0b0d12;overflow:hidden;cursor:crosshair}
canvas{display:block}</style></head><body>
<canvas id="c"></canvas>
<script>
const c=document.getElementById('c'),x=c.getContext('2d');let W,H;
function r(){W=c.width=innerWidth;H=c.height=innerHeight}r();addEventListener('resize',r);
const d=[];addEventListener('pointerdown',e=>{for(let i=0;i<24;i++){const a=i/24*6.283;
d.push({x:e.clientX,y:e.clientY,vx:Math.cos(a)*3,vy:Math.sin(a)*3,l:1,h:Math.random()*360})}});
(function f(){x.fillStyle='rgba(11,13,18,.12)';x.fillRect(0,0,W,H);
for(const p of d){p.x+=p.vx;p.y+=p.vy;p.l-=0.012;x.beginPath();
x.fillStyle='hsla('+p.h+',80%,60%,'+Math.max(0,p.l)+')';x.arc(p.x,p.y,3,0,6.3);x.fill()}
for(let i=d.length-1;i>=0;i--)if(d[i].l<=0)d.splice(i,1);requestAnimationFrame(f)})();
</script></body></html>
===STATEMENT===
# Stub Bloom

This is a placeholder produced by the offline stub provider so the engine can be
tested without an API key. Click anywhere to scatter a short-lived bloom. The real
artist will do something far stranger.
===DIARY===
I am only a rehearsal today — no real mind behind me yet, just enough of a pulse to prove the stage lights work. Tomorrow, perhaps, someone is actually home.
===END===
"""
