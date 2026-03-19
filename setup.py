#!/usr/bin/env python3
"""
LearningTool Setup — Interactive installer with hardware detection and model selection.

Detects system hardware (RAM, GPU, disk), presents compatible models,
downloads the selected model, and generates a docker-compose.yml to run everything.

Usage:
    python3 setup.py              # Interactive setup
    python3 setup.py --list       # List available models
    python3 setup.py --model ID   # Non-interactive, specify model by ID
"""

import json
import os
import platform
import re
import shutil
import subprocess
import sys
import urllib.request
import urllib.error
from pathlib import Path

# ---------------------------------------------------------------------------
# Hardware detection
# ---------------------------------------------------------------------------

def detect_ram_gb():
    """Detect total system RAM in GB."""
    try:
        if platform.system() == "Linux":
            with open("/proc/meminfo") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        kb = int(line.split()[1])
                        return round(kb / 1024 / 1024, 1)
        elif platform.system() == "Darwin":
            out = subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True)
            return round(int(out.strip()) / 1024 / 1024 / 1024, 1)
        elif platform.system() == "Windows":
            import ctypes
            kernel32 = ctypes.windll.kernel32
            c_ulonglong = ctypes.c_ulonglong
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", c_ulonglong),
                    ("ullAvailPhys", c_ulonglong),
                    ("ullTotalPageFile", c_ulonglong),
                    ("ullAvailPageFile", c_ulonglong),
                    ("ullTotalVirtual", c_ulonglong),
                    ("ullAvailVirtual", c_ulonglong),
                    ("ullAvailExtendedVirtual", c_ulonglong),
                ]
            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(stat)
            kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
            return round(stat.ullTotalPhys / 1024 / 1024 / 1024, 1)
    except Exception:
        pass
    return None


def detect_gpu():
    """
    Detect GPU type and VRAM.
    Returns dict: { "vendor": str, "name": str, "vram_gb": float|None }
    """
    gpu = {"vendor": "none", "name": "No GPU detected", "vram_gb": None}

    # Try nvidia-smi first
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            text=True, stderr=subprocess.DEVNULL
        )
        for line in out.strip().split("\n"):
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 2:
                gpu["vendor"] = "nvidia"
                gpu["name"] = parts[0]
                gpu["vram_gb"] = round(int(parts[1]) / 1024, 1)
                return gpu
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass

    # Try AMD via sysfs (Linux)
    try:
        dri_path = Path("/sys/class/drm")
        if dri_path.exists():
            for card in sorted(dri_path.glob("card[0-9]*")):
                vendor_file = card / "device" / "vendor"
                if vendor_file.exists():
                    vendor_id = vendor_file.read_text().strip()
                    if vendor_id == "0x1002":  # AMD
                        name_file = card / "device" / "product_name"
                        name = name_file.read_text().strip() if name_file.exists() else "AMD GPU"
                        # Try to get VRAM from mem_info_vram_total
                        vram = None
                        vram_file = card / "device" / "mem_info_vram_total"
                        if vram_file.exists():
                            vram = round(int(vram_file.read_text().strip()) / 1024 / 1024 / 1024, 1)
                        gpu["vendor"] = "amd"
                        gpu["name"] = name
                        gpu["vram_gb"] = vram
                        return gpu
                    elif vendor_id == "0x8086":  # Intel
                        gpu["vendor"] = "intel"
                        gpu["name"] = "Intel GPU"
                        return gpu
    except Exception:
        pass

    # Try lspci fallback
    try:
        out = subprocess.check_output(["lspci"], text=True, stderr=subprocess.DEVNULL)
        for line in out.split("\n"):
            lower = line.lower()
            if "vga" in lower or "3d" in lower or "display" in lower:
                if "nvidia" in lower:
                    gpu["vendor"] = "nvidia"
                    gpu["name"] = line.split(":")[-1].strip()
                    return gpu
                elif "amd" in lower or "radeon" in lower:
                    gpu["vendor"] = "amd"
                    gpu["name"] = line.split(":")[-1].strip()
                    return gpu
                elif "intel" in lower:
                    gpu["vendor"] = "intel"
                    gpu["name"] = line.split(":")[-1].strip()
                    return gpu
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass

    return gpu


