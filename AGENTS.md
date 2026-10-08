# Agent instructions

## Agent skills

### Issue tracker

Track issues and specifications in GitHub Issues for `stanley50z/ahk-computer-use`. Read `docs/agents/issue-tracker.md` when creating, reading, or updating issues.

### Triage labels

Use the five canonical triage labels. Read `docs/agents/triage-labels.md` when triaging an issue.

### Domain docs

Use a single-context layout with root `CONTEXT.md` and `docs/adr/`. Read `docs/agents/domain.md` before exploring domain terminology or architectural decisions.

<!-- OPENWIKI:START -->

## OpenWiki

This repository has a generated `openwiki/` evidence index. It is optional just-in-time context, not required startup reading.

- Treat source code and tests as authoritative. A brief's unknowns and review items are verification gaps, not automatic requirements.
- Prefer the narrowest quiet validation that proves the changed behavior. Preserve complete failure output.

Generate locally with `OPENWIKI_PROVIDER=openai-chatgpt` and `OPENWIKI_MODEL_ID=gpt-5.6-luna`. Publish pages from the separate `openwiki/` GitHub Wiki clone. For Wiki generation or publication, read the `openwiki` skill. Regenerate page content through OpenWiki unless the user requests manual edits.

<!-- OPENWIKI:END -->
