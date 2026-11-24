# Devpost submission text (Kiroween 2026, Skeleton Crew)

Field by field, ready to paste. Every claim follows `.kiro/steering/product.md` ("must state together" and "do not say").

---

## Project name

RefCov

## Elevator pitch (tagline)

Coverage for reference material: proof that your AI coding agent read the docs you gave it before it wrote the code.

## Links

- Demo video (2:34): https://youtu.be/uLVd3n8dgg0
- Live demo page: https://3322jj.github.io/refcov/
- Code (MIT): https://github.com/3322jj/refcov
- How we used Kiro (full write-up): https://github.com/3322jj/refcov/blob/main/docs/how-we-used-kiro.md

## Category

Skeleton Crew. The skeleton is the RefCov core plus its Kiro integration; the two applications are `apps/shot-coverage` (reference video) and `apps/layer-coverage` (GIS data).

## Built with

Kiro IDE, kiro-cli, Kiro hooks, Kiro specs, Kiro steering, MCP, Python, Hypothesis (property-based tests), pytest, ffmpeg, GitHub Pages, GitHub Actions

---

## About the project

### Inspiration

A project's standards live in the material you hand the AI, not in the model's memory. You put the style guide, the API notes or the data dictionary in the repository, the agent says it followed them, and you have no way to check whether it opened them. Code has test coverage. We wanted the same thing for reference material: **how much of it the AI read should be a number, not a sentence like "I read the docs".**

### Who it's for

People who hand material to an AI and expect it to be followed: a team's style guide or design system, API documentation, a data dictionary, or a reference video to imitate.

I ran into this myself. While making videos for social media, I asked an agent to analyse a video I wanted to model mine on. Its analysis sounded convincing, but the video it made was far from the reference. When I asked again, it admitted it had not watched the reference closely. Time and credits wasted.

Code is the same: the AI says "I followed the project's guidelines", and you cannot check. RefCov gives an answer you can check: which units were read, in which session, and which are still missing. In Kiro, the write waits until the required ones are read.

### What it does

- **Split.** Each registered source is split into units: a section of a Markdown document, a shot of a video, the coordinate system or a field of a GIS layer.
- **Read.** The AI fetches units through RefCov's MCP tools (`read_unit`, `list_units`). Every fetch is recorded in a hash-chained log in the repository. Coverage is computed from those records only. The AI's own claims do not count, and reading the file directly does not count either.
- **Gate.** In Kiro, a `PreToolUse` hook blocks the built-in file-write tools while the required units for that path are unread, and a `PreTaskExec` hook blocks a spec task whose cited units are unread. A `UserPromptSubmit` hook puts a one-line coverage status into the agent's context on every message.
- **Cite.** Requirements cite the unit they came from (`[ref:source/unit]`). The report lists requirements with no source (phantom requirements), units read but never cited (ignored units) and required units never read (ghost units).
- **Register from the chat.** Say "register docs/card.md as reference material". Kiro proposes it with a read-only tool, then registers it with `apply_proposal` after you approve Kiro's permission prompt. That prompt has no "Always allow", so one click cannot make registration automatic. This path only adds sources.
- **Report.** `refcov report` shows coverage per source and per Kiro session; `refcov doctor` checks the install.

Install: `uv tool install git+https://github.com/3322jj/refcov`, then `refcov init` in your project writes the MCP entry and the five hooks.

### What we measured

Five front-end tasks (an account settings page, an FAQ accordion, a dropdown menu, a dark-mode switch, a long article page), claude-haiku-5.5 on kiro-cli 3.3.0, three or four runs per group per task. The workspace held Chrome's modern web guidance (209 guides); a one-line README said front-end code follows it. These are descriptions of 16 runs per group, not statistics.

- Without RefCov, 13 of 16 runs wrote their code without opening any registered guide. With RefCov, 16 of 16 read every required unit before writing.
- The guide practices the checks looked for were used 9 of 58 times without RefCov and 39 of 58 with it. Under a rule written before the runs, 2 of the 5 tasks show a clear difference in the code.
- A headless browser check of the first task's pages found they mostly worked in every group. Without RefCov the features were built too, with older techniques. So the claim is "follows the project's practices", not "the pages work better".
- Reading is not following. In three tasks, some runs read the guides and still chose older code for browser support. In the dark-mode task, runs without RefCov found and read the guide themselves.
- Skipping the guides came from claude-haiku-5.5 and Kiro's automatic model selection (which model it picked is not in the logs). On the first task, claude-sonnet-5.5 without RefCov read 6 to 7 relevant guides every time.
- For the first task, the eight guides were picked knowing which four practices the check would look for. For the other four tasks, the guide pack's own search rules picked them.
- The write gate never fired in the first task; the status line was enough. In the four later tasks it blocked 4 of 12 runs that tried to write after reading part of the guides. In a GIS group with only the gate on, it blocked all 5 runs before they read; each then read the 24 units and wrote.
- RefCov costs credits. On the four later tasks, Haiku runs with RefCov used 3 to more than 30 times the credits of runs without it.

### Two apps from one skeleton

- **`apps/shot-coverage`** turns a reference video into shot units: ffmpeg scene detection writes a shot list, each shot is a required unit, and reading it returns a keyframe. With a 7 min 40 s video (46 shots), every run with the app read all 46 shots (claude-sonnet-5.5, 3 runs per group). Text accuracy was 100% in both groups, and we do not claim the app made runs faster or cheaper. Shots are split at hard cuts only.
- **`apps/layer-coverage`** splits a GIS layer's manifest and its data dictionary into units: the coordinate system, the extent, and one unit per field with statistics computed from the data (24 units for the Bayside subset of NYC Building Footprints). Three GIS rounds did not show that reading changes the answer. RefCov fills information gaps, not skill gaps.

