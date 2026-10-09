# Agent instructions

## Agent skills

### Issue tracker

Track issues and specifications in GitHub Issues for `stanley50z/ahk-computer-use`. Read `docs/agents/issue-tracker.md` when creating, reading, or updating issues.

### Triage labels

Use the five canonical triage labels. Read `docs/agents/triage-labels.md` when triaging an issue.

### Domain docs

Use a single-context layout with root `CONTEXT.md` and `docs/adr/`. Read `docs/agents/domain.md` before exploring domain terminology or architectural decisions.

## Development

Run the tests with `python -m pytest`, about fifteen seconds. They open small windows, move the cursor, and take screenshots, and several assert cursor positions, so keep hands off the mouse and keyboard during a run. The screenshot tests need Pillow. Launcher usage, prelude behavior, and debugging artifact paths are in `README.md`.

`acu/` doubles as the agent skill directory: `acu/SKILL.md` is what other harnesses load, and `install_skill.py` links the directory into their skill roots. Keep the skill under about 120 lines; longer material belongs in `README.md`.

## Wiki maintenance

Read `docs/openwiki-sync.md` when installing the post-commit hook, investigating Wiki sync failures, or retrying publication. Project commit and push operations finish without waiting for or repairing the background Wiki job.

<!-- OPENWIKI:START -->

## OpenWiki

This repository has a generated `openwiki/` evidence index. It is optional just-in-time context, not required startup reading.

- Treat source code and tests as authoritative. A brief's unknowns and review items are verification gaps, not automatic requirements.
- Prefer the narrowest quiet validation that proves the changed behavior. Preserve complete failure output.

Generate locally with `OPENWIKI_PROVIDER=openai-chatgpt` and `OPENWIKI_MODEL_ID=gpt-6.1-sol`, using the saved ChatGPT subscription login. The local post-commit hook publishes to the separate `openwiki/` GitHub Wiki clone; this project has no scheduled OpenWiki GitHub Actions workflow. For generation or publication, read the `openwiki` skill and `docs/openwiki-sync.md`. Regenerate page content through OpenWiki unless manual edits are explicitly requested.

<!-- OPENWIKI:END -->
