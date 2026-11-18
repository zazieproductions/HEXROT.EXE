"""Test the real local supervisor with harmless interpreter commands."""
import json
import math
import subprocess
import sys
from pathlib import Path
import pytest

SUPERVISOR = Path(__file__).resolve().parents[2] / 'backend/workers/supervisor.py'


def invoke(command, *, memory=512, timeout=5):
    return subprocess.run([sys.executable, str(SUPERVISOR), '--hexrot-memory-mb', str(memory),
        '--hexrot-timeout', str(timeout), '--', *command], capture_output=True, text=True, timeout=10)


def test_supervisor_runs_actual_command_and_records_exit_code():
    result = invoke([sys.executable, '-c', 'print("supervisor-ok")'])
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload['returncode'] == 0 and payload['stdout'].strip() == 'supervisor-ok'
    assert payload['stdout_truncated'] is False


def test_supervisor_rejects_invalid_limits():
    result = invoke([sys.executable, '-c', 'print("should-not-run")'], memory=8)
    assert result.returncode != 0
    assert 'should-not-run' not in result.stdout


@pytest.mark.skipif(sys.platform == 'win32', reason='POSIX resource limits')
def test_supervisor_enforces_child_resource_limits():
    command = [sys.executable, '-c', 'import resource,json; print(json.dumps({'
        '"as":resource.getrlimit(resource.RLIMIT_AS)[0],'
        '"core":resource.getrlimit(resource.RLIMIT_CORE)[0],'
        '"files":resource.getrlimit(resource.RLIMIT_NOFILE)[0]}))']
    result = invoke(command)
    assert result.returncode == 0, result.stderr
    inner = json.loads(json.loads(result.stdout)['stdout'])
    assert inner['as'] == 512 * 1024 * 1024
    assert inner['core'] == 0
    assert inner['files'] == 64