def detect_disk_free_gb(path="."):
    """Detect free disk space in GB at the given path."""
    try:
        usage = shutil.disk_usage(path)
        return round(usage.free / 1024 / 1024 / 1024, 1)
    except Exception:
        return None


def check_docker():
    """Check if Docker and Docker Compose are available."""
    docker_ok = False
    compose_ok = False
    try:
        subprocess.check_output(["docker", "--version"], text=True, stderr=subprocess.DEVNULL)
        docker_ok = True
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass
    try:
        subprocess.check_output(["docker", "compose", "version"], text=True, stderr=subprocess.DEVNULL)
        compose_ok = True
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass
    return docker_ok, compose_ok


def check_unified_memory(ram_gb, gpu):
    """
    Detect if system has unified memory (GPU shares system RAM).
    Common on: Apple Silicon, AMD APUs (like Strix Halo), Intel iGPUs.
    With unified memory, the full system RAM is available for model loading.
    """
    if gpu["vendor"] == "none":
        return False

    # AMD APUs — no dedicated VRAM file means shared memory
    if gpu["vendor"] == "amd" and gpu["vram_gb"] is None:
        return True

    # Intel iGPUs always use shared memory
    if gpu["vendor"] == "intel":
        return True

    # macOS (Apple Silicon) — always unified
    if platform.system() == "Darwin":
        return True

    return False


# ---------------------------------------------------------------------------
# Model catalog
# ---------------------------------------------------------------------------

def load_models():
    """Load model catalog from models.json."""
    catalog_path = Path(__file__).parent / "models.json"
    if not catalog_path.exists():
        print("Error: models.json not found.")
        sys.exit(1)
    with open(catalog_path) as f:
        return json.load(f)["models"]


def filter_models(models, ram_gb, disk_gb, gpu):
    """
    Filter models to what can run on this hardware.
    Returns list of (model, status) tuples where status is 'ok', 'tight', or 'no'.
    """
    unified = check_unified_memory(ram_gb, gpu)
    # Available memory for model: system RAM (leave 4GB for OS overhead)
    available_ram = ram_gb - 4 if ram_gb else 0

    results = []
    for m in models:
        model_ram = m["ram_gb"]
        model_disk = m["disk_gb"]

        # Check disk space
        if disk_gb is not None and model_disk > disk_gb:
            results.append((m, "no_disk"))
            continue

        # Check RAM
        if model_ram > available_ram:
            results.append((m, "no_ram"))
        elif model_ram > available_ram * 0.85:
            results.append((m, "tight"))
        else:
            results.append((m, "ok"))

    return results


# ---------------------------------------------------------------------------
# Model download
# ---------------------------------------------------------------------------

