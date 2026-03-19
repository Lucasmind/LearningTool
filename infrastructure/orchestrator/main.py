"""
LearningTool Orchestrator with Web Search

Agentic proxy that sits between clients and any OpenAI-compatible LLM backend
(llama.cpp, Ollama, vLLM, etc.), providing web search, thinking mode control,
and smart request routing.

Exposes an OpenAI-compatible /v1/chat/completions endpoint on port 8081.

Configuration via environment variables:
    LLAMA_URL          - Primary LLM backend URL (default: http://llama-server:8080)
                         Works with llama.cpp, Ollama (http://host:11434), vLLM, etc.
    LLAMA_URLS         - Comma-separated list of backend URLs for failover
    SEARXNG_URL        - SearXNG search engine URL (default: http://searxng:8080)
    MAX_TOOL_ROUNDS    - Max agentic tool-call rounds (default: 8)
    SEARCH_RESULTS_COUNT - Number of search results to return (default: 5)
    PAGE_CACHE_SIZE    - LRU cache size for fetched pages (default: 20)
    REQUEST_TIMEOUT    - HTTP request timeout in seconds (default: 300)
"""

import os
import re
import json
import logging
from collections import OrderedDict

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
import httpx
import trafilatura
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

LLAMA_URL = os.getenv("LLAMA_URL", "http://llama-server:8080")
LLAMA_URLS = [u.strip() for u in os.getenv("LLAMA_URLS", LLAMA_URL).split(",")]
SEARXNG_URL = os.getenv("SEARXNG_URL", "http://searxng:8080")
MAX_TOOL_ROUNDS = int(os.getenv("MAX_TOOL_ROUNDS", "8"))
SEARCH_RESULTS_COUNT = int(os.getenv("SEARCH_RESULTS_COUNT", "5"))
PAGE_CACHE_SIZE = int(os.getenv("PAGE_CACHE_SIZE", "20"))
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "300"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("orchestrator")

app = FastAPI(title="LearningTool Orchestrator with Web Search")

# Track whether the backend model supports tool calling.
# If the first tool attempt fails with 500, disable tools for future requests.
_tools_supported = True


# ---------------------------------------------------------------------------
# Backend discovery — find a healthy LLM backend (llama.cpp, Ollama, vLLM, etc.)
# ---------------------------------------------------------------------------


async def _check_backend_health(client: httpx.AsyncClient, url: str) -> bool:
    """Check if an LLM backend is healthy. Tries multiple endpoint patterns."""
    # llama.cpp uses /health
    for endpoint in [f"{url}/health", f"{url}/v1/models"]:
        try:
            r = await client.get(endpoint, timeout=5.0)
            if r.status_code == 200:
                return True
        except Exception:
            continue
    return False


async def get_active_backend() -> str:
    """Return the base URL for the first healthy backend."""
    async with httpx.AsyncClient() as client:
        for url in LLAMA_URLS:
            if await _check_backend_health(client, url):
                log.info("Using backend %s", url)
                return url
            log.debug("Backend %s not reachable", url)

    # Fall back to first URL even if unhealthy
    log.warning("No healthy backend found, falling back to %s", LLAMA_URLS[0])
    return LLAMA_URLS[0]

# ---------------------------------------------------------------------------
# Page cache (LRU) for browser.open / browser.find
# ---------------------------------------------------------------------------

page_cache: OrderedDict[str, dict] = OrderedDict()


def cache_put(url: str, data: dict) -> None:
    page_cache[url] = data
    page_cache.move_to_end(url)
    while len(page_cache) > PAGE_CACHE_SIZE:
        page_cache.popitem(last=False)


# ---------------------------------------------------------------------------
# Browser tool definitions (OpenAI tools format)
# ---------------------------------------------------------------------------

BROWSER_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "browser.search",
            "description": "Search the web for information. Returns a list of results with titles, URLs, and snippets.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "topn": {"type": "integer", "description": "Number of results to return", "default": 5},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser.open",
            "description": "Open a URL and read its content. Only open 1-2 pages max — prefer using search snippets when possible.",
            "parameters": {
                "type": "object",
                "properties": {
                    "id": {"type": "string", "description": "URL to open"},
                    "num_lines": {"type": "integer", "description": "Number of lines to return", "default": 120},
                    "cursor": {"type": "integer", "description": "Line offset to start from", "default": 0},
                },
                "required": ["id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser.find",
            "description": "Search for a pattern in the most recently opened page.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Text or regex to find"},
                    "cursor": {"type": "integer", "description": "Line offset to start from", "default": 0},
                },
                "required": ["pattern"],
            },
        },
    },
]

