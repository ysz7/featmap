# featmap

An AI-maintained feature map for your project.

`featmap` creates and validates `MAP.md` — a living, three-level
[Minto-pyramid](https://en.wikipedia.org/wiki/Barbara_Minto) map of your
project (*Project → Layers → Features*) that answers **what** exists and
**where** it lives, never *how* it works.

The twist: you don't maintain the map — your AI assistant does. `featmap init`
installs a rules block into `AGENTS.md` that makes updating the map part of
every change's definition of done, and an optional pre-commit hook reminds
about forgotten updates. The tool itself contains **no LLM integration**: no
API keys, no model calls — just files, a parser and a deterministic validator.

## Why

With AI-assisted development, code is generated faster than a human can absorb
it. A month later you no longer remember which mechanisms your own project has.
Conventional docs die because updating them is a separate manual chore.
`MAP.md` stays alive because the assistant reads it at the start of every
session and must update it *in the same commit* that changes a feature.

## Install

The tool stays **outside** your project — it never becomes a dependency.
Zero runtime dependencies (Python ≥ 3.10, stdlib only):

```sh
uv tool install featmap
# or run it once without installing:
uvx featmap check
```

## Quick start

```sh
cd your-project
featmap init --hook
```

This will:

1. Create `MAP.md` from a template (if missing).
2. Add an AI-assistant rules block to `AGENTS.md` between
   `<!-- featmap:rules:start/end -->` markers (idempotent; `--target claude`
   writes to `CLAUDE.md` instead).
3. Install a **non-blocking** pre-commit hook that runs `featmap check --staged`.
4. For a non-empty project, print a bootstrap prompt — paste it to your AI
   assistant and it will scan the code and fill in the map.

## The development cycle

```text
you:        "add rate limiting to the API client"
assistant:  reads MAP.md, finds the right layer and files instantly
assistant:  implements the feature
assistant:  updates the feature's section in MAP.md   ← same commit
you:        git commit
hook:       featmap check --staged                    ← warns if the map was forgotten
```

The hook never blocks a commit — it only warns (blocking hooks get disabled).

## Example MAP.md

```markdown
<!-- featmap v1 -->
# Project: shopd

E-commerce backend: catalog, cart, payments.
The map is the top of the pyramid: you can stop reading at any level.

## Layer: Payments

Everything money-related: providers, webhooks, refunds.

### Checkout payment {#checkout-payment}

**What:** Charges the customer via the provider and records the order result.
**Files:** `app/payments/charge.py`, `app/payments/webhook.py:42`
**Depends:** [Cart](#cart)
**Status:** active
**Used by:** <!-- autogen --> [Refunds](#refunds)
```

Format rules (v1): exactly one `#`; `##` only for layers (`## Layer: ...`);
`###` only for features with a unique kebab-case `{#anchor}`; no deeper
headings; fields in fixed order `**What:** / **Files:** / **Depends:** /
**Status:**`; feature body ≤ 6 lines; paths relative to the repo root.
This very repository dogfoods the format — see [MAP.md](MAP.md).

## Commands

| Command | What it does |
|---|---|
| `featmap init [--hook] [--target agents\|claude]` | create `MAP.md`, rules block, hook |
| `featmap check [--staged] [--strict]` | validate the map, print `MAP.md:<line>: <CODE> <message>` |
| `featmap links` | regenerate the `**Used by:**` reverse-link lines |
| `featmap version` | print tool and format versions |

`check` exits `1` on errors (`E*`), `0` with output on warnings (`W*`, `V10`);
`--strict` turns warnings into failures. `--staged` adds the V10 check: a
staged file belongs to a feature whose `MAP.md` section has no staged changes.

| Code | Meaning |
|---|---|
| E1 | format rule F1–F10 broken (marker, structure, fields, status…) |
| E2 | duplicate `{#anchor}` |
| E3 | `**Depends:**` points to a non-existent anchor |
| E4 | dependency cycle |
| W1 | a path in `**Files:**` does not exist |
| W2 | something depends on a `deprecated` feature |
| W3 | `**Used by:**` out of sync — run `featmap links` |
| W4 | layer without features / feature without files |
| V10 | (only `--staged`) staged code change without a map update |

## Principles

1. **No LLM inside.** The tool only manages files; all intelligence comes from
   the user's assistant via the `AGENTS.md` rules.
2. **Tool outside, artifacts inside.** Your repo only gains `MAP.md`, a rules
   block and a hook script. The project can be in any language.
3. **Stdlib only.** Zero dependencies, instant `uvx` startup.
4. **What and where, never how.** The "how" lives in code.
5. **Deterministic validator.** Same input — same output, no heuristics.

## License

MIT