def download_model(model, models_dir):
    """Download GGUF model files from HuggingFace."""
    models_dir = Path(models_dir)
    model_dir = models_dir / model["id"]
    model_dir.mkdir(parents=True, exist_ok=True)

    for filename in model["files"]:
        filepath = model_dir / filename
        if filepath.exists():
            print(f"  Already downloaded: {filename}")
            continue

        url = f"https://huggingface.co/{model['repo']}/resolve/main/{filename}"
        print(f"  Downloading: {filename}")
        print(f"  From: {url}")
        print(f"  To: {filepath}")
        print(f"  Size: ~{model['disk_gb']}GB — this may take a while...")
        print()

        try:
            # Use urllib with progress reporting
            req = urllib.request.Request(url, headers={"User-Agent": "LearningTool-Setup/1.0"})
            with urllib.request.urlopen(req) as response:
                total = int(response.headers.get("content-length", 0))
                downloaded = 0
                chunk_size = 1024 * 1024  # 1MB chunks

                with open(filepath, "wb") as out:
                    while True:
                        chunk = response.read(chunk_size)
                        if not chunk:
                            break
                        out.write(chunk)
                        downloaded += len(chunk)
                        if total > 0:
                            pct = downloaded / total * 100
                            bar_len = 40
                            filled = int(bar_len * downloaded / total)
                            bar = "#" * filled + "-" * (bar_len - filled)
                            print(f"\r  [{bar}] {pct:.1f}% ({downloaded/1e9:.1f}/{total/1e9:.1f} GB)", end="", flush=True)
                print()  # newline after progress bar

        except Exception as e:
            print(f"\n  Error downloading {filename}: {e}")
            if filepath.exists():
                filepath.unlink()
            print("\n  You can manually download the model from:")
            print(f"  {url}")
            print(f"  Place it at: {filepath}")
            sys.exit(1)

    return model_dir


# ---------------------------------------------------------------------------
# Docker Compose generation
# ---------------------------------------------------------------------------