# ---------------------------------------------------------------------------
# Tool execution
# ---------------------------------------------------------------------------


async def execute_search(query: str, topn: int | str = 5) -> str:
    """Query SearXNG and return formatted results."""
    # Coerce topn to int — small models sometimes pass "5" instead of 5
    try:
        topn = int(topn)
    except (ValueError, TypeError):
        topn = SEARCH_RESULTS_COUNT
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{SEARXNG_URL}/search",
                params={"q": query, "format": "json", "pageno": 1},
                timeout=30.0,
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        log.error("SearXNG search failed: %s", e)
        return f"Search error: {e}"

    results = data.get("results", [])[:topn]
    if not results:
        return "No results found."

    formatted = []
    for i, r in enumerate(results, 1):
        title = r.get("title", "No title")
        url = r.get("url", "")
        snippet = r.get("content", "No snippet available")
        formatted.append(f"[{i}] {title}\n    URL: {url}\n    {snippet}")

    return "\n\n".join(formatted)


async def execute_open(url: str, num_lines: int | str = 120, cursor: int | str = 0) -> str:
    """Fetch a URL, extract text, cache it, and return requested lines."""
    try:
        num_lines = int(num_lines)
    except (ValueError, TypeError):
        num_lines = 60
    try:
        cursor = int(cursor)
    except (ValueError, TypeError):
        cursor = 0
    if url not in page_cache:
        try:
            async with httpx.AsyncClient(follow_redirects=True) as client:
                resp = await client.get(
                    url,
                    timeout=30.0,
                    headers={
                        "User-Agent": (
                            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                            "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
                        ),
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                        "Accept-Language": "en-US,en;q=0.5",
                    },
                )
                if resp.status_code >= 400:
                    log.warning("HTTP %d fetching %s", resp.status_code, url)
                    return (
                        f"Error: HTTP {resp.status_code} when fetching {url}. "
                        f"The site may block automated access. "
                        f"Try using the search snippets instead of opening the page directly."
                    )
                html = resp.text
        except Exception as e:
            log.error("Failed to fetch %s: %s", url, e)
            return f"Error fetching URL: {e}. Try using the search snippets instead."

        # Extract readable text
        text = trafilatura.extract(html) or ""
        if not text:
            soup = BeautifulSoup(html, "html.parser")
            text = soup.get_text(separator="\n", strip=True)

        # Get title
        title = ""
        soup = BeautifulSoup(html, "html.parser")
        if soup.title and soup.title.string:
            title = soup.title.string.strip()

        lines = text.split("\n")
        cache_put(url, {"text": text, "title": title, "lines": lines})

    cached = page_cache[url]
    lines = cached["lines"]
    total = len(lines)
    selected = lines[cursor : cursor + num_lines]
    end_line = min(cursor + num_lines, total)

    header = (
        f"Title: {cached['title']}\n"
        f"URL: {url}\n"
        f"Lines {cursor + 1}-{end_line} of {total}\n"
        f"---\n"
    )
    return header + "\n".join(selected)


async def execute_find(pattern: str, cursor: int = 0) -> str:
    """Search within the most recently opened page."""
    if not page_cache:
        return "Error: No page is currently open. Use browser.open first."

    # Most recently cached page
    last_url = next(reversed(page_cache))
    cached = page_cache[last_url]
    lines = cached["lines"]

    matches = []
    for i, line in enumerate(lines):
        if i < cursor:
            continue
        try:
            if re.search(pattern, line, re.IGNORECASE):
                matches.append(f"Line {i + 1}: {line}")
        except re.error:
            # Treat as literal string if regex is invalid
            if pattern.lower() in line.lower():
                matches.append(f"Line {i + 1}: {line}")
        if len(matches) >= 10:
            break

    if matches:
        return f"Found {len(matches)} matches in {last_url}:\n" + "\n".join(matches)
    return f"No matches for '{pattern}' in {last_url}"


