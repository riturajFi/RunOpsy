from __future__ import annotations

import logging
import time
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
        request_id: str,
    ) -> None:
        self.parseable_url = parseable_url.rstrip("/")
        self.dataset = dataset
        self.auth = (username, password)
        self.service_name = service_name
        self.request_id = request_id
        self.run_id = request_id
        self.enabled = all([parseable_url, dataset, username, password])
        self.last_model: str | None = None
        self.last_total_tokens: int | None = None
        self._llm_started_at: float | None = None

    def _log(self, entry: dict[str, Any]) -> None:
        if not self.enabled:
            return

        payload = {
            **entry,
            "run_id": self.run_id,
            "request_id": self.request_id,
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
            logger.warning(
                "Parseable logging failed.",
                extra={
                    "step": "parseable_ingest_failed",
                    "request_id": self.request_id,
                    "error": str(exc),
                },
            )

    def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        **kwargs: Any,
    ) -> None:
        model_name = serialized.get("name") or serialized.get("id") or "unknown"
        self.last_model = model_name
        self._llm_started_at = time.monotonic()
        self._log(
            {
                "event": "llm_start",
                "step": "llm_analysis_started",
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
            self.last_total_tokens = token_usage.get("total_tokens")

        duration_ms = None
        if self._llm_started_at is not None:
            duration_ms = round((time.monotonic() - self._llm_started_at) * 1000, 2)
        self._log(
            {
                "event": "llm_end",
                "step": "llm_analysis_completed",
                "model": self.last_model,
                "generations": len(response.generations),
                "duration_ms": duration_ms,
                **usage,
            }
        )

    def on_llm_error(self, error: BaseException, **kwargs: Any) -> None:
        self._log(
            {
                "event": "llm_error",
                "step": "llm_analysis_failed",
                "model": self.last_model,
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
                "step": "tool_start",
                "tool_name": tool_name,
                "input": input_str[:1000],
            }
        )

    def on_tool_end(self, output: Any, **kwargs: Any) -> None:
        self._log(
            {
                "event": "tool_end",
                "step": "tool_end",
                "output": str(output)[:2000],
            }
        )

    def on_tool_error(self, error: BaseException, **kwargs: Any) -> None:
        self._log(
            {
                "event": "tool_error",
                "step": "tool_error",
                "error": str(error),
                "error_type": type(error).__name__,
            }
        )
