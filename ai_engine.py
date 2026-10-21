# =============================================================================
# ai_engine.py — Universal API client: Groq / OpenAI / Anthropic / Gemini / Ollama
# =============================================================================
"""
Reads config from ~/.ast_engine/config.json (written by settings.py).
On first run (no config) → auto-opens the settings screen.
On rate limit / auth error → opens the key-update screen, then retries once.
"""

import json
import re
import sys
from typing import Optional

import requests

from config import API_TIMEOUT, PROVIDERS
from settings import load_config, open_settings, prompt_key_update


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

_SYSTEM_INSTRUCTION = """\
You are an expert C/C++ compiler diagnostics engine.
You will receive:
  1. A raw compiler error message with file/line/column coordinates.
  2. The exact AST node type and source snippet at those coordinates.
  3. The enclosing statement/expression.
  4. The enclosing function scope source code.

You MUST respond with ONLY a single valid JSON object — no markdown fences,
no prose before or after — matching this exact schema:

{
  "root_cause": "<one concise paragraph: why this specific AST node violates C/C++ type/scope rules>",
  "rule_violated": "<exact C/C++ semantic or syntactic rule broken, e.g. ISO C11 §6.5.3.2>",
  "suggested_patch": "<unified diff snippet showing the minimal fix, starting with --- and +++>"
}
"""


def _build_prompt(compiler_data: dict, ast_data: dict) -> str:
    return f"""\
=== COMPILER ERROR ===
File   : {compiler_data.get('file', '<unknown>')}
Line   : {compiler_data.get('line', 0)}
Column : {compiler_data.get('col', 0)}
Error  : {compiler_data.get('raw_error', '')}

Full stderr:
{compiler_data.get('stderr', '')}

=== AST CONTEXT ===
Target node type  : {ast_data.get('node_type', 'unknown')}
Target node code  :
{ast_data.get('node_code', '')}

Enclosing statement type : {ast_data.get('parent_type', 'unknown')}
Enclosing statement code :
{ast_data.get('parent_code', '')}

Enclosing function/scope :
{ast_data.get('scope_code', '')}

=== TASK ===
Analyse the above and produce ONLY a JSON object with keys:
  root_cause, rule_violated, suggested_patch
"""


# ---------------------------------------------------------------------------
# Provider-specific callers
# ---------------------------------------------------------------------------

def _call_openai_compatible(cfg: dict, prompt: str):
    provider_key = cfg["provider"]
    base_url     = PROVIDERS[provider_key]["base_url"]
    headers = {
        "Content-Type":  "application/json",
        "Authorization": f"Bearer {cfg['api_key']}",
    }
    payload = {
        "model":    cfg["model"],
        "messages": [
            {"role": "system", "content": _SYSTEM_INSTRUCTION},
            {"role": "user",   "content": prompt},
        ],
        "temperature": 0.1,
        "max_tokens":  1024,
    }
    resp = requests.post(base_url, headers=headers, json=payload, timeout=API_TIMEOUT)
    text = ""
    if resp.status_code == 200:
        text = resp.json().get("choices", [{}])[0].get("message", {}).get("content", "")
    return resp, text


def _call_anthropic(cfg: dict, prompt: str):
    base_url = PROVIDERS["anthropic"]["base_url"]
    headers  = {
        "Content-Type":      "application/json",
        "x-api-key":         cfg["api_key"],
        "anthropic-version": "2023-06-01",
    }
    payload = {
        "model":      cfg["model"],
        "max_tokens": 1024,
        "system":     _SYSTEM_INSTRUCTION,
        "messages":   [{"role": "user", "content": prompt}],
    }
    resp = requests.post(base_url, headers=headers, json=payload, timeout=API_TIMEOUT)
    text = ""
    if resp.status_code == 200:
        blocks = resp.json().get("content", [])
        text   = " ".join(b.get("text", "") for b in blocks if b.get("type") == "text")
    return resp, text


def _call_gemini(cfg: dict, prompt: str):
    model    = cfg["model"]
    base_url = PROVIDERS["gemini"]["base_url"].format(model=model)
    url      = f"{base_url}?key={cfg['api_key']}"
    payload  = {
        "contents": [{"parts": [{"text": _SYSTEM_INSTRUCTION + "\n\n" + prompt}]}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 1024},
    }
    resp = requests.post(url, json=payload, timeout=API_TIMEOUT)
    text = ""
    if resp.status_code == 200:
        candidates = resp.json().get("candidates", [])
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            text  = "".join(p.get("text", "") for p in parts)
    return resp, text