TOOL_DISPATCH = {
    "browser.search": lambda args: execute_search(
        args.get("query", ""), args.get("topn", SEARCH_RESULTS_COUNT)
    ),
    "browser.open": lambda args: execute_open(
        args.get("id") or args.get("url", ""), min(args.get("num_lines", 60), 60), args.get("cursor", 0)
    ),
    "browser.find": lambda args: execute_find(
        args.get("pattern", ""), args.get("cursor", 0)
    ),
}

# ---------------------------------------------------------------------------
# Search intent classification (Option C: keyword heuristic + ambiguous)
# ---------------------------------------------------------------------------

# Strong signals that the user wants a web search
_SEARCH_KEYWORDS = re.compile(
    r'\b('
    r'search\s+(the\s+)?(web|internet|online|for)|'
    r'look\s+up|look\s+online|'
    r'find\s+(me\s+)?(online|on\s+the\s+web|on\s+the\s+internet)|'
    r'google|browse|'
    r'latest\s+news|recent\s+news|current\s+events|'
    r'what\s+happened\s+(today|yesterday|this\s+week|recently)|'
    r'news\s+about|updates?\s+on'
    r')\b',
    re.IGNORECASE,
)

# Signals that suggest the user might need current/real-time info (ambiguous)
_MAYBE_SEARCH_KEYWORDS = re.compile(
    r'\b('
    r'latest|newest|recent|current|today|yesterday|this\s+week|this\s+month|'
    r'(in|as\s+of)\s+202[4-9]|'
    r'right\s+now|at\s+the\s+moment|'
    r'price\s+of|stock\s+price|weather|score|'
    r'who\s+won|who\s+is\s+winning|'
    r'breaking|just\s+(announced|released|launched)|'
    r'http[s]?://|www\.'
    r')\b',
    re.IGNORECASE,
)

# Strong signals that no search is needed
_NO_SEARCH_KEYWORDS = re.compile(
    r'\b('
    r'explain|define|what\s+is\s+(a|an|the)\b|how\s+does\s+.+\s+work|'
    r'write\s+(me\s+)?(a|an|some|the)|'
    r'summarize|translate|rewrite|paraphrase|'
    r'help\s+me\s+(with|write|understand|code|debug)|'
    r'code|function|class|implement|refactor|'
    r'solve|calculate|convert|compare'
    r')\b',
    re.IGNORECASE,
)


# Detect lightweight/utility requests (title generation, tag generation, etc.)
# that don't benefit from thinking mode
_UTILITY_REQUEST_PATTERNS = re.compile(
    r'('
    r'###\s*Task:\s*\n.*?(title|tags?|keywords?)|'
    r'generate\s+a\s+(concise\s+)?(title|summary)|'
    r'generate\s+a\s+short\s+title|'
    r'create\s+a\s+(short\s+)?title|'
    r'title\s+for\s+(this|the)\s+(conversation|chat|message)|'
    r'for\s+a\s+research\s+session\s+about|'
    r'summarize\s+(this|the)\s+(conversation|chat).{0,20}(title|short|brief|one.?line)|'
    r'generate\s+\d+\s+to\s+\d+\s+word|'
    r'reply\s+with\s+only\s+the\s+title|'
    r'in\s+\d+\s+words?\s+or\s+(less|fewer)|'
    r'max\s+\d+\s+words?.{0,20}(title|no\s+quotes)|'
    r'generate\s+a?\s*tags?\s+for|'
    r'keywords?\s+for\s+(this|the)\s+(conversation|chat)|'
    r'###\s*Chat\s*History:'
    r')',
    re.IGNORECASE | re.DOTALL,
)


def is_utility_request(messages: list) -> bool:
    """
    Detect if this is a utility/housekeeping request from the UI
    (e.g., title generation, tag generation) that should skip thinking.
    """
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, str) and _UTILITY_REQUEST_PATTERNS.search(content):
            return True
    return False


def has_image_content(messages: list) -> bool:
    """
    Detect if any message contains image data (base64 or URL).
    Image requests should skip thinking for faster, cleaner responses.
    """
    for msg in messages:
        content = msg.get("content")
        if isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get("type") == "image_url":
                    return True
    return False


