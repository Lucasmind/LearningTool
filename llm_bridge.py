"""
Async LLM integration via OpenAI-compatible API.
Supports both non-streaming (submit) and streaming (stream) modes.
"""

import asyncio
import json
import re
from urllib.request import Request, urlopen
from urllib.error import URLError


# Default LLM endpoint (chimera AI server)
DEFAULT_LLM_URL = "http://192.168.1.221:8080/v1/chat/completions"
DEFAULT_LLM_MODEL = ""


def _strip_thinking(text: str) -> str:
    """Strip LLM thinking/reasoning tokens from the response.

    Handles multiple formats:
      - <think>...</think> blocks
      - <|start|>...<|channel|>final<|message|> token sequences
      - Bare "analysis" prefix (when server strips token delimiters but leaves content)
    """
    # Remove <think>...</think> blocks
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)

    # Remove everything up to the final channel marker (full token format)
    if '<|channel|>final<|message|>' in text:
        text = re.sub(
            r'.*<\|channel\|>final<\|message\|>',
            '', text, flags=re.DOTALL
        )

    # Clean up any remaining special tokens
    text = re.sub(r'<\|[^|]*\|>', '', text)

    # Handle bare "analysis" prefix — server stripped token delimiters but
    # left the thinking content. Cut everything before the first markdown header.
    if re.match(r'\s*analysis', text, re.IGNORECASE):
        header_match = re.search(r'^#{1,6}\s', text, re.MULTILINE)
        if header_match:
            text = text[header_match.start():]

    return text.strip()


class LocalLLMQueue:
    """Calls an LLM server via its OpenAI-compatible API."""

    def __init__(self, url: str = DEFAULT_LLM_URL, model: str = DEFAULT_LLM_MODEL):
        self._url = url
        self._model = model

    async def submit(self, prompt: str, timeout: int = 300) -> dict:
        """Send prompt and return complete response (non-streaming)."""
        return await asyncio.get_event_loop().run_in_executor(
            None, self._call_llm, prompt, timeout
        )

    async def stream(self, prompt: str, timeout: int = 300):
        """Async generator yielding (event_type, data) tuples.

        Events:
          ("thinking", "")       — model is in reasoning phase
          ("token", text_chunk)  — content token(s) to display
          ("done", full_text)    — stream complete, full content text
          ("error", message)     — error occurred
        """
        queue = asyncio.Queue()
        loop = asyncio.get_event_loop()

        def _run():
            try:
                for event in self._stream_llm(prompt, timeout):
                    loop.call_soon_threadsafe(queue.put_nowait, event)
            except Exception as e:
                loop.call_soon_threadsafe(queue.put_nowait, ("error", str(e)))
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, None)

        loop.run_in_executor(None, _run)

        while True:
            event = await queue.get()
            if event is None:
                break
            yield event

    def _call_llm(self, prompt: str, timeout: int) -> dict:
        """Synchronous non-streaming call."""
        payload = json.dumps({
            "model": self._model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 4096,
            "temperature": 0.7,
        }).encode("utf-8")

        req = Request(
            self._url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                text = data["choices"][0]["message"]["content"]
                text = _strip_thinking(text)
                return {"text": text, "html": ""}
        except URLError as e:
            raise RuntimeError(
                f"Cannot reach LLM at {self._url}. "
                f"Is the server running? Error: {e}"
            )
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            raise RuntimeError(f"Unexpected LLM response format: {e}")

    def _stream_llm(self, prompt: str, timeout: int):
        """Synchronous generator yielding (event_type, data) from streaming LLM.

        Handles both true SSE streaming and servers that return a regular
        JSON response when stream=True is not supported.
        """
        payload = json.dumps({
            "model": self._model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 4096,
            "temperature": 0.7,
            "stream": True,
        }).encode("utf-8")

        req = Request(
            self._url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urlopen(req, timeout=timeout) as resp:
                content_type = resp.headers.get("Content-Type", "")

                # Server doesn't support streaming — fall back to reading full response
                if "text/event-stream" not in content_type:
                    data = json.loads(resp.read().decode("utf-8"))
                    text = data["choices"][0]["message"]["content"]
                    clean = _strip_thinking(text)
                    if _has_thinking(text):
                        yield ("thinking", "")
                    if clean:
                        yield ("token", clean)
                    yield ("done", clean)
                    return

                # True SSE streaming
                raw_buffer = ""
                content_buffer = ""
                phase = "detecting"  # detecting | thinking | content

                while True:
                    raw_line = resp.readline()
                    if not raw_line:
                        break
                    line = raw_line.decode("utf-8").strip()
                    if not line.startswith("data: "):
                        continue
                    data_str = line[6:]
                    if data_str.strip() == "[DONE]":
                        break

                    try:
                        chunk = json.loads(data_str)
                        token = chunk["choices"][0]["delta"].get("content", "")
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue
                    if not token:
                        continue

                    raw_buffer += token

                    if phase == "detecting":
                        stripped = raw_buffer.lstrip()
                        if len(stripped) < 15:
                            continue
                        if _has_thinking(stripped):
                            phase = "thinking"
                            yield ("thinking", "")
                        else:
                            phase = "content"
                            content_buffer = raw_buffer
                            yield ("token", content_buffer)

                    elif phase == "thinking":
                        # Check for content transition
                        match = re.search(r'^#{1,6}\s', raw_buffer, re.MULTILINE)
                        has_final = '<|channel|>final<|message|>' in raw_buffer
                        if match or has_final:
                            phase = "content"
                            content_buffer = _strip_thinking(raw_buffer)
                            yield ("token", content_buffer)

                    elif phase == "content":
                        content_buffer += token
                        yield ("token", token)

                # Edge cases: never left detecting or thinking phase
                if phase == "detecting" and raw_buffer:
                    content_buffer = _strip_thinking(raw_buffer)
                    if content_buffer:
                        yield ("token", content_buffer)
                elif phase == "thinking":
                    content_buffer = _strip_thinking(raw_buffer)
                    if content_buffer:
                        yield ("token", content_buffer)

                # Always apply _strip_thinking as final safety net
                content_buffer = _strip_thinking(content_buffer) if content_buffer else ""
                yield ("done", content_buffer)

        except URLError as e:
            raise RuntimeError(
                f"Cannot reach LLM at {self._url}. "
                f"Is the server running? Error: {e}"
            )


def _has_thinking(text: str) -> bool:
    """Detect if text contains thinking/reasoning content."""
    lower = text.lstrip().lower()
    return (lower.startswith("analysis") or
            "<|channel|>analysis" in lower or
            "<think>" in lower)
