#!/usr/bin/env python3
# =============================================================================
# main.py — CLI entry point for the AST Diagnostic Engine
# =============================================================================
"""
Usage:
    python main.py <compiler> [compiler_args...]   — run diagnostic pipeline
    python main.py --config                        — open settings screen

Examples:
    python main.py gcc test_cases/bad_pointer.c -o out
    python main.py g++ test_cases/type_mismatch.cpp -o out
    python main.py --config
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from interceptor import execute_compiler
from ast_engine  import extract_ast_context, resolve_language
from ai_engine   import generate_diagnostics
from formatter   import display_results, display_success, console
from settings    import open_settings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_source_file(cmd_args: list[str]) -> str:
    c_extensions = {".c", ".cpp", ".cc", ".cxx", ".h", ".hpp"}
    for arg in cmd_args:
        p = Path(arg)
        if p.suffix.lower() in c_extensions and not arg.startswith("-"):
            return str(p)
    return ""


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run(cmd_args: list[str]) -> int:
    if not cmd_args:
        console.print(
            "[bold red]Error:[/bold red] No compiler command provided.\n"
            "Usage:  python main.py <compiler> [args...]\n"
            "        python main.py --config"
        )
        return 1

    # ------------------------------------------------------------------
    # --config flag → open settings screen
    # ------------------------------------------------------------------
    if cmd_args[0] == "--config":
        open_settings(reason="user_request")
        return 0

    # ------------------------------------------------------------------
    # Stage 1: Run compiler & capture stderr
    # ------------------------------------------------------------------
    console.print(f"\n[dim]► Running:[/dim] [cyan]{' '.join(cmd_args)}[/cyan]\n")
    compiler_data = execute_compiler(cmd_args)

    if compiler_data["success"]:
        display_success(cmd_args)
        return 0

    # ------------------------------------------------------------------
    # Stage 2: Locate source file
    # ------------------------------------------------------------------
    source_file = compiler_data.get("file", "") or _find_source_file(cmd_args[1:])

    if not source_file:
        console.print(
            "[bold yellow]Warning:[/bold yellow] Could not identify the source file. "
            "AST context will be unavailable.\n"
        )
        ast_data: dict = {
            "node_type":   "unknown",
            "node_code":   "",
            "parent_type": "unknown",
            "parent_code": "",
            "scope_code":  "",
            "error":       "Source file could not be identified from compiler output.",
        }
    else:
        # ------------------------------------------------------------------
        # Stage 3: Extract AST context
        # ------------------------------------------------------------------
        lang = resolve_language(source_file)
        console.print(
            f"[dim]► Parsing AST:[/dim] [cyan]{source_file}[/cyan] "
            f"(lang={lang}, line={compiler_data['line']}, col={compiler_data['col']})\n"
        )
        ast_data = extract_ast_context(
            file_path=source_file,
            line=compiler_data["line"],
            col=compiler_data["col"],
            lang=lang,
        )

    # ------------------------------------------------------------------
    # Stage 4: AI diagnostics
    # ------------------------------------------------------------------
    console.print("[dim]► Querying AI for diagnostics …[/dim]\n")
    ai_response = generate_diagnostics(compiler_data, ast_data)

    # ------------------------------------------------------------------
    # Stage 5: Render 3-panel Rich UI
    # ------------------------------------------------------------------
    display_results(compiler_data, ast_data, ai_response)
    return 1


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(
            "Usage:  python main.py <compiler> [compiler_args...]\n"
            "        python main.py --config\n"
            "Example: python main.py gcc test_cases/bad_pointer.c -o out",
            file=sys.stderr,
        )
        sys.exit(1)

    sys.exit(run(sys.argv[1:]))
