"""Append-only JSONL audit log for every mutating Gmail operation.

Each draft create, draft send, and filter create/delete appends one line
capturing what was done. The log is the safety spine: it is never rewritten,
only appended, so it is a faithful record even if a later call misbehaves.
Args are hashed (not stored verbatim) to avoid persisting recipient/subject
content while still proving "a call with these inputs happened".
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _args_hash(args: dict[str, Any]) -> str:
    canonical = json.dumps(args, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


def record_mutation(
    *,
    action: str,
    args: dict[str, Any],
    result: dict[str, Any] | None,
    log_path: Path,
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Append one audit record and return it.

    ``timestamp`` is injectable for deterministic tests; defaults to now (UTC).
    """
    record = {
        "timestamp": timestamp or datetime.now(timezone.utc).isoformat(),
        "action": action,
        "args_hash": _args_hash(args),
        "result": result,
    }
    log_path = Path(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")
    return record
