from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from requests import RequestException

from app.analyzer import AnalysisOutcome, PRFailureAnalyzer
from app.config import get_settings
from app.github_client import GitHubAPIError


class AnalyzeRequest(BaseModel):
    pr_url: str = Field(..., description="GitHub pull request URL to analyze.")


class AnalyzeResponse(BaseModel):
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


app = FastAPI(
    title="Runopsy",
    version="0.1.0",
    description="Analyze failed GitHub Actions PR jobs with LangChain and Parseable tracing.",
)


def _build_analyzer() -> PRFailureAnalyzer:
    return PRFailureAnalyzer(get_settings())


def _response_from_outcome(outcome: AnalysisOutcome) -> AnalyzeResponse:
    return AnalyzeResponse(
        pr_url=outcome.pr_url,
        run_id=outcome.run_id,
        analysis=outcome.analysis,
        used_llm=outcome.used_llm,
        parseable_logging_enabled=outcome.parseable_logging_enabled,
    )


@app.get("/")
def root() -> dict[str, str]:
    return {
        "service": "Runopsy",
        "docs": "/docs",
        "health": "/health",
        "analyze": "/api/v1/analyze",
    }


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = get_settings()
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
    analyzer = _build_analyzer()
    missing = analyzer.settings.missing_analysis_env()
    if missing:
        raise HTTPException(
            status_code=503,
            detail={
                "message": "Missing required environment variables for analysis.",
                "missing": missing,
            },
        )

    try:
        outcome = analyzer.analyze_pr_failure(request.pr_url)
        return _response_from_outcome(outcome)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except GitHubAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except RequestException as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Network error while calling upstream services: {exc}",
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Unexpected server error: {exc}") from exc
