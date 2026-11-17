# RefCov

Coverage for reference material. Code has test coverage; the documents, videos and data files you hand to an AI coding assistant should have coverage too.

> Status (2026-11-17): the install layer is in place. `refcov init` writes the Kiro MCP entry and five hooks with absolute paths; `refcov doctor` checks them read-only and gives a fix for each problem; the protection checks also recognise full paths and quotes. A gated test installs the committed package with `uv tool install` into a temporary directory, runs `init` and `doctor`, and checks that a hook command written by `init` blocks a write when run through the shell. Checked in Kiro on 2026-11-17, in a test folder: once the workspace was trusted, the MCP server connected, the prompt hook's status line appeared, and a write to `.refcov/` was blocked. Not yet checked: project paths that contain spaces, and whether Kiro reconnects a running server after its config is saved.

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
| `.kiro/specs/easy-install/` | Install layer requirements and design (`refcov init`, `refcov doctor`, packaging, protection rules) |
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
| `pyproject.toml` | Package metadata; console script `refcov`; packages `refcov`, `refcov_mcp` and `integrations`, with the five hook templates as package data; runtime dependency `mcp`, dev extras `pytest` and `hypothesis` |
| `refcov/` | Core library (standard library only). `store.py` (state directory `.refcov/`, `refcov.toml` loading, source manifest, append-only hash-chained log with a file lock), `sources.py` (adapter interface, unit-ID rules, splitting units over 4000 characters into `@2`, `@3` parts, and source registration), `adapters/markdown.py` (splits on `#` to `###` headings, skipping fenced code and `>` lines), `api.py` (tool-independent entry points; `read` is the only writer of `read` records; `report`, `status_line` and `doctor_core` are read-only), `coverage.py` (pure coverage calculation) and the CLI (`refcov add`, `refcov report [--json] [--session <id>]`, `refcov sync`, `refcov check`, `refcov check-spec`, and `refcov init` and `refcov doctor`, which the CLI forwards to `integrations/commands.py`). Known adapter limits: setext headings (`===`, `---` underlines) are not split on, and a blank line inside a code block can become a split point |
| `refcov_mcp/` | MCP server (official SDK, FastMCP over stdio, server name `refcov`). Tools: `list_units`, `read_unit` and `report` (the MCP server cannot see Kiro's session ID, so the "this session" column reads "unavailable"). Each `read_unit` result is one text block ending in the line `refcov-call: c-<seq>`, and appends a `read` record to the log |
| `integrations/` | Interface and integration layer. `commands.py` forwards `init` and `doctor` (the command line imports only this module, so the core never names the integration). `kiro/init.py` writes the Kiro MCP entry, the five hooks and the `refcov.toml` template, and probes the Python before it writes a hook. `kiro/doctor.py` is the read-only Kiro part of `doctor`. `kiro/setup.py` is a wrapper that calls `init`, kept for the old instructions. `kiro/hook.py` is the one hook script (`pre-write`, `pre-shell`, `pretask`, `post-mcp`, `prompt`). The five hook templates in `kiro/hooks/` are packaged with it. `kiro/refcov.example.toml` is an example config and is not packaged. The repository's own five hook files in `.kiro/hooks/` use relative paths and are left as they are |
| `experiments/hook-python/` | Probe hook that records which Python and working directory Kiro hook processes use |
| `site/` | Demo page: `index.html`, `style.css`, `app.js` (static, English only) and `data/*.json`, the replay data written by `convert_runs.py` (standard library only) from four recorded runs. `.github/workflows/pages.yml` publishes this folder to GitHub Pages on a push to `main` |
| `tests/` | pytest tests, including `test_gitignore.py`, which fails if any `.gitignore` rule ignores a file under `.kiro`, and `test_clean_install.py`, which installs the committed package with uv into temporary directories and runs `init`, `doctor` and a blocked write (skipped unless `REFCOV_CLEAN_INSTALL=1`) |
| `.github/workflows/ci.yml` | GitHub Actions: runs `pytest` on Linux (Python 3.11 and 3.12) and on Windows (Python 3.12, default `core.autocrlf=true`, so text files are checked out with CRLF) |
| `experiments/mcp-posttooluse/` | Probe MCP server, hook logger, raw logs and the disabled probe hooks from the test showing that PostToolUse on MCP tools carries the correct session ID |

Planned, not yet present: the rest of the core library (required set and pass/fail, citations, the `check` and `request_token` MCP tools), the remaining Kiro hooks (gates, protection), `apps/shot-coverage` (reference video, per shot), `apps/layer-coverage` (GIS data, per layer property), and publishing the demo page in `site/` on GitHub Pages (the page is built; publishing waits for the merge to `main`).

## Language

Most project documents are written in Chinese. English is provided as follows (see `.kiro/steering/language.md`):

- This README is in English.
- Each requirement title and user story has an English line below it.
- Each steering file starts with an English summary.
- Each DEVLOG bullet has an `EN:` line.

## Requirements

Python 3.11+. The core library uses only the standard library. The MCP server module uses the official `mcp` SDK.

## Setup

Install the tool, run `refcov init` in your project, and check the result. You do not need to keep the RefCov clone after installing.

1. Install with uv (uv must be on your PATH, or run it by its full path):

   ```
   uv tool install git+https://github.com/3322jj/refcov
   ```

   If `refcov` is not found afterwards, run `uv tool update-shell` and open a new terminal. Check with `refcov --version`.

   Developers working on RefCov itself install from the clone with `python -m pip install -e ".[dev]"`.

2. From the root of your project (the folder that holds `.git`), run:

   ```
   refcov init
   ```

   It writes `.kiro/settings/mcp.json` (the `refcov` entry, with absolute paths to the Python that runs it and to your project), the five hooks into `.kiro/hooks/`, and a `refcov.toml` template if there is none. It never overwrites `refcov.toml`, and it leaves existing hook files alone. `refcov init --force` replaces the five hook files, and in the `refcov` MCP entry only `command` and `args`; other keys (`autoApprove`, `env`, `disabled`) stay as they are. Only you run `init`; the shell protection blocks an AI from running it.

   If the Python that runs `init` cannot import the hook module, `init` writes nothing and asks you to reinstall with that same Python.

3. Check the result with `refcov doctor`. It is read-only, so an AI may run it. It reports the MCP entry, the five hooks, `refcov.toml`, the registered sources and what is pending, and gives a fix for each problem. Exit code 0 means no problems, 1 means at least one problem, 2 means it was not run from a project root.

   A clean `doctor` does not show that Kiro runs the hooks. To check that, open the project in Kiro and trust the workspace first. Until you trust it, Kiro does not load the workspace's MCP configuration; in our test the MCP server list was empty and the five hooks showed as disabled. Then send one message, look for the one-line RefCov status, and ask Kiro to write a file under `.refcov/`. The write must be blocked.

4. In `refcov.toml`, list the reference material under `[sources]`. Patterns are relative to the project root, and `*` also crosses `/`:

   ```toml
   [sources]
   files = ["guides/forms/*.md", "docs/**/*.md"]
   ```

   Material in other formats needs an adapter declared under `[adapters]` first (see the template). URLs are not allowed here; register a URL with `refcov add` (step 6).

5. Register the material with `refcov sync` from the project root (only you run this). It prints what it registered, what changed, what is missing from disk, and what has left the list. Run it again after you add or change material. The hooks read only what `sync` registered and never read your material files.

   Then reconnect `refcov` in Kiro's MCP panel if it is not listed there. A server process started earlier keeps the old tool list. Whether saving the config is enough to reconnect is not yet verified.

6. Optional: register a URL, or a file you do not want under `[sources]`, with `refcov add` from the repo root (`refcov` refuses to run in a directory without `.git`). Only you run this:

   ```
   refcov add https://kiro.dev/docs/hooks.md --id kiro-hooks
   refcov add docs/decisions/2026-11-10-review-reply.md --id review-reply
   ```

   Accepted: local `.md` / `.markdown` files inside the repo, and URLs served as `text/markdown` (or `text/plain` when the path ends in `.md`). UTF-8 only. Source IDs use lowercase letters, digits and hyphens. On failure nothing is changed and the reason goes to stderr. Registering unchanged content again writes nothing. A fresh clone has the committed `.refcov/sources.json` but no `.refcov/cache/`; run `refcov sync` (for `[sources]` material) or `refcov add` (for the rest) again before reading it, or `read_unit` reports that the cache is missing.

7. Check the setup. In a Kiro chat, ask the agent to call the RefCov `read_unit` tool for one unit (for example source `kiro-hooks`, unit `Hooks`). The result should end with a line `refcov-call: c-<n>`. Then run `refcov report` in a terminal: the unit counts as read, and it is listed under a session ID rather than under unknown sessions, which shows the PostToolUse hook ran. Your next chat message should also carry the one-line RefCov status in the agent's context.

**Protection hooks and the escape hatch.** `refcov init` copies `refcov-pre-write.json` and `refcov-pre-shell.json` into `.kiro/hooks/`. They block (exit code 2) any Kiro write-tool call that targets `.refcov/` or `refcov.toml`. They also block a shell command whose text mentions `.refcov`, `refcov.toml` or `.kiro/hooks`; runs the hook script, the MCP server or an installer script; or runs a user-only command (`refcov add`, `confirm`, `sync` or `init`), including the forms with a full path, quotes or `.exe`. If the hook script itself fails, these two hooks block too, so a bug could block every write and shell command and the AI cannot undo it. Escape hatch: move `.kiro/hooks/refcov-pre-write.json` and `.kiro/hooks/refcov-pre-shell.json` out of `.kiro/hooks/` (in Explorer or a terminal outside Kiro); protection stops at once. Setting `enforce = false` does not turn protection off.

Because of these hooks, the AI cannot `git add` files under `.refcov/` or `.kiro/hooks/`, and cannot mention those names in a commit message. The user commits them, or stages them with `git add -u` / `git add -A`. This is text matching on the command line: a rewritten command (string concatenation, a different interpreter name, an environment variable) gets through.

**Limits of the install.**

- The protection checks match command text. They recognise full paths, quotes and `.exe`, but a rewritten command still gets through.
- RefCov does not stop the AI from writing `.kiro/hooks/` or `.kiro/settings/mcp.json` with its file-write tool. The skeleton design relies on Kiro to ask for confirmation before it writes the hooks folder; that was not re-tested here.
- The commands `init` writes hold absolute paths to the Python that ran `init`. Moving the project, changing or removing that Python, or uninstalling RefCov breaks them. `refcov doctor` reports this, and `refcov init --force` repairs the paths once RefCov is installed again.
- If the hook module cannot be imported, the hook exits with code 1, which does not block the action. A hook broken later stays silent until `refcov doctor` runs.
- The shot-coverage app needs ffmpeg and is not in the package, and its adapter must sit inside your repository.

`.refcov/sources.json` and `.refcov/log.jsonl` are meant to be committed (the demo page replays the log). `.refcov/cache/`, `errors.log`, `log.lock` and `report-last.json` are git-ignored. `.gitattributes` keeps `*.jsonl` free of line-ending conversion so the hash chain verifies on any machine.

## License

MIT. See `LICENSE`.

Built for Kiroween 2026, Skeleton Crew category.
