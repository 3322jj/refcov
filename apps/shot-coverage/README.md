# Shot coverage

EN summary: this app turns a long reference video into shot units so that an AI agent can read it shot by shot through RefCov's MCP tools, and so that "how much of the video did the AI read" is a number taken from records. It is a RefCov adapter plus three commands (`detect`, `count`, `page`). It does not understand what is in the pictures. Limitations are listed below; read them before relying on the numbers.

## What it does

1. `detect` runs ffmpeg scene detection **once** and writes a small Markdown file, the *shot list* (`<video>.shots.md`): the video's path, SHA-256, size and modification time, the detection parameters, and one section per shot with its start and end.
2. You register the shot list (not the video) with RefCov and the `shot` adapter. Every shot becomes one required unit.
3. The agent reads a shot with `read_unit`. RefCov checks that the video has not changed, extracts one JPEG keyframe from the middle of the shot with ffmpeg, and returns a line of text plus that picture. Each read is recorded, with the number of images sent.
4. In Kiro, the write-file gate and the task-start gate refuse until every required shot has been read (strict mode). `count` and `page` show how many shots were read.

The video is never copied into RefCov's cache. Frames are not stored; they are cut out when read and sent through a pipe.

## Requirements

- Python 3.11 or newer, with RefCov installed (`pip install -e .` in the repository).
- `ffmpeg` and `ffprobe` on `PATH`. Only this app calls them; RefCov's core does not need them.

## Quick start

Run everything from the repository root (the directory that contains `.git`).

```text
python apps/shot-coverage/cli.py detect reference.mp4
```

This writes `reference.shots.md` next to the video (or at the repository root if the video is outside the repository) and prints the next step. Options: `--out`, `--threshold` (default 0.25), `--min-shot` (default 0.5 seconds), `--scale`, `--video-path`.

Declare the adapter in `refcov.toml`. Only you can edit this file; Kiro blocks the agent from changing it:

```toml
[adapters]
shot = "apps/shot-coverage/adapter.py"
```

Register the shot list in a terminal. Only you can run this; Kiro blocks the agent from running it:

```text
refcov add reference.shots.md --id ep01 --adapter shot
```

Then set up the MCP server and the hooks as described in the main README. The agent reads shots with `list_units` and `read_unit` (source `ep01`, unit `shot-00-31-2`, and so on). Unit ids are built from the shot's start time: `shot-<minutes>-<seconds>-<tenths>`.

```text
python apps/shot-coverage/cli.py count
python apps/shot-coverage/cli.py page --out shot-strip.html
```

`count` prints how many shots were read, how many reads, and how many images were sent (valid reads only; add `--json` for scripts). `page` writes one HTML file: a strip of cells, one per shot, lit when read, with a mark on shots a requirement cites, and a play button that replays the reads in order. The page makes no network requests and embeds no video frames.

If you replace the video, run `detect` again and register again. The shots' checksums change and all earlier reads become invalid.

## Limitations

- **Hard cuts only.** Scene detection finds sudden changes. A slow zoom, a fade or a dissolve does not start a new shot, so those frames sit inside one unit.
- **One keyframe per shot, from the middle.** It cannot show text or motion that appears elsewhere in the shot. In a real test, a shot with three lines of on-screen text showed only one of them in its middle frame. Reading a shot's keyframe is not the same as having seen every frame of it.
- **The video check compares size and modification time first.** If both are unchanged, the video is assumed unchanged and the SHA-256 is not recomputed. A file edited in place without changing its size or its modification time is not noticed. If either differs, the SHA-256 is recomputed and a changed video is refused.
- **The adapter file is ordinary code.** Editing its `kinds` declaration (for example setting `strict` to `False`) shrinks the required set. This is the same kind of change as editing RefCov's core, and it falls under "no defence against deliberate tampering" (RefCov guards against laziness and over-claiming, not against someone editing the code). Kiro's write gate covers writes to this file made with its own write tools; it does not stop writes made through the shell.
- **The adapter file runs inside RefCov's own process** (the MCP server and the hook scripts load it). Declare only files you trust. Importing it does nothing expensive: no ffmpeg call, no hashing, no file reads.
- **Detection is not perfect.** On the 7-minute 40-second test video, threshold 0.25 found 42 of the 43 hard cuts in the answer key, missed one, and also cut at two white flashes and one more point. Scaling the picture down before detection changed nothing and was not faster, so the default is no scaling.
- **Tested with the Kiro CLI, not yet in the Kiro IDE.** Real keyframes were delivered and read in the CLI (`docs/验证结果.md`, item 10). The IDE test is still to do.
- **No speed or cost claim.** Whether reading by shot is faster or cheaper than an agent doing its own frame extraction has not been measured yet.
- Shots shorter than `--min-shot` are merged into the previous shot (the last one into the one before it); a video shorter than `--min-shot` is a single shot.

## Not a power

Packaging this as a Kiro power was evaluated and not done (`docs/冲刺计划.md`, section 6): the documented power format does not mention hooks or a way to give the MCP server the workspace path, so a power would remove only one of the five set-up steps.

## Tests

```text
python -m pytest tests -k shot
```

Tests that need ffmpeg build their own videos from synthetic sources (solid colours) and are skipped when ffmpeg is missing. No video or frame from a real reference video is stored in the repository.
