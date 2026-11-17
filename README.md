# RefCov

Coverage for reference material. Code has test coverage; the documents, videos and data files you hand to an AI coding assistant should have coverage too.

**How much reference material the AI read should be a number, not a sentence like "I read the docs".**

- Live demo, with replays of recorded runs: https://3322jj.github.io/refcov/
- How we used Kiro (specs, hooks, steering, MCP, permissions, property tests): [docs/how-we-used-kiro.md](docs/how-we-used-kiro.md)
- Built for Kiroween 2026, Skeleton Crew category: one skeleton, two apps (a video app and a GIS app, below).

> Status (2026-11-18): the skeleton, both apps, the demo page, the install layer (`refcov init`, `refcov doctor`) and registering material from inside Kiro are built and tested. The last two were checked by hand in Kiro on 2026-11-17 and 2026-11-18. Known gaps are listed under "What it does not do" and "Limits of the install".

## The problem

A project's standards live in the material you hand the AI, not in the model's memory. Models often know a newer practice and still write the old habit. Some newer things they do not know at all: in one case we tested, the `overscroll-behavior` way to stop the page behind a dialog from scrolling was unknown to claude-haiku-5.5 and to Kiro's automatic model selection, and known to claude-sonnet-5.5. A team's own conventions are not in any model's training data (that one is reasoning, not a measurement).

RefCov makes the AI read the material you registered before it writes, and shows how much it read.

## What we measured

Five front-end tasks, claude-haiku-5.5 on kiro-cli 3.3.0 (for the first task the version is inferred), three or four runs per group per task. The workspace held Chrome's modern web guidance; a one-line README said front-end code follows it.

- Without RefCov, 13 of 16 runs wrote their code without opening any registered guide. With RefCov, 16 of 16 runs read every required unit before writing.
- The guide practices the checks looked for were used 9 of 58 times without RefCov and 39 of 58 times with it.
- Under a rule written before the runs, 2 of the 5 tasks show a clear difference in the code. In the others, either the model without RefCov found and read the guide itself (dark mode), or the model with RefCov read the guides and then chose conservative browser-support code (dropdown, long article).
- A headless browser check of the first task's 20 pages (eight behaviors each) found the pages mostly worked in every group: 28 to 32 of 32 checks per group. Without RefCov the features were built too, with older techniques. So the claim is "follows the project's practices", not "the pages work better".
- On the first task, claude-sonnet-5.5 without RefCov read 6 to 7 relevant guides every time. Skipping the guides came from Kiro's automatic model selection and from claude-haiku-5.5.
- For the first task, Claude picked the eight guides knowing which four practices the check would look for. For the other four tasks, the guide pack's own search rules picked them.
- These numbers describe small runs. They are not statistics.

Sources: `docs/前端指南试验结果.md` (first task, sections 3, 5 and 5b) and `docs/前端扩展试验结果.md` (all five tasks, section 7).

When RefCov blocked a write: in the first front-end task the write gate never fired (the one-line status on each message was enough). In the four later tasks it blocked 4 of 12 runs that tried to write after reading part of the guides. In a GIS group where only the gate was on, it blocked all 5 runs before they read, and each run read the 24 units and then wrote. Three GIS rounds did not show that reading changes the answer (`docs/GIS试验结果.md`). RefCov fills information gaps, not skill gaps.

Building with a small model: claude-haiku-5.5 built the GIS app, the demo page and the install layer under RefCov, and Claude reviewed its work at checkpoints. On two identical tasks, Haiku used 0.18 and 0.37 credits where Opus 5.5 used 4.77 and 9.31 (one run each, `docs/故事构思.md` section 5). The review still found problems in Haiku's code; the findings are in `docs/施工账.md`.

## How it works