def classify_search_intent(messages: list) -> str:
    """
    Classify whether the user's message needs web search.
    Returns: 'search', 'no_search', or 'ambiguous'
    """
    # Look at the last user message
    user_text = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            content = msg.get("content", "")
            if isinstance(content, str):
                user_text = content
            elif isinstance(content, list):
                # Multimodal message — extract text parts
                user_text = " ".join(
                    p.get("text", "") for p in content
                    if isinstance(p, dict) and p.get("type") == "text"
                )
            break

    if not user_text:
        return "no_search"

    # Check for explicit search request
    if _SEARCH_KEYWORDS.search(user_text):
        return "search"

    # Check for strong no-search signals
    if _NO_SEARCH_KEYWORDS.search(user_text):
        return "no_search"

    # Check for ambiguous signals (might need current info)
    if _MAYBE_SEARCH_KEYWORDS.search(user_text):
        return "ambiguous"

    # Default: no search needed
    return "no_search"


# ---------------------------------------------------------------------------
# Agentic loop
# ---------------------------------------------------------------------------


SEARCH_SYSTEM_PROMPT = (
    "You have access to browser tools for searching the web. "
    "When you search, you will get results with titles, URLs, and snippet text. "
    "IMPORTANT: Prefer using search snippets to compose your answer. "
    "Only use browser.open on 1-2 pages maximum if the snippets are truly insufficient. "
    "Many websites block automated page access (returning HTTP 403 errors). "
    "If browser.open fails, DO NOT retry other pages — use the search snippets instead. "
    "When providing your final answer, write a helpful, complete response for the user "
    "including relevant URLs as references."
)


async def agentic_chat(request_body: dict) -> dict:
    """
    Forward request to llama-server with browser tools.
    Execute tool calls in a loop until the model returns a final response.
    Automatically detects which backend is available.
    """
    backend_url = await get_active_backend()
    log.info("Agentic chat using backend %s", backend_url)

    messages = list(request_body.get("messages", []))
    original_max_tokens = request_body.get("max_tokens")

    # Inject search guidance system message if not already present
    if messages and messages[0].get("role") == "system":
        messages[0] = {
            **messages[0],
            "content": messages[0]["content"] + "\n\n" + SEARCH_SYSTEM_PROMPT,
        }
    else:
        messages.insert(0, {"role": "system", "content": SEARCH_SYSTEM_PROMPT})

    for round_num in range(MAX_TOOL_ROUNDS):
        # Build payload with tools
        payload = {
            **request_body,
            "messages": messages,
            "tools": BROWSER_TOOLS,
            "stream": False,
        }
        # Allow more tokens for intermediate rounds
        if original_max_tokens:
            payload["max_tokens"] = max(original_max_tokens, 2048)

        log.info("Tool round %d: sending %d messages to %s", round_num + 1, len(messages), backend_url)

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{backend_url}/v1/chat/completions",
                json=payload,
                timeout=REQUEST_TIMEOUT,
            )

        if resp.status_code != 200:
            global _tools_supported
            error_body = resp.text[:500]
            log.error("Backend returned %d on tool round %d: %s",
                      resp.status_code, round_num + 1, error_body)
            log.error("Payload keys: %s, message roles: %s",
                      list(payload.keys()),
                      [m.get("role") for m in messages])
            # Mark tools as unsupported so future requests skip agentic path
            if round_num == 0 and "Failed to parse" in error_body:
                _tools_supported = False
                log.warning("Model cannot handle tool calls — disabling tools for future requests")
            # Fall back to direct answer without tools
            return await _get_final_answer(request_body, messages, backend_url)

        result = resp.json()

        if not result.get("choices"):
            log.warning("No choices in response")
            return result

        choice = result["choices"][0]
        assistant_msg = choice["message"]
        tool_calls = assistant_msg.get("tool_calls")

        if not tool_calls:
            return await _cleanup_response(result, messages, request_body, backend_url)

        # Model wants to call tools
        log.info(
            "Model requested %d tool call(s): %s",
            len(tool_calls),
            [tc["function"]["name"] for tc in tool_calls],
        )

        # Append the assistant message (with tool_calls) to conversation
        messages.append(assistant_msg)

        # Execute each tool call
        for tc in tool_calls:
            fn_name = tc["function"]["name"]
            try:
                args = json.loads(tc["function"]["arguments"])
            except json.JSONDecodeError:
                args = {}

            handler = TOOL_DISPATCH.get(fn_name)
            if handler:
                log.info("Executing %s(%s)", fn_name, json.dumps(args, ensure_ascii=False)[:200])
                try:
                    tool_result = await handler(args)
                except Exception as e:
                    log.error("Tool %s failed: %s", fn_name, e)
                    tool_result = f"Error executing {fn_name}: {e}"
            else:
                tool_result = f"Unknown tool: {fn_name}"
                log.warning("Unknown tool call: %s", fn_name)

            # Truncate very long results to avoid blowing context
            if len(tool_result) > 4000:
                tool_result = tool_result[:4000] + "\n\n[... truncated]"

            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": tool_result,
            })

    # Exhausted tool rounds — explicitly tell model to produce a final answer
    log.warning("Exhausted %d tool rounds, requesting final answer", MAX_TOOL_ROUNDS)
    messages.append({
        "role": "user",
        "content": (
            "You have finished searching. Now please write your final, comprehensive "
            "response to my original question using all the information you gathered. "
            "Include relevant URLs as references. Do not attempt any more tool calls."
        ),
    })

    return await _get_final_answer(request_body, messages, backend_url)


