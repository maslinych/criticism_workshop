# CLAUDE.md

Guidance for Claude Code. This file exists only on the development branch `claude-dev`; `main` is agent-neutral (D-020). All project rules and orientation are in `AGENTS.md`, imported here and binding:

@AGENTS.md

## Claude-specific working notes

- Work on `claude-dev` (or branches made from it). Never commit directly to `main`.
- Read `STATUS.md` and `docs/decisions.md` at the start of every session; update `STATUS.md` at the end.
- Never publish anything yourself (pushes, tags, GitHub releases): give the project owner the commands (D-019).
- Changes reach `main` only by merging `claude-dev` into it, done by the project owner. `CLAUDE.md` must not reach `main`, so the merge removes it:

  ```
  git switch main
  git merge --no-ff --no-commit claude-dev
  git rm -qf --ignore-unmatch CLAUDE.md
  git commit --no-edit
  git switch claude-dev
  ```

  If the merge reports a conflict on `CLAUDE.md` (because it changed on `claude-dev`), the `git rm` line resolves it (`-f` is needed because the merge has just staged the file). Fix any other conflicts before `git commit`.
- Never merge `main` into `claude-dev`: it would delete this file. Nothing is committed on `main` except these merges, so there is nothing to bring back.
