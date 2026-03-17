"""
Settings manager for Learning Tool.
Handles persistent provider configuration with file-based JSON storage.
"""

import json
import re
from pathlib import Path


class SettingsManager:
    """Manages LLM provider settings with file-based persistence."""

    def __init__(self, settings_dir: Path, cli_url: str = "", cli_model: str = ""):
        self._dir = settings_dir
        self._file = settings_dir / "providers.json"
        self._data = None
        self._dir.mkdir(parents=True, exist_ok=True)

        if self._file.exists():
            self._load()
            if cli_url or cli_model:
                print("Note: Using saved provider settings. "
                      "CLI args --llm-url/--llm-model are ignored when settings file exists.")
        else:
            self._seed(cli_url, cli_model)

    def _seed(self, cli_url: str, cli_model: str):
        """Create initial settings from CLI arguments."""
        provider_id = "local-llm"
        self._data = {
            "default_provider_id": provider_id,
            "fallback_provider_id": None,
            "providers": {
                provider_id: {
                    "id": provider_id,
                    "alias": "Local LLM",
                    "type": "openai-compatible",
                    "url": cli_url or "http://localhost:11434/v1/chat/completions",
                    "model": cli_model or "",
                    "api_key": "",
                    "enabled": True,
                    "max_tokens": 4096,
                    "temperature": 0.7,
                    "timeout": 300,
                }
            },
        }
        self._save()
        print("Created initial provider settings from CLI arguments.")

    def _load(self):
        with open(self._file, "r") as f:
            self._data = json.load(f)

    def _save(self):
        with open(self._file, "w") as f:
            json.dump(self._data, f, indent=2)

    @staticmethod
    def _mask_key(key: str) -> str:
        if not key or len(key) <= 8:
            return key
        return key[:3] + "..." + key[-4:]

    @staticmethod
    def _slugify(text: str) -> str:
        slug = re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')
        return slug or "provider"

    def _masked_provider(self, prov: dict) -> dict:
        out = dict(prov)
        out["api_key"] = self._mask_key(out.get("api_key", ""))
        return out

    def get_all_providers(self) -> list[dict]:
        return [self._masked_provider(p) for p in self._data["providers"].values()]

    def get_provider(self, provider_id: str) -> dict | None:
        prov = self._data["providers"].get(provider_id)
        return self._masked_provider(prov) if prov else None

    def get_provider_raw(self, provider_id: str) -> dict | None:
        return self._data["providers"].get(provider_id)

    def get_provider_list(self) -> list[dict]:
        """Lightweight list for dropdown: id, alias, type, enabled."""
        return [
            {"id": p["id"], "alias": p["alias"], "type": p["type"], "enabled": p["enabled"]}
            for p in self._data["providers"].values()
        ]

    def add_provider(self, config: dict) -> dict:
        slug = self._slugify(config.get("alias", "provider"))
        # Ensure unique ID
        provider_id = slug
        counter = 2
        while provider_id in self._data["providers"]:
            provider_id = f"{slug}-{counter}"
            counter += 1

        provider = {
            "id": provider_id,
            "alias": config.get("alias", "New Provider"),
            "type": config.get("type", "openai-compatible"),
            "url": config.get("url", ""),
            "model": config.get("model", ""),
            "api_key": config.get("api_key", ""),
            "enabled": config.get("enabled", True),
            "max_tokens": config.get("max_tokens", 4096),
            "temperature": config.get("temperature", 0.7),
            "timeout": config.get("timeout", 300),
        }
        self._data["providers"][provider_id] = provider
        self._save()
        return self._masked_provider(provider)

    def update_provider(self, provider_id: str, updates: dict) -> dict | None:
        prov = self._data["providers"].get(provider_id)
        if not prov:
            return None

        for key, val in updates.items():
            if key == "id":
                continue  # Don't allow ID changes
            if key == "api_key":
                # If the value looks masked, keep the existing key
                if val and "..." in val and len(val) <= 10:
                    continue
            prov[key] = val

        self._save()
        return self._masked_provider(prov)

    def delete_provider(self, provider_id: str) -> bool:
        if provider_id not in self._data["providers"]:
            return False
        # Prevent deleting the last provider
        if len(self._data["providers"]) <= 1:
            return False

        del self._data["providers"][provider_id]

        # Clear default/fallback if they referenced this provider
        if self._data["default_provider_id"] == provider_id:
            self._data["default_provider_id"] = next(iter(self._data["providers"]))
        if self._data["fallback_provider_id"] == provider_id:
            self._data["fallback_provider_id"] = None

        self._save()
        return True

    def get_default_id(self) -> str:
        return self._data["default_provider_id"]

    def get_fallback_id(self) -> str | None:
        return self._data["fallback_provider_id"]

    def set_default(self, provider_id: str) -> bool:
        if provider_id not in self._data["providers"]:
            return False
        self._data["default_provider_id"] = provider_id
        self._save()
        return True

    def set_fallback(self, provider_id: str | None) -> bool:
        if provider_id is not None and provider_id not in self._data["providers"]:
            return False
        self._data["fallback_provider_id"] = provider_id
        self._save()
        return True
