# Workflow for this repo

## File changes

Whenever asked to create or edit a file in this repo, never commit directly to `main`. Instead:

1. Sync `main`: `git checkout main && git pull origin main`
2. Create a new branch named `claude/<short-task-description>`
3. Make the change, committing with a clear, descriptive message
4. Push the branch: `git push -u origin claude/<branch-name>`
5. Open a PR into `main`: `gh pr create --base main --head <branch> --title "..." --body "..."`
6. Wait for the `claude-review` GitHub Actions check to pass: `gh pr checks <PR#> --watch --interval 15`
7. Once it passes, merge automatically — no need to ask first: `gh pr merge <PR#> --merge --delete-branch`

## Output organization

Every command that produces code or other generated output must create a new, self-contained folder holding both that code and its output, rather than scattering files loose at the repo root. Name the folder for the task it came from (e.g. `claude/<short-task-description>/`, matching the branch name), and keep everything the task produced inside it.

## Version history and restoring previous versions

- Always edit files at their existing path rather than renaming or duplicating them, so `git log -- <path>` shows the complete history of a file across every version.
- Never force-push, rebase, or rewrite history on `main` or on pushed task branches. Restoring or undoing a change is always a **new commit** made through a new branch + PR, never an erasure of old commits. This keeps every past version permanently visible and restorable.
- To restore a file to an earlier version: `git checkout <commit-sha> -- <path>`, then commit, push, PR, and merge that restoration like any other change (steps above).
- To browse history: `git log --oneline -- <path>` locally, or the file's "History" view on GitHub.

## Environment notes (Windows, this machine)

- Git for Windows lives at `C:\Program Files\Git\cmd` and the GitHub CLI at `C:\Program Files\GitHub CLI`. Both are on the permanent PATH, but a Claude Code session may need `$env:Path += ";C:\Program Files\Git\cmd;C:\Program Files\GitHub CLI"` added explicitly if a fresh terminal within the session doesn't pick it up.
- `gh` is authenticated as `samuel-moore-22908`, and `gh auth setup-git` has already wired git's credential helper to it globally — this is what lets push/PR/merge run non-interactively.
- Claude's GitHub MCP connector (the `mcp__plugin_github_github__*` tools) is enterprise-managed and may not have API access to this repo. Use the `git`/`gh` CLI workflow above instead of those tools for this repo.
