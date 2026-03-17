# Contributing to LearningTool

Thanks for your interest in contributing! This project is built to be simple and contributor-friendly.

## Setup

```bash
git clone https://github.com/Lucasmind/LearningTool.git
cd LearningTool
pip install -r requirements.txt
python app.py
# Opens at http://localhost:8100
```

No build step. No framework. Edit files, refresh browser.

## Architecture

See [development-docs/system-architecture.md](development-docs/system-architecture.md) for the full system design.

The project has two main parts:

- **Learning Tool** (`app.py`, `static/`) — The web application
- **Infrastructure** (`infrastructure/`) — Bundled LLM server, orchestrator, and web search

## Code Style

- **Backend:** Python, standard library where possible, FastAPI for the API layer
- **Frontend:** Vanilla JS, IIFE module pattern, no framework, no build step
- **Infrastructure:** Docker Compose, shell scripts
- **Keep it simple.** The lack of complexity is a feature.

## Pull Requests

- One feature or fix per PR
- Test with at least one LLM provider before submitting
- Update `development-docs/system-architecture.md` if you change the architecture
- If adding a new frontend module, use the IIFE pattern matching existing files

## Adding Models to the Catalog

To add a new model option to `models.json`:

1. Verify the GGUF file works with llama.cpp's `llama-server`
2. Test the RAM requirement on a machine with that much memory
3. Include accurate `ram_gb` and `disk_gb` values
4. Submit a PR with the model entry and a note about what hardware you tested on

## Reporting Issues

Please include:
- Your OS and hardware (RAM, GPU if applicable)
- Which LLM provider you're using
- Browser console errors if it's a frontend issue
- Steps to reproduce