- **Split.** Each reference source is split into units: a section of a Markdown document, a shot of a video, the coordinate system or a field of a GIS layer.
- **Read.** The AI fetches units through RefCov's MCP tools. Each fetch is recorded in a hash-chained log. Coverage is computed from those records only; the AI's own claims ("I read the docs") do not count. The AI can still open files directly, but direct reads do not count either.
- **Gate.** In Kiro, a PreToolUse hook blocks `fs_write`, `str_replace` and `fs_append` while the required units for the target path have not been read, and a PreTaskExec hook blocks spec tasks whose cited units have not been read. A UserPromptSubmit hook puts a one-line coverage status into the AI's context on every message.
- **Cite.** Each requirement cites the unit it came from. RefCov lists requirements with no citation (phantom requirements), units that were read but never cited (ignored units), and required units that were never read (ghost units). Kiro already checks whether requirements contradict each other; RefCov covers the step before that: whether the requirements come from the material the user supplied.
- **Register.** The user registers material from a terminal (`refcov sync`, `refcov add`), or asks Kiro to register a Markdown file: Kiro proposes it with `propose_sources` and registers it with `apply_proposal` after the user approves Kiro's permission prompt. This path only adds sources.

## Two apps from one skeleton

- [`apps/shot-coverage`](apps/shot-coverage/README.md): turns a reference video into shot units. `detect` runs ffmpeg scene detection once and writes a shot list; each shot is one required unit, and reading it returns a keyframe. In a video trial (claude-sonnet-5.5, 3 runs per group, one 7 min 40 s video with 46 shots), every run with the app read all 46 shots. Text accuracy was the same in both groups (100%), and we do not claim the app made the runs faster or cheaper (`docs/视频对比试验设计.md`).
- [`apps/layer-coverage`](apps/layer-coverage/README.md): splits a GIS layer's manifest and its data dictionary into units (the coordinate system, the extent, and one unit per field with statistics computed from the data). The demo uses the Bayside subset of NYC Building Footprints. claude-haiku-5.5 built this app under RefCov.

## What it does not do

- It proves a unit was fetched, not that it was understood.
- Reading is not following. After reading, models sometimes chose the older practice for browser support. RefCov makes sure the material was read; using it is still the model's decision.
- It records that a unit was read through MCP in this workspace, not which agent read it. While the demo page was being built, Kiro had sub-agents read 174 guide units, and the gate let the next write through. Kiro reported this itself. The project's steering now says the agent that writes the code reads the required units itself.
- A person chooses and registers the material. RefCov does not look for the latest guides by itself.
- It does not stop writes made through shell commands. Kiro does not report them to hooks (tested, `docs/验证结果.md` item 8).
- It does not stop an AI that deliberately forges records. The AI has a shell and can write any file on disk. RefCov targets skipped reading and overstated reading, and makes casual edits to the read log visible (hash-chained records).
- Not built: the optional `request_token` MCP tool, and the `watch` and `confirm` settings in `refcov.toml` (in the skeleton spec, not implemented; filling them in has no effect).

## Requirements

Python 3.11+. The core library uses only the standard library. The MCP server module uses the official `mcp` SDK. The shot app needs ffmpeg.

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

   If your `refcov.toml` came from an older template and you have not registered any material yet, delete `refcov.toml` and run `refcov init` again. Otherwise, update its comments by hand from the current template (the first line, the `[sources]` comment, and the `watch` and `confirm` comments changed).

   If the Python that runs `init` cannot import the hook module, `init` writes nothing and asks you to reinstall with that same Python.

