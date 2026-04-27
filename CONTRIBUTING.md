# Contributing

Thanks for considering a contribution. D-ND_LAB is small, opinionated,
and strict about a few things — this file documents what those are so
your time isn't wasted.

## Direction of changes

- **Core** (`core/`) is universal. PRs that bake domain-specific logic
  into core will be asked to refactor into a domain plugin first.
- **Domains** (`domains/`) are content. PRs adding/improving a domain
  are welcome.
- **Original research framework** lives at
  [d-nd.com](https://d-nd.com) (`MM_D-ND/` in the operator's tree).
  D-ND_LAB is the operational template of that framework — changes to
  the model itself happen upstream, not here.

## Before opening a PR

1. **Run a dry-run** on at least one domain:
   ```bash
   dndlab dry-run --domain physics
   ```
   Your change should not break this. If it does, that's expected for
   some refactors — say so in the PR description.

2. **Run a real cycle** if your change touches the agent or adapter
   path, with a free-tier model so it costs nothing:
   ```bash
   LLM_MODEL=tencent/hy3-preview:free dndlab run --domain physics
   ```
   (Free models may not finish; that's a known limitation. Even a
   `max_turns reached` outcome confirms the orchestrator path works.)

3. **Don't add core dependencies lightly.** The core ships with a
   small dependency surface (openai, networkx, click, jsonschema,
   httpx, pyyaml). Adding a new core dep is an Approve-level change
   — open a discussion first.

4. **Domain dependencies are free.** A domain can pip install whatever
   it needs into its own optional-extras.

## Code style

- Python 3.11+. Use modern syntax (`X | Y` unions, `dict[str, Y]`,
  pattern matching where it clarifies).
- Type hints on new code.
- `ruff` for lint, `mypy --strict` aspirational (not yet enforced
  across all of core; new code should pass it).
- Comments explain *why*, not *what*. Code documents itself if named
  well.
- No emojis in code or commit messages unless requested.

## Commit messages

Conventional commits style:

```
feat(scope): brief description

Longer body if needed.
```

Scopes used so far: `core`, `adapter`, `tools`, `domains/<name>`,
`docker`, `docs`, `cli`, `deploy`. Add new ones as needed.

## Anti-patterns the project actively avoids

These are the same anti-patterns the lab scans for in
`structural_check`. PRs that introduce them will be flagged:

1. **Numbers binding qualitative concepts.** Don't use a float as a
   threshold to decide on a state that should be qualitative
   (`if intensity > 0.7:` is a smell — use a structural test).
2. **Hardcoded paths to `/opt/...` in the codebase.** Use
   `core.paths` and env vars.
3. **Domain knowledge in `core/`.** If your change references a
   specific tension id, theory letter, or domain-specific concept,
   that change probably belongs in `domains/<name>/`.
4. **Tool calls without sandboxing.** New tools that touch the
   filesystem must go through `core.tools._Sandbox` or its successor.
5. **Silent failures.** Movements should record errors in
   `ctx.errors` or raise — never swallow.

## Issues

For bug reports, include:
- The cycle's `lab_health.json` and the relevant report
- Output of `dndlab inspect --domain <name>`
- Your `LLM_BASE_URL` and `LLM_MODEL` (not the API key)
- Whether you ran via Docker or standalone

For feature requests, ground the request in a concrete use: "I have
domain X, the current orchestrator does Y, I'd like Z because…".

## Domain contributions

If you want to ship a domain in the seed:

1. Read [docs/domains/extending.md](docs/domains/extending.md)
2. Write the domain in your fork, run several real cycles
3. Open a PR with: the domain dir, a short writeup of what cycles
   produced (3-5 example reports), and the rationale for shipping it
   in-tree (vs as a separate repo)

Not every domain belongs in the seed. The seed should ship domains
that demonstrate distinct capability shapes (numeric, semantic,
operational, …). Variations on existing shapes are usually better as
external repos.

## License

Contributions are MIT-licensed under the project's LICENSE. By
opening a PR you agree to release your contribution under the same
license.