def _strip_think_tags(text: str) -> str:
    """Strip <think>...</think> blocks from content.
    Some backends (Ollama, etc.) embed thinking in the content field
    instead of using a separate reasoning_content field."""
    return re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()


async def _cleanup_response(result: dict, messages: list,
                            request_body: dict, backend_url: str) -> dict:
    """
    Clean up a final model response: fall back to reasoning_content if
    content is empty, strip reasoning_content, and remove <think> tags
    from content (for backends that embed thinking in content).
    """
    choice = result["choices"][0]
    assistant_msg = choice["message"]
    content = assistant_msg.get("content") or ""
    reasoning = assistant_msg.get("reasoning_content") or ""

    # If content is empty but reasoning_content is present, use it as fallback
    if not content and reasoning:
        log.info("Content empty but reasoning_content present, using reasoning")
        assistant_msg["content"] = reasoning

    # Strip reasoning_content to prevent it showing in clients
    if "reasoning_content" in assistant_msg:
        del assistant_msg["reasoning_content"]

    # Strip <think> tags from content (Ollama and other backends that
    # embed thinking directly in the content field)
    if assistant_msg.get("content"):
        assistant_msg["content"] = _strip_think_tags(assistant_msg["content"])

    return result


async def _get_final_answer(request_body: dict, messages: list,
                            backend_url: str | None = None) -> dict:
    """Request a final answer from the model without tools, with cleanup."""
    url = backend_url or LLAMA_URLS[0]
    payload = {**request_body, "messages": messages, "stream": False}
    payload.pop("tools", None)

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{url}/v1/chat/completions",
            json=payload,
            timeout=REQUEST_TIMEOUT,
        )

    result = resp.json()
    if result.get("choices"):
        msg = result["choices"][0]["message"]
        content = msg.get("content") or ""
        reasoning = msg.get("reasoning_content") or ""

        # If content is empty, use reasoning_content as fallback
        if not content and reasoning:
            msg["content"] = reasoning

        # Strip reasoning_content from the response
        if "reasoning_content" in msg:
            del msg["reasoning_content"]

        # Strip <think> tags from content (Ollama and other backends)
        if msg.get("content"):
            msg["content"] = _strip_think_tags(msg["content"])

    return result


# ---------------------------------------------------------------------------
# Streaming support
# ---------------------------------------------------------------------------


