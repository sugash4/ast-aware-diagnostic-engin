# =============================================================================
# settings.py — Rich-powered CLI settings screen (Cline-style)
# =============================================================================
"""
Handles:
  - First-run detection and auto-redirect to settings
  - Provider / model / API key selection via clean Rich terminal UI
  - Config persistence to ~/.ast_engine/config.json
  - Key masking display (shows sk-••••••••)
  - Key update screen when rate limit / auth error occurs
"""

import json
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich import box

from config import PROVIDERS, USER_CONFIG_DIR, USER_CONFIG_FILE

console = Console()


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------

def load_config() -> dict | None:
    """Return saved config dict or None if not configured yet."""
    if USER_CONFIG_FILE.exists():
        try:
            return json.loads(USER_CONFIG_FILE.read_text())
        except Exception:
            return None
    return None


def save_config(cfg: dict) -> None:
    """Save config to ~/.ast_engine/config.json."""
    USER_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    USER_CONFIG_FILE.write_text(json.dumps(cfg, indent=2))


def _mask_key(key: str) -> str:
    """Return a masked version: first 4 chars + bullets."""
    if not key or key == "not-required":
        return key
    visible = key[:6] if len(key) > 10 else key[:2]
    return visible + "•" * min(14, len(key) - len(visible))


# ---------------------------------------------------------------------------
# UI building blocks
# ---------------------------------------------------------------------------

def _print_header(title: str = "Settings") -> None:
    console.print()
    console.print(
        Panel(
            Text(f"AST Diagnostic Engine — {title}", justify="center", style="bold white"),
            border_style="bold cyan",
            box=box.DOUBLE_EDGE,
            padding=(0, 4),
        )
    )
    console.print()


def _print_provider_menu(current: str | None = None) -> None:
    """Print numbered provider list inside a styled panel."""
    lines = Text()
    provider_keys = list(PROVIDERS.keys())
    for i, key in enumerate(provider_keys, 1):
        p   = PROVIDERS[key]
        tag = "[green]Free[/green]" if p["free"] else "[yellow]Paid[/yellow]"
        selected = " ◄ current" if key == current else ""
        lines.append(f"  [{i}]  ", style="bold cyan")
        lines.append(f"{p['label']:<18}", style="bold white")
        lines.append(f"{p['tag']}", style="dim")
        lines.append(f"{selected}\n", style="green")

    console.print(
        Panel(
            lines,
            title="[bold cyan]Select API Provider[/bold cyan]",
            border_style="cyan",
            box=box.ROUNDED,
            padding=(0, 2),
        )
    )


def _print_model_menu(provider_key: str, current_model: str | None = None) -> None:
    """Print numbered model list for the selected provider."""
    models = PROVIDERS[provider_key]["models"]
    lines  = Text()
    for i, m in enumerate(models, 1):
        rec      = "  ← recommended" if i == 1 else ""
        selected = " ◄ current" if m == current_model else ""
        lines.append(f"  [{i}]  ", style="bold cyan")
        lines.append(f"{m}", style="bold white")
        lines.append(f"{rec}{selected}\n", style="dim green")

    console.print(
        Panel(
            lines,
            title=f"[bold cyan]Select Model — {PROVIDERS[provider_key]['label']}[/bold cyan]",
            border_style="cyan",
            box=box.ROUNDED,
            padding=(0, 2),
        )
    )


def _print_current_config(cfg: dict) -> None:
    """Display the saved config summary."""
    p = PROVIDERS.get(cfg.get("provider", ""), {})
    lines = Text()
    lines.append("  Provider  :  ", style="bold white")
    lines.append(f"{p.get('label', cfg.get('provider', ''))}\n", style="bright_cyan")
    lines.append("  Model     :  ", style="bold white")
    lines.append(f"{cfg.get('model', '')}\n", style="bright_cyan")
    lines.append("  API Key   :  ", style="bold white")
    lines.append(f"{_mask_key(cfg.get('api_key', ''))}\n", style="bright_cyan")
    lines.append("  Saved at  :  ", style="bold white")
    lines.append(str(USER_CONFIG_FILE), style="dim")

    console.print(
        Panel(
            lines,
            title="[bold green]✓ Current Configuration[/bold green]",
            border_style="green",
            box=box.ROUNDED,
            padding=(0, 2),
        )
    )
    console.print()


# ---------------------------------------------------------------------------
# Input helpers
# ---------------------------------------------------------------------------

def _pick_number(prompt: str, max_n: int, default: int | None = None) -> int:
    """Ask user to pick a number in [1, max_n]. Returns 1-indexed int."""
    while True:
        suffix = f" (Enter for {default})" if default else ""
        raw = input(f"  {prompt}{suffix}: ").strip()
        if raw == "" and default:
            return default
        if raw.isdigit() and 1 <= int(raw) <= max_n:
            return int(raw)
        console.print(f"  [red]Please enter a number between 1 and {max_n}.[/red]")


