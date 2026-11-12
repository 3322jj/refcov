# RefCov

Coverage for reference material. Code has test coverage; the documents, videos and data files you hand to an AI coding assistant should have coverage too.

> Status (2026-11-11): implementation has started. Only the state directory, config loading and the hash-chained log exist (`refcov/store.py`, task 1), plus the `.gitignore` check and a Linux CI workflow (task 2), unit IDs with the Markdown adapter (task 3), source registration with `refcov add` (task 4), the MCP server with `list_units` and `read_unit` (task 5), the PostToolUse hook that attaches Kiro's session ID to each read (task 6), and the coverage report plus a one-line status on every user message (task 7). The report does not yet compute the required set: for now every unit counts as required, and there is no pass/fail. Everything else below describes what the skeleton is specified to do, not what it does today.

## What it does

- Splits each reference source into units: a section of a Markdown document, a shot of a video, the coordinate system or field list of a GIS layer.
- The AI fetches units through RefCov's MCP tools. Each fetch is recorded. Coverage is computed from those records only; the AI's own claims ("I read the docs") are ignored. The AI can still open files directly, but direct reads do not count.
- In Kiro, a PreToolUse hook blocks `fs_write`, `str_replace` and `fs_append` while the required units for the target path have not been read, and a PreTaskExec hook blocks spec tasks whose cited units have not been read. Writes the hooks did not block are recorded afterwards from Kiro's post-write events and flagged in the report. Writes made through shell commands may not be caught at all (not yet tested).
- Each requirement cites the unit it came from. RefCov lists requirements with no citation (phantom requirements), units that were read but never cited (ignored units), and required units that were never read (ghost units).

Kiro already checks whether requirements contradict each other. RefCov covers the step before that: whether the requirements actually come from the material the user supplied.

## What it does not do

- It proves a unit was fetched, not that it was understood.
- It does not stop an AI that deliberately forges records. The AI has a shell and can write any file on disk. RefCov targets skipped reading and overstated reading, and makes casual edits to the read log visible (hash-chained records).

## Related work