async def _stream_from_backend(backend_url: str, payload: dict,
                                strip_reasoning: bool = True):
    """
    Stream SSE from any OpenAI-compatible backend (llama.cpp, Ollama, vLLM, etc.),
    optionally filtering out reasoning tokens.

    Handles two thinking formats:
    - reasoning_content deltas (llama.cpp with --reasoning-format deepseek)
    - <think>...</think> tags in content deltas (Ollama, other backends)
    """
    payload = {**payload, "stream": True}
    payload.pop("tools", None)

    # State for <think> tag stripping in streaming content
    in_think_block = False
    think_buffer = ""

    async with httpx.AsyncClient() as client:
        async with client.stream(
            "POST",
            f"{backend_url}/v1/chat/completions",
            json=payload,
            timeout=REQUEST_TIMEOUT,
        ) as resp:
            async for line in resp.aiter_lines():
                if not line or not line.startswith("data: "):
                    continue

                # Pass through [DONE]
                if line.strip() == "data: [DONE]":
                    yield line + "\n\n"
                    continue

                if not strip_reasoning:
                    yield line + "\n\n"
                    continue

                # Parse the chunk and filter reasoning
                try:
                    chunk = json.loads(line[6:])  # strip "data: "
                    choices = chunk.get("choices", [])
                    if not choices:
                        yield line + "\n\n"
                        continue

                    delta = choices[0].get("delta", {})

                    # --- Format 1: reasoning_content field (llama.cpp) ---
                    # Drop pure reasoning_content chunks
                    if "reasoning_content" in delta and "content" not in delta:
                        continue

                    # Strip reasoning_content from mixed chunks
                    if "reasoning_content" in delta:
                        del delta["reasoning_content"]

                    # Skip initial chunk where content is null (role announcement)
                    if delta.get("content") is None and "role" in delta:
                        yield line + "\n\n"
                        continue

                    # --- Format 2: <think> tags in content (Ollama, etc.) ---
                    content = delta.get("content", "")
                    if content and strip_reasoning:
                        # Check for <think> tag opening
                        if "<think>" in content:
                            in_think_block = True
                            # Keep any content before the tag
                            before = content.split("<think>")[0]
                            if before:
                                delta["content"] = before
                                yield f"data: {json.dumps(chunk)}\n\n"
                            continue
                        # Check for </think> tag closing
                        if "</think>" in content:
                            in_think_block = False
                            # Keep any content after the tag
                            after = content.split("</think>")[-1]
                            if after:
                                delta["content"] = after
                                yield f"data: {json.dumps(chunk)}\n\n"
                            continue
                        # Inside think block — suppress
                        if in_think_block:
                            continue

                    # Forward content chunks and finish chunks
                    yield f"data: {json.dumps(chunk)}\n\n"

                except (json.JSONDecodeError, KeyError, IndexError):
                    # Can't parse — forward as-is
                    yield line + "\n\n"


async def stream_direct(request_body: dict, backend_url: str,
                         skip_thinking: bool = False,
                         strip_reasoning: bool = True):
    """Stream a direct (non-search) request."""
    payload = {**request_body}
    if skip_thinking:
        payload["chat_template_kwargs"] = {"enable_thinking": False}
        strip_reasoning = False  # nothing to strip

    async for chunk in _stream_from_backend(backend_url, payload,
                                             strip_reasoning=strip_reasoning):
        yield chunk


