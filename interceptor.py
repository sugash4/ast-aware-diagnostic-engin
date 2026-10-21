# =============================================================================
# interceptor.py — Compiler subprocess wrapper & stderr coordinate extractor
# =============================================================================
"""
Runs an arbitrary compiler command, captures stderr, and extracts structured
error information (file path, line, column, raw message) using regex adapters
for GCC, Clang, Keil armcc, and IAR toolchains.
"""

import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

from config import COMPILER_PATTERNS


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _try_pattern(pattern_key: str, line: str) -> Optional[dict]:
    """Attempt to match one compiler error pattern against a stderr line."""
    pattern = COMPILER_PATTERNS[pattern_key]
    match = re.match(pattern, line.strip(), re.IGNORECASE)
    if not match:
        return None

    groups = match.groupdict()
    col_raw = groups.get("col") or "1"
    # IAR uses error code in col field; treat as col=1 if non-numeric
    col = int(col_raw) if col_raw.isdigit() else 1

    return {
        "file":      groups.get("file", "").strip(),
        "line":      int(groups.get("line", 1)),
        "col":       col,
        "raw_error": groups.get("message", "").strip(),
    }


def _parse_stderr(stderr_text: str) -> Optional[dict]:
    """
    Scan every line of stderr output and return the first parseable
    error record.  Priority order: gcc_clang > keil > iar.
    """
    priority = ["gcc_clang", "keil", "iar"]

    for stderr_line in stderr_text.splitlines():
        if not stderr_line.strip():
            continue
        for key in priority:
            result = _try_pattern(key, stderr_line)
            if result:
                # Resolve file path relative to cwd if it exists on disk
                candidate = Path(result["file"])
                if not candidate.is_absolute() and candidate.exists():
                    result["file"] = str(candidate.resolve())
                return result

    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def execute_compiler(cmd_args: list[str]) -> dict:
    """
    Execute the compiler command and capture its output.

    Parameters
    ----------
    cmd_args : list[str]
        Full compiler invocation, e.g. ["gcc", "test.c", "-o", "test"].

    Returns
    -------
    dict with keys:
        success   (bool)  — True if compiler returned exit code 0
        file      (str)   — Source file containing the first error
        line      (int)   — 1-indexed line number
        col       (int)   — 1-indexed column number
        raw_error (str)   — First parsed error message
        stderr    (str)   — Full raw stderr string
        stdout    (str)   — Full raw stdout string
    """
    # Baseline result (populated on success)
    result: dict = {
        "success":   True,
        "file":      "",
        "line":      0,
        "col":       0,
        "raw_error": "",
        "stderr":    "",
        "stdout":    "",
    }

    try:
        proc = subprocess.run(
            cmd_args,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        compiler_name = cmd_args[0] if cmd_args else "unknown"
        print(
            f"[interceptor] ERROR: Compiler '{compiler_name}' not found on PATH.",
            file=sys.stderr,
        )
        result["success"] = False
        result["raw_error"] = f"Compiler '{compiler_name}' not found on PATH."
        return result

    result["stdout"] = proc.stdout
    result["stderr"] = proc.stderr

    if proc.returncode == 0:
        # Compilation succeeded — nothing more to do
        return result

    # --- Compilation failed ---
    result["success"] = False

    parsed = _parse_stderr(proc.stderr)
    if parsed:
        result.update(parsed)
    else:
        # Could not parse structured coordinates; store raw stderr as message
        result["raw_error"] = proc.stderr.strip()
        # Attempt a looser file extraction from the first non-empty line
        first_line = next(
            (ln for ln in proc.stderr.splitlines() if ln.strip()), ""
        )
        result["raw_error"] = first_line or proc.stderr.strip()

    return result