The closest implementation we found is a pull request to Hermes Agent, [NousResearch/hermes-agent#125313](https://github.com/NousResearch/hermes-agent/pull/125313) ("gate whole-folder synthesis on verified full reads"). It was opened on 2026-09-27 and closed by its author on 2026-10-10 without being merged. The issue it answered, [#124875](https://github.com/NousResearch/hermes-agent/issues/124875), is still open (checked 2026-11-12).

The issue reports the same problem RefCov targets: asked to read every file in a folder, the agent reads some, says it read all, and answers. The reporter notes that instructions to read everything were present in the system prompt and in project files and were ignored, and concludes the problem is mechanical, not instructional.

The pull request shares one idea with RefCov: a read only counts while the file is still the version that was read, and the gate consults recorded reads, not the agent's claims. The rest differs:

| | Hermes #125313 | RefCov |
| --- | --- | --- |
| What turns the gate on | Pattern matching on the user's message ("read all files", "read everything") | Sources the user registered with `refcov add`, and rules in `refcov.toml` |
| What is blocked | The final answer of the turn | File writes and spec task starts |
| Granularity | Whole files in a folder, all or nothing | Units (a section, a shot, a layer property), with a required set per target path and per mode |
| Requirements | Not covered | Each requirement cites its unit; requirements with no citation are listed |
| Repeated blocks | Review comments on the PR found the refusal could renew itself every turn, and "stop" or "never mind" did not cancel it | From the second block on the same target, the AI is told to stop and ask the user; the user can set `enforce = false` |

A commenter on that pull request describes an incident with a local implementation of the same design: a message asking to recheck a few edited files matched the "read everything" pattern, the gate demanded an inventory of the whole working directory, and the session used up its remaining API budget before the user interrupted. RefCov does not infer scope from what the user types, which avoids this class of false trigger. It has the opposite cost: nothing is required until the user registers sources and writes rules.

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
| `refcov/` | Core library (standard library only). So far: `store.py` (state directory `.refcov/`, `refcov.toml` loading, source manifest, append-only hash-chained log with a file lock), `sources.py` (adapter interface, unit-ID rules, splitting units over 4000 characters into `@2`, `@3` parts, and source registration), `adapters/markdown.py` (splits on `#` to `###` headings, skipping fenced code and `>` lines), `api.py` (tool-independent entry points; `read` is the only writer of `read` records; `report` and `status_line` are read-only), `coverage.py` (pure coverage calculation) and the CLI (`refcov add`, `refcov report [--json] [--session <id>]`). Known adapter limits: setext headings (`===`, `---` underlines) are not split on, and a blank line inside a code block can become a split point |
| `refcov_mcp/` | MCP server (official SDK, FastMCP over stdio, server name `refcov`). So far three tools: `list_units`, `read_unit` and `report` (the MCP server cannot see Kiro's session ID, so the "this session" column reads "unavailable"). Each `read_unit` result is one text block ending in the line `refcov-call: c-<seq>`, and appends a `read` record to the log |
| `integrations/kiro/` | Kiro integration layer. So far: `refcov.example.toml` (example config with Kiro paths), `hook.py` (one hook script dispatching on its first argument: `post-mcp`, `prompt`), `hooks/refcov-prompt.json` (UserPromptSubmit: writes one status line to stdout, which Kiro adds to the AI's context; the user's message text is never read or logged) and `hooks/refcov-post-mcp.json` (PostToolUse on `^mcp_refcov_`: reads the `refcov-call: c-<seq>` last line of the tool result and appends a `session` record). Copies of both hook files are committed in `.kiro/hooks/`, where Kiro picks them up; moving a file out of that folder disables it immediately |
| `experiments/hook-python/` | Probe hook that records which Python and working directory Kiro hook processes use |
| `tests/` | pytest tests, including `test_gitignore.py`, which fails if any `.gitignore` rule ignores a file under `.kiro` |
| `.github/workflows/ci.yml` | GitHub Actions: runs `pytest` on Linux (Python 3.11 and 3.12) and on Windows (Python 3.12, default `core.autocrlf=true`, so text files are checked out with CRLF) |
| `experiments/mcp-posttooluse/` | Probe MCP server, hook logger, raw logs and the disabled probe hooks from the test showing that PostToolUse on MCP tools carries the correct session ID |

Planned, not yet present: the rest of the core library (required set and pass/fail, citations, the `check` and `request_token` MCP tools), the remaining Kiro hooks (gates, protection), `apps/shot-coverage` (reference video, per shot), `apps/layer-coverage` (GIS data, per layer property), and an online demo page that replays recorded sessions.

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

3. Configure the MCP server. `.kiro/settings/mcp.json` is not in the repo (it holds local paths), so a fresh clone has no RefCov tools until you create it. Copy `docs/mcp.example.json` to `.kiro/settings/mcp.json` and replace both placeholders with absolute paths: the Python you installed into in step 1 (`python -c "import sys; print(sys.executable)"`) and the repo root. Example:

   ```json
   {
     "mcpServers": {
       "refcov": {
         "command": "D:\\pyth\\python.exe",
         "args": ["-m", "refcov_mcp", "--root", "D:\\agent\\kiro\\refcov"],
         "disabled": false
       }
     }
   }
   ```

   Then open the MCP panel in Kiro and check that `refcov` is connected. After pulling changes that add MCP tools, reconnect `refcov` there; a server process started earlier keeps the old tool list.
4. Hooks need no setup. `.kiro/hooks/refcov-post-mcp.json` and `.kiro/hooks/refcov-prompt.json` are committed and take effect as soon as the clone is open in Kiro. Open the repo root itself as the workspace: the hook commands run `python integrations/kiro/hook.py ...` with a relative path. To disable a hook, move its file out of `.kiro/hooks/`.

   **Protection hooks and the escape hatch.** `integrations/kiro/hooks/refcov-pre-write.json` and `refcov-pre-shell.json` are copied into `.kiro/hooks/` by the user. They block (exit code 2) any Kiro write-tool call targeting `.refcov/` or `refcov.toml`, and any shell command whose text mentions `.refcov`, `refcov.toml` or `.kiro/hooks`, runs the hook script or the MCP server, or runs `refcov add` / `refcov confirm`. If the hook script itself fails, these two hooks block too, so a bug could block every write and shell command and the AI cannot undo it. Escape hatch: move `.kiro/hooks/refcov-pre-write.json` and `.kiro/hooks/refcov-pre-shell.json` out of `.kiro/hooks/` (in Explorer or a terminal outside Kiro); protection stops at once. Setting `enforce = false` does not turn protection off.

   Because of these hooks, the AI cannot `git add` files under `.refcov/` or `.kiro/hooks/`, and cannot mention those names in a commit message. The user commits them, or stages them with `git add -u` / `git add -A`. This is text matching on the command line: a rewritten command (string concatenation, `py` instead of `python`) gets through.
5. Register at least one piece of reference material from the repo root (`refcov` refuses to run in a directory without `.git`). Only the user runs this; an AI must not (the hook that blocks it comes in task 14):

   ```
   refcov add https://kiro.dev/docs/hooks.md --id kiro-hooks
   refcov add docs/decisions/2026-11-10-review-reply.md --id review-reply
   ```

   Accepted: local `.md` / `.markdown` files inside the repo, and URLs served as `text/markdown` (or `text/plain` when the path ends in `.md`). UTF-8 only. Source IDs use lowercase letters, digits and hyphens. On failure nothing is changed and the reason goes to stderr. Registering unchanged content again writes nothing. A fresh clone has the committed `.refcov/sources.json` but no `.refcov/cache/`; run `refcov add` again for each listed source before reading it, or `read_unit` reports that the cache is missing.
6. Check the setup. In a Kiro chat, ask the agent to call the RefCov `read_unit` tool for one unit (for example source `kiro-hooks`, unit `Hooks`). The result should end with a line `refcov-call: c-<n>`. Then run `refcov report` in a terminal: the unit counts as read, and it is listed under a session ID rather than under unknown sessions, which shows the PostToolUse hook ran. Your next chat message should also carry the one-line RefCov status in the agent's context.

`.refcov/sources.json` and `.refcov/log.jsonl` are meant to be committed (the demo page replays the log). `.refcov/cache/`, `errors.log`, `log.lock` and `report-last.json` are git-ignored. `.gitattributes` keeps `*.jsonl` free of line-ending conversion so the hash chain verifies on any machine.

## License

MIT. See `LICENSE`.

Built for Kiroween 2026, Skeleton Crew category.