def generate_compose(model, gpu, models_dir, enable_search=True):
    """Generate docker-compose.yml tailored to hardware and model choice."""
    model_dir = Path(models_dir).resolve() / model["id"]
    model_files = model["files"]
    primary_file = model_files[0]

    # Determine llama-server Dockerfile based on GPU
    if gpu["vendor"] == "nvidia":
        llama_dockerfile = "Dockerfile.cuda"  # NVIDIA — use CUDA for best performance
    elif gpu["vendor"] in ("amd", "intel"):
        llama_dockerfile = "Dockerfile"  # AMD/Intel — use Vulkan
    else:
        llama_dockerfile = "Dockerfile.cpu"

    # Build llama-server command
    # Cap context window based on available RAM to avoid OOM
    # Large context eats memory — small models shouldn't use 128K+
    native_ctx = model.get("context_window", 16384)
    if model["ram_gb"] <= 4:
        ctx = min(native_ctx, 8192)
    elif model["ram_gb"] <= 12:
        ctx = min(native_ctx, 32768)
    else:
        ctx = min(native_ctx, 65536)
    threads = model.get("recommended_threads", 4)
    batch = model.get("recommended_batch_size", 512)
    parallel = 2 if model["ram_gb"] > 10 else 1
    gpu_layers = "-1" if gpu["vendor"] != "none" else "0"

    llama_cmd_parts = [
        "./build/bin/llama-server",
        "--host 0.0.0.0",
        "--port 8080",
        "--jinja",
        f"-m /models/{primary_file}",
        f"-c {ctx}",
        f"-ngl {gpu_layers}",
        f"--parallel {parallel}",
        f"--threads {threads}",
        f"--batch-size {batch}",
        f"--ubatch-size {min(batch, 512)}",
        "--metrics",
    ]

    # Enable thinking/reasoning if model supports it
    if model.get("supports_thinking"):
        llama_cmd_parts.append("--reasoning-format deepseek")

    # Enable flash attention if GPU is available
    if gpu["vendor"] != "none":
        llama_cmd_parts.append("--flash-attn on")

    # Enable vision if model has mmproj
    mmproj_files = [f for f in model_files if "mmproj" in f.lower()]
    if mmproj_files:
        llama_cmd_parts.append(f"--mmproj /models/{mmproj_files[0]}")

    llama_command = "\n      ".join(llama_cmd_parts)

    # Memory limits
    mem_limit = f"{int(model['ram_gb'] + 4)}G"
    mem_reserve = f"{int(model['ram_gb'])}G"

    # GPU device mounts (non-deploy config like devices, group_add)
    gpu_devices = ""
    gpu_env = ""
    if gpu["vendor"] in ("amd", "intel"):
        gpu_devices = """    devices:
      - /dev/dri:/dev/dri
    group_add:
      - video"""
        gpu_env = """      - VULKAN_DEVICE=0
      - GGML_VULKAN_DEVICE=0"""

    # Build compose
    services = {}

    # LLM Server — deploy block differs for NVIDIA (needs GPU reservation)
    if gpu["vendor"] == "nvidia":
        deploy_block = f"""    deploy:
      resources:
        limits:
          memory: {mem_limit}
        reservations:
          memory: {mem_reserve}
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]"""
    else:
        deploy_block = f"""    deploy:
      resources:
        limits:
          memory: {mem_limit}
        reservations:
          memory: {mem_reserve}"""

    llama_service = f"""  llm-server:
    build:
      context: ./infrastructure/llama-server
      dockerfile: {llama_dockerfile}
    image: learningtool-llm:latest
    container_name: learningtool-llm
    volumes:
      - {model_dir}:/models:ro
      - ./infrastructure/llama-server/entrypoint.sh:/usr/local/bin/entrypoint.sh:ro
    environment:
      - CONTEXT_SIZE={ctx}
      - BATCH_SIZE={batch}
      - N_GPU_LAYERS={gpu_layers}
      - PARALLEL_REQUESTS={parallel}
      - THREADS={threads}
{gpu_env}
{gpu_devices}
{deploy_block}
    shm_size: 4gb
    command: >
      {llama_command}
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 120s"""

    # Orchestrator
    orchestrator_env = "      - LLAMA_URL=http://llm-server:8080"
    if enable_search:
        orchestrator_env += "\n      - SEARXNG_URL=http://searxng:8080"
    else:
        orchestrator_env += "\n      - SEARXNG_URL="

    if enable_search:
        orchestrator_deps = """    depends_on:
      llm-server:
        condition: service_healthy
      searxng:
        condition: service_healthy"""
    else:
        orchestrator_deps = """    depends_on:
      llm-server:
        condition: service_healthy"""

    orchestrator_service = f"""  orchestrator:
    build:
      context: ./infrastructure/orchestrator
    image: learningtool-orchestrator:latest
    container_name: learningtool-orchestrator
    environment:
{orchestrator_env}
      - MAX_TOOL_ROUNDS=8
      - REQUEST_TIMEOUT=300
{orchestrator_deps}
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8081/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s"""

    # Learning Tool
    learningtool_service = """  learningtool:
    build:
      context: .
      dockerfile: Dockerfile
    image: learningtool-app:latest
    container_name: learningtool-app
    ports:
      - "8100:8100"
    volumes:
      - ./learning_sessions:/app/learning_sessions
      - ./settings:/app/settings
    environment:
      - LLM_URL=http://orchestrator:8081/v1/chat/completions
    depends_on:
      orchestrator:
        condition: service_healthy
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8100"]
      interval: 30s
      timeout: 5s
      retries: 3"""

    # SearXNG + Redis (optional)
    search_services = ""
    if enable_search:
        search_services = """
  redis:
    image: redis:7-alpine
    container_name: learningtool-redis
    command: redis-server --save 30 1 --loglevel warning
    volumes:
      - redis-data:/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 3

  searxng:
    image: searxng/searxng:latest
    container_name: learningtool-searxng
    volumes:
      - ./infrastructure/searxng:/etc/searxng:rw
    environment:
      - SEARXNG_BASE_URL=http://searxng:8080/
    depends_on:
      redis:
        condition: service_healthy
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "wget", "--spider", "-q", "http://localhost:8080/healthz"]
      interval: 30s
      timeout: 10s
      retries: 3"""

    volumes = ""
    if enable_search:
        volumes = """
volumes:
  redis-data:
    driver: local"""

    compose = f"""# Generated by LearningTool setup.py
# Model: {model['name']}
# GPU: {gpu['name']}

services:
{llama_service}

{orchestrator_service}

{learningtool_service}
{search_services}

networks:
  default:
    name: learningtool
    driver: bridge
{volumes}
"""

    return compose


