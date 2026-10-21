# =============================================================================
# ast_engine.py — Tree-sitter AST parser & scope/symbol extractor
# =============================================================================
"""
Reads a C/C++ source file, parses it into an Abstract Syntax Tree via
tree-sitter, locates the exact AST node at the compiler-reported coordinates,
and walks upward to extract the enclosing statement, expression, and function
scope for rich diagnostic context.
"""

import sys
from pathlib import Path
from typing import Optional

# tree-sitter 0.21.x + tree-sitter-languages --------------------------------
try:
    from tree_sitter import Language, Parser
    from tree_sitter_languages import get_language, get_parser
except ImportError as exc:
    print(
        "[ast_engine] FATAL: tree-sitter or tree-sitter-languages not installed.\n"
        "  Run: pip install tree-sitter==0.21.3 tree-sitter-languages",
        file=sys.stderr,
    )
    raise SystemExit(1) from exc

from config import LANGUAGE_MAP, MAX_SCOPE_BYTES


# ---------------------------------------------------------------------------
# Node-type taxonomy
# ---------------------------------------------------------------------------

# AST node types that represent a containing *statement*
_STATEMENT_TYPES = {
    "expression_statement",
    "declaration",
    "return_statement",
    "if_statement",
    "for_statement",
    "while_statement",
    "do_statement",
    "switch_statement",
    "assignment_expression",
    "call_expression",
    "binary_expression",
    "init_declarator",
}

# AST node types that represent a containing *function/scope*
_SCOPE_TYPES = {
    "function_definition",
    "function_declarator",
    "compound_statement",
    "translation_unit",
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _node_text(node, source_bytes: bytes) -> str:
    """Return the UTF-8 source text for an AST node, safely truncated."""
    try:
        raw = source_bytes[node.start_byte : node.end_byte]
        text = raw.decode("utf-8", errors="replace")
        return text[:MAX_SCOPE_BYTES]
    except Exception:
        return "<unavailable>"


def _walk_up_to(node, target_types: set):
    """Walk up the parent chain until a node of a target type is found."""
    current = node.parent
    while current is not None:
        if current.type in target_types:
            return current
        current = current.parent
    return None


def _find_enclosing_function(node):
    """Return the nearest enclosing function_definition node, or None."""
    return _walk_up_to(node, {"function_definition"})


def _find_enclosing_statement(node):
    """Return the nearest enclosing statement-level node."""
    return _walk_up_to(node, _STATEMENT_TYPES)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_ast_context(
    file_path: str,
    line: int,
    col: int,
    lang: str,
) -> dict:
    """
    Parse *file_path* and return AST context centred on (line, col).

    Parameters
    ----------
    file_path : str
        Absolute or relative path to the C/C++ source file.
    line : int
        1-indexed line number reported by the compiler.
    col : int
        1-indexed column number reported by the compiler.
    lang : str
        Language identifier accepted by tree-sitter-languages ('c' or 'cpp').

    Returns
    -------
    dict with keys:
        node_type    (str)  — tree-sitter node type at the error point
        node_code    (str)  — source text of that node
        parent_type  (str)  — node type of the enclosing statement
        parent_code  (str)  — source text of the enclosing statement
        scope_code   (str)  — source text of the enclosing function (if any)
        error        (str)  — non-empty string if AST extraction failed
    """
    result: dict = {
        "node_type":   "unknown",
        "node_code":   "",
        "parent_type": "unknown",
        "parent_code": "",
        "scope_code":  "",
        "error":       "",
    }

    # --- Read source bytes ---------------------------------------------------
    source_path = Path(file_path)
    if not source_path.exists():
        result["error"] = f"Source file not found: {file_path}"
        return result

    try:
        source_bytes = source_path.read_bytes()
    except OSError as exc:
        result["error"] = f"Cannot read source file: {exc}"
        return result

    # --- Resolve language ----------------------------------------------------
    # Accept explicit lang string or derive from file extension
    if lang not in ("c", "cpp"):
        ext = source_path.suffix.lower()
        lang = LANGUAGE_MAP.get(ext, "c")

    # --- Build parser --------------------------------------------------------
    try:
        parser = get_parser(lang)
    except Exception as exc:
        result["error"] = f"tree-sitter-languages cannot load '{lang}': {exc}"
        return result

    # --- Parse ---------------------------------------------------------------
    try:
        tree = parser.parse(source_bytes)
    except Exception as exc:
        result["error"] = f"tree-sitter parse failed: {exc}"
        return result

    root = tree.root_node

    # --- Locate target node --------------------------------------------------
    # tree-sitter uses 0-indexed (row, col); compiler reports 1-indexed
    ts_row = max(0, line - 1)
    ts_col = max(0, col - 1)
    point = (ts_row, ts_col)

    try:
        target_node = root.named_descendant_for_point_range(point, point)
    except Exception:
        target_node = None

    if target_node is None:
        result["error"] = (
            f"No AST node found at line {line}, col {col}. "
            "The error coordinate may point to a macro expansion or empty line."
        )
        return result

    # --- Extract target node info --------------------------------------------
    result["node_type"] = target_node.type
    result["node_code"] = _node_text(target_node, source_bytes)

    # --- Enclosing statement -------------------------------------------------
    stmt_node = _find_enclosing_statement(target_node)
    if stmt_node:
        result["parent_type"] = stmt_node.type
        result["parent_code"] = _node_text(stmt_node, source_bytes)
    else:
        # Fall back to direct parent
        if target_node.parent:
            result["parent_type"] = target_node.parent.type
            result["parent_code"] = _node_text(target_node.parent, source_bytes)

    # --- Enclosing function scope --------------------------------------------
    fn_node = _find_enclosing_function(target_node)
    if fn_node:
        result["scope_code"] = _node_text(fn_node, source_bytes)
    else:
        # No function found — use translation unit snippet around the error line
        lines = source_bytes.decode("utf-8", errors="replace").splitlines()
        start = max(0, ts_row - 5)
        end   = min(len(lines), ts_row + 6)
        result["scope_code"] = "\n".join(lines[start:end])

    return result


def resolve_language(file_path: str) -> str:
    """
    Return the tree-sitter language identifier for a given source file path.
    Defaults to 'c' if the extension is unrecognised.
    """
    ext = Path(file_path).suffix.lower()
    return LANGUAGE_MAP.get(ext, "c")
