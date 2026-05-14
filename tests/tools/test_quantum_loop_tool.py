import json

from hermes_cli.commands import resolve_command
from tools.quantum_loop_tool import (
    disable_quantum_loop,
    enable_quantum_loop,
    get_quantum_loop_state,
    quantum_loop,
    reserve_quantum_loop_iteration,
)
from toolsets import get_toolset, resolve_toolset


def test_quantum_loop_max_iterations_one_allows_one_reserved_iteration():
    key = "test-quantum-loop-max-iterations-one"
    disable_quantum_loop(session_key=key, reason="test-reset")

    state = enable_quantum_loop(session_key=key, max_iterations=1)
    assert state["enabled"] is True

    reserved = reserve_quantum_loop_iteration(session_key=key)
    assert reserved is not None
    assert reserved["iterations"] == 1

    state = get_quantum_loop_state(session_key=key)
    assert state["enabled"] is False
    assert state["disabled_reason"] == "max_iterations"

    disable_quantum_loop(session_key=key, reason="test-cleanup")


def test_quantum_loop_tool_enable_status_disable():
    key = "test-quantum-loop-tool-actions"
    disable_quantum_loop(session_key=key, reason="test-reset")

    enabled = json.loads(quantum_loop(action="enable", max_minutes=0.25, task_id=key))
    assert enabled["ok"] is True
    assert enabled["state"]["enabled"] is True
    assert enabled["state"]["max_minutes"] == 0.25

    status = json.loads(quantum_loop(action="status", task_id=key))
    assert status["state"]["enabled"] is True

    disabled = json.loads(quantum_loop(action="disable", task_id=key))
    assert disabled["state"]["enabled"] is False


def test_quantum_loop_command_and_toolset_registration():
    assert resolve_command("quantum-loop").name == "quantum-loop"
    assert resolve_command("quantum_loop").name == "quantum-loop"
    assert resolve_command("ql").name == "quantum-loop"

    assert get_toolset("quantum_loop")["tools"] == ["quantum_loop"]
    assert "quantum_loop" in resolve_toolset("hermes-discord")
