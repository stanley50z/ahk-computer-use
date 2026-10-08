# Automatic Wiki synchronization

The project uses a separate native GitHub Wiki clone at `openwiki/`. The main repository ignores that folder. Generation runs locally with the saved ChatGPT login, provider `openai-chatgpt`, and model `gpt-5.6-luna`.

## Hook installation

The repository-local hook is `.githooks/post-commit`. It calls `.githooks/openwiki-sync`, which launches `.githooks/openwiki_post_commit.py` as a detached background process. The runner and launcher are unchanged copies from the `setup-git-repo` skill bundle. Git, Python 3.10+, and an authenticated OpenWiki CLI must be on PATH.

This checkout uses `core.hooksPath=.githooks`. After cloning the main repository elsewhere, initialize or clone its native Wiki into `openwiki/`, complete OpenWiki authentication, then enable the hook with:

```sh
git config --local core.hooksPath .githooks
```

Each project commit returns without waiting for the Wiki job. The worker pulls the Wiki with `--ff-only`, runs `openwiki code --update --print` from the project root, normalizes and validates pages, commits changed pages, and pushes the Wiki's remote default branch. It does not commit, amend, or push the main project. Generated `AGENTS.md` or `CLAUDE.md` changes remain uncommitted for later review. Newly generated OpenWiki CI workflows are removed; unrelated workflows are preserved.

Dirty working trees, divergence, unexpected changes, invalid links, and credential errors stop publication without changing the completed project commit. No force pushes run. A per-Wiki lock prevents overlapping workers. Generation has a 30-minute timeout, with child-process cleanup. Workers and their subprocesses do not open Windows console windows.

## Logs and recovery

Persistent diagnostics are private to the Wiki's Git directory:

- `openwiki/.git/openwiki-background.log` records worker PIDs, status, and failures.
- `openwiki/.git/openwiki-sync.log` contains generation and Git diagnostics. Treat it as sensitive even though common credential formats are redacted.
- `openwiki/.git/openwiki-setup-generation.log` records initial setup generation, including the resolved expired-token failure.
- `openwiki/.git/openwiki-auth-refresh.log` records the successful saved-login refresh without token values.

For this checkout, the log directory is `C:\Users\13982\ahk-computer-use\openwiki\.git\`. Native crash dumps are not configured for these scripts; uncaught Python worker exceptions are captured with tracebacks in the background log. Handled failures and generator crash output appear in the logs above.

After resolving a failure and reviewing pending changes, retry synchronously from the project root:

```sh
python .githooks/openwiki_post_commit.py --root .
```

Use `--generation-timeout <seconds>` to override the manual generation limit. If `openwiki/.git/openwiki-sync.lock` survives an interruption, confirm no worker is running before removing that specific lock. Do not remove it while synchronization is active.
