"""Subprocess execution with a timeout that kills the whole process tree.

subprocess.run(timeout=...) kills only the direct child. `gcc` is a driver that
starts `cc1`, `as` and `ld`; on Windows those survive the kill, keep the output
pipes open, and the parent then waits forever. So on timeout we kill the tree.
"""
from __future__ import annotations

import os
import signal
import subprocess
from dataclasses import dataclass


@dataclass
class ProcResult:
    returncode: int | None
    stdout: str
    stderr: str
    timed_out: bool


def _kill_tree(p: subprocess.Popen) -> None:
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)], capture_output=True, timeout=30)
        else:
            os.killpg(p.pid, signal.SIGKILL)
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        p.kill()
    except OSError:
        pass


def run_cmd(cmd: list[str], timeout_s: float) -> ProcResult:
    kw = ({"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt"
          else {"start_new_session": True})
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                         errors="replace", **kw)
    try:
        out, err = p.communicate(timeout=timeout_s)
        return ProcResult(p.returncode, out or "", err or "", False)
    except subprocess.TimeoutExpired:
        _kill_tree(p)
        try:
            out, err = p.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            out, err = "", ""
        return ProcResult(None, out or "", err or "", True)