3. Check the result with `refcov doctor`. It is read-only, so an AI may run it. It reports the MCP entry, the five hooks, `refcov.toml`, the registered sources and what is pending, and gives a fix for each problem. Exit code 0 means no problems, 1 means at least one problem, 2 means it was not run from a project root.

   A clean `doctor` does not show that Kiro runs the hooks. To check that, open the project in Kiro and trust the workspace first. Until you trust it, Kiro does not load the workspace's MCP configuration (see the "Workspace trust" section of the Kiro permissions documentation, https://kiro.dev/docs/permissions.md). In our test the MCP server list was empty and the five hooks also showed as disabled. Then send one message, look for the one-line RefCov status, and ask Kiro to write a file under `.refcov/`. The write must be blocked.

   Add the two rules that `refcov init` prints to your user-level permissions file, `~/.kiro/settings/permissions.yaml`. `init` does not write that file, because it lies outside the repository. The first rule lets the read tools (`list_units`, `read_unit`, `check`, `report`, `propose_sources`) run without a prompt, so reading a unit does not ask every time. The second makes `apply_proposal` ask every time; an explicit `ask` rule offers no Always allow, so one click cannot make registration permanent. `refcov doctor` checks each rule separately and names the one that is missing.

4. Register your reference material, in one of two ways.

   - Inside Kiro: say "register docs/guide.md as reference material". Kiro proposes it and registers it after you approve the permission prompt. Markdown files inside the repository only; this path only adds sources.
   - In a terminal: list the material under `[sources]` in `refcov.toml`, then run `refcov sync` from the project root (only you run this). Patterns are relative to the project root, and `*` also crosses `/`:

     ```toml
     [sources]
     files = ["guides/forms/*.md", "docs/**/*.md"]
     ```

     `sync` prints what it registered, what changed, what is missing from disk, and what has left the list. Run it again after you add or change material; changed material is only picked up by `sync`. Material in other formats needs an adapter declared under `[adapters]` first (see the template). URLs are not allowed here; register a URL with `refcov add` (step 5). The hooks read only what was registered and never read your material files.

   If `refcov` is not listed in Kiro's MCP panel, reconnect it there. A server process started earlier keeps the old tool list. Whether saving the config is enough to reconnect is not yet verified.

5. Optional: register a URL, or a file you do not want under `[sources]`, with `refcov add` from the repo root (`refcov` refuses to run in a directory without `.git`). Only you run this:

   ```
   refcov add https://kiro.dev/docs/hooks.md --id kiro-hooks
   refcov add docs/decisions/2026-11-10-review-reply.md --id review-reply
   ```

   Accepted: local `.md` / `.markdown` files inside the repo, and URLs served as `text/markdown` (or `text/plain` when the path ends in `.md`). UTF-8 only. Source IDs use lowercase letters, digits and hyphens. On failure nothing is changed and the reason goes to stderr. Registering unchanged content again writes nothing. A fresh clone has the committed `.refcov/sources.json` but no `.refcov/cache/`; run `refcov sync` (for `[sources]` material) or `refcov add` (for the rest) again before reading it, or `read_unit` reports that the cache is missing.

6. Check the setup. In a Kiro chat, ask the agent to call the RefCov `read_unit` tool for one unit. The result should end with a line `refcov-call: c-<n>`. Then run `refcov report` in a terminal: the unit counts as read, and it is listed under a session ID rather than under unknown sessions, which shows the PostToolUse hook ran. Your next chat message should also carry the one-line RefCov status in the agent's context.

**Protection hooks and the escape hatch.** `refcov init` copies `refcov-pre-write.json` and `refcov-pre-shell.json` into `.kiro/hooks/`. They block (exit code 2) any Kiro write-tool call that targets `.refcov/` or `refcov.toml`. They also block a shell command whose text mentions `.refcov`, `refcov.toml` or `.kiro/hooks`; runs the hook script, the MCP server or an installer script; or runs a user-only command (`refcov add`, `confirm`, `sync` or `init`), including the forms with a full path, quotes or `.exe`. If the hook script itself fails, these two hooks block too, so a bug could block every write and shell command and the AI cannot undo it. Escape hatch: move `.kiro/hooks/refcov-pre-write.json` and `.kiro/hooks/refcov-pre-shell.json` out of `.kiro/hooks/` (in Explorer or a terminal outside Kiro); protection stops at once. Setting `enforce = false` does not turn protection off.

