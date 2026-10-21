# =============================================================================
# config.py — Global configuration for AST Diagnostic Engine
# =============================================================================

from pathlib import Path

# ---------------------------------------------------------------------------
# User config — stored in home directory, personal to each machine
# Never inside the project folder (won't get committed to git)
# ---------------------------------------------------------------------------
USER_CONFIG_DIR  = Path.home() / ".ast_engine"
USER_CONFIG_FILE = USER_CONFIG_DIR / "config.json"

# ---------------------------------------------------------------------------
# Supported providers
# ---------------------------------------------------------------------------
PROVIDERS = {
    "groq": {
        "label":         "Groq",
        "tag":           "Free — fast, hosts Qwen/Llama models",
        "base_url":      "https://api.groq.com/openai/v1/chat/completions",
        "style":         "openai",
        "default_model": "qwen2.5-coder",
        "models":        ["qwen2.5-coder", "llama-3.3-70b-versatile", "llama3-70b-8192"],
        "key_url":       "https://console.groq.com/keys",
        "free":          True,
    },
    "gemini": {
        "label":         "Google Gemini",
        "tag":           "Free tier available",
        "base_url":      "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        "style":         "gemini",
        "default_model": "gemini-2.0-flash",
        "models":        ["gemini-2.0-flash", "gemini-1.5-pro"],
        "key_url":       "https://aistudio.google.com/app/apikey",
        "free":          True,
    },
    "openai": {
        "label":         "OpenAI",
        "tag":           "Paid — GPT-4o / GPT-4o-mini",
        "base_url":      "https://api.openai.com/v1/chat/completions",
        "style":         "openai",
        "default_model": "gpt-4o-mini",
        "models":        ["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"],
        "key_url":       "https://platform.openai.com/api-keys",
        "free":          False,
    },
    "anthropic": {
        "label":         "Anthropic",
        "tag":           "Paid — Claude Haiku / Sonnet",
        "base_url":      "https://api.anthropic.com/v1/messages",
        "style":         "anthropic",
        "default_model": "claude-haiku-4-5-20251001",
        "models":        ["claude-haiku-4-5-20251001", "claude-sonnet-4-6"],
        "key_url":       "https://console.anthropic.com/settings/keys",
        "free":          False,
    },
    "ollama": {
        "label":         "Ollama",
        "tag":           "Free — fully offline, needs local install",
        "base_url":      "http://localhost:11434/api/generate",
        "style":         "ollama",
        "default_model": "qwen2.5-coder",
        "models":        ["qwen2.5-coder", "llama3", "codellama", "mistral"],
        "key_url":       "https://ollama.ai",
        "free":          True,
    },
}

# Request timeout in seconds
API_TIMEOUT = 60

# Map source file extensions -> tree-sitter language identifiers
LANGUAGE_MAP = {
    ".c":   "c",
    ".h":   "c",
    ".cpp": "cpp",
    ".cc":  "cpp",
    ".cxx": "cpp",
    ".hpp": "cpp",
    ".hxx": "cpp",
}

# Compiler stderr regex patterns
COMPILER_PATTERNS = {
    "gcc_clang": r"^(?P<file>[^:]+):(?P<line>\d+):(?P<col>\d+):\s*(?:error|warning|fatal error):\s*(?P<message>.+)$",
    "keil":      r'^"(?P<file>[^"]+)",\s*line\s*(?P<line>\d+)(?::(?P<col>\d+))?:\s*(?:Error|Warning)[^:]*:\s*(?P<message>.+)$',
    "iar":       r"^(?P<file>[^\(]+)\((?P<line>\d+)\)\s*:\s*(?:Error|Warning)\[(?P<col>[^\]]*)\]:\s*(?P<message>.+)$",
}

# Rich panel border colours
PANEL_COLORS = {
    "error": "bold red",
    "ast":   "bold blue",
    "ai":    "bold green",
}

# Maximum bytes of scope code sent to the LLM
MAX_SCOPE_BYTES = 2048