def _input_api_key(provider_key: str, current_key: str | None = None) -> str:
    """Prompt for API key with key URL hint."""
    if provider_key == "ollama":
        return "not-required"

    p = PROVIDERS[provider_key]
    console.print()
    console.print(
        Panel(
            Text(f"  Get your free API key at:\n  {p['key_url']}", style="bold white"),
            title="[bold cyan]API Key[/bold cyan]",
            border_style="cyan",
            box=box.ROUNDED,
            padding=(0, 2),
        )
    )

    if current_key:
        console.print(
            f"  Current key: [dim]{_mask_key(current_key)}[/dim]  "
            "(Press Enter to keep)"
        )

    while True:
        key = input("  Paste API key: ").strip()
        if key == "" and current_key:
            return current_key
        if key:
            return key
        console.print("  [red]API key cannot be empty.[/red]")


# ---------------------------------------------------------------------------
# Public settings screens
# ---------------------------------------------------------------------------

def open_settings(reason: str = "user_request") -> dict:
    """
    Full settings screen — provider, model, API key.
    reason: "first_run" | "user_request" | "rate_limit" | "auth_error"
    Returns saved config dict.
    """
    existing = load_config()

    _print_header("Settings")

    # --- Reason banner ---
    if reason == "first_run":
        console.print(
            Panel(
                Text(
                    "  No API key configured yet.\n"
                    "  Set up your provider and key below — takes 30 seconds.\n"
                    "  Your key stays on your machine only.",
                    style="bold white",
                ),
                border_style="yellow",
                box=box.ROUNDED,
                padding=(0, 2),
            )
        )
        console.print()
    elif reason == "rate_limit":
        console.print(
            Panel(
                Text("  Rate limit hit. Update your API key or switch provider.", style="bold yellow"),
                border_style="yellow", box=box.ROUNDED, padding=(0, 1),
            )
        )
        console.print()
    elif reason == "auth_error":
        console.print(
            Panel(
                Text("  API key rejected. Please enter a valid key.", style="bold red"),
                border_style="red", box=box.ROUNDED, padding=(0, 1),
            )
        )
        console.print()

    # --- Show existing config if present ---
    if existing and reason == "user_request":
        _print_current_config(existing)
        console.print("  Reconfigure below, or press Ctrl+C to cancel.\n")

    # --- Provider selection ---
    current_provider = existing.get("provider") if existing else None
    _print_provider_menu(current=current_provider)

    provider_keys   = list(PROVIDERS.keys())
    current_idx     = (provider_keys.index(current_provider) + 1) if current_provider in provider_keys else None
    provider_choice = _pick_number("Select provider", len(provider_keys), default=current_idx)
    provider_key    = provider_keys[provider_choice - 1]
    provider        = PROVIDERS[provider_key]

    console.print(
        f"\n  [bold green]✓[/bold green] Provider: [bold cyan]{provider['label']}[/bold cyan]\n"
    )

    # --- Model selection ---
    current_model = existing.get("model") if existing and existing.get("provider") == provider_key else None
    _print_model_menu(provider_key, current_model=current_model)

    models        = provider["models"]
    current_m_idx = (models.index(current_model) + 1) if current_model in models else 1
    model_choice  = _pick_number("Select model", len(models), default=current_m_idx)
    chosen_model  = models[model_choice - 1]

    console.print(
        f"\n  [bold green]✓[/bold green] Model: [bold cyan]{chosen_model}[/bold cyan]\n"
    )

    # --- API key ---
    current_key = existing.get("api_key") if existing and existing.get("provider") == provider_key else None
    api_key     = _input_api_key(provider_key, current_key=current_key)

    # --- Save ---
    cfg = {
        "provider": provider_key,
        "model":    chosen_model,
        "api_key":  api_key,
    }
    save_config(cfg)

    console.print()
    console.print(
        Panel(
            Text(
                f"  Provider  :  {provider['label']}\n"
                f"  Model     :  {chosen_model}\n"
                f"  API Key   :  {_mask_key(api_key)}\n\n"
                f"  Saved to  :  {USER_CONFIG_FILE}",
                style="bold white",
            ),
            title="[bold green]✓ Configuration Saved[/bold green]",
            border_style="green",
            box=box.DOUBLE_EDGE,
            padding=(0, 2),
        )
    )
    console.print()
    return cfg


def prompt_key_update(cfg: dict, reason: str) -> dict:
    """
    Lightweight key-update screen shown on rate limit / auth error.
    User can update key only, or open full settings to switch provider.
    Returns updated config.
    """
    _print_header("Update API Key")
    _print_current_config(cfg)

    console.print("  [1]  Update API key (keep current provider & model)")
    console.print("  [2]  Switch provider / full reconfigure")
    console.print()
    choice = _pick_number("Choice", 2, default=1)

    if choice == 2:
        return open_settings(reason=reason)

    # Just update the key
    new_key = _input_api_key(cfg["provider"])
    cfg["api_key"] = new_key
    save_config(cfg)

    console.print(
        f"\n  [bold green]✓[/bold green] Key updated: [dim]{_mask_key(new_key)}[/dim]\n"
    )
    return cfg
