# Agent Instructions

## Commit messages

- Attribution line: `Co-Authored-By: Claude <model name> <noreply@anthropic.com>` — always include the model name,
  e.g. `Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>`
- Do **not** include a `Claude-Session:` line — the session URL is private.
- Explain **why**, not what — don't restate in prose what's already obvious from `git diff` of
  the commit (e.g. "add a notice to the README", "update section X").

## CHANGELOG

- Only document **user-facing** changes (features, bug fixes, removed support).
- Test tooling changes (e.g. `Pipfile`, `Pipfile.lock`) are not user-facing → no entry needed.
- Wording for Python version support: `declare compatibility with \`python3.X\``

## Pull requests

- Rebase on `master` before opening a PR.
- One commit per PR; amend rather than adding new commits.
- Force-push with `--force-with-lease` on feature branches.
- **Never force-push to `master`.**
- **Always open a pull request — never push directly to `master`.**
- **Never amend or force-push a branch whose PR is already merged or closed** — that rewrites
  history that's already landed (or been reviewed) and leaves a dangling branch that no longer
  reflects what merged. For a follow-up change, create a **new** branch (from current `master`)
  and a **new** PR instead.

## CI failures

- Fix CI failures automatically, iterating until all checks are green — no need to ask first.

## GitHub comments that @-mention a bot

- Commands like `@dependabot rebase` must reach GitHub as plain text — tool-call composition can
  silently insert stray characters (e.g. interpunct `·`) into `@mentions`, which stops the bot from
  recognizing the command.
- After posting such a comment, read it back and confirm the body matches exactly what was
  intended; if not, fix it immediately with an update rather than leaving a broken command posted.

## Pipfile / dependency management

- Generate `Pipfile.lock` on the **lowest** supported Python version.
- When a package is a conditional transitive dependency (e.g. `backports.asyncio.runner`,
  `exceptiongroup`, `tomli`) whose pip markers depend on the lock-generation Python version, add
  it **explicitly** as a direct dependency in `Pipfile` (without a version marker) so it installs
  on all supported Python versions.
- When constrained packages (e.g. `setuptools`, `urllib3`) need to override transitive
  resolution, put them in `[packages]`, not `[dev-packages]`.
