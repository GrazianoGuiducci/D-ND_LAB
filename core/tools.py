"""Built-in tools for the lab agent.

Phase 2 ships these as inline Python callables (not full MCP servers).
Each tool has:
  - schema: OpenAI tool format (so any OpenAI-compatible model can call it)
  - fn: Python callable that executes safely

Safety contract:
  - All filesystem ops are allowlisted: only paths under the lab data dir
    or the domain dir can be read/written.
  - run_python uses a subprocess with timeout + size cap.
  - run_bash uses a subprocess with timeout + size cap, no shell expansion
    by default (passing as list to subprocess), runs from CWD inside the
    sandbox dir.
  - All outputs truncated to 50KB to prevent flood.

Phase 2.5 will replace these with MCP server processes for proper
isolation. The schemas stay the same (OpenAI format = MCP tool format).

Artifact persistence (added 2026-04-28):
  When cycle_ts is provided, every run_python / run_bash call is auto-
  persisted as data/{domain}/artifacts/{cycle_ts}/call_<NNN>.json with
  full code + stdout + stderr + exit code. This lets the report_falsifier
  movement cross-check report claims against the actual computation
  trace without changing the agent prompt (option 3 of the
  diagnose/2026-04-28 plan).
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core import paths
from core.llm_adapter import ToolEntry

logger = logging.getLogger(__name__)


MAX_OUTPUT_BYTES = 50_000  # 50KB cap on tool result content


def build_default_tools(domain: str, cycle_ts: str | None = None) -> list[ToolEntry]:
    """Build the standard set of tools for a lab agent cycle.

    The sandbox roots are:
      - paths.domain_data_dir(domain)  (read+write — reports, seed, graph)
      - paths.domain_dir(domain)        (read-only — context, configs)
      - tempfile dir                    (read+write — scratch)

    Anything outside these paths is rejected.
    """
    sandbox = _Sandbox(domain, cycle_ts=cycle_ts)

    def read_file(path: str) -> str:
        return sandbox.read_file(path)

    def write_file(path: str, content: str) -> str:
        return sandbox.write_file(path, content)

    def list_dir(path: str) -> str:
        return sandbox.list_dir(path)

    def run_python(code: str, timeout_s: int = 60) -> str:
        return sandbox.run_python(code, timeout_s)

    def run_bash(command: str, timeout_s: int = 60) -> str:
        return sandbox.run_bash(command, timeout_s)

    return [
        {
            "fn": read_file,
            "schema": {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": (
                        "Read a text file. Path must be inside the lab data dir or domain dir. "
                        "Returns file contents (max 50KB)."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "File path"},
                        },
                        "required": ["path"],
                    },
                },
            },
        },
        {
            "fn": write_file,
            "schema": {
                "type": "function",
                "function": {
                    "name": "write_file",
                    "description": (
                        "Write a text file. Path must be inside the lab data dir. "
                        "Creates parent dirs if needed. Overwrites existing files."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                            "content": {"type": "string"},
                        },
                        "required": ["path", "content"],
                    },
                },
            },
        },
        {
            "fn": list_dir,
            "schema": {
                "type": "function",
                "function": {
                    "name": "list_dir",
                    "description": "List a directory's contents (file names + sizes).",
                    "parameters": {
                        "type": "object",
                        "properties": {"path": {"type": "string"}},
                        "required": ["path"],
                    },
                },
            },
        },
        {
            "fn": run_python,
            "schema": {
                "type": "function",
                "function": {
                    "name": "run_python",
                    "description": (
                        "Execute Python code. Returns stdout + stderr. Has access to numpy/scipy/sympy/etc. "
                        "if installed. CWD is the lab data dir. Timeout default 60s."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "code": {"type": "string"},
                            "timeout_s": {"type": "integer", "default": 60},
                        },
                        "required": ["code"],
                    },
                },
            },
        },
        {
            "fn": run_bash,
            "schema": {
                "type": "function",
                "function": {
                    "name": "run_bash",
                    "description": (
                        "Execute a bash command from the lab data dir. Returns stdout + stderr. "
                        "Timeout default 60s. Use this for git, ls, find, grep, etc."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "command": {"type": "string"},
                            "timeout_s": {"type": "integer", "default": 60},
                        },
                        "required": ["command"],
                    },
                },
            },
        },
    ]


class _Sandbox:
    """Path allowlist + safe subprocess execution for the agent.

    cycle_ts: when provided, every run_python/run_bash call is captured
    to data/{domain}/artifacts/{cycle_ts}/call_<NNN>.json so the
    report_falsifier can later cross-check report claims against actual
    numerical outputs. None disables persistence (e.g., for tests).
    """

    def __init__(self, domain: str, cycle_ts: str | None = None):
        self.domain = domain
        self.data_root = paths.domain_data_dir(domain).resolve()
        self.domain_root = paths.domain_dir(domain).resolve()
        self.data_root.mkdir(parents=True, exist_ok=True)
        self.cycle_ts = cycle_ts
        self.artifact_idx = 0
        if cycle_ts:
            self.artifact_dir = self.data_root / "artifacts" / cycle_ts
            self.artifact_dir.mkdir(parents=True, exist_ok=True)
        else:
            self.artifact_dir = None

    def _resolve(self, path: str, must_be_writable: bool = False) -> Path:
        """Resolve path against data_root, then domain_root if read-only."""
        p = Path(path)
        if not p.is_absolute():
            # Relative — resolve under data_root
            p = (self.data_root / p).resolve()
        else:
            p = p.resolve()

        # Allowlist check
        if self._is_under(p, self.data_root):
            return p
        if not must_be_writable and self._is_under(p, self.domain_root):
            return p
        raise PermissionError(
            f"path '{path}' is outside the sandbox "
            f"(data: {self.data_root}, domain: {self.domain_root})"
        )

    @staticmethod
    def _is_under(child: Path, parent: Path) -> bool:
        try:
            child.relative_to(parent)
            return True
        except ValueError:
            return False

    def read_file(self, path: str) -> str:
        try:
            p = self._resolve(path, must_be_writable=False)
        except PermissionError as e:
            return f"ERROR: {e}"
        if not p.exists():
            return f"ERROR: file not found: {p}"
        try:
            content = p.read_text(errors="replace")
        except Exception as e:
            return f"ERROR: read failed: {e}"
        if len(content.encode()) > MAX_OUTPUT_BYTES:
            content = content[:MAX_OUTPUT_BYTES] + "\n[... truncated]"
        return content

    def write_file(self, path: str, content: str) -> str:
        try:
            p = self._resolve(path, must_be_writable=True)
        except PermissionError as e:
            return f"ERROR: {e}"
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)
            return f"OK: wrote {len(content.encode())} bytes to {p}"
        except Exception as e:
            return f"ERROR: write failed: {e}"

    def list_dir(self, path: str) -> str:
        try:
            p = self._resolve(path, must_be_writable=False)
        except PermissionError as e:
            return f"ERROR: {e}"
        if not p.exists():
            return f"ERROR: dir not found: {p}"
        if not p.is_dir():
            return f"ERROR: not a directory: {p}"
        try:
            entries = sorted(p.iterdir())
        except Exception as e:
            return f"ERROR: list failed: {e}"
        lines = []
        for entry in entries[:200]:
            kind = "d" if entry.is_dir() else "f"
            try:
                size = entry.stat().st_size if entry.is_file() else 0
            except Exception:
                size = 0
            lines.append(f"{kind}  {size:>10}  {entry.name}")
        return "\n".join(lines) if lines else "(empty)"

    def run_python(self, code: str, timeout_s: int = 60) -> str:
        return self._run_subprocess(
            ["python3", "-c", code],
            timeout_s=min(timeout_s, 600),
            kind="python",
            source=code,
        )

    def run_bash(self, command: str, timeout_s: int = 60) -> str:
        # Use bash -c with the command as single arg — subject to shell expansion
        # within the sandbox CWD. Safety: timeout + size cap. Network not blocked
        # at this layer (do that at container level if needed).
        return self._run_subprocess(
            ["bash", "-c", command],
            timeout_s=min(timeout_s, 600),
            kind="bash",
            source=command,
        )

    def _run_subprocess(
        self,
        argv: list[str],
        timeout_s: int,
        kind: str = "subprocess",
        source: str = "",
    ) -> str:
        t0 = datetime.now(timezone.utc)
        try:
            result = subprocess.run(
                argv,
                cwd=str(self.data_root),
                capture_output=True,
                text=True,
                timeout=timeout_s,
                env=self._safe_env(),
            )
            stdout = result.stdout or ""
            stderr = result.stderr or ""
            exit_code = result.returncode
            err_kind = None
        except subprocess.TimeoutExpired:
            stdout, stderr, exit_code, err_kind = "", "", -1, f"timeout after {timeout_s}s"
        except FileNotFoundError as e:
            stdout, stderr, exit_code, err_kind = "", "", -1, f"command not found: {e}"
        except Exception as e:
            stdout, stderr, exit_code, err_kind = "", "", -1, f"subprocess failed: {e}"

        # Persist artifact (option 3 of the diagnose plan: no prompt change,
        # tool layer captures full computation trace). Best-effort — if
        # persistence fails we still return the body to the agent.
        if self.artifact_dir is not None:
            try:
                self.artifact_idx += 1
                t1 = datetime.now(timezone.utc)
                artifact = {
                    "kind": kind,
                    "ts": t0.isoformat(),
                    "duration_ms": int((t1 - t0).total_seconds() * 1000),
                    "source": source,
                    "stdout": stdout,
                    "stderr": stderr,
                    "exit_code": exit_code,
                    "error": err_kind,
                }
                out_path = self.artifact_dir / f"call_{self.artifact_idx:03d}_{kind}.json"
                out_path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2))
            except Exception as e:
                logger.warning("artifact persistence failed: %s", e)

        if err_kind:
            return f"ERROR: {err_kind}"
        body = stdout
        if stderr:
            body += f"\n--- stderr ---\n{stderr}"
        if exit_code != 0:
            body += f"\n--- exit code: {exit_code} ---"
        if len(body.encode()) > MAX_OUTPUT_BYTES:
            body = body[:MAX_OUTPUT_BYTES] + "\n[... truncated]"
        return body

    def _safe_env(self) -> dict[str, str]:
        """Return a sanitized env: keep PATH + a few essentials, drop secrets."""
        keep = {"PATH", "LANG", "LC_ALL", "HOME", "TERM"}
        env = {k: v for k, v in os.environ.items() if k in keep}
        # Drop any LLM_* / NOTIFY_* / API keys to prevent agent code leaking them
        for k in list(os.environ.keys()):
            if k.startswith("LLM_") or k.startswith("NOTIFY_") or "TOKEN" in k or "API_KEY" in k or "SECRET" in k:
                env.pop(k, None)
        return env
