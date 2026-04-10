from __future__ import annotations

import logging
import time
from typing import Any, Type

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field, PrivateAttr

from app.github_client import GitHubClient, parse_pr_url
from app.observability import log_event
from app.otel_compat import trace
from app.parseable import ParseableCallbackHandler


FAILED_JOB_CONCLUSIONS = {
    "failure",
    "timed_out",
    "cancelled",
    "startup_failure",
    "action_required",
}

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)


class PRInput(BaseModel):
    pr_url: str = Field(..., description="GitHub pull request URL to inspect.")


class GetFailedJobLogTool(BaseTool):
    name: str = "get_failed_job_log_for_pr"
    description: str = (
        "Given a GitHub PR URL, fetch the most relevant failed GitHub Actions job log "
        "for that PR and return job metadata plus log text."
    )
    args_schema: Type[BaseModel] = PRInput

    _handler: ParseableCallbackHandler = PrivateAttr()
    _github_client: GitHubClient = PrivateAttr()
    _log_tail_chars: int = PrivateAttr()
    _last_metadata: dict[str, Any] = PrivateAttr(default_factory=dict)

    def __init__(
        self,
        *,
        handler: ParseableCallbackHandler,
        github_client: GitHubClient,
        log_tail_chars: int = 25000,
        **data: Any,
    ) -> None:
        super().__init__(**data)
        self._handler = handler
        self._github_client = github_client
        self._log_tail_chars = log_tail_chars
        self._last_metadata = {}

    @property
    def last_metadata(self) -> dict[str, Any]:
        return self._last_metadata

    def _run(self, pr_url: str) -> str:
        tool_started_at = time.monotonic()
        self._handler._log(
            {
                "event": "tool_start",
                "tool_name": self.name,
                "input": pr_url,
            }
        )

        try:
            with tracer.start_as_current_span("parse_pr_url") as span:
                owner, repo, pr_number = parse_pr_url(pr_url)
                span.set_attribute("request_id", self._handler.request_id)
                span.set_attribute("github.owner", owner)
                span.set_attribute("github.repo", repo)
                span.set_attribute("github.pr_number", pr_number)

            log_event(
                logger,
                logging.INFO,
                "Parsed GitHub PR URL.",
                step="parse_pr_url",
                pr_url=pr_url,
                owner=owner,
                repo=repo,
            )
            self._handler._log(
                {
                    "event": "parse_pr_url",
                    "step": "parse_pr_url",
                    "pr_url": pr_url,
                    "owner": owner,
                    "repo": repo,
                    "pr_number": pr_number,
                }
            )

            with tracer.start_as_current_span("fetch_pr_metadata") as span:
                fetch_started_at = time.monotonic()
                pr = self._github_client.get_pull_request(owner, repo, pr_number)
                fetch_duration_ms = round((time.monotonic() - fetch_started_at) * 1000, 2)
                head_sha = pr["head"]["sha"]
                head_branch = pr["head"]["ref"]
                span.set_attribute("request_id", self._handler.request_id)
                span.set_attribute("github.head_sha", head_sha)
                span.set_attribute("github.head_branch", head_branch)
                span.set_attribute("duration_ms", fetch_duration_ms)

            log_event(
                logger,
                logging.INFO,
                "Fetched PR metadata from GitHub.",
                step="fetch_pr_metadata",
                owner=owner,
                repo=repo,
                pr_url=pr_url,
                duration_ms=fetch_duration_ms,
            )
            self._handler._log(
                {
                    "event": "fetch_pr_metadata",
                    "step": "fetch_pr_metadata",
                    "owner": owner,
                    "repo": repo,
                    "pr_number": pr_number,
                    "head_sha": head_sha,
                    "head_branch": head_branch,
                    "duration_ms": fetch_duration_ms,
                }
            )

            with tracer.start_as_current_span("find_failed_job") as span:
                runs_started_at = time.monotonic()
                pr_runs = self._github_client.list_workflow_runs(
                    owner,
                    repo,
                    params={"event": "pull_request"},
                )
                branch_runs = self._github_client.list_workflow_runs(
                    owner,
                    repo,
                    params={"branch": head_branch},
                )
                runs = self._dedupe_runs(pr_runs + branch_runs)
                matching_runs = self._select_matching_runs(
                    runs,
                    pr_number=pr_number,
                    head_sha=head_sha,
                )
                find_job_duration_ms = round((time.monotonic() - runs_started_at) * 1000, 2)
                span.set_attribute("request_id", self._handler.request_id)
                span.set_attribute("github.runs_scanned", len(runs))
                span.set_attribute("github.matching_runs", len(matching_runs))
                span.set_attribute("duration_ms", find_job_duration_ms)

            log_event(
                logger,
                logging.INFO,
                "Located candidate workflow runs for PR.",
                step="find_failed_job",
                owner=owner,
                repo=repo,
                pr_url=pr_url,
                duration_ms=find_job_duration_ms,
                runs_scanned=len(runs),
                matching_runs=len(matching_runs),
            )
            self._handler._log(
                {
                    "event": "find_failed_job",
                    "step": "find_failed_job",
                    "owner": owner,
                    "repo": repo,
                    "pr_number": pr_number,
                    "head_sha": head_sha,
                    "head_branch": head_branch,
                    "runs_scanned": len(runs),
                    "matching_runs": len(matching_runs),
                    "duration_ms": find_job_duration_ms,
                }
            )

            if not matching_runs:
                result = (
                    "No matching workflow run found for this PR. "
                    f"Checked PR-linked, branch, and head SHA matches for head_sha={head_sha}."
                )
                self._last_metadata = {
                    "owner": owner,
                    "repo": repo,
                    "pr_number": pr_number,
                    "analysis_status": "no_matching_run",
                }
                self._handler._log(
                    {
                        "event": "tool_end",
                        "tool_name": self.name,
                        "output": result,
                        "pr_number": pr_number,
                        "head_sha": head_sha,
                        "head_branch": head_branch,
                        "runs_scanned": len(runs),
                    }
                )
                return result

            matching_runs.sort(
                key=lambda run: (
                    int(run.get("run_number") or 0),
                    int(run.get("run_attempt") or 0),
                ),
                reverse=True,
            )

            for run in matching_runs:
                jobs = self._github_client.list_run_jobs(owner, repo, int(run["id"]))
                failed_jobs = [
                    job for job in jobs if job.get("conclusion") in FAILED_JOB_CONCLUSIONS
                ]
                if not failed_jobs:
                    continue

                job = failed_jobs[0]
                with tracer.start_as_current_span("fetch_job_logs") as span:
                    logs_started_at = time.monotonic()
                    log_text = self._github_client.download_job_logs(owner, repo, int(job["id"]))
                    fetch_logs_duration_ms = round((time.monotonic() - logs_started_at) * 1000, 2)
                    span.set_attribute("request_id", self._handler.request_id)
                    span.set_attribute("github.run_id", int(run["id"]))
                    span.set_attribute("github.job_id", int(job["id"]))
                    span.set_attribute("duration_ms", fetch_logs_duration_ms)

                log_event(
                    logger,
                    logging.INFO,
                    "Fetched failed GitHub Actions job logs.",
                    step="fetch_job_logs",
                    owner=owner,
                    repo=repo,
                    pr_url=pr_url,
                    job_id=int(job["id"]),
                    failure_type=job.get("conclusion"),
                    duration_ms=fetch_logs_duration_ms,
                )
                result = (
                    f"repo={owner}/{repo}\n"
                    f"pr_number={pr_number}\n"
                    f"head_sha={head_sha}\n"
                    f"run_id={run['id']}\n"
                    f"run_name={run.get('name')}\n"
                    f"run_attempt={run.get('run_attempt')}\n"
                    f"job_id={job['id']}\n"
                    f"job_name={job['name']}\n"
                    f"conclusion={job.get('conclusion')}\n"
                    f"started_at={job.get('started_at')}\n"
                    f"completed_at={job.get('completed_at')}\n\n"
                    f"LOG_START\n{log_text[-self._log_tail_chars:]}\nLOG_END"
                )
                tool_duration_ms = round((time.monotonic() - tool_started_at) * 1000, 2)
                self._last_metadata = {
                    "owner": owner,
                    "repo": repo,
                    "pr_number": pr_number,
                    "job_id": int(job["id"]),
                    "job_name": job["name"],
                    "failure_type": job.get("conclusion"),
                    "analysis_status": "failed_job_found",
                }

                self._handler._log(
                    {
                        "event": "fetch_job_logs",
                        "step": "fetch_job_logs",
                        "repo": f"{owner}/{repo}",
                        "pr_number": pr_number,
                        "job_id_github": job["id"],
                        "job_name": job["name"],
                        "failure_type": job.get("conclusion"),
                        "duration_ms": fetch_logs_duration_ms,
                    }
                )
                self._handler._log(
                    {
                        "event": "tool_end",
                        "tool_name": self.name,
                        "repo": f"{owner}/{repo}",
                        "pr_number": pr_number,
                        "head_sha": head_sha,
                        "head_branch": head_branch,
                        "run_id_github": run["id"],
                        "job_id_github": job["id"],
                        "job_name": job["name"],
                        "failure_type": job.get("conclusion"),
                        "duration_ms": tool_duration_ms,
                        "output": f"Fetched failed log for {owner}/{repo} PR #{pr_number}",
                    }
                )
                return result

            result = "Runs found, but no failed jobs found."
            self._last_metadata = {
                "owner": owner,
                "repo": repo,
                "pr_number": pr_number,
                "analysis_status": "no_failed_jobs",
            }
            self._handler._log(
                {
                    "event": "tool_end",
                    "tool_name": self.name,
                    "output": result,
                    "pr_number": pr_number,
                    "head_sha": head_sha,
                    "head_branch": head_branch,
                    "runs_scanned": len(matching_runs),
                }
            )
            return result
        except Exception as exc:
            log_event(
                logger,
                logging.ERROR,
                "GitHub job discovery failed.",
                step="request_failed",
                pr_url=pr_url,
                error=str(exc),
                status_code=502,
            )
            self._handler._log(
                {
                    "event": "tool_error",
                    "tool_name": self.name,
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                }
            )
            raise

    @staticmethod
    def _dedupe_runs(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen_ids: set[int] = set()
        deduped: list[dict[str, Any]] = []
        for run in runs:
            run_id = run.get("id")
            if not isinstance(run_id, int) or run_id in seen_ids:
                continue
            seen_ids.add(run_id)
            deduped.append(run)
        return deduped

    @staticmethod
    def _select_matching_runs(
        runs: list[dict[str, Any]],
        *,
        pr_number: int,
        head_sha: str,
    ) -> list[dict[str, Any]]:
        prioritized: list[tuple[int, dict[str, Any]]] = []
        for run in runs:
            linked_prs = run.get("pull_requests") or []
            linked_pr_numbers = {
                pr.get("number")
                for pr in linked_prs
                if isinstance(pr, dict) and pr.get("number") is not None
            }
            score = 0
            if pr_number in linked_pr_numbers:
                score = 3
            elif run.get("head_sha") == head_sha:
                score = 2
            elif run.get("event") == "pull_request":
                score = 1

            if score:
                prioritized.append((score, run))

        prioritized.sort(
            key=lambda item: (
                item[0],
                int(item[1].get("run_number") or 0),
                int(item[1].get("run_attempt") or 0),
            ),
            reverse=True,
        )
        return [run for _, run in prioritized]
