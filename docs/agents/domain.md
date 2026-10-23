# Domain docs

Read these before exploring domain terminology or architectural decisions:

- `CONTEXT.md` at the repository root defines this project's vocabulary.
- `docs/adr/` records architectural decisions. Read the records relevant to the area being explored, including any superseding records they link to.

This repository uses a single-context layout. `CONTEXT.md` is its glossary; when an engineering skill refers to `GLOSSARY.md`, use `CONTEXT.md` here rather than creating or renaming a second glossary. There is no current context map or context-specific ADR tree.

## Use the glossary's vocabulary

Use terms as defined in `CONTEXT.md` in issue titles, refactor proposals, hypotheses and test names. Avoid synonyms the glossary explicitly rejects.

If a needed concept is missing, first check whether an existing term covers it. Use the `domain-modeling` skill when a real terminology gap or decision needs to be resolved and recorded. Keep implementation details in code or ADRs, not glossary definitions.

## Flag ADR conflicts

If a proposal contradicts an existing ADR, identify the conflict and its reason instead of silently overriding the record. Preserve superseded decisions as history and link to the current decision.

For example: "Contradicts ADR-0009's persistent-desktop-state decision; reopening it would require a reason to restore focus between scripts."
