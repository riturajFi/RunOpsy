from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

from langchain_openai import ChatOpenAI

from app.config import Settings
from app.github_client import GitHubClient
from app.observability import log_event
from app.otel_compat import trace
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


logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)


@dataclass(slots=True)
class AnalysisOutcome:
    request_id: str
    pr_url: str
    run_id: str
    analysis: str
    used_llm: bool
    parseable_logging_enabled: bool
    model: str | None
    total_tokens: int | None
    owner: str | None
    repo: str | None
    job_id: int | None
    failure_type: str | None
    analysis_status: str
    duration_ms: float


class PRFailureAnalyzer:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def analyze_pr_failure(self, pr_url: str, request_id: str) -> AnalysisOutcome:
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
            request_id=request_id,
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
        log_event(
            logger,
            logging.INFO,
            "Analysis started.",
            step="analysis_start",
            pr_url=pr_url,
            model=self.settings.openai_model,
        )
        handler._log(
            {
                "event": "analysis_start",
                "step": "analysis_start",
                "pr_url": pr_url,
                "model": self.settings.openai_model,
            }
        )

        try:
            with tracer.start_as_current_span("analyze_pr_failure") as span:
                span.set_attribute("request_id", request_id)
                span.set_attribute("pr_url", pr_url)
                span.set_attribute("model", self.settings.openai_model)
                tool_result = tool.run({"pr_url": pr_url})
                metadata = tool.last_metadata

            if "LOG_START" not in tool_result:
                duration_ms = round((time.monotonic() - started_at) * 1000, 2)
                analysis_status = metadata.get("analysis_status", "completed_without_llm")
                log_event(
                    logger,
                    logging.INFO,
                    "Analysis completed without LLM call.",
                    step="response_ready",
                    pr_url=pr_url,
                    owner=metadata.get("owner"),
                    repo=metadata.get("repo"),
                    job_id=metadata.get("job_id"),
                    analysis_status=analysis_status,
                    duration_ms=duration_ms,
                )
                handler._log(
                    {
                        "event": "analysis_end",
                        "step": "analysis_end",
                        "pr_url": pr_url,
                        "result": tool_result[:4000],
                        "duration_ms": duration_ms,
                        "used_llm": False,
                        "analysis_status": analysis_status,
                    }
                )
                return AnalysisOutcome(
                    request_id=request_id,
                    pr_url=pr_url,
                    run_id=handler.run_id,
                    analysis=tool_result,
                    used_llm=False,
                    parseable_logging_enabled=handler.enabled,
                    model=None,
                    total_tokens=None,
                    owner=metadata.get("owner"),
                    repo=metadata.get("repo"),
                    job_id=metadata.get("job_id"),
                    failure_type=metadata.get("failure_type"),
                    analysis_status=analysis_status,
                    duration_ms=duration_ms,
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

            log_event(
                logger,
                logging.INFO,
                "Starting LLM analysis.",
                step="llm_analysis_started",
                pr_url=pr_url,
                owner=metadata.get("owner"),
                repo=metadata.get("repo"),
                job_id=metadata.get("job_id"),
                model=self.settings.openai_model,
            )
            with tracer.start_as_current_span("llm_analysis") as span:
                span.set_attribute("request_id", request_id)
                span.set_attribute("model", self.settings.openai_model)
                span.set_attribute("github.repo", metadata.get("repo") or "")
                llm_started_at = time.monotonic()
                response = llm.invoke(prompt)
                llm_duration_ms = round((time.monotonic() - llm_started_at) * 1000, 2)
                span.set_attribute("duration_ms", llm_duration_ms)
                if handler.last_total_tokens is not None:
                    span.set_attribute("llm.total_tokens", handler.last_total_tokens)
            result_text = _message_text(response.content)
            duration_ms = round((time.monotonic() - started_at) * 1000, 2)
            analysis_status = "completed"
            log_event(
                logger,
                logging.INFO,
                "LLM analysis completed.",
                step="llm_analysis_completed",
                pr_url=pr_url,
                owner=metadata.get("owner"),
                repo=metadata.get("repo"),
                job_id=metadata.get("job_id"),
                model=handler.last_model,
                total_tokens=handler.last_total_tokens,
                analysis_status=analysis_status,
                duration_ms=llm_duration_ms,
            )
            handler._log(
                {
                    "event": "analysis_end",
                    "step": "analysis_end",
                    "pr_url": pr_url,
                    "result": result_text[:4000],
                    "duration_ms": duration_ms,
                    "used_llm": True,
                    "model": handler.last_model,
                    "total_tokens": handler.last_total_tokens,
                    "analysis_status": analysis_status,
                }
            )
            return AnalysisOutcome(
                request_id=request_id,
                pr_url=pr_url,
                run_id=handler.run_id,
                analysis=result_text,
                used_llm=True,
                parseable_logging_enabled=handler.enabled,
                model=handler.last_model,
                total_tokens=handler.last_total_tokens,
                owner=metadata.get("owner"),
                repo=metadata.get("repo"),
                job_id=metadata.get("job_id"),
                failure_type=metadata.get("failure_type"),
                analysis_status=analysis_status,
                duration_ms=duration_ms,
            )
        except Exception as exc:
            duration_ms = round((time.monotonic() - started_at) * 1000, 2)
            log_event(
                logger,
                logging.ERROR,
                "Analysis failed.",
                step="request_failed",
                pr_url=pr_url,
                model=self.settings.openai_model,
                analysis_status="failed",
                error=str(exc),
                duration_ms=duration_ms,
            )
            handler._log(
                {
                    "event": "analysis_error",
                    "step": "analysis_error",
                    "pr_url": pr_url,
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                    "duration_ms": duration_ms,
                }
            )
            raise
