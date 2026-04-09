from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from langchain_openai import ChatOpenAI

from app.config import Settings
from app.github_client import GitHubClient
from app.parseable import ParseableCallbackHandler
from app.tools import GetFailedJobLogTool


def _message_text(content: Any) -> str:
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
                continue
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
                continue
            parts.append(str(item))
        return "\n".join(part for part in parts if part).strip()

    return str(content)


@dataclass(slots=True)
class AnalysisOutcome:
    pr_url: str
    run_id: str
    analysis: str
    used_llm: bool
    parseable_logging_enabled: bool


class PRFailureAnalyzer:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def analyze_pr_failure(self, pr_url: str) -> AnalysisOutcome:
        missing = self.settings.missing_analysis_env()
        if missing:
            missing_display = ", ".join(missing)
            raise RuntimeError(f"Missing required environment variables: {missing_display}")

        handler = ParseableCallbackHandler(
            parseable_url=self.settings.parseable_url or "",
            dataset=self.settings.parseable_dataset,
            username=self.settings.parseable_username or "",
            password=self.settings.parseable_password or "",
            service_name=self.settings.service_name,
        )
        github_client = GitHubClient(
            api_url=self.settings.github_api_url,
            timeout=self.settings.request_timeout,
            token=self.settings.github_token,
        )
        tool = GetFailedJobLogTool(
            handler=handler,
            github_client=github_client,
            log_tail_chars=self.settings.log_tail_chars,
        )
        llm = ChatOpenAI(
            api_key=self.settings.openai_api_key,
            model=self.settings.openai_model,
            temperature=self.settings.openai_temperature,
            callbacks=[handler],
        )

        started_at = time.monotonic()
        handler._log(
            {
                "event": "analysis_start",
                "pr_url": pr_url,
            }
        )

        try:
            tool_result = tool.run({"pr_url": pr_url})

            if "LOG_START" not in tool_result:
                duration_ms = round((time.monotonic() - started_at) * 1000, 2)
                handler._log(
                    {
                        "event": "analysis_end",
                        "pr_url": pr_url,
                        "result": tool_result[:4000],
                        "duration_ms": duration_ms,
                        "used_llm": False,
                    }
                )
                return AnalysisOutcome(
                    pr_url=pr_url,
                    run_id=handler.run_id,
                    analysis=tool_result,
                    used_llm=False,
                    parseable_logging_enabled=handler.enabled,
                )

            prompt = f"""
You are analyzing a failed GitHub Actions job.

Input:
{tool_result}

Task:
1. Find the root cause.
2. Ignore downstream noise.
3. Quote the exact failing lines if present.
4. Return:
- Failure reason
- Why it failed
- Most likely fix direction
""".strip()

            response = llm.invoke(prompt)
            result_text = _message_text(response.content)
            duration_ms = round((time.monotonic() - started_at) * 1000, 2)
            handler._log(
                {
                    "event": "analysis_end",
                    "pr_url": pr_url,
                    "result": result_text[:4000],
                    "duration_ms": duration_ms,
                    "used_llm": True,
                }
            )
            return AnalysisOutcome(
                pr_url=pr_url,
                run_id=handler.run_id,
                analysis=result_text,
                used_llm=True,
                parseable_logging_enabled=handler.enabled,
            )
        except Exception as exc:
            duration_ms = round((time.monotonic() - started_at) * 1000, 2)
            handler._log(
                {
                    "event": "analysis_error",
                    "pr_url": pr_url,
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                    "duration_ms": duration_ms,
                }
            )
            raise
