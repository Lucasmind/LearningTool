"""
Claude Code CLI provider for Learning Tool.
Uses the claude CLI binary to get LLM responses via an existing Claude Code subscription.
"""

import asyncio
import json
import shutil


class ClaudeCLIProvider:
    """Calls Claude via the claude CLI binary (non-streaming, subprocess-based).

    Uses asyncio.create_subprocess_exec (not shell) to safely invoke the claude
    binary. Prompt text is passed via stdin pipe, not as a shell argument.
    """

    # Claude CLI accepts short model names: opus, sonnet, haiku
    MODEL_ALIASES = {
        "opus": "opus", "opus 4.6": "opus", "claude opus": "opus", "claude-opus-4-6": "opus",
        "sonnet": "sonnet", "sonnet 4.6": "sonnet", "claude sonnet": "sonnet", "claude-sonnet-4-6": "sonnet",
        "haiku": "haiku", "haiku 4.5": "haiku", "claude haiku": "haiku", "claude-haiku-4-5": "haiku",
    }

    def __init__(self, model: str = "opus", timeout: int = 120, provider_id: str = ""):
        self._model = self._normalize_model(model)
        self._timeout = timeout
        self.provider_id = provider_id

    @classmethod
    def _normalize_model(cls, model: str) -> str:
        """Normalize model name to Claude CLI short format."""
        lookup = model.strip().lower()
        if lookup in cls.MODEL_ALIASES:
            return cls.MODEL_ALIASES[lookup]
        # If it contains a known name, extract it
        for key in ("opus", "sonnet", "haiku"):
            if key in lookup:
                return key
        return model  # Pass through as-is, CLI will validate

    async def submit(self, prompt: str, timeout: int = None) -> dict:
        """Send prompt to Claude CLI and return complete response."""
        timeout = timeout or self._timeout

        if not shutil.which("claude"):
            raise RuntimeError(
                "Claude CLI not found. Install Claude Code first: "
                "https://docs.anthropic.com/en/docs/claude-code"
            )

        # Safe: create_subprocess_exec passes args as a list, no shell injection.
        # Prompt is piped via stdin, never interpolated into the command.
        cmd = [
            "claude", "-p",
            "--output-format", "json",
            "--tools", "",
            "--model", self._model,
        ]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(input=prompt.encode("utf-8")),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            raise RuntimeError(f"Claude CLI timed out after {timeout}s")
        except FileNotFoundError:
            raise RuntimeError("Claude CLI binary not found on PATH")

        if proc.returncode != 0:
            err = stderr.decode("utf-8", errors="replace").strip()
            out = stdout.decode("utf-8", errors="replace").strip()
            detail = err or out or "(no output)"
            raise RuntimeError(f"Claude CLI error (exit {proc.returncode}): {detail}")

        # Parse JSON response
        try:
            response_data = json.loads(stdout.decode("utf-8"))
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Failed to parse Claude CLI response: {e}")

        if response_data.get("type") != "result":
            raise RuntimeError(
                f"Unexpected Claude CLI response type: {response_data.get('type')}"
            )

        if response_data.get("is_error"):
            raise RuntimeError(response_data.get("result", "Unknown Claude CLI error"))

        result_text = response_data.get("result", "")
        return {"text": result_text, "html": ""}

    async def stream(self, prompt: str, timeout: int = None):
        """Async generator yielding (event_type, data) tuples.

        Claude CLI is non-streaming, so we emit thinking -> token -> done
        to stay compatible with the SSE streaming path.
        """
        yield ("thinking", "")

        try:
            result = await self.submit(prompt, timeout)
            text = result["text"]
            if text:
                yield ("token", text)
            yield ("done", text)
        except Exception as e:
            yield ("error", str(e))

    async def test(self) -> dict:
        """Test Claude CLI connectivity."""
        if not shutil.which("claude"):
            return {
                "success": False,
                "message": "Claude CLI binary not found on PATH. Install Claude Code first.",
                "response_preview": "",
            }

        try:
            result = await self.submit("Reply with exactly: OK", timeout=30)
            text = result.get("text", "").strip()
            return {
                "success": True,
                "message": f"Claude CLI responded successfully (model: {self._model})",
                "response_preview": text[:200],
            }
        except Exception as e:
            return {
                "success": False,
                "message": str(e),
                "response_preview": "",
            }
