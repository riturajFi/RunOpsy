from __future__ import annotations

import logging
import time
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from requests import RequestException

from app.analyzer import AnalysisOutcome, PRFailureAnalyzer
from app.config import get_settings
from app.frontend import render_home_page
from app.github_client import GitHubAPIError
from app.observability import configure_observability, log_event, record_analyze_metrics
from app.otel_compat import trace
from app.request_context import reset_request_id, set_request_id


class AnalyzeRequest(BaseModel):
    pr_url: str = Field(..., description="GitHub pull request URL to analyze.")


class AnalyzeResponse(BaseModel):
    request_id: str
    pr_url: str
    run_id: str
    analysis: str
    used_llm: bool
    parseable_logging_enabled: bool


class HealthResponse(BaseModel):
    status: str
    service: str
    environment: str
    openai_configured: bool
    parseable_configured: bool
    github_token_configured: bool
    missing_analysis_env: list[str]


settings = get_settings()
configure_observability(settings)
logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

app = FastAPI(
    title="Runopsy",
    version="0.1.0",
    description="Analyze failed GitHub Actions PR jobs with LangChain and Parseable tracing.",
)


def _build_analyzer() -> PRFailureAnalyzer:
    return PRFailureAnalyzer(settings)


def _response_from_outcome(outcome: AnalysisOutcome) -> AnalyzeResponse:
    return AnalyzeResponse(
        request_id=outcome.request_id,
        pr_url=outcome.pr_url,
        run_id=outcome.run_id,
        analysis=outcome.analysis,
        used_llm=outcome.used_llm,
        parseable_logging_enabled=outcome.parseable_logging_enabled,
    )


@app.get("/", response_class=HTMLResponse)
def root() -> HTMLResponse:
    return HTMLResponse(render_home_page())


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service=settings.service_name,
        environment=settings.environment,
        openai_configured=bool(settings.openai_api_key),
        parseable_configured=settings.parseable_configured,
        github_token_configured=bool(settings.github_token),
        missing_analysis_env=settings.missing_analysis_env(),
    )


@app.post("/api/v1/analyze", response_model=AnalyzeResponse)
def analyze(request: AnalyzeRequest) -> AnalyzeResponse:
    request_id = str(uuid.uuid4())
    request_token = set_request_id(request_id)
    request_started_at = time.monotonic()
    status_code = 200

    analyzer = _build_analyzer()

    try:
        with tracer.start_as_current_span("analyze_request") as span:
            span.set_attribute("request_id", request_id)
            span.set_attribute("http.route", "/api/v1/analyze")
            span.set_attribute("pr_url", request.pr_url)
            log_event(
                logger,
                logging.INFO,
                "Analyze request received.",
                step="request_received",
                request_id=request_id,
                pr_url=request.pr_url,
            )

            missing = analyzer.settings.missing_analysis_env()
            if missing:
                status_code = 503
                raise HTTPException(
                    status_code=503,
                    detail={
                        "message": "Missing required environment variables for analysis.",
                        "missing": missing,
                        "request_id": request_id,
                    },
                )

            outcome = analyzer.analyze_pr_failure(request.pr_url, request_id=request_id)
            response = _response_from_outcome(outcome)
            duration_ms = round((time.monotonic() - request_started_at) * 1000, 2)
            span.set_attribute("analysis_status", outcome.analysis_status)
            span.set_attribute("duration_ms", duration_ms)
            if outcome.repo:
                span.set_attribute("github.repo", outcome.repo)
            if outcome.job_id is not None:
                span.set_attribute("github.job_id", outcome.job_id)
            if outcome.total_tokens is not None:
                span.set_attribute("llm.total_tokens", outcome.total_tokens)

            log_event(
                logger,
                logging.INFO,
                "Analyze response ready.",
                step="response_ready",
                pr_url=request.pr_url,
                owner=outcome.owner,
                repo=outcome.repo,
                job_id=outcome.job_id,
                model=outcome.model,
                total_tokens=outcome.total_tokens,
                analysis_status=outcome.analysis_status,
                failure_type=outcome.failure_type,
                duration_ms=duration_ms,
                status_code=status_code,
            )
            return response
    except HTTPException as exc:
        status_code = exc.status_code
        log_event(
            logger,
            logging.ERROR if exc.status_code >= 500 else logging.WARNING,
            "Analyze request failed.",
            step="request_failed",
            pr_url=request.pr_url,
            status_code=exc.status_code,
            error=str(exc.detail),
        )
        raise
    except ValueError as exc:
        status_code = 400
        log_event(
            logger,
            logging.WARNING,
            "Analyze request failed.",
            step="request_failed",
            pr_url=request.pr_url,
            status_code=status_code,
            error=str(exc),
        )
        raise HTTPException(status_code=400, detail={"message": str(exc), "request_id": request_id}) from exc
    except GitHubAPIError as exc:
        status_code = 502
        log_event(
            logger,
            logging.ERROR,
            "Analyze request failed.",
            step="request_failed",
            pr_url=request.pr_url,
            status_code=status_code,
            error=str(exc),
        )
        raise HTTPException(status_code=502, detail={"message": str(exc), "request_id": request_id}) from exc
    except RequestException as exc:
        status_code = 502
        log_event(
            logger,
            logging.ERROR,
            "Analyze request failed.",
            step="request_failed",
            pr_url=request.pr_url,
            status_code=status_code,
            error=str(exc),
        )
        raise HTTPException(
            status_code=502,
            detail={
                "message": f"Network error while calling upstream services: {exc}",
                "request_id": request_id,
            },
        ) from exc
    except RuntimeError as exc:
        status_code = 503
        log_event(
            logger,
            logging.ERROR,
            "Analyze request failed.",
            step="request_failed",
            pr_url=request.pr_url,
            status_code=status_code,
            error=str(exc),
        )
        raise HTTPException(
            status_code=503,
            detail={"message": str(exc), "request_id": request_id},
        ) from exc
    except Exception as exc:
        status_code = 500
        log_event(
            logger,
            logging.ERROR,
            "Analyze request failed.",
            step="request_failed",
            pr_url=request.pr_url,
            status_code=status_code,
            error=str(exc),
        )
        raise HTTPException(
            status_code=500,
            detail={"message": f"Unexpected server error: {exc}", "request_id": request_id},
        ) from exc
    finally:
        duration_ms = round((time.monotonic() - request_started_at) * 1000, 2)
        record_analyze_metrics(status_code=status_code, duration_ms=duration_ms)
        reset_request_id(request_token)
