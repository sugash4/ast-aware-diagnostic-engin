# =============================================================================
# formatter.py — Rich 3-panel terminal diagnostic display
# =============================================================================
"""
Renders three styled Rich panels in the terminal:
  Panel 1 (Red)   — Raw compiler error + coordinates
  Panel 2 (Blue)  — AST node / scope context (Compiler Theory Proof)
  Panel 3 (Green) — AI plain-English diagnosis + syntax-highlighted diff patch
"""

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text
from rich.columns import Columns
from rich.rule import Rule
from rich import box

from config import PANEL_COLORS

console = Console()


# ---------------------------------------------------------------------------
# Internal panel builders
# ---------------------------------------------------------------------------

def _panel_compiler_error(compiler_data: dict) -> Panel:
    """Panel 1: Raw compiler error with file/line/col coordinates."""
    file_str  = compiler_data.get("file", "<unknown>")
    line_str  = str(compiler_data.get("line", "?"))
    col_str   = str(compiler_data.get("col", "?"))
    raw_err   = compiler_data.get("raw_error", "No error message captured.")
    stderr    = compiler_data.get("stderr", "").strip()

    content = Text()
    content.append("File   : ", style="bold white")
    content.append(f"{file_str}\n", style="cyan")
    content.append("Line   : ", style="bold white")
    content.append(f"{line_str}\n", style="yellow")
    content.append("Column : ", style="bold white")
    content.append(f"{col_str}\n\n", style="yellow")
    content.append("Primary Error:\n", style="bold white")
    content.append(f"{raw_err}\n", style="red")

    if stderr and stderr != raw_err:
        content.append("\nFull stderr output:\n", style="bold white")
        content.append(stderr, style="dim red")

    return Panel(
        content,
        title="[bold red]● COMPILER ERROR[/bold red]",
        border_style=PANEL_COLORS["error"],
        box=box.DOUBLE_EDGE,
        padding=(1, 2),
    )


def _panel_ast_context(ast_data: dict) -> Panel:
    """Panel 2: AST node type, code snippet, and scope code."""
    node_type   = ast_data.get("node_type", "unknown")
    node_code   = ast_data.get("node_code", "").strip()
    parent_type = ast_data.get("parent_type", "unknown")
    parent_code = ast_data.get("parent_code", "").strip()
    scope_code  = ast_data.get("scope_code", "").strip()
    ast_error   = ast_data.get("error", "")

    content = Text()

    if ast_error:
        content.append("⚠  AST extraction error:\n", style="bold yellow")
        content.append(ast_error + "\n", style="yellow")
    else:
        content.append("Target AST Node Type : ", style="bold white")
        content.append(f"{node_type}\n\n", style="bright_cyan")

        if node_code:
            content.append("Node Source Snippet:\n", style="bold white")

    renderables = [content]

    if not ast_error:
        if node_code:
            renderables.append(
                Syntax(node_code, "c", theme="monokai", line_numbers=False)
            )

        stmt_header = Text()
        stmt_header.append("\nEnclosing Statement Type : ", style="bold white")
        stmt_header.append(f"{parent_type}\n\n", style="bright_cyan")
        if parent_code:
            stmt_header.append("Statement Source:\n", style="bold white")
        renderables.append(stmt_header)

        if parent_code:
            renderables.append(
                Syntax(parent_code, "c", theme="monokai", line_numbers=False)
            )

        if scope_code:
            scope_header = Text("\nEnclosing Function/Scope:\n", style="bold white")
            renderables.append(scope_header)
            renderables.append(
                Syntax(scope_code, "c", theme="monokai", line_numbers=True)
            )

    from rich.console import Group
    return Panel(
        Group(*renderables),
        title="[bold blue]◈ AST / SCOPE DEBUG TREE[/bold blue]",
        border_style=PANEL_COLORS["ast"],
        box=box.DOUBLE_EDGE,
        padding=(1, 2),
    )


def _panel_ai_diagnostics(ai_response: dict) -> Panel:
    """Panel 3: AI plain-English root cause + diff patch."""
    root_cause    = ai_response.get("root_cause", "").strip()
    rule_violated = ai_response.get("rule_violated", "").strip()
    patch         = ai_response.get("suggested_patch", "").strip()
    model_used    = ai_response.get("model_used", "unknown")
    ai_error      = ai_response.get("error", "")

    content_parts = []

    if ai_error:
        err_text = Text()
        err_text.append("⚠  AI engine error:\n", style="bold yellow")
        err_text.append(ai_error, style="yellow")
        content_parts.append(err_text)
    else:
        header = Text()
        header.append(f"Model : ", style="bold white")
        header.append(f"{model_used}\n\n", style="bright_green")

        if root_cause:
            header.append("Root Cause:\n", style="bold white")
            header.append(root_cause + "\n", style="green")

        if rule_violated:
            header.append("\nRule Violated:\n", style="bold white")
            header.append(rule_violated + "\n", style="bright_yellow")

        content_parts.append(header)

        if patch:
            patch_header = Text("\nSuggested Patch (unified diff):\n", style="bold white")
            content_parts.append(patch_header)
            content_parts.append(
                Syntax(patch, "diff", theme="monokai", line_numbers=False)
            )
        else:
            no_patch = Text("\nNo patch generated.", style="dim")
            content_parts.append(no_patch)

    from rich.console import Group
    return Panel(
        Group(*content_parts),
        title="[bold green]✦ AI DIAGNOSIS & CODE REPAIR[/bold green]",
        border_style=PANEL_COLORS["ai"],
        box=box.DOUBLE_EDGE,
        padding=(1, 2),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def display_results(
    compiler_data: dict,
    ast_data: dict,
    ai_response: dict,
) -> None:
    """
    Render the full 3-panel diagnostic display to the terminal.

    Parameters
    ----------
    compiler_data : dict   — output of interceptor.execute_compiler()
    ast_data      : dict   — output of ast_engine.extract_ast_context()
    ai_response   : dict   — output of ai_engine.generate_diagnostics()
    """
    console.print()
    console.rule("[bold white]AST-AWARE UNIVERSAL DIAGNOSTIC ENGINE[/bold white]")
    console.print()

    console.print(_panel_compiler_error(compiler_data))
    console.print()
    console.print(_panel_ast_context(ast_data))
    console.print()
    console.print(_panel_ai_diagnostics(ai_response))
    console.print()
    console.rule("[dim]End of diagnostic report[/dim]")
    console.print()


def display_success(cmd_args: list[str]) -> None:
    """Display a simple success banner when compilation succeeds."""
    console.print()
    console.print(
        Panel(
            Text(
                f"✓  Build succeeded with zero errors.\n"
                f"   Command: {' '.join(cmd_args)}",
                style="bold green",
                justify="center",
            ),
            title="[bold green]● BUILD SUCCESSFUL[/bold green]",
            border_style="bold green",
            box=box.DOUBLE_EDGE,
            padding=(1, 2),
        )
    )
    console.print()