### How we built it, and how we used Kiro

Three roles: Claude proposed the direction, drafted the public text and reviewed at fixed checkpoints; Kiro wrote the code and the specs; the user decided and ran the commands only a person may run, such as registering material. Kiro built RefCov under RefCov: the repository's own hooks gated Kiro's writes, and its own log holds 645 recorded unit reads and 31 protection-check blocks from the build. The write gate's three blocks in this repository were arranged tests, not catches.

- **Specs.** Six spec folders in `.kiro/specs/` (the skeleton, the install layer, registration from chat, both apps, the demo page), each with requirements and a design. Requirements cite registered units, so a requirement the AI invented, or one based on material it never read, shows up in the report. A chat-only build leaves nothing to check this way.
- **Hooks.** Five hooks (`PreToolUse` on file writes and on shell commands, `PreTaskExec`, `PostToolUse` on RefCov's MCP tools, `UserPromptSubmit`). A hook blocks only with exit code 2 and a reason on stderr; we measured that exit code 1 does not block. The two protection checks block when they fail, so a crash does not open them.
- **Steering.** Six files read in every session. Three rules came from failures we can name: sending dependent calls in one batch, sub-agents reading required units in place of the writing agent, and log wording that tripped the protection check.
- **MCP.** RefCov's MCP server is the only way a read counts. The registration tools pair with Kiro's permission rules: the read tools run without a prompt, `apply_proposal` asks every time.
- **Property-based tests.** Hypothesis tests check the coverage rules from the spec (coverage stays between 0 and 1, a repeated read counts once, a cited but unread unit fails, text the AI writes does not change the verdict, strict mode passing implies light mode passing) and the input-handling code such as Markdown splitting. The full suite has 996 passing tests.
- **Kiro IDE and kiro-cli.** We built in the IDE and ran the comparison trials with kiro-cli in non-interactive mode, one fresh folder per run.
- **Switching to a small model.** Halfway through, we switched Kiro to claude-haiku-5.5 and let RefCov guard it: before every write, Haiku had to read the specs and the data notes. Haiku built the GIS app, the demo page and the install layer. On the same two tasks, Haiku used 0.18 and 0.37 credits where Opus 5.5 used 4.77 and 9.31 (one run each). Claude still reviewed Haiku's work at every checkpoint, and the review still found problems. The two halves of the build did different work, so their total credits do not compare.
- **Kiro powers.** We evaluated packaging RefCov as a power and did not build one: the power documentation we read did not show a power shipping hooks or naming the workspace root in its MCP entry. `refcov init` does that setup instead.

### Where Kiro surprised us

- **The reminder worked before the gate did.** While recording the demo, we wanted to film a blocked write. Haiku never tried to write first: its reasoning quoted the hook's status line ("this session 0/18 ... 15 still missing"), it read the 15 units itself, and only then wrote the file.
- **Kiro reported the hole itself.** While building the demo page, Kiro had sub-agents read 174 guide units and bring back only the counts. RefCov does not record which agent read a unit, so the gate let the next write through. Kiro said so in its own report, and we added a steering rule: the agent that writes the code reads the required units itself.
- **Our own wording talked Kiro out of it.** In the first acceptance test of registering material from the chat, Kiro refused to call the registration tool, because our config comments and hint text said the AI could not register on the user's behalf. After we changed the wording, it proposed the registration and waited for the user's approval. Hint text steers the agent too, so we now review it as part of the design.

### Challenges we ran into

- Shell writes are invisible to Kiro's file-write hooks (we tested it), so RefCov does not claim to stop them. The protection checks match command text and can be evaded by a rewritten command.
- RefCov records that a unit was read through MCP in this workspace, not which agent read it. While the demo page was being built, Kiro had sub-agents read 174 guide units, and the gate let the next write through. Kiro reported this itself, and the steering now says the agent that writes the code reads the required units itself.
- RefCov targets skipped and overstated reading, not deliberate forgery. The agent has a shell and can write any file; the hash chain makes casual edits to the log visible.

### Accomplishments that we're proud of

- A number where there used to be a claim: every read is a record, and the repository ships its own read log for anyone to check.
- An honest result. We report where RefCov made no difference (GIS answers, reading not leading to following) next to where it did.
- One skeleton running a video app and a GIS app, and the project's own development run under it.

### What we learned

Agents skipped the material when three things met: a field the model thinks it knows, a task that works without reading, and a default or low-cost model. When any of the three was missing, our trials did not show skipping: in trap tasks, store conventions, ticket backlogs and video comparisons, the models (mostly a fixed claude-sonnet-5.5) read the material. RefCov proves the AI read your material. It does not prove it understood.

### What's next

- Show which agent made each read, so sub-agent reads can be told apart.
- More adapters (PDF, API schemas) on the same skeleton.
- Test project paths with spaces and automatic MCP reconnection in Kiro, which we have not checked yet.

### Third-party material and pre-existing work

The repository was created on 2026-11-10, during the submission period. Third-party material: Chrome's web guidance (Apache 2.0, in `docs/reference/chrome-guides/` with its license), NYC Building Footprints (downloaded by a script, not stored in the repository), the official MCP Python SDK, Hypothesis and ffmpeg. The video's narration voice was generated with ElevenLabs; the video uses no music.
