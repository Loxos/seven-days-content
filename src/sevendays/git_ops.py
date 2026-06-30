"""Git plumbing for the published `content` branch.

In production the engine clones the content branch into CONTENT_DIR, writes the
day's artifact, and pushes. A git-sync sidecar on the gallery Deployment then
serves it within ~60s. Push uses a pull --rebase retry loop to survive the
concurrent-push race (the same fix brelock's CI adopted).
"""
from __future__ import annotations

import subprocess

from .config import Config


def _run(args: list[str], check: bool = True) -> subprocess.CompletedProcess:
    r = subprocess.run(args, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"`{' '.join(args)}` failed: {r.stderr.strip()}")
    return r


def _auth_url(cfg: Config) -> str:
    if cfg.content_repo and cfg.content_repo.startswith("https://"):
        return cfg.content_repo.replace(
            "https://", f"https://x-access-token:{cfg.git_token}@", 1
        )
    return cfg.content_repo or ""


def ensure_content_repo(cfg: Config) -> None:
    """Make CONTENT_DIR a working tree of the content branch (prod only)."""
    if not (cfg.content_repo and cfg.git_token):
        return  # local dev: CONTENT_DIR is just a directory
    d = cfg.content_dir
    if (d / ".git").exists():
        _run(["git", "-C", str(d), "fetch", "origin", cfg.content_branch], check=False)
        _run(["git", "-C", str(d), "checkout", cfg.content_branch], check=False)
        _run(["git", "-C", str(d), "pull", "--ff-only", "origin", cfg.content_branch], check=False)
        return
    d.mkdir(parents=True, exist_ok=True)
    url = _auth_url(cfg)
    cloned = _run(
        ["git", "clone", "--branch", cfg.content_branch, "--single-branch", url, str(d)],
        check=False,
    )
    if cloned.returncode != 0:
        # Branch doesn't exist yet — start it.
        _run(["git", "init", str(d)])
        _run(["git", "-C", str(d), "remote", "add", "origin", url])
        _run(["git", "-C", str(d), "checkout", "-b", cfg.content_branch])


def commit_and_push(cfg: Config, message: str) -> None:
    if not cfg.git_push:
        print("[git] GIT_PUSH=false — not committing")
        return
    d = str(cfg.content_dir)
    _run(["git", "-C", d, "config", "user.name", cfg.git_author_name])
    _run(["git", "-C", d, "config", "user.email", cfg.git_author_email])
    _run(["git", "-C", d, "add", "-A"])
    if not _run(["git", "-C", d, "status", "--porcelain"]).stdout.strip():
        print("[git] nothing to commit")
        return
    _run(["git", "-C", d, "commit", "-m", message])
    for _ in range(5):
        pushed = _run(["git", "-C", d, "push", "origin", cfg.content_branch], check=False)
        if pushed.returncode == 0:
            print("[git] pushed")
            return
        _run(["git", "-C", d, "pull", "--rebase", "origin", cfg.content_branch], check=False)
    raise RuntimeError("git push failed after 5 rebase-retry attempts")
