from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

import requests
from langchain_core.callbacks.base import BaseCallbackHandler
from langchain_core.outputs import LLMResult


logger = logging.getLogger(__name__)


class ParseableCallbackHandler(BaseCallbackHandler):
    def __init__(
        self,
        parseable_url: str,
        dataset: str,
        username: str,
        password: str,
        service_name: str,
    ) -> None:
        self.parseable_url = parseable_url.rstrip("/")
        self.dataset = dataset
        self.auth = (username, password)
        self.service_name = service_name
        self.run_id = str(uuid.uuid4())
        self.enabled = all([parseable_url, dataset, username, password])

    def _log(self, entry: dict[str, Any]) -> None:
        if not self.enabled:
            return

        payload = {
            **entry,
            "run_id": self.run_id,
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "service": self.service_name,
        }

        try:
            response = requests.post(
                f"{self.parseable_url}/api/v1/ingest",
                json=[payload],
                auth=self.auth,
                headers={"X-P-Stream": self.dataset},
                timeout=5,
            )
            response.raise_for_status()
        except Exception as exc:
            logger.warning("Parseable logging failed: %s", exc)

    def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        **kwargs: Any,
    ) -> None:
        model_name = serialized.get("name") or serialized.get("id") or "unknown"
        self._log(
            {
                "event": "llm_start",
                "model": model_name,
                "prompt_preview": prompts[0][:500] if prompts else None,
            }
        )

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        usage: dict[str, Any] = {}
        if response.llm_output:
            token_usage = response.llm_output.get("token_usage", {})
            usage = {
                "prompt_tokens": token_usage.get("prompt_tokens"),
                "completion_tokens": token_usage.get("completion_tokens"),
                "total_tokens": token_usage.get("total_tokens"),
            }

        self._log(
            {
                "event": "llm_end",
                "generations": len(response.generations),
                **usage,
            }
        )

    def on_llm_error(self, error: BaseException, **kwargs: Any) -> None:
        self._log(
            {
                "event": "llm_error",
                "error": str(error),
                "error_type": type(error).__name__,
            }
        )

    def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        **kwargs: Any,
    ) -> None:
        tool_name = serialized.get("name") or serialized.get("id") or "unknown"
        self._log(
            {
                "event": "tool_start",
                "tool_name": tool_name,
                "input": input_str[:1000],
            }
        )

    def on_tool_end(self, output: Any, **kwargs: Any) -> None:
        self._log(
            {
                "event": "tool_end",
                "output": str(output)[:2000],
            }
        )

    def on_tool_error(self, error: BaseException, **kwargs: Any) -> None:
        self._log(
            {
                "event": "tool_error",
                "error": str(error),
                "error_type": type(error).__name__,
            }
        )
