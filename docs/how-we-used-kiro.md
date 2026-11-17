# How RefCov Used Kiro

## Kiro IDE and CLI

RefCov is a coverage tool for reference material. We built it in the Kiro IDE and tested parts of it with kiro-cli. The judging criteria ask how thoroughly the project uses Kiro, whether there was a strategy, whether several tools were used, and whether there were experiments (rules, 6. Judges & Criteria). The development log records work in the IDE and in kiro-cli only. We did not use Kiro Web or Kiro Crew (docs/DEVLOG.md).

The build ledger starts on 2026-11-15, and every row records claude-haiku-5.5 (docs/施工账.md). The first half of the build used Opus (docs/故事构思.md). Claude reviewed at checkpoints, and the user relayed the reviews. The IDE also ran live checks: a PreTaskExec probe hook stopped one task from starting while a second task started (DEVLOG 2026-11-10, PreTaskExec result).

The CLI ran the comparison trials. Each run was a new process, `kiro-cli chat --v3 --no-interactive --trust-all-tools --model <model> --output-format stream-json`, in its own folder, with no answers from the operator and no sub-agents (docs/验证结果.md, item 9; docs/漏读试验设计.md). `--no-interactive` means nobody answers a prompt. Without `--trust-all-tools`, our CLI runs refused a tool call with "[denied] tool permission approval is not supported in non-interactive mode" (docs/权限实测结果.md, row 4). Kiro's documentation calls the flag a session-scope override for CI use (kiro-permissions, CI and headless environments). It also skips every confirmation in that run, so editor approval results do not carry over to those runs (docs/权限实测结果.md, conclusions).

The IDE and the CLI differ in three ways. The IDE asks before a tool that needs approval runs (docs/权限实测结果.md, row 3), and an explicit `ask` rule offers no "Always allow" (docs/易用性改造方案.md, section 3.1). The CLI in non-interactive mode denies such a call unless a trust flag allows it. An untrusted IDE workspace does not load its MCP configuration, and in our test the five hooks showed as disabled (README, install steps). Interactive CLI runs show a trust screen once per folder, and non-interactive runs skip it (kiro-permissions, Trust a workspace in Kiro CLI). The CLI trials did not test the approval prompt at all, so they say nothing about approval behaviour (docs/漏读试验设计.md).

## Spec-driven development

The repository has six spec folders under `.kiro/specs/`: `refcov-skeleton`, `easy-install`, `source-proposals` (the second layer), `shot-coverage` and `layer-coverage` (the two example applications), and `demo-page`. Each has a requirements document and a design. Three also have a task list (.kiro/specs/).

Requirements cite registered units as `[ref:source/unit]` (.kiro/steering/citation.md). The checker reports phantom requirements (no valid reference), invalid references (a missing source or unit) and unconverted text citations. The second-layer spec was first checked with 0 phantom, 0 invalid and 5 unconverted (docs/施工账.md, 2026-11-17 row). The current report still lists 20 text citations to convert (RefCov report, 2026-11-18), so conversion is not finished.

The first task-start test in the IDE used a probe hook. It stopped task 1 with exit code 2, and task 2 started (DEVLOG 2026-11-10, PreTaskExec result; docs/验证结果.md, item 5). Some later tasks ran from chat rather than through Start task. On 2026-11-11, tasks 3 to 5 did, so the gate's effect on Start task is only partly tested (DEVLOG 2026-11-11, tasks 3 to 5). Two spec items were never built: the watch and confirm checksum groups, and the `refcov confirm` command. The config template says so (DEVLOG 2026-11-17, acceptance; integrations/kiro/init.py).

The spec flow changed the work in ways we can point to. For the second layer, the agent read the Kiro permission documents through MCP before writing the spec. An ad-hoc discussion has no such step, and its sources rest on memory (DEVLOG 2026-11-17, layer 2 spec). During design, the agent found that `register` replaces an entry with the same ID, so the approval path could not call it, and both paths now share one locked write (DEVLOG 2026-11-17, layer 2 spec). During implementation it found that a change to line endings alone is not a content change, and the design was corrected before review (DEVLOG 2026-11-17, layer 2 implementation). Claude's review of commit 16d07b8 then found that state files were not git-ignored in user projects, a gap since the first layer (DEVLOG 2026-11-17, state-directory .gitignore).

The spec process did not catch everything. The wording problem found in the 2026-11-17 acceptance came from hint text that no spec step covered, and a design step was added afterwards (.kiro/specs/source-proposals/design.md, section 7).

## Agent hooks

We use five hooks. Their templates are in `integrations/kiro/hooks/`, and `refcov init` copies them into the user's `.kiro/hooks/` with absolute paths.