async def stream_agentic(request_body: dict, backend_url: str,
                          strip_reasoning: bool = True):
    """
    Run tool rounds non-streaming, then stream the final answer.
    """
    messages = list(request_body.get("messages", []))
    original_max_tokens = request_body.get("max_tokens")

    # Inject search guidance system message
    if messages and messages[0].get("role") == "system":
        messages[0] = {
            **messages[0],
            "content": messages[0]["content"] + "\n\n" + SEARCH_SYSTEM_PROMPT,
        }
    else:
        messages.insert(0, {"role": "system", "content": SEARCH_SYSTEM_PROMPT})

    for round_num in range(MAX_TOOL_ROUNDS):
        payload = {
            **request_body,
            "messages": messages,
            "tools": BROWSER_TOOLS,
            "stream": False,
        }
        if original_max_tokens:
            payload["max_tokens"] = max(original_max_tokens, 2048)

        log.info("Tool round %d (streaming): sending %d messages to %s",
                 round_num + 1, len(messages), backend_url)

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{backend_url}/v1/chat/completions",
                json=payload,
                timeout=REQUEST_TIMEOUT,
            )

        if resp.status_code != 200:
            global _tools_supported
            error_body = resp.text[:500]
            log.error("Backend returned %d on tool round %d: %s",
                      resp.status_code, round_num + 1, error_body)
            log.error("Payload keys: %s, message roles: %s",
                      list(payload.keys()),
                      [m.get("role") for m in messages])
            # Mark tools as unsupported so future requests skip agentic path
            if round_num == 0 and "Failed to parse" in error_body:
                _tools_supported = False
                log.warning("Model cannot handle tool calls — disabling tools for future requests")
            # Fall back to streaming without tools instead of crashing
            final_payload = {**request_body, "messages": messages}
            async for chunk in _stream_from_backend(backend_url, final_payload,
                                                     strip_reasoning=strip_reasoning):
                yield chunk
            return

        result = resp.json()
        if not result.get("choices"):
            yield f"data: {json.dumps(result)}\n\n"
            yield "data: [DONE]\n\n"
            return

        choice = result["choices"][0]
        assistant_msg = choice["message"]
        tool_calls = assistant_msg.get("tool_calls")

        if not tool_calls:
            # No more tools — stream the final answer
            # Re-request with streaming, no tools
            final_payload = {**request_body, "messages": messages}
            async for chunk in _stream_from_backend(backend_url, final_payload,
                                                     strip_reasoning=strip_reasoning):
                yield chunk
            return

        # Execute tools
        log.info("Model requested %d tool call(s): %s",
                 len(tool_calls),
                 [tc["function"]["name"] for tc in tool_calls])
        messages.append(assistant_msg)

        for tc in tool_calls:
            fn_name = tc["function"]["name"]
            try:
                args = json.loads(tc["function"]["arguments"])
            except json.JSONDecodeError:
                args = {}

            handler = TOOL_DISPATCH.get(fn_name)
            if handler:
                log.info("Executing %s(%s)", fn_name,
                         json.dumps(args, ensure_ascii=False)[:200])
                try:
                    tool_result = await handler(args)
                except Exception as e:
                    log.error("Tool %s failed: %s", fn_name, e)
                    tool_result = f"Error executing {fn_name}: {e}"
            else:
                tool_result = f"Unknown tool: {fn_name}"

            if len(tool_result) > 4000:
                tool_result = tool_result[:4000] + "\n\n[... truncated]"

            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": tool_result,
            })

    # Exhausted tool rounds — stream final answer without tools
    log.warning("Exhausted %d tool rounds, streaming final answer", MAX_TOOL_ROUNDS)
    messages.append({
        "role": "user",
        "content": (
            "You have finished searching. Now please write your final, comprehensive "
            "response to my original question using all the information you gathered. "
            "Include relevant URLs as references. Do not attempt any more tool calls."
        ),
    })
    final_payload = {**request_body, "messages": messages}
    async for chunk in _stream_from_backend(backend_url, final_payload,
                                             strip_reasoning=True):
        yield chunk


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------


@app.get("/health")
async def health():
    """Health check — verify at least one LLM backend and SearXNG are reachable."""
    errors = []
    any_backend_healthy = False
    async with httpx.AsyncClient() as client:
        for url in LLAMA_URLS:
            if await _check_backend_health(client, url):
                any_backend_healthy = True
            else:
                errors.append(f"{url}: not reachable")

        if not any_backend_healthy:
            errors.insert(0, "No healthy LLM backend available")

        try:
            r = await client.get(f"{SEARXNG_URL}/healthz", timeout=5.0)
            if r.status_code != 200:
                errors.append(f"searxng: HTTP {r.status_code}")
        except Exception as e:
            errors.append(f"searxng: {e}")

    if not any_backend_healthy:
        return JSONResponse({"status": "unhealthy", "errors": errors}, status_code=503)
    if errors:
        return JSONResponse({"status": "degraded", "errors": errors, "note": "At least one backend is healthy"})
    return {"status": "ok"}