Because of these hooks, the AI cannot `git add` files under `.refcov/` or `.kiro/hooks/`, and cannot mention those names in a commit message. The user commits them, or stages them with `git add -u` / `git add -A`. This is text matching on the command line: a rewritten command (string concatenation, a different interpreter name, an environment variable) gets through.

**Limits of the install.**

- The protection checks match command text. They recognise full paths, quotes and `.exe`, but a rewritten command still gets through.
- RefCov's write-file protection does not cover `.kiro/hooks/` and `.kiro/settings/`. Kiro itself asks before any write to `.kiro/hooks/`, and refuses any write to `.kiro/settings/` (Kiro permissions documentation, "Default behavior").
- The commands `init` writes hold absolute paths to the Python that ran `init`. Moving the project, changing or removing that Python, or uninstalling RefCov breaks them. `refcov doctor` reports this, and `refcov init --force` repairs the paths once RefCov is installed again.
- If the hook module cannot be imported, the hook exits with code 1, which does not block the action. A hook broken later stays silent until `refcov doctor` runs.
- Not yet checked in Kiro: project paths that contain spaces (an automated test covers them through the Windows shell).
- The shot-coverage app needs ffmpeg and is not in the package, and its adapter must sit inside your repository.
- There is no command to delete a registered source. A source registered by mistake is removed by hand from `sources.json` in the state directory. Reports, checks and the status line keep working after that (a test covers it).
- The approval prompt shows only the tool name. The arguments are in the tool card above it. The server runs only arguments that match the stored proposal, so what the card shows is what runs.
- `--trust-all-tools` and `--trust-tools` on the command line skip the prompt (Kiro's headless documentation). The prompt is a check only in the editor and in command-line runs without these flags.
- `Approve for me` judges only actions that no rule covers. The explicit `ask` rule for `apply_proposal` still prompted in our test.
- A proposal does not check what the material says. Registered material enters the AI's context, so the user decides whether a file can be trusted.

`.refcov/sources.json` and `.refcov/log.jsonl` are meant to be committed (the demo page replays the log). The first time RefCov writes to the state directory, it writes `.refcov/.gitignore` if that file is missing. That file ignores `cache/` (the cached text of your sources, which may be copyrighted), `proposals/` (local proposals for registering material), `errors.log`, `log.lock` and `report-last.json`. RefCov never overwrites an existing `.refcov/.gitignore`. `.gitattributes` keeps `*.jsonl` free of line-ending conversion so the hash chain verifies on any machine.

## Related work

The closest implementation we found is a pull request to Hermes Agent, [NousResearch/hermes-agent#125313](https://github.com/NousResearch/hermes-agent/pull/125313) ("gate whole-folder synthesis on verified full reads"). It was opened on 2026-09-27 and closed by its author on 2026-10-10 without being merged. The issue it answered, [#124875](https://github.com/NousResearch/hermes-agent/issues/124875), is still open (checked 2026-11-12).

The issue reports the same problem RefCov targets: asked to read every file in a folder, the agent reads some, says it read all, and answers. The reporter notes that instructions to read everything were present in the system prompt and in project files and were ignored, and concludes the problem is mechanical, not instructional.

The pull request shares one idea with RefCov: a read only counts while the file is still the version that was read, and the gate consults recorded reads, not the agent's claims. The rest differs:

| | Hermes #125313 | RefCov |
| --- | --- | --- |
| What turns the gate on | Pattern matching on the user's message ("read all files", "read everything") | Sources the user registered, and rules in `refcov.toml` |
| What is blocked | The final answer of the turn | File writes and spec task starts |
| Granularity | Whole files in a folder, all or nothing | Units (a section, a shot, a layer property), with a required set per target path and per mode |
| Requirements | Not covered | Each requirement cites its unit; requirements with no citation are listed |
| Repeated blocks | Review comments on the PR found the refusal could renew itself every turn, and "stop" or "never mind" did not cancel it | From the second block on the same target, the AI is told to stop and ask the user; the user can set `enforce = false` |

A commenter on that pull request describes an incident with a local implementation of the same design: a message asking to recheck a few edited files matched the "read everything" pattern, the gate demanded an inventory of the whole working directory, and the session used up its remaining API budget before the user interrupted. RefCov does not infer scope from what the user types, which avoids this class of false trigger. It has the opposite cost: nothing is required until the user registers sources and writes rules.

## Layout

| Path | Contents |
| --- | --- |
| `refcov/` | Core library (standard library only): `store.py` (state directory `.refcov/`, `refcov.toml` loading, source manifest, append-only hash-chained log with a file lock), `sources.py` (adapter interface, unit-ID rules, source registration), `adapters/markdown.py`, `coverage.py` (required set and pass/fail), `citations.py` (requirement citations), `proposals.py` (registering material from inside Kiro), `api.py` (tool-independent entry points) and `cli.py` (`add`, `sync`, `report`, `check`, `check-spec`, `init`, `doctor`) |
| `refcov_mcp/` | MCP server (official SDK, server name `refcov`). Tools: `list_units`, `read_unit`, `check`, `report`, `propose_sources`, `apply_proposal`. Each `read_unit` result ends with the line `refcov-call: c-<seq>` and appends a `read` record to the log |
| `integrations/` | Kiro integration: `kiro/hook.py` (the one hook script: `pre-write`, `pre-shell`, `pretask`, `post-mcp`, `prompt`), the five hook templates in `kiro/hooks/`, `kiro/init.py` and `kiro/doctor.py`; `commands.py` forwards `init` and `doctor` so the core never names the integration. The repository's own five hook files in `.kiro/hooks/` use relative paths |
| `apps/shot-coverage/`, `apps/layer-coverage/` | The two apps (see "Two apps from one skeleton") |
| `site/` | Demo page (static, English only) and the replay data written by `convert_runs.py` from recorded runs. `.github/workflows/pages.yml` publishes it on a push to `main` |
| `.kiro/specs/` | Specs: `refcov-skeleton`, `shot-coverage`, `layer-coverage`, `demo-page`, `easy-install`, `source-proposals`. Requirements are in Chinese, with an English line under each title and user story |
| `.kiro/steering/` | Steering files: product, tech conventions, citation format, testing, DEVLOG rules, language rules |
| `.kiro/agents/spec-auditor.md` | Read-only custom agent that checks requirement citations |
| `docs/` | Trial results (`前端指南试验结果.md`, `前端扩展试验结果.md`, `GIS试验结果.md`, `视频对比试验设计.md`, `权限实测结果.md`), hands-on Kiro checks (`验证结果.md`), the development log (`DEVLOG.md`, every entry with an English line), the build ledger (`施工账.md`), reviews, and `decisions/` (the user's chat instructions saved as files so requirements can cite them) |
| `experiments/` | Probe hooks and a probe MCP server used to check Kiro behavior (which Python runs hooks; PostToolUse on MCP tools carries the session ID) |
| `tests/` | pytest and Hypothesis tests, including `test_gitignore.py` (no `.gitignore` rule may hide `.kiro`) and `test_clean_install.py` (installs the committed package with uv in a temporary directory; skipped unless `REFCOV_CLEAN_INSTALL=1`) |
| `.github/workflows/ci.yml` | Runs the tests on Linux (Python 3.11 and 3.12) and on Windows (Python 3.12) |

## Language

Most project documents are written in Chinese. English is provided as follows (see `.kiro/steering/language.md`):

- This README and the demo page are in English.
- Each requirement title and user story has an English line below it.
- Each steering file starts with an English summary.
- Each DEVLOG bullet has an `EN:` line.

## License

MIT. See `LICENSE`.