- `PreToolUse` on `fs_write`, `str_replace` and `fs_append`: a protection check for the state directory and the config file, then the write gate, which blocks a write to a path whose required units are unread (refcov-pre-write.json).
- `PreToolUse` on `execute_pwsh`, `control_pwsh_process` and `execute_bash`: a shell check that matches command text against protected paths, hook and installer scripts, and user-only subcommands (refcov-pre-shell.json).
- `PreTaskExec`: blocks a task start whose cited units are unread (refcov-pretask.json).
- `PostToolUse` on `mcp_refcov_*`: records the session ID for the read, using the call number on the last line of the result (refcov-post-mcp.json).
- `UserPromptSubmit`: adds a one-line coverage status to the agent's context (refcov-prompt.json).

A hook blocks only with exit code 2 and a reason on stderr. Exit code 1 does not block, and the agent never sees the reason (.kiro/steering/tech.md, measured). On an internal error most hooks allow. The two protection checks block instead, so a crash does not open the protection (.kiro/steering/tech.md; integrations/kiro/hook.py).

The write hook receives the target path, and the shell hook receives the command text. A null command counts as empty text (docs/验证结果.md, item 7). A file written by a shell command did not trigger PostFileSave (item 8), and the write-file hook matches only Kiro's file-write tools, so shell writes are outside it.

