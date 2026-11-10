"""Durable JSONL records, recoverable checkpoints, and lossless exports."""
from __future__ import annotations

import csv
import json
import os
from pathlib import Path
from typing import Any


def atomic_json(path: Path, value: Any) -> None:
    """Replace a checkpoint only after the complete UTF-8 JSON has been flushed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def read_jsonl(path: Path, repair_tail: bool = False) -> list[dict]:
    """Read records, optionally discarding only an incomplete final JSON fragment.

    Complete corrupt lines and duplicates always fail. On resume, a valid final
    record lacking a newline is retained and the newline is restored before append.
    """
    if not path.exists():
        return []
    raw = path.read_bytes()
    lines = raw.splitlines(keepends=True)
    result, seen, offset = [], set(), 0
    for index, line in enumerate(lines):
        try:
            record = json.loads(line)
        except (ValueError, UnicodeDecodeError):
            if repair_tail and index == len(lines) - 1 and not line.endswith(b"\n"):
                with path.open("r+b") as f:
                    f.truncate(offset)
                break
            raise ValueError(f"Invalid JSONL at {path}, line {index + 1}")
        if not isinstance(record, dict) or not record.get("url"):
            raise ValueError(f"Each record must be an object with a source URL: line {index + 1}")
        if record["url"] in seen:
            raise ValueError(f"Duplicate source URL at {path}, line {index + 1}")
        seen.add(record["url"])
        result.append(record)
        offset += len(line)
    if repair_tail and result and path.read_bytes() and not path.read_bytes().endswith(b"\n"):
        with path.open("ab") as f:
            f.write(b"\n")
    return result


def append_record(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")
        f.flush()
        os.fsync(f.fileno())


def export_records(records: list[dict], destination: Path, format: str) -> None:
    """Export complete fields; nested CSV values remain JSON, never truncated."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    if format == "json":
        atomic_json(destination, records)
    else:
        columns = list(dict.fromkeys(k for r in records for k in r))
        with destination.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=columns)
            writer.writeheader()
            for record in records:
                writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v
                                 for k, v in record.items()})