async def direct_chat(request_body: dict, skip_thinking: bool = False) -> dict:
    """
    Forward request directly to LLM backend WITHOUT tools (non-streaming).
    Used for non-streaming requests or as fallback.
    """
    backend_url = await get_active_backend()
    log.info("Direct chat (no search%s) using backend %s",
             ", no-think" if skip_thinking else "", backend_url)

    payload = {**request_body, "stream": False}
    payload.pop("tools", None)

    if skip_thinking:
        payload["chat_template_kwargs"] = {"enable_thinking": False}

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{backend_url}/v1/chat/completions",
            json=payload,
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()

    result = resp.json()

    # Strip reasoning_content
    if result.get("choices"):
        msg = result["choices"][0]["message"]
        if "reasoning_content" in msg:
            del msg["reasoning_content"]

    return result


@app.post("/v1/chat/completions")
@app.post("/chat/completions")
async def chat_completions(request: Request):
    """OpenAI-compatible chat completions with intelligent web search routing."""
    body = await request.json()
    was_streaming = body.get("stream", False)

    # Allow explicit opt-in/out via request parameters
    force_search = body.pop("web_search", None)
    force_no_think = body.pop("thinking", None) is False  # "thinking": false
    stream_reasoning = body.pop("stream_reasoning", False)  # send thinking tokens to client

    messages = body.get("messages", [])
    if force_search is True:
        intent = "search"
    elif force_search is False:
        intent = "no_search"
    else:
        intent = classify_search_intent(messages)

    # Detect requests that should skip thinking
    skip_thinking = force_no_think
    skip_reason = ""
    if force_no_think:
        skip_reason = "explicit thinking:false"
    elif is_utility_request(messages):
        skip_thinking = True
        skip_reason = "utility request"
    elif has_image_content(messages):
        skip_thinking = True
        skip_reason = "image request"
    log.info("Search intent: %s%s", intent,
             f" ({skip_reason}, skip thinking)" if skip_reason else "")

    # If the backend model doesn't support tool calling, downgrade search to direct
    global _tools_supported
    if intent == "search" and not _tools_supported:
        log.info("Model does not support tools — downgrading search to direct")
        intent = "no_search"

    # Get active backend
    backend_url = await get_active_backend()

    # --- STREAMING PATH ---
    if was_streaming:
        strip_reasoning = not stream_reasoning
        if skip_thinking:
            log.info("Streaming direct (no-think) via %s", backend_url)
            return StreamingResponse(
                stream_direct(body, backend_url, skip_thinking=True),
                media_type="text/event-stream",
            )
        elif intent == "no_search":
            log.info("Streaming direct (thinking%s) via %s",
                     "+reasoning" if stream_reasoning else "", backend_url)
            return StreamingResponse(
                stream_direct(body, backend_url, skip_thinking=False,
                              strip_reasoning=strip_reasoning),
                media_type="text/event-stream",
            )
        else:
            log.info("Streaming agentic search (reasoning=%s) via %s",
                     stream_reasoning, backend_url)
            return StreamingResponse(
                stream_agentic(body, backend_url,
                               strip_reasoning=strip_reasoning),
                media_type="text/event-stream",
            )

    # --- NON-STREAMING PATH ---
    if skip_thinking:
        result = await direct_chat(body, skip_thinking=True)
    elif intent == "no_search":
        result = await direct_chat(body)
    else:
        result = await agentic_chat(body)

    return JSONResponse(content=result)


@app.get("/v1/models")
@app.get("/models")
async def list_models():
    """Aggregate models list from all healthy backends."""
    all_models = []
    async with httpx.AsyncClient() as client:
        for url in LLAMA_URLS:
            try:
                resp = await client.get(f"{url}/v1/models", timeout=10.0)
                if resp.status_code == 200:
                    data = resp.json()
                    all_models.extend(data.get("data", []))
            except Exception:
                continue

    return JSONResponse(content={"object": "list", "data": all_models})


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy(path: str, request: Request):
    """Proxy all other endpoints directly to the active llama-server."""
    try:
        backend_url = await get_active_backend()
        body = await request.body()
        headers = {
            k: v for k, v in request.headers.items()
            if k.lower() not in ("host", "content-length")
        }

        async with httpx.AsyncClient() as client:
            resp = await client.request(
                method=request.method,
                url=f"{backend_url}/{path}",
                headers=headers,
                content=body,
                params=dict(request.query_params),
                timeout=REQUEST_TIMEOUT,
            )

        return JSONResponse(content=resp.json(), status_code=resp.status_code)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
