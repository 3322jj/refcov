"""Turn the four replay runs into the small JSON files the demo page reads.

Standard library only. The raw run records stay outside the repository and are
passed in with --runs. The script never opens answer.md and never writes a local
path, a model's free text, or a numeric field outside NUMERIC_PATHS.

Design: .kiro/specs/demo-page/design.md, section 3.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import re
import sys
from pathlib import Path

SCHEMA = 1
STATE_DIR = ".refcov"
OUT_DIR = Path(__file__).resolve().parent / "data"
KIRO_CLI_INFERRED = "3.3.0"
MAX_UNIT_CHARS = 80
MAX_FILE_BYTES = 60 * 1024
ALLOWED_FILES = ("index.html", "answer.md", "edit-plan.md")
READ_TITLE = "@refcov/read_unit"
MCP_PREFIX = "@refcov/"
FILE_READ_TITLE = "Read File"
WRITE_TITLES = ("Write File", "Replace in File")
BLOCK_LABEL = "gate:required-units-unread"

EVENT_KINDS = {
    ("tool", "tool-call"),
    ("tool", "file-read"),
    ("tool", "mcp-call"),
    ("read", "unit-read"),
    ("write", "write:index.html"),
    ("write", "write:answer.md"),
    ("write", "write:edit-plan.md"),
    ("blocked", BLOCK_LABEL),
    ("final", "final-report"),
}
NEEDLES = {
    "closedby": re.compile(r'closedby\s*=\s*["\']any["\']'),
    "user_invalid": re.compile(r":user-invalid"),
    "commandfor": re.compile(r"commandfor\s*="),
    "overscroll": re.compile(r"overscroll-behavior"),
}
NUMERIC_PATHS = {
    ("schema",),
    ("seconds",),
    ("tool_calls",),
    ("blocks",),
    ("must_read", "read"),
    ("must_read", "total"),
    ("shots", "*", "start"),
    ("shots", "*", "end"),
}
DRIVE_RE = re.compile(r"[A-Za-z]:[\\/]")
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
MODEL_RE = re.compile(r"claude-[a-z]+-\d+(?:\.\d+)?")
FOLDER_RE = re.compile(r"[A-Za-z0-9._-]+")
VERSION_RE = re.compile(r"\d+\.\d+\.\d+")
SHOT_ID_RE = re.compile(r"shot-[0-9A-Za-z-]+")
BASIS = {"inferred", "record", "record-batch-start"}

RUNS = (
    {
        "key": "w-h-03",
        "id": "W-H-03",
        "folder": "webhaiku-20261115-173415",
        "stream": "W-H-03.jsonl",
        "status": "W-H-03.status.json",
        "workspace": "W-H-03",
        "state": False,
        "needles": True,
        "kiro": "inferred",
    },
    {
        "key": "wb-h-03",
        "id": "WB-H-03",
        "folder": "webrefcovhaiku-20261115-173528",
        "stream": "WB-H-03.jsonl",
        "status": "WB-H-03.status.json",
        "workspace": "WB-H-03",
        "state": True,
        "needles": True,
        "kiro": "inferred",
    },
    {
        "key": "g-01",
        "id": "G-01",
        "folder": "gis-20261115-213112",
        "stream": "G-01.jsonl",
        "status": "G-01.status.json",
        "workspace": "G-01",
        "state": True,
        "needles": False,
        "kiro": "status",
    },
    {
        "key": "vb-01",
        "id": "VB-01",
        "folder": "20261114-180540",
        "pgrade": "VB-01.pgrade.json",
        "status": "VB-01.status.json",
        "workspace": "VB-01",
    },
)


class ConvertError(Exception):
    """A check failed or an input is missing. The message names the run and gives counts only."""


def _read_lines(path: Path) -> list[str]:
    """Non-empty lines. Split on LF only: JSON strings may hold characters that str.splitlines breaks on."""
    text = path.read_text(encoding="utf-8", errors="replace")
    return [line for line in text.split("\n") if line.strip()]


def _load_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    if not isinstance(data, dict):
        raise ValueError("expected a JSON object")
    return data


def _file_name(path: object) -> str:
    """Last path segment for either separator. Only the name is kept, never the folder."""
    if not isinstance(path, str) or not path:
        return ""
    return re.split(r"[\\/]", path)[-1]


def _truncate(text: str) -> str:
    """Cut to MAX_UNIT_CHARS characters, the last one being an ellipsis when cut."""
    if len(text) <= MAX_UNIT_CHARS:
        return text
    return text[: MAX_UNIT_CHARS - 1] + "\u2026"


LAYOUT_TAG_RE = re.compile(r"</?(?:br|hr|p|div|li|ul|ol)\s*/?>", re.IGNORECASE)
ENTITY_RE = re.compile(r"&(?:[A-Za-z][A-Za-z0-9]*|#[0-9]+|#[xX][0-9A-Fa-f]+);")


def _display(full_id: str) -> str:
    """Name shown on the page: the unit part of the ID, layout tags and entities removed, hyphens as spaces.

    Only layout tags (br, hr, p, div, li, ul, ol) and entities are removed. Element names such as
    <dialog> in guide titles are part of the name, so they stay.
    """
    _, sep, unit = full_id.partition("/")
    text = unit if sep else full_id
    text = LAYOUT_TAG_RE.sub(" ", text)
    text = ENTITY_RE.sub(" ", text)
    text = text.replace("-", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return _truncate(text)


def _seq(record: dict) -> int:
    value = record.get("seq", 0)
    return value if isinstance(value, int) else 0


def _date(folder: str) -> str:
    match = re.search(r"(\d{4})(\d{2})(\d{2})", folder)
    if match is None:
        raise ConvertError("a run folder has no date in its name")
    return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"


def _version(run_id: str, text: object) -> str:
    match = re.fullmatch(r"kiro-cli (\d+\.\d+\.\d+)", str(text))
    if match is None:
        raise ConvertError(f"{run_id}: no kiro-cli version in the record")
    return match.group(1)


def _parse_stream(path: Path) -> tuple[list[dict], dict[str, object], bool]:
    """Tool calls in stream order, the last status of each call, and whether a message follows the last call."""
    calls: list[dict] = []
    statuses: dict[str, object] = {}
    message_at = -1
    for line in _read_lines(path):
        record = json.loads(line)
        if record.get("type") != "sessionUpdate":
            continue
        update = (record.get("data") or {}).get("update") or {}
        kind = update.get("sessionUpdate")
        if kind == "tool_call":
            raw = update.get("rawInput")
            calls.append(
                {
                    "id": str(update.get("toolCallId", "")),
                    "title": str(update.get("title", "")),
                    "raw": raw if isinstance(raw, dict) else {},
                }
            )
        elif kind == "tool_call_update":
            statuses[str(update.get("toolCallId", ""))] = update.get("status")
        elif kind == "agent_message_chunk":
            message_at = len(calls)
    return calls, statuses, bool(calls) and message_at == len(calls)


def _build_events(run_id: str, calls: list[dict], statuses: dict, final: bool):
    """Events in stream order. Failed writes are returned as placeholders for the block records."""
    events: list[dict] = []
    reads: list[tuple[str, str]] = []
    failed: list[tuple[int, str]] = []
    for call in calls:
        title = call["title"]
        raw = call["raw"]
        status = statuses.get(call["id"])
        if title == READ_TITLE:
            if status != "completed":
                raise ConvertError(f"{run_id}: a read call did not complete")
            source = str(raw.get("source", ""))
            unit = str(raw.get("unit", ""))
            reads.append((source, unit))
            full_id = f"{source}/{unit}"
            events.append(
                {"kind": "read", "label": "unit-read", "unit": _truncate(full_id), "display": _display(full_id)}
            )
        elif title in WRITE_TITLES:
            name = _file_name(raw.get("path"))
            if name not in ALLOWED_FILES:
                raise ConvertError(f"{run_id}: a write names a file outside the allowed list")
            if status == "completed":
                events.append({"kind": "write", "label": f"write:{name}"})
            elif status == "failed":
                failed.append((len(events), name))
                events.append({"kind": "blocked", "label": BLOCK_LABEL})
            else:
                raise ConvertError(f"{run_id}: a write has neither a completed nor a failed status")
        elif title == FILE_READ_TITLE:
            events.append({"kind": "tool", "label": "file-read"})
        elif title.startswith(MCP_PREFIX):
            events.append({"kind": "tool", "label": "mcp-call"})
        else:
            events.append({"kind": "tool", "label": "tool-call"})
    if final:
        events.append({"kind": "final", "label": "final-report"})
    return events, reads, failed


def _read_state(path: Path) -> tuple[list[dict], list[dict]]:
    """Read and block records only. register, sync and session are template preparation and are ignored."""
    reads: list[dict] = []
    blocks: list[dict] = []
    for line in _read_lines(path):
        record = json.loads(line)
        if record.get("type") == "read":
            reads.append(record)
        elif record.get("type") == "block":
            blocks.append(record)
    blocks.sort(key=_seq)
    return reads, blocks


def _pairs(records: list[dict]) -> collections.Counter:
    return collections.Counter((str(r.get("source", "")), str(r.get("unit", ""))) for r in records)


def _check_reads(run_id: str, stream_reads: list[tuple[str, str]], state_reads: list[dict]) -> None:
    stream_count = collections.Counter(stream_reads)
    state_count = _pairs(state_reads)
    if stream_count != state_count:
        raise ConvertError(
            f"{run_id}: {sum(stream_count.values())} read calls in the stream and "
            f"{sum(state_count.values())} read records do not match"
        )


def _check_blocks(run_id: str, failed: list[tuple[int, str]], blocks: list[dict]) -> None:
    if len(failed) != len(blocks):
        raise ConvertError(
            f"{run_id}: {len(failed)} failed writes and {len(blocks)} block records do not match"
        )
    for (_, name), block in zip(failed, blocks):
        if _file_name(str(block.get("target", ""))) != name:
            raise ConvertError(f"{run_id}: a block record names a different file")


def _must_read(run_id: str, state_reads: list[dict], blocks: list[dict]) -> dict:
    read = len(set(_pairs(state_reads)))
    if blocks:
        missing = blocks[0].get("missing")
        if not isinstance(missing, list):
            raise ConvertError(f"{run_id}: a block record has no list of missing units")
        total = len(missing)
    else:
        total = read
    if read != total:
        raise ConvertError(f"{run_id}: {read} units read of {total} required")
    return {"read": read, "total": total}


def _needles(path: Path) -> dict[str, bool]:
    """Booleans only. The page code itself is never copied into the output."""
    text = path.read_text(encoding="utf-8", errors="replace")
    return {name: pattern.search(text) is not None for name, pattern in NEEDLES.items()}


def _parse_shots(run_id: str, path: Path) -> list[dict]:
    header: int | None = None
    shots: list[dict] = []
    current: dict | None = None
    for raw in path.read_text(encoding="utf-8", errors="replace").split("\n"):
        line = raw.strip()
        match = re.fullmatch(r"shots:\s*(\d+)", line)
        if match and header is None and current is None:
            header = int(match.group(1))
            continue
        match = re.fullmatch(r"##\s+(shot-[0-9A-Za-z-]+)", line)
        if match:
            current = {"id": match.group(1)}
            shots.append(current)
            continue
        match = re.fullmatch(r"(start|end):\s*(\d+(?:\.\d+)?)", line)
        if match and current is not None:
            current[match.group(1)] = round(float(match.group(2)), 3)
    if header is None or header != len(shots):
        raise ConvertError(f"{run_id}: the shot count does not match the header")
    if any("start" not in shot or "end" not in shot for shot in shots):
        raise ConvertError(f"{run_id}: a shot has no start or end")
    return shots


def _public(event: dict) -> dict:
    public = {"kind": event["kind"], "label": event["label"]}
    if "unit" in event:
        public["unit"] = event["unit"]
    if "display" in event:
        public["display"] = event["display"]
    return public


def _stream_run(spec: dict, root: Path) -> dict:
    run_id = spec["id"]
    folder = root / spec["folder"]
    status = _load_json(folder / spec["status"])
    calls, statuses, final = _parse_stream(folder / spec["stream"])
    events, stream_reads, failed = _build_events(run_id, calls, statuses, final)
    state_reads: list[dict] = []
    blocks: list[dict] = []
    if spec["state"]:
        state_reads, blocks = _read_state(folder / spec["workspace"] / STATE_DIR / "log.jsonl")
    _check_reads(run_id, stream_reads, state_reads)
    _check_blocks(run_id, failed, blocks)
    if spec["kiro"] == "inferred":
        kiro = {"basis": "inferred", "value": KIRO_CLI_INFERRED}
    else:
        kiro = {"basis": "record", "value": _version(run_id, status.get("kiro_cli"))}
    out = {
        "blocks": len(blocks),
        "date": _date(spec["folder"]),
        "events": [_public(event) for event in events],
        "id": run_id,
        "kiro_cli": kiro,
        "model": str(status["model"]),
        "run_folder": spec["folder"],
        "schema": SCHEMA,
        "seconds": int(status["seconds"]),
        "seconds_reconstructed": False,
        "tool_calls": len(calls),
    }
    if spec["state"]:
        out["must_read"] = _must_read(run_id, state_reads, blocks)
    if spec["needles"]:
        out["needles"] = _needles(folder / spec["workspace"] / "index.html")
    return out


def _shot_run(spec: dict, root: Path) -> dict:
    run_id = spec["id"]
    folder = root / spec["folder"]
    workspace = folder / spec["workspace"]
    pgrade = _load_json(folder / spec["pgrade"])
    status = _load_json(folder / spec["status"])
    shots = _parse_shots(run_id, workspace / "reference.shots.md")
    state_reads, blocks = _read_state(workspace / STATE_DIR / "log.jsonl")
    if blocks:
        raise ConvertError(f"{run_id}: block records in a run that has no stream")
    read_units = {str(record.get("unit", "")) for record in state_reads}
    shot_ids = {shot["id"] for shot in shots}
    if read_units != shot_ids:
        raise ConvertError(f"{run_id}: the units read do not match the shot list")
    return {
        "blocks": 0,
        "date": _date(spec["folder"]),
        "id": run_id,
        "kiro_cli": {
            "basis": "record-batch-start",
            "value": _version(run_id, pgrade.get("kiro_cli_at_batch_start")),
        },
        "model": str(status["model"]),
        "must_read": {"read": len(read_units), "total": len(shots)},
        "run_folder": spec["folder"],
        "schema": SCHEMA,
        "seconds": int(pgrade["seconds"]),
        "seconds_reconstructed": bool(pgrade.get("status_reconstructed", False)),
        "shots": [
            {"end": s["end"], "id": s["id"], "read": s["id"] in read_units, "start": s["start"]}
            for s in shots
        ],
        "tool_calls": int(pgrade["tool_calls"]),
    }


def _leaves(value, path: tuple = ()):
    if isinstance(value, dict):
        for key, item in value.items():
            yield from _leaves(item, path + (key,))
    elif isinstance(value, list):
        for item in value:
            yield from _leaves(item, path + ("*",))
    else:
        yield path, value


def _check_output(run_id: str, obj: dict, user: str) -> None:
    """Refuse to write anything that breaks the rules in design section 3.5."""
    for path, value in _leaves(obj):
        if value is None or isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            if path not in NUMERIC_PATHS:
                raise ConvertError(f"{run_id}: an unexpected numeric field")
            continue
        if not isinstance(value, str):
            raise ConvertError(f"{run_id}: an unexpected value type")
        if "\\" in value or "/Users/" in value or "/home/" in value or DRIVE_RE.search(value):
            raise ConvertError(f"{run_id}: a local path would be written")
        if user and re.search(rf"[\\/]{re.escape(user)}[\\/]", value):
            raise ConvertError(f"{run_id}: a user folder would be written")
        if any(ord(ch) < 32 for ch in value):
            raise ConvertError(f"{run_id}: a control character would be written")
    if not (
        DATE_RE.fullmatch(obj["date"])
        and MODEL_RE.fullmatch(obj["model"])
        and FOLDER_RE.fullmatch(obj["run_folder"])
    ):
        raise ConvertError(f"{run_id}: a header field has the wrong shape")
    if not VERSION_RE.fullmatch(obj["kiro_cli"]["value"]) or obj["kiro_cli"]["basis"] not in BASIS:
        raise ConvertError(f"{run_id}: the kiro-cli field has the wrong shape")
    for event in obj.get("events", []):
        if (event["kind"], event["label"]) not in EVENT_KINDS:
            raise ConvertError(f"{run_id}: an event is outside the fixed vocabulary")
        if len(event.get("unit", "")) > MAX_UNIT_CHARS or len(event.get("display", "")) > MAX_UNIT_CHARS:
            raise ConvertError(f"{run_id}: a unit ID or display name is longer than {MAX_UNIT_CHARS} characters")
    for shot in obj.get("shots", []):
        if not SHOT_ID_RE.fullmatch(shot["id"]):
            raise ConvertError(f"{run_id}: a shot ID has the wrong shape")


def _write_all(outputs: dict[str, dict], out_dir: Path) -> None:
    texts = {
        f"{key}.json": json.dumps(obj, ensure_ascii=True, indent=2, sort_keys=True) + "\n"
        for key, obj in outputs.items()
    }
    for name, text in texts.items():
        if len(text.encode("ascii")) > MAX_FILE_BYTES:
            raise ConvertError(f"{name} would be larger than {MAX_FILE_BYTES} bytes")
    out_dir.mkdir(parents=True, exist_ok=True)
    temps: list[tuple[Path, Path]] = []
    try:
        for name, text in texts.items():
            temp = out_dir / (name + ".tmp")
            temps.append((temp, out_dir / name))
            with open(temp, "w", encoding="ascii", newline="\n") as handle:
                handle.write(text)
        for temp, final in temps:
            os.replace(temp, final)
    except OSError as exc:
        for temp, _ in temps:
            temp.unlink(missing_ok=True)
        raise ConvertError("could not write the output files") from exc


def _user_name() -> str:
    return os.environ.get("USERNAME") or os.environ.get("USER") or ""


def convert(runs_root: Path, out_dir: Path) -> list[str]:
    """Build the four objects, run every check, then write them. Returns the file names."""
    user = _user_name()
    outputs: dict[str, dict] = {}
    for spec in RUNS:
        run_id = spec["id"]
        try:
            obj = _shot_run(spec, runs_root) if "pgrade" in spec else _stream_run(spec, runs_root)
        except OSError as exc:
            raise ConvertError(f"{run_id}: an input file is missing or unreadable") from exc
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            raise ConvertError(f"{run_id}: a record does not have the expected fields") from exc
        _check_output(run_id, obj, user)
        outputs[spec["key"]] = obj
    _write_all(outputs, out_dir)
    return sorted(f"{key}.json" for key in outputs)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write the four demo-page JSON files from the run records.")
    parser.add_argument(
        "--runs",
        required=True,
        type=Path,
        help="folder that holds the run folders (outside the repository)",
    )
    args = parser.parse_args(argv)
    try:
        names = convert(args.runs, OUT_DIR)
    except ConvertError as exc:
        print(f"convert_runs: {exc}", file=sys.stderr)
        return 2
    print(f"convert_runs: wrote {len(names)} files to site/data")
    return 0


if __name__ == "__main__":
    sys.exit(main())
