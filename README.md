# RefCov

Coverage for reference material. Code has test coverage; the documents, videos and data files you hand to an AI coding assistant should have coverage too.

> Status (2026-11-11): implementation has started. Only the state directory, config loading and the hash-chained log exist (`refcov/store.py`, task 1), plus the `.gitignore` check and a Linux CI workflow (task 2), unit IDs with the Markdown adapter (task 3), source registration with `refcov add` (task 4), the MCP server with `list_units` and `read_unit` (task 5), and the PostToolUse hook that attaches Kiro's session ID to each read (task 6). Everything else below describes what the skeleton is specified to do, not what it does today.

## What it does

- Splits each reference source into units: a section of a Markdown document, a shot of a video, the coordinate system or field list of a GIS layer.
- The AI fetches units through RefCov's MCP tools. Each fetch is recorded. Coverage is computed from those records only; the AI's own claims ("I read the docs") are ignored. The AI can still open files directly, but direct reads do not count.
- In Kiro, a PreToolUse hook blocks `fs_write`, `str_replace` and `fs_append` while the required units for the target path have not been read, and a PreTaskExec hook blocks spec tasks whose cited units have not been read. Writes the hooks did not block are recorded afterwards from Kiro's post-write events and flagged in the report. Writes made through shell commands may not be caught at all (not yet tested).
- Each requirement cites the unit it came from. RefCov lists requirements with no citation (phantom requirements), units that were read but never cited (ignored units), and required units that were never read (ghost units).

Kiro already checks whether requirements contradict each other. RefCov covers the step before that: whether the requirements actually come from the material the user supplied.

## What it does not do

- It proves a unit was fetched, not that it was understood.
- It does not stop an AI that deliberately forges records. The AI has a shell and can write any file on disk. RefCov targets skipped reading and overstated reading, and makes casual edits to the read log visible (hash-chained records).

## Layout

| Path | Contents |
| --- | --- |
| `.kiro/specs/refcov-skeleton/requirements.md` | Skeleton requirements (Chinese, with an English line under each requirement title and user story) |
| `.kiro/steering/` | Steering files: product, tech conventions, citation format, testing, DEVLOG rules, language rules |
| `.kiro/agents/spec-auditor.md` | Read-only custom agent that checks requirement citations |
| `docs/验证结果.md` | Hands-on verification of Kiro hooks and MCP behavior (exit codes, hook payloads, MCP images, session IDs) |
| `docs/DEVLOG.md` | Development log; every entry has an English line (`EN:`) |
| `docs/需求第五稿审阅.md` | External review of requirements draft 5 |
| `docs/设计第二版审阅.md` | External review of design v2 and the task list |
| `docs/decisions/` | The user's chat instructions saved as files, one heading per instruction, so requirements can cite them like any other unit |
| `.kiro/specs/refcov-skeleton/design.md` | Skeleton design: modules, data formats, MCP tools, hooks, unit-ID rules, property tests, build order |
| `.kiro/specs/refcov-skeleton/tasks.md` | Implementation tasks; the thinnest path (register, split, read via MCP, record, report) comes first |
| `docs/mcp.example.json` | Example workspace MCP config for the RefCov server (`python -m refcov_mcp --root <repo root>`). Copy it to `.kiro/settings/mcp.json` and fill in the absolute paths of your Python and the repo. The real file is kept out of git via `.git/info/exclude`, not `.gitignore` |
| `pyproject.toml` | Package metadata; console script `refcov`; runtime dependency `mcp`, dev extras `pytest` and `hypothesis` |
| `refcov/` | Core library (standard library only). So far: `store.py` (state directory `.refcov/`, `refcov.toml` loading, source manifest, append-only hash-chained log with a file lock), `sources.py` (adapter interface, unit-ID rules, splitting units over 4000 characters into `@2`, `@3` parts, and source registration), `adapters/markdown.py` (splits on `#` to `###` headings, skipping fenced code and `>` lines), `api.py` (tool-independent entry points; `read` is the only writer of `read` records) and the CLI (`refcov add` only so far). Known adapter limits: setext headings (`===`, `---` underlines) are not split on, and a blank line inside a code block can become a split point |
| `refcov_mcp/` | MCP server (official SDK, FastMCP over stdio, server name `refcov`). So far two tools: `list_units` and `read_unit`. Each `read_unit` result is one text block ending in the line `refcov-call: c-<seq>`, and appends a `read` record to the log |
| `integrations/kiro/` | Kiro integration layer. So far: `refcov.example.toml` (example config with Kiro paths), `hook.py` (one hook script dispatching on its first argument; currently only `post-mcp`) and `hooks/refcov-post-mcp.json` (PostToolUse on `^mcp_refcov_`: reads the `refcov-call: c-<seq>` last line of the tool result and appends a `session` record). The user copies hook files into `.kiro/hooks/`; moving a file out of that folder disables it immediately |
| `experiments/hook-python/` | Probe hook that records which Python and working directory Kiro hook processes use |
| `tests/` | pytest tests, including `test_gitignore.py`, which fails if any `.gitignore` rule ignores a file under `.kiro` |
| `.github/workflows/ci.yml` | GitHub Actions: runs `pytest` on Linux (Python 3.11 and 3.12) |
| `experiments/mcp-posttooluse/` | Probe MCP server, hook logger, raw logs and the disabled probe hooks from the test showing that PostToolUse on MCP tools carries the correct session ID |

Planned, not yet present: the rest of the core library (coverage, citations, the `check`, `request_token` and `report` MCP tools), the remaining Kiro hooks (gates, protection, status line), `apps/shot-coverage` (reference video, per shot), `apps/layer-coverage` (GIS data, per layer property), and an online demo page that replays recorded sessions.

## Language

Most project documents are written in Chinese. English is provided as follows (see `.kiro/steering/language.md`):

- This README is in English.
- Each requirement title and user story has an English line below it.
- Each steering file starts with an English summary.
- Each DEVLOG bullet has an `EN:` line.

## Requirements

Python 3.11+. The core library uses only the standard library. The MCP server module uses the official `mcp` SDK.

## Setup

1. Install into the `python` that is first on your PATH. Kiro's hook commands run plain `python`, so the package must be importable from that interpreter:

   ```
   python -m pip install -e ".[dev]"
   ```

   Check with `python -c "import refcov"`. If the hooks run a different Python than the one you installed into, they fail silently (errors go to `.refcov/errors.log`).
2. Copy `integrations/kiro/refcov.example.toml` to `refcov.toml` in the repo root and edit it there. Only the user edits this file. There is no `refcov init`; the state directory `.refcov/` is created on the first write.

3. Register reference material from the repo root (`refcov` refuses to run in a directory without `.git`). Only the user runs this; an AI must not (the hook that blocks it comes in task 14):

   ```
   refcov add https://kiro.dev/docs/hooks.md --id kiro-hooks
   refcov add docs/decisions/2026-11-10-review-reply.md --id review-reply
   ```

   Accepted: local `.md` / `.markdown` files inside the repo, and URLs served as `text/markdown` (or `text/plain` when the path ends in `.md`). UTF-8 only. Source IDs use lowercase letters, digits and hyphens. On failure nothing is changed and the reason goes to stderr. Registering unchanged content again writes nothing.

`.refcov/sources.json` and `.refcov/log.jsonl` are meant to be committed (the demo page replays the log). `.refcov/cache/`, `errors.log`, `log.lock` and `report-last.json` are git-ignored. `.gitattributes` keeps `*.jsonl` free of line-ending conversion so the hash chain verifies on any machine.

## License

MIT. See `LICENSE`.

Built for Kiroween 2026, Skeleton Crew category.
