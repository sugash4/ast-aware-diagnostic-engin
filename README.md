# AST-Aware Universal Diagnostic Engine

AI-powered compiler error translation and code repair for C/C++/Embedded C toolchains.

---

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.10+ | `python --version` |
| GCC / G++ | any | or Clang / armcc |
| Ollama | latest | https://ollama.ai |
| `qwen2.5-coder` model | — | pulled via Ollama |

---

## Setup

```bash
# 1. Clone / unzip the project
cd ast_diagnostic_engine

# 2. Create a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Start Ollama (in a separate terminal)
ollama serve

# 5. Pull the AI model
ollama pull qwen2.5-coder
```

---

## Usage

```bash
python main.py <compiler> [compiler_flags...] <source_file> [-o output]
```

### Examples

```bash
# C — void pointer dereference
python main.py gcc test_cases/bad_pointer.c -o /tmp/bad_ptr

# C++ — type mismatch / narrowing conversion
python main.py g++ test_cases/type_mismatch.cpp -o /tmp/type_mm

# Clang
python main.py clang test_cases/bad_pointer.c -o /tmp/bad_ptr

# Any real project file
python main.py gcc -Wall -O2 src/main.c -o build/firmware
```

The tool wraps the compiler transparently:
- If compilation **succeeds** → prints a green success banner, exits 0.
- If compilation **fails** → runs the full AST → AI → Rich-UI pipeline.

---

## Output

Three Rich terminal panels are displayed:

| Panel | Border | Content |
|---|---|---|
| 1 | Red | Raw compiler error + coordinates |
| 2 | Blue | AST node type, source snippet, enclosing scope |
| 3 | Green | AI root-cause, rule violated, unified diff patch |

---

## Project Structure

```
ast_diagnostic_engine/
├── main.py           ← CLI entry point
├── interceptor.py    ← subprocess wrapper + stderr parser
├── ast_engine.py     ← tree-sitter parser + AST context extractor
├── ai_engine.py      ← Ollama REST client + prompt builder
├── formatter.py      ← Rich 3-panel UI renderer
├── config.py         ← global settings
├── requirements.txt
└── test_cases/
    ├── bad_pointer.c
    └── type_mismatch.cpp
```

---

## Configuration

Edit `config.py` to change:

| Variable | Default | Description |
|---|---|---|
| `OLLAMA_URL` | `http://localhost:11434/api/generate` | Ollama endpoint |
| `DEFAULT_MODEL` | `qwen2.5-coder` | Primary LLM |
| `FALLBACK_MODELS` | `["llama3", "codellama", "mistral"]` | Tried in order if primary fails |
| `OLLAMA_TIMEOUT` | `120` | Seconds before timeout |
| `MAX_SCOPE_BYTES` | `2048` | Max bytes of scope code sent to LLM |

---

## Supported Compilers

| Compiler | Error Pattern |
|---|---|
| GCC / G++ | `file:line:col: error: message` |
| Clang / Clang++ | `file:line:col: error: message` |
| Keil armcc | `"file", line N: Error: message` |
| IAR | `file(line) : Error[code]: message` |

---

## Troubleshooting

**`tree-sitter` import error**
```bash
pip install tree-sitter==0.21.3 tree-sitter-languages
```

**`Could not reach Ollama`**
```bash
ollama serve          # start Ollama daemon
ollama pull qwen2.5-coder
```

**No AST node found at coordinates**
This happens when the error points to a macro expansion or a line that
tree-sitter represents differently. The AI panel will still run with
whatever partial context is available.