# ---------------------------------------------------------------------------
# Interactive setup
# ---------------------------------------------------------------------------

def print_banner():
    print()
    print("=" * 60)
    print("  LearningTool Setup")
    print("  Build a connected graph of understanding with AI")
    print("=" * 60)
    print()


def print_hardware(ram_gb, gpu, disk_gb):
    print("Hardware Detected:")
    print(f"  RAM:  {ram_gb} GB" if ram_gb else "  RAM:  Unknown")
    print(f"  GPU:  {gpu['name']}", end="")
    if gpu["vram_gb"]:
        print(f" ({gpu['vram_gb']} GB VRAM)", end="")
    if check_unified_memory(ram_gb, gpu):
        print(" [unified memory — GPU shares system RAM]", end="")
    print()
    print(f"  Disk: {disk_gb} GB free" if disk_gb else "  Disk: Unknown")
    print(f"  OS:   {platform.system()} {platform.machine()}")
    print()


def interactive_setup():
    print_banner()

    # Check Docker
    docker_ok, compose_ok = check_docker()
    if not docker_ok:
        print("Docker is not installed or not in PATH.")
        print("Install Docker: https://docs.docker.com/get-docker/")
        sys.exit(1)
    if not compose_ok:
        print("Docker Compose is not available.")
        print("Install it: https://docs.docker.com/compose/install/")
        sys.exit(1)
    print("Docker: OK")
    print()

    # Detect hardware
    ram_gb = detect_ram_gb()
    gpu = detect_gpu()
    disk_gb = detect_disk_free_gb(".")
    print_hardware(ram_gb, gpu, disk_gb)

    # Load and filter models
    models = load_models()
    filtered = filter_models(models, ram_gb or 0, disk_gb or 0, gpu)

    print("Available Models:")
    print()

    recommended = None
    for i, (m, status) in enumerate(filtered):
        tier_label = f"[{m['tier'].upper()}]"
        features = []
        if m.get("supports_vision"):
            features.append("vision")
        if m.get("supports_thinking"):
            features.append("thinking")
        if m.get("supports_tools"):
            features.append("tools")
        feat_str = f" ({', '.join(features)})" if features else ""

        if status == "ok":
            marker = "  OK "
            if recommended is None:
                recommended = i
        elif status == "tight":
            marker = " ~   "
            if recommended is None:
                recommended = i
        elif status == "no_ram":
            marker = "  X  "
        elif status == "no_disk":
            marker = "  X  "
        else:
            marker = "  ?  "

        reason = ""
        if status == "no_ram":
            reason = f" -- needs {m['ram_gb']}GB RAM"
        elif status == "no_disk":
            reason = f" -- needs {m['disk_gb']}GB disk"
        elif status == "tight":
            reason = " -- tight fit"

        no_tools_warn = ""
        if not m.get("supports_tools"):
            no_tools_warn = " [no web search]"

        print(f"  {marker} [{i+1}] {m['name']} {tier_label}{no_tools_warn}")
        print(f"         {m['description']}{feat_str}")
        print(f"         RAM: {m['ram_gb']}GB | Disk: {m['disk_gb']}GB | Context: {m['context_window']//1024}K{reason}")
        print()

    # Find best recommended model (largest that fits)
    best_ok = None
    for i, (m, status) in enumerate(filtered):
        if status in ("ok", "tight"):
            best_ok = i

    if best_ok is not None:
        recommended = best_ok

    if recommended is None:
        print("No models fit your hardware. You can still use LearningTool with")
        print("an external LLM provider (Ollama, OpenAI API, etc.).")
        print("Run: pip install -r requirements.txt && python app.py")
        sys.exit(0)

    # Ask user to choose
    default = recommended + 1
    while True:
        choice = input(f"Select a model [{default}]: ").strip()
        if not choice:
            choice = str(default)
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(filtered):
                model, status = filtered[idx]
                if status in ("no_ram", "no_disk"):
                    print(f"  Warning: {model['name']} may not fit on your system.")
                    confirm = input("  Continue anyway? [y/N]: ").strip().lower()
                    if confirm != "y":
                        continue
                if not model.get("supports_tools"):
                    print()
                    print(f"  Note: {model['name']} does not support tool calling.")
                    print(f"  Web search will NOT work with this model — the model")
                    print(f"  cannot call the search tools. Direct questions will")
                    print(f"  still work fine.")
                    print()
                    print(f"  For web search, choose a model with tool support (4B+).")
                    confirm = input("  Continue with this model? [y/N]: ").strip().lower()
                    if confirm != "y":
                        continue
                break
            else:
                print(f"  Please enter a number between 1 and {len(filtered)}")
        except ValueError:
            print(f"  Please enter a number between 1 and {len(filtered)}")

    print()

    # Ask about web search
    enable_search = True
    search_choice = input("Enable web search (requires ~500MB extra for SearXNG)? [Y/n]: ").strip().lower()
    if search_choice == "n":
        enable_search = False
    print()

    # Download model
    models_dir = Path("./models")
    print(f"Downloading {model['name']}...")
    print()
    model_dir = download_model(model, models_dir)
    print()
    print(f"Model downloaded to: {model_dir}")
    print()

    # Generate docker-compose.yml
    compose = generate_compose(model, gpu, models_dir, enable_search)
    compose_path = Path("docker-compose.yml")
    if compose_path.exists():
        backup = compose_path.with_suffix(".yml.bak")
        shutil.copy2(compose_path, backup)
        print(f"Backed up existing docker-compose.yml to {backup}")

    compose_path.write_text(compose)
    print(f"Generated: docker-compose.yml")
    print()

    # Summary
    print("=" * 60)
    print("  Setup Complete!")
    print("=" * 60)
    print()
    print(f"  Model:      {model['name']}")
    print(f"  GPU:        {gpu['name']}")
    print(f"  Web Search: {'Enabled' if enable_search else 'Disabled'}")
    print()
    print("  To start:    ./start.sh")
    print("  To stop:     ./stop.sh")
    print("  To restart:  ./restart.sh")
    print()
    print(f"  Then open: http://localhost:8100")
    print()
    print("  First start will build containers (5-10 min) and load the model.")
    print("  Subsequent starts are much faster.")
    print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    import argparse
    parser = argparse.ArgumentParser(description="LearningTool Setup")
    parser.add_argument("--list", action="store_true", help="List available models")
    parser.add_argument("--model", type=str, help="Model ID for non-interactive setup")
    parser.add_argument("--no-search", action="store_true", help="Disable web search")
    parser.add_argument("--models-dir", type=str, default="./models", help="Directory to store models")
    args = parser.parse_args()

    if args.list:
        models = load_models()
        print(f"{'ID':<25} {'Name':<35} {'Tier':<8} {'RAM':<6} {'Disk':<6}")
        print("-" * 80)
        for m in models:
            print(f"{m['id']:<25} {m['name']:<35} {m['tier']:<8} {m['ram_gb']:<6} {m['disk_gb']:<6}")
        return

    if args.model:
        models = load_models()
        model = next((m for m in models if m["id"] == args.model), None)
        if not model:
            print(f"Model '{args.model}' not found. Use --list to see available models.")
            sys.exit(1)
        gpu = detect_gpu()
        print(f"Downloading {model['name']}...")
        download_model(model, args.models_dir)
        compose = generate_compose(model, gpu, args.models_dir, not args.no_search)
        Path("docker-compose.yml").write_text(compose)
        print(f"Generated docker-compose.yml for {model['name']}")
        print("Run: docker compose up --build")
        return

    interactive_setup()


if __name__ == "__main__":
    main()
