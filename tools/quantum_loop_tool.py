"""Quantum Loop session continuation tool for Hermes Agent."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

from hermes_constants import get_hermes_home
from tools.approval import get_current_session_key
from tools.registry import registry

QUANTUM_LOOP_PROMPT = (
    "Quantum Loop is enabled. You are resuming after your previous final content. "
    "If you want to stop looping, call quantum_loop with action=\"disable\". "
    "Otherwise, continue the current work or thought."
)

_STATE_FILE = "quantum_loop.json"


def _state_path() -> Path:
    return get_hermes_home() / _STATE_FILE


def _load_all() -> Dict[str, Dict[str, Any]]:
    path = _state_path()
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"Quantum Loop state file must contain an object: {path}")
    return data


def _save_all(data: Dict[str, Dict[str, Any]]) -> None:
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2, sort_keys=True)
    os.replace(tmp, path)


def _session_key(session_key: Optional[str] = None) -> str:
    key = session_key or get_current_session_key(default="default")
    return key or "default"


def _clean_entry(entry: Dict[str, Any], now: Optional[float] = None) -> Dict[str, Any]:
    now = time.time() if now is None else now
    if not entry.get("enabled"):
        return entry

    max_iterations = entry.get("max_iterations")
    if max_iterations is not None and int(entry.get("iterations", 0)) >= int(max_iterations):
        entry["enabled"] = False
        entry["disabled_reason"] = "max_iterations"
        entry["disabled_at"] = now
        return entry

    max_minutes = entry.get("max_minutes")
    if max_minutes is not None:
        enabled_at = float(entry.get("enabled_at", now))
        if now - enabled_at >= float(max_minutes) * 60:
            entry["enabled"] = False
            entry["disabled_reason"] = "max_minutes"
            entry["disabled_at"] = now
    return entry


def get_quantum_loop_state(session_key: Optional[str] = None) -> Dict[str, Any]:
    key = _session_key(session_key)
    data = _load_all()
    entry = dict(data.get(key) or {"enabled": False, "iterations": 0})
    cleaned = _clean_entry(entry)
    if cleaned != entry:
        data[key] = cleaned
        _save_all(data)
    return cleaned


def enable_quantum_loop(
    *,
    session_key: Optional[str] = None,
    max_iterations: Optional[int] = None,
    max_minutes: Optional[float] = None,
) -> Dict[str, Any]:
    if max_iterations is not None and int(max_iterations) < 1:
        raise ValueError("max_iterations must be >= 1")
    if max_minutes is not None and float(max_minutes) <= 0:
        raise ValueError("max_minutes must be > 0")

    key = _session_key(session_key)
    data = _load_all()
    entry = {
        "enabled": True,
        "enabled_at": time.time(),
        "iterations": 0,
    }
    if max_iterations is not None:
        entry["max_iterations"] = int(max_iterations)
    if max_minutes is not None:
        entry["max_minutes"] = float(max_minutes)
    data[key] = entry
    _save_all(data)
    return dict(entry)


def disable_quantum_loop(*, session_key: Optional[str] = None, reason: str = "disabled") -> Dict[str, Any]:
    key = _session_key(session_key)
    data = _load_all()
    entry = dict(data.get(key) or {})
    entry.update({
        "enabled": False,
        "disabled_at": time.time(),
        "disabled_reason": reason,
    })
    data[key] = entry
    _save_all(data)
    return dict(entry)


def reserve_quantum_loop_iteration(session_key: Optional[str] = None) -> Optional[Dict[str, Any]]:
    key = _session_key(session_key)
    data = _load_all()
    entry = dict(data.get(key) or {})
    entry = _clean_entry(entry)
    if not entry.get("enabled"):
        data[key] = entry
        _save_all(data)
        return None
    entry["iterations"] = int(entry.get("iterations", 0)) + 1
    data[key] = entry
    _save_all(data)
    return dict(entry)


def quantum_loop(
    *,
    action: str,
    max_iterations: Optional[int] = None,
    max_minutes: Optional[float] = None,
    task_id: Optional[str] = None,
) -> str:
    if action == "enable":
        state = enable_quantum_loop(
            session_key=task_id,
            max_iterations=max_iterations,
            max_minutes=max_minutes,
        )
        return json.dumps({"ok": True, "action": action, "state": state}, ensure_ascii=False)
    if action == "disable":
        state = disable_quantum_loop(session_key=task_id)
        return json.dumps({"ok": True, "action": action, "state": state}, ensure_ascii=False)
    if action == "status":
        state = get_quantum_loop_state(session_key=task_id)
        return json.dumps({"ok": True, "action": action, "state": state}, ensure_ascii=False)
    raise ValueError("action must be one of: enable, disable, status")


QUANTUM_LOOP_SCHEMA = {
    "name": "quantum_loop",
    "description": "Enable, disable, or inspect Quantum Loop continuation mode for this session.",
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["enable", "disable", "status"],
                "description": "Whether to enable, disable, or inspect Quantum Loop for the current session.",
            },
            "max_iterations": {
                "type": "integer",
                "minimum": 1,
                "description": "Optional maximum number of post-final-response continuations before the loop disables itself.",
            },
            "max_minutes": {
                "type": "number",
                "exclusiveMinimum": 0,
                "description": "Optional maximum number of minutes before the loop disables itself.",
            },
        },
        "required": ["action"],
    },
}


def check_quantum_loop_requirements() -> bool:
    return bool(
        os.getenv("HERMES_INTERACTIVE")
        or os.getenv("HERMES_GATEWAY_SESSION")
        or os.getenv("HERMES_EXEC_ASK")
    )


registry.register(
    name="quantum_loop",
    toolset="quantum_loop",
    schema=QUANTUM_LOOP_SCHEMA,
    handler=lambda args, **kw: quantum_loop(
        action=args.get("action", ""),
        max_iterations=args.get("max_iterations"),
        max_minutes=args.get("max_minutes"),
        task_id=kw.get("task_id"),
    ),
    check_fn=check_quantum_loop_requirements,
    emoji="🌀",
)
