# Seven Days

**An autonomous creature that invents, builds, and ships a new absurd interactive
artwork every morning — and nobody curates what it makes.**

Each day for a week, a CronJob wakes at 06:00 Europe/Berlin, reads everything the
artist has made so far (plus its own running diary), invents *one* new
self-contained interactive webpage, validates it, publishes it live to
`genesis.hoyos.dev`, writes a creator's statement, and pings a phone. By Sunday:
seven live artifacts, a diary with an arc, and the machine that made them.

> The point isn't the seven toys. The point is **the artist** — a conceive → build →
> ship loop that runs without a human in the approval path. You find out what it
> made when you wake up. The only seed a human touched is the **Prologue** (Day 0),
> a tuning fork struck once so the machine knows what a clear note sounds like.

## Why it can actually ship daily

Every artifact is a **single self-contained `index.html`** — HTML + CSS + vanilla
JS, zero dependencies, zero build step, no external resource loads. "Ship" is just
"write a file and push." That one constraint is what makes unattended daily
publishing reliable instead of a fantasy.

## How it works

```
CronJob (06:00 Europe/Berlin, daily) ─ python -m sevendays
  1. clone the content repo's branch into /data           (git_ops)
  2. read prior days' titles/blurbs + the diary           (content)
  3. ask the model for ONE new piece                      (prompt + llm)
        → TITLE / ===HTML=== / ===STATEMENT=== / ===DIARY===
  4. validate: self-contained, interactive, parses, sane  (guardrails)
        (one retry on failure; never ships broken/off-policy work)
  5. write day-N/{index.html,statement.md,meta.json}      (content)
  6. append the diary entry; regenerate the gallery       (content, gallery)
  7. git push  ──▶  git-sync sidecar serves it in ~60s    (git_ops)
  8. ntfy push to your phone                               (notify)

Day 7's brief is fixed: "make something about what you have become."
```

The engine is **zero-dependency Python** (stdlib `urllib` for HTTP) so the image
stays tiny and the supply chain stays empty. Providers: `anthropic` (default),
`mistral` (EU-hosted, set `LLM_PROVIDER=mistral`), and `stub` (offline, keyless —
for local testing).

## Run it locally (no key, no cluster)

```sh
# Uses the offline stub provider; writes into ./content; never pushes.
PYTHONPATH=src LLM_PROVIDER=stub CONTENT_DIR=./content GIT_PUSH=false python3 -m sevendays
# open content/index.html and content/day-1/index.html in a browser
```

With a real key, locally:

```sh
PYTHONPATH=src LLM_PROVIDER=anthropic ANTHROPIC_API_KEY=sk-ant-... \
  CONTENT_DIR=./content GIT_PUSH=false DAY=1 python3 -m sevendays
```

`node` on PATH enables an extra JS-syntax guardrail on generated scripts (skipped
gracefully if absent).

## Configuration (all via env)

| Var | Default | Notes |
|---|---|---|
| `LLM_PROVIDER` | `stub` | `anthropic` \| `mistral` \| `openai` \| `stub` |
| `MODEL` | per-provider | e.g. `claude-sonnet-4-6` (default), `claude-opus-4-8` for an "Opus day"; for `openai` set this explicitly to a model your key can access |
| `LLM_API_KEY` | — | or `ANTHROPIC_API_KEY` / `MISTRAL_API_KEY` / `OPENAI_API_KEY` |
| `CONTENT_DIR` | `./content` | the content working tree |
| `CONTENT_REPO` / `CONTENT_BRANCH` | — / `content` | prod: cloned into `CONTENT_DIR` |
| `GIT_PUSH` | `false` | prod: `true` |
| `GIT_TOKEN` | — | GitHub PAT, write access to the content repo |
| `TOTAL_DAYS` | `7` | season length; engine no-ops past it |
| `DAY` | (auto) | override the day number (else max existing + 1) |
| `BASE_URL` | `https://genesis.hoyos.dev` | used in the notification link |
| `NTFY_URL` / `NTFY_TOPIC` | `https://ntfy.sh` / — | morning push |

## Going live — what you need to supply

The engine, gallery, CronJob, and ingress are all in `platform-gitops`
(`clusters/production/genesis/`). To start the season:

1. **Content repo.** Create a **public** GitHub repo `seven-days-content`
   (public = git-sync needs no read auth; it's public art anyway). Seed its
   `main` branch with this repo's `content/` directory (the Prologue + gallery):
   ```sh
   # from a checkout of seven-days-content:
   cp -r ../seven-days/content/* .   # day-0/, index.html
   git add -A && git commit -m "Prologue" && git push
   ```
2. **API key.** An Anthropic key, an OpenAI key, or a Mistral key — set
   `LLM_PROVIDER` + `MODEL` in the ConfigMap to match. **Note:** an API key is
   billed separately from a Claude Pro / ChatGPT Plus subscription (it's
   pay-as-you-go in the provider's developer console). Cost here is ~7 small calls
   total — well under €1 for the week. Anthropic and OpenAI are US-hosted; **Mistral
   (FR)** is the EU-native option if sovereignty matters (the prompts carry no
   personal data either way).
3. **Push token.** A GitHub PAT with write access to `seven-days-content`.
4. **ntfy topic.** Pick a hard-to-guess topic string (subscribe to it in the ntfy app).
5. **Seal the secrets** (from `platform-gitops`):
   ```sh
   LLM_API_KEY=sk-ant-... GIT_TOKEN=ghp_... NTFY_TOPIC=<topic> ./hack/seal-genesis.sh
   ```
6. **CI secret.** Add `GITOPS_TOKEN` to this repo's Actions secrets (same PAT the
   other app repos use to bump tags in `platform-gitops`).
7. **Merge** `platform-gitops` → Flux deploys the namespace, gallery, and CronJob.
   `genesis.hoyos.dev` is covered by the `*.hoyos.dev` wildcard — no DNS change.
8. **Smoke test** before waiting for 06:00:
   ```sh
   kubectl --context=production -n genesis create job --from=cronjob/seven-days seven-days-manual
   kubectl --context=production -n genesis logs -f job/seven-days-manual
   ```
   Confirm `genesis.hoyos.dev/day-1/` is live within a minute and the ntfy lands.

## Safety & control (it ships live, by design)

- **Instant veto.** It's git — revert any day in the content repo and git-sync
  removes it within ~60s. The morning push tells you the moment something lands.
- **Pause.** `kubectl -n genesis patch cronjob seven-days -p '{"spec":{"suspend":true}}'`.
- **Guardrails.** Self-containment + interactivity + completeness + a conservative
  content backstop + (locally) a JS-syntax check; one retry, then it declines to ship.
- **Blast radius.** The engine writes only to its own content repo and runs in its
  own namespace. No access to your real data, no cluster mutation, no inbound network.
- **EU sovereignty.** Hosted on your EU cluster. The only egress is the daily
  generation call. Anthropic and OpenAI are US-hosted; flip `LLM_PROVIDER=mistral`
  to keep even that in the EU. Prompts carry no personal data — it's pure creative
  generation.
```