def _call_ollama(cfg: dict, prompt: str):
    base_url = PROVIDERS["ollama"]["base_url"]
    payload  = {
        "model":   cfg["model"],
        "prompt":  _SYSTEM_INSTRUCTION + "\n\n" + prompt,
        "stream":  False,
        "options": {"temperature": 0.1, "num_predict": 1024},
    }
    resp = requests.post(base_url, json=payload, timeout=API_TIMEOUT)
    text = ""
    if resp.status_code == 200:
        text = resp.json().get("response", "")
    return resp, text


def _dispatch(cfg: dict, prompt: str):
    style = PROVIDERS[cfg["provider"]]["style"]
    if style == "openai":
        return _call_openai_compatible(cfg, prompt)
    if style == "anthropic":
        return _call_anthropic(cfg, prompt)
    if style == "gemini":
        return _call_gemini(cfg, prompt)
    if style == "ollama":
        return _call_ollama(cfg, prompt)
    raise ValueError(f"Unknown provider style: {style}")


# ---------------------------------------------------------------------------
# Error classification
# ---------------------------------------------------------------------------

def _classify_error(status_code: int, body: str) -> str:
    body_lower = body.lower()
    if status_code == 429 or "rate_limit" in body_lower or "quota" in body_lower:
        return "rate_limit"
    if status_code in (401, 403) or "invalid api key" in body_lower or "unauthorized" in body_lower:
        return "auth_error"
    return "other"


# ---------------------------------------------------------------------------
# JSON extraction
# ---------------------------------------------------------------------------

def _extract_json(raw_text: str) -> dict:
    cleaned = re.sub(r"```(?:json)?", "", raw_text).strip()
    start   = cleaned.find("{")
    end     = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in model response.")
    return json.loads(cleaned[start : end + 1])


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_diagnostics(compiler_data: dict, ast_data: dict) -> dict:
    """
    Main entry point. Loads config, dispatches to provider, handles errors.
    Auto-opens settings on first run. Prompts key update on rate limit / auth error.
    """
    result: dict = {
        "root_cause":      "",
        "rule_violated":   "",
        "suggested_patch": "",
        "model_used":      "",
        "raw_response":    "",
        "error":           "",
    }

    # --- Load config — open settings if missing --------------------------
    cfg = load_config()
    if cfg is None:
        cfg = open_settings(reason="first_run")

    prompt = _build_prompt(compiler_data, ast_data)

    # --- Attempt with one retry on recoverable errors --------------------
    for attempt in range(2):
        try:
            print(
                f"[ai_engine] {cfg['provider']} / {cfg['model']} …",
                file=sys.stderr,
            )
            resp, raw_text = _dispatch(cfg, prompt)

        except requests.exceptions.ConnectionError:
            if cfg["provider"] == "ollama":
                result["error"] = "Cannot reach Ollama. Start it with: ollama serve"
            else:
                result["error"] = f"Cannot reach {cfg['provider']}. Check your internet connection."
            return result

        except requests.exceptions.Timeout:
            result["error"] = f"Request to {cfg['provider']} timed out after {API_TIMEOUT}s."
            return result

        except Exception as exc:
            result["error"] = f"Unexpected error: {exc}"
            return result

        # --- HTTP error handling -----------------------------------------
        if resp.status_code != 200:
            error_cls = _classify_error(resp.status_code, resp.text)

            if attempt == 0 and error_cls in ("rate_limit", "auth_error"):
                cfg = prompt_key_update(cfg, reason=error_cls)
                continue  # retry with updated config

            result["error"] = (
                f"API error from {cfg['provider']} "
                f"(HTTP {resp.status_code}): {resp.text[:300]}"
            )
            return result

        # --- Success -------------------------------------------------------
        result["model_used"]   = f"{cfg['provider']} / {cfg['model']}"
        result["raw_response"] = raw_text

        try:
            parsed = _extract_json(raw_text)
        except (ValueError, json.JSONDecodeError) as exc:
            result["error"]      = f"Model response was not valid JSON: {exc}"
            result["root_cause"] = raw_text
            return result

        result["root_cause"]      = parsed.get("root_cause", "")
        result["rule_violated"]   = parsed.get("rule_violated", "")
        result["suggested_patch"] = parsed.get("suggested_patch", "")
        return result

    result["error"] = "All retry attempts exhausted."
    return result
