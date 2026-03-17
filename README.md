# LearningTool

**Build a connected graph of understanding.** Ask a question, get an AI response, highlight text to branch into deeper exploration. Every follow-up becomes a connected node in a visual knowledge graph.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-green.svg)](https://www.python.org/)
[![No Build Step](https://img.shields.io/badge/Frontend-No%20Build%20Step-orange.svg)](#architecture)

<!-- TODO: Add demo GIF here
![Demo](docs/demo.gif)
-->

## How It Works

1. **Ask a question** -- type in the top bar, get a streaming AI response in a visual node
2. **Highlight text** in any response, right-click, and choose:
   - **Explain in Context** -- what does this mean in the current discussion?
   - **Dig Deeper** -- explain this concept from first principles
   - **Ask a Question** -- ask anything about the highlighted text
3. **A new connected node appears** with the AI's response, linked by an edge from your highlight
4. **Keep branching** -- build a tree of understanding as deep as you want

Each node carries the conversation context forward, so the AI always knows what you've explored so far.

## Quick Start

### Full Stack (includes local LLM + web search)

Everything you need in one command. The setup script detects your hardware, lets you pick a model that fits, downloads it, and generates a Docker Compose configuration.

```bash
git clone https://github.com/Lucasmind/LearningTool.git
cd LearningTool
python3 setup.py
docker compose up --build
# Opens at http://localhost:8100
```

**What gets installed:**
- LearningTool web app (port 8100)
- llama.cpp server running your chosen model (Vulkan GPU or CPU)
- Smart orchestrator with web search capability
- SearXNG meta-search engine (optional)

**Requirements:** Docker, Docker Compose, Python 3.10+ (for setup script only)

### Bring Your Own LLM

Already have Ollama, vLLM, or an API key? Run the tool standalone:

```bash
git clone https://github.com/Lucasmind/LearningTool.git
cd LearningTool
pip install -r requirements.txt
python app.py
# Opens at http://localhost:8100
# Configure providers in the Settings UI (gear icon)
```

**3 Python dependencies.** No build step. No framework.

## Supported LLM Providers

| Provider | How to Connect |
|----------|---------------|
| **Bundled llama.cpp** | `python3 setup.py` -- included in full stack |
| **Ollama** | Settings UI -> Add Provider -> Ollama (auto-detects models) |
| **OpenAI / Anthropic / Gemini** | Settings UI -> Add Provider -> API key |
| **Any OpenAI-compatible API** | Settings UI -> Add Provider -> URL + optional key |
| **Claude Code CLI** | Settings UI -> Add Provider -> Claude CLI (uses your subscription) |
| **Local servers** (vLLM, llama.cpp, etc.) | Settings UI -> Add Provider -> URL |

## Bundled Models

The setup script offers models at every hardware tier:

| Tier | Model | RAM | Quality | Best For |
|------|-------|-----|---------|----------|
| Tiny | Llama 3.2 1B | 2 GB | Basic | Testing, Raspberry Pi |
| Small | Qwen3 4B | 4 GB | Decent | 8GB machines |
| Medium | Qwen3 8B | 8 GB | Good | 16GB laptops |
| Large | Qwen3.5 27B | 20 GB | Very good | 32GB desktops |
| XL | Qwen3 235B-A22B | 64 GB | Excellent | 128GB workstations |

Hardware detection checks your RAM, GPU, and disk space, then shows which models will actually run.

## Screenshots

<!-- TODO: Add screenshots
- Initial query with streaming response
- Branched graph with multiple nodes connected by edges
- Settings panel showing provider configuration
-->

## Architecture

```
Browser (localhost:8100)
    |
    |  REST API + SSE streaming
    v
FastAPI Server (app.py)
    |
    |  OpenAI-compatible API
    v
Orchestrator (infrastructure/orchestrator)
    |           |
    v           v
llama.cpp    SearXNG
(your model)  (web search)
```

- **Frontend:** Vanilla JS, CSS transforms for infinite canvas, no framework, no build step
- **Backend:** Python/FastAPI, SSE streaming, file-based JSON sessions
- **Orchestrator:** Agentic proxy with web search, thinking mode control, smart routing
- **LLM Server:** llama.cpp with Vulkan GPU or CPU fallback

## Configuration

### CLI Arguments

| Flag | Default | Description |
|------|---------|-------------|
| `--port` | 8100 | Server port |
| `--llm-url` | `localhost:11434/v1/...` | LLM endpoint (first-run only) |
| `--llm-model` | `""` | Model name (first-run only) |

After first run, providers are managed through the Settings UI and persisted in `settings/providers.json`.

### Settings UI

Click the gear icon in the top bar to:
- Add, edit, and remove LLM providers
- Test provider connectivity
- Set default and fallback providers
- Configure per-provider model, temperature, max tokens, timeout

## Docker (Standalone)

To run just the Learning Tool in Docker (without the bundled LLM):

```bash
docker build -t learningtool .
docker run -p 8100:8100 \
  -v ./learning_sessions:/app/learning_sessions \
  -v ./settings:/app/settings \
  learningtool
```

## Project Structure

```
LearningTool/
├── app.py                      # FastAPI server, API routes, SSE streaming
├── models.py                   # Pydantic request/response models
├── prompt_engineer.py          # Prompt templates with lineage context
├── llm_bridge.py               # OpenAI-compatible provider + registry
├── claude_cli_provider.py      # Claude Code CLI integration
├── settings_manager.py         # Provider settings persistence
├── session_manager.py          # File-based session CRUD + trash
├── setup.py                    # Interactive installer + HW detection
├── models.json                 # Model catalog for setup.py
├── static/                     # Frontend (vanilla JS, no build step)
│   ├── index.html
│   ├── css/main.css
│   └── js/ (app, canvas, node, edge, session, settings, api, context_menu)
├── infrastructure/             # Bundled LLM infrastructure
│   ├── orchestrator/           # Smart routing proxy with web search
│   ├── llama-server/           # llama.cpp Docker build (Vulkan + CPU)
│   └── searxng/                # SearXNG meta-search config
├── learning_sessions/          # Your session data (gitignored)
└── development-docs/           # Architecture docs + dev journey
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). The simplicity of the stack is intentional -- vanilla JS, minimal Python dependencies, no build step. PRs welcome.

## License

[MIT](LICENSE)