Limits: text matching can be evaded by rewriting a command (integrations/kiro/hooks/refcov-pre-shell.json). If the interpreter cannot start, the hook cannot block (.kiro/steering/tech.md). A shell command that moved files out of the hook folder did not prompt, although writes into that folder do (DEVLOG 2026-11-10, closing commit; Kiro's permissions documentation). The escape hatch is to move the two protection files out of `.kiro/hooks/`.

## Steering

The six steering files in `.kiro/steering/` are read in every session: `devlog.md` (how to write the log), `language.md` (where English goes), `product.md` (what the public text may claim, and the scope freeze), `tech.md` (technical, hook, ordering and reading rules), `citation.md` (how requirements cite sources) and `testing.md` (property-test rules). Steering is text the agent reads, not enforcement. The agent has broken these rules, and each break is in the log (DEVLOG 2026-11-13, task 12). Three rules came from failures we can name.

Ordering. On 2026-11-12, during task 8, the agent sent dependent calls in one batch four times, so a test could run before the change it tested and a push before its commit. The user asked for an operation-order section, and dependent steps are now sent one at a time (DEVLOG 2026-11-12, task 8; tech.md).

Required reading. On 2026-11-17, five sub-agents read 174 guide units through MCP for the demo page and returned only counts, so the main agent never held that content. RefCov still recorded the reads, because it does not record which agent made them. The rule in tech.md now says the writing agent reads required units itself, through MCP (DEVLOG 2026-11-17; tech.md). The public text states the same limit (product.md).

Log words. On 2026-11-17 the protection check blocked a commit whose message named a subcommand only the user may run. The check matches text and cannot tell a message from a command without parsing the shell, so we did not add an exception. We reworded the message (DEVLOG 2026-11-17, Claude review entry). The log rule keeps those words out of the log, so logging is not blocked too (devlog.md).

We cannot say which rule made the biggest difference. Each came from a failure we can name (DEVLOG 2026-11-12; DEVLOG 2026-11-17).

## Custom agents

We created one custom agent, `spec-auditor` (`.kiro/agents/spec-auditor.md`). It has read-only tools, preloads `citation.md` through `resources`, and reports in a fixed format in the chat without writing files.

On 2026-11-10 we ran it in the IDE on the draft-5 requirements. Kiro loaded it only after the workspace was trusted and the window reloaded (DEVLOG 2026-11-10, spec-auditor first run). It found no phantom requirements, but three wording problems: citations without item numbers, four reply items no requirement cited, and one handover item cited by two unrelated requirements. It could not check the citations' content, because the handover note lies outside the workspace (same entry). That day we also called it as a sub-agent on the design. It found two acceptance criteria with no design counterpart and six places where the design conflicted with the requirements (DEVLOG 2026-11-10, design audit). Its report marks anything that needs registry data as "not checked" (.kiro/agents/spec-auditor.md).

## MCP

RefCov's MCP server (`refcov_mcp/server.py`) exposes six tools: `list_units`, `read_unit`, `check`, `report`, `propose_sources` and `apply_proposal`. `read_unit` is the only tool that records a read. `check` and `report` only read. `propose_sources` writes a proposal, and `apply_proposal` adds sources after approval.

MCP made three things possible that plain file access could not do. First, counting reads: Kiro's file reads trigger PreToolUse but not PostToolUse, so no hook sees which file was read (DEVLOG 2026-11-10, first step). Second, session attribution: the MCP server cannot see the session ID (docs/验证结果.md, item 6), so a PostToolUse hook records the session for each read. In a probe, four of four calls across two sessions got the right ID (DEVLOG 2026-11-10, step-4 probe; experiments/mcp-posttooluse). Third, images: a tool result can carry an image, and the model read a 3×3 grid of colour blocks correctly (DEVLOG 2026-11-10, first step; docs/验证结果.md, items 4 and 9). Keyframes worked in kiro-cli, but we did not test them in the IDE (docs/验证结果.md, item 10), and the shot-coverage app depends on that path.

A record shows that a workspace read through MCP happened. It does not show who read, or that the agent understood the material or followed it (.kiro/steering/product.md).

## Permissions and workspace trust

The second layer lets the AI register a Markdown file from inside Kiro, only after the user approves. We measured the behaviour first. A user-level `ask` rule prompted every time in the three editor modes, `autoApprove` had no effect in our test, and we found no bypass in the editor (docs/权限实测结果.md; docs/易用性改造方案.md, section 3.1).

`refcov init` prints two rules for the user's permissions file, which lies outside the repository. Read tools are allowed, so reading a unit does not prompt. `apply_proposal` asks every time. `doctor` checks that both rules are present (README, "Registering material from inside Kiro"; DEVLOG 2026-11-17, layer 2 implementation).

The install test on 2026-11-17 passed five of six checks. The sixth failed: Kiro refused to call the tool, because our config comment and hint text said the AI could not register on the user's behalf. We changed the wording. On 2026-11-18, in a fresh chat, the user asked only that docs/tabs.md be registered as reference material. Kiro proposed and applied the registration itself. The tool card above the approval prompt showed the proposal ID, path, SHA-256 and source ID, and the prompt offered no "Always allow". Kiro then explained the change to the required reading scope and asked the user before reading any unit (DEVLOG 2026-11-17, acceptance; DEVLOG 2026-11-18, acceptance).

The limit: `--trust-all-tools` and `--trust-tools` skip the confirmation, so the approval holds only in the editor and in CLI runs without them (docs/权限实测结果.md, conclusions). We do not claim that RefCov prevents deliberate bypass. Likewise, an untrusted workspace does not load its MCP configuration or hooks (README, install steps).

## Property-based testing

We used Hypothesis where the coverage numbers depend on a rule. Requirement 16 has six properties, and `tests/test_properties.py` gives each one a `@given` test (DEVLOG 2026-11-13, task 12). The second layer has properties P1 to P6 and a manual-deletion test (`tests/test_proposals.py`; DEVLOG 2026-11-17, layer 2 implementation). The layer-coverage statistics have five properties at 200 examples each (docs/施工账.md, task 1 row).

We have no record of a property test catching a product bug that unit tests missed. No property found a counterexample in requirement 16 or the second layer (DEVLOG 2026-11-13; DEVLOG 2026-11-17). Two findings concern the tests themselves:

- The first generator for property 16.6 never produced a case where strict mode passed, so the property checked nothing in 100 examples. We changed the generator so that half the cases give every unit a valid read. The product code did not change (DEVLOG 2026-11-13).
- To check that a property can fail, an agent made `assign_ids` ignore borrowed titles on purpose. The property covering borrowed titles failed in five of five runs (DEVLOG 2026-11-11, task 3). This shows the property can fail, not that it found a real bug.

Property 16.4 runs 30 examples instead of 100, because 100 took over 20 seconds locally (DEVLOG 2026-11-13).

## Kiro powers

We looked at Kiro powers and did not use one. An introspect sub-agent read Kiro's power documentation on 2026-11-13. It did not say whether a power can ship hooks or steering, or whether MCP arguments can name the workspace root that our server needs as `--root` (DEVLOG 2026-11-13, read-only job 2). We estimated one to one and a half days of work, which would remove one of five install steps. The estimate is our guess and was not tested. The plan records the decision (docs/冲刺计划.md, section 6).

The other tools are the MCP Python SDK at runtime, Hypothesis and pytest for tests, ffmpeg for the shot app, and geopandas for the GIS app (.kiro/steering/tech.md).

## Building with a small model

The build ledger records claude-haiku-5.5 for every row from 2026-11-15. It lists Haiku for the GIS app (`apps/layer-coverage`), the demo page, the install layer and the second layer. RefCov's hooks were configured in the repository, and Claude reviewed at checkpoints (docs/施工账.md; DEVLOG 2026-11-17).

The cost comparison is one run each. For two tasks, Haiku used 0.18 and 0.37 credits and Opus used 4.77 and 9.31. Haiku took about half the time, and both sides gave the same full-suite result. The only failure on both sides was `test_gitignore.py`, which failed because the copy had an empty `.git` folder (docs/故事构思.md, section 5). The same document says the two halves of the project cannot be compared, because they were different work (docs/故事构思.md, section 6).

Limits: Haiku's code needed review, and on the second task it had rougher parts than Opus's (docs/故事构思.md, section 6). Claude's review of 16d07b8 found a gap in the state-directory ignores that the first layer had introduced (DEVLOG 2026-11-17). Cost is the other limit. RefCov added to the trials: in the extension trial the median credits with RefCov were three to more than thirty times those without, and in the GIS demo about 1.6 to 1.9 times (docs/故事构思.md, section 6). Kiro's automatic model choice does not show which model ran (.kiro/steering/product.md), so the trials name their models.
