# Agent instructions (youtube-upload)

This file is **repo-local guidance** for coding agents (Cursor, Claude Code,
Copilot, OpenCode, and similar) working in this repository. It is the
**canonical** place to record project-specific conventions and lessons learned.
Prefer updating this file over one-off chat memory.

## Instruction hierarchy

1. **This file (`AGENTS.md`)** — durable rules for *this* repo (stack, layout,
   style, workflows).
2. **`pyproject.toml`** — tool configuration (Ruff, pytest, Hatch, interrogate,
   pydoclint); treat as source of truth for settings.
3. **User chat** — immediate task scope; if the user gives a rule that should
   persist, fold it into this file (see [Self-improvement](#self-improvement)).

If `CLAUDE.md` or `.claude/CLAUDE.md` appears later, consolidate duplicated
guidance here and point those files at `AGENTS.md` (or replace them with a short
stub) so instructions do not conflict.

## Stack (do not fight the template)

- **Python**: `>=3.10` (see `pyproject.toml`).
- **Env / tasks**: **uv** — `uv sync`, `uv run …`, `uv tool …`. Do **not** use
  `pixi`, `pipx`, or bare `pip install` for environment management. (The upstream
  cookiecutter uses Pixi; **this fork intentionally uses uv** per the maintainer's
  global rules.)
- **Packaging**: **Hatchling** (`[build-system]` in `pyproject.toml`). The
  version is **static** (`[project].version`), bumped by the release workflow
  via `uv version`; `youtube_upload.__init__.VERSION` mirrors it at runtime via
  `importlib.metadata`.
- **Lint & format**: **Ruff** (`ruff check`, `ruff format`) and **pre-commit**
  (see `.pre-commit-config.yaml`).
- **Tests**: **pytest** (`uv run pytest`).
- **CLI**: **argparse**, preserved from upstream to maintain the documented
  upstream UX. **This is a deliberate deviation** from the cookiecutter default,
  which wires the CLI to **Typer**. A future Typer migration is a possible
  follow-up, but until then keep argparse and do not introduce Typer.
- **Docs**: **MkDocs** (Material) — `mkdocs.yaml`, `docs/`.

When adding dependencies, declare them in **`pyproject.toml`** (`[project]` for
runtime, `[project.optional-dependencies].dev` for dev tooling) and re-sync with
`uv sync` rather than ad-hoc `pip install`.

## Repository layout (expectations)

- **Package code**: `youtube_upload/` — main library and CLI (`main.py` exposes
  `main()` and `run()`; `auth/` holds the modernized OAuth layer).
- **Tests**: `tests/` — pytest; mirror public behavior. Smoke tests must not
  require network or credentials.
- **Docs**: `docs/` — Markdown for MkDocs; keep navigation in `mkdocs.yaml`.
- **Config**: `pyproject.toml` at repo root; avoid duplicating tool config in
  random dotfiles.

## Code style (match existing code)

- **Type hints** on new functions and public APIs (the `auth/` package is fully
  typed; follow that lead).
- **`pathlib.Path`** over `os.path` where practical (the modernized `auth/`
  package uses `pathlib`).
- **Ruff** is the formatter and linter; run `uv run ruff format` /
  `uv run ruff check` or `pre-commit run --all-files` before claiming work is
  clean.
- **Docstrings**: Sphinx-style with `:param` / `:returns`, matching the
  `auth/__init__.py` style. Do not strip existing docstring depth.
- Prefer **small, reviewable diffs** — avoid drive-by refactors unrelated to the
  task.

If the user's global preferences differ from this repo, **follow this repo's
existing patterns** unless the user explicitly asks to migrate.

## Quality gates (before saying "done")

- Run **tests**: `uv run pytest` after substantive Python changes.
- Run **Ruff** / **pre-commit** when edits touch Python or config hooks care
  about: `uv run pre-commit run --all-files`.
- Do not claim CI passes unless you actually ran the relevant commands and they
  succeeded.

## Security note (secrets)

- **Never commit** OAuth client-secret files or token files. They grant API
  access and the token contains a refresh token.
- These live under `~/.config/youtube-upload/` (the global default resolution
  path) and are matched by `.gitignore` patterns (`client_secret*.json`,
  `client_secrets*.json`, `token.json`, `*.token`, `.youtube-upload-credentials.json`,
  `.client_secrets.json`).
- If you must keep a fixture for tests, place it under `tests/fixtures/` and
  ensure it is a **dummy** (non-functional) secret — never a real credential.

## Self-improvement (how this file evolves)

When the user corrects the agent ("always do X", "never do Y", "use Z for this
repo"), treat it as a candidate **permanent** rule:

1. **Propose** a concrete edit to `AGENTS.md` (section + wording), integrated
   into existing bullets — not a dated diary entry.
2. **Resolve conflicts** — if the new rule contradicts an older bullet, replace
   or narrow the old text so there is a single clear rule.
3. **Ask once** — "Should I add this to `AGENTS.md`?" — and apply after
   confirmation.

This keeps agent behavior stable across sessions and contributors.

## Glossary

- **OAuth client secrets** (`client_secrets.json`): the JSON you download from
  the Google Cloud Console identifying your OAuth app. Read-only identity, not a
  login.
- **Token file** (`token.json`): the refreshable user credential this tool
  *generates* after the first browser authorization. Secret — treat like a
  password; it lets a client mint new access tokens without re-auth.
- **Resumable upload**: YouTube's chunked upload protocol. If a chunk fails, the
  upload resumes from the last received byte rather than restarting, with
  exponential backoff on transient (5xx / network) errors.
- **Made-for-kids**: a per-video COPPA declaration (`--made-for-kids`) YouTube
  requires for some channels; affects personalization and comments.
- **Loopback OAuth**: the OAuth redirect targets `http://localhost:8080` rather
  than the deprecated out-of-band (OOB) copy/paste flow.

---

*This repository was scaffolded from
[cookiecutter-python-project](https://github.com/ericmjl/cookiecutter-python-project)
and adapted to this fork (uv instead of pixi; argparse instead of Typer; GPLv3).
Edit freely as the project grows.*
