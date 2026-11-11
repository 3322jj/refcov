# RefCov

Coverage for reference material. Code has test coverage; the documents, videos and data files you hand to an AI coding assistant should have coverage too.

> Status (2026-11-11): implementation has started. Only the state directory, config loading and the hash-chained log exist (`refcov/store.py`, task 1). Everything else below describes what the skeleton is specified to do, not what it does today.

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
| `docs/mcp.example.json` | Example workspace MCP config for the probe server. Copy it to `.kiro/settings/mcp.json` and fill in the absolute repo path. The real file is kept out of git via `.git/info/exclude`, not `.gitignore` |
| `pyproject.toml` | Package metadata; console script `refcov`; runtime dependency `mcp`, dev extras `pytest` and `hypothesis` |
| `refcov/` | Core library (standard library only). So far: `store.py` (state directory `.refcov/`, `refcov.toml` loading, source manifest, append-only hash-chained log with a file lock) and a stub CLI |
| `refcov_mcp/` | MCP server module (empty package for now) |
| `integrations/kiro/` | Kiro integration layer. So far: `refcov.example.toml`, the example config with Kiro paths |
| `tests/` | pytest tests |
| `experiments/mcp-posttooluse/` | Probe MCP server, hook logger, raw logs and the disabled probe hooks from the test showing that PostToolUse on MCP tools carries the correct session ID |

Planned, not yet present: the rest of the core library (adapters, coverage, citations, MCP tools), the Kiro hooks, `apps/shot-coverage` (reference video, per shot), `apps/layer-coverage` (GIS data, per layer property), and an online demo page that replays recorded sessions.

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

`.refcov/sources.json` and `.refcov/log.jsonl` are meant to be committed (the demo page replays the log). `.refcov/cache/`, `errors.log`, `log.lock` and `report-last.json` are git-ignored. `.gitattributes` keeps `*.jsonl` free of line-ending conversion so the hash chain verifies on any machine.

## License

MIT. See `LICENSE`.

Built for Kiroween 2026, Skeleton Crew category.
