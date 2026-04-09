from __future__ import annotations

from typing import Any, Type

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field, PrivateAttr

from app.github_client import GitHubClient, parse_pr_url
from app.parseable import ParseableCallbackHandler


FAILED_JOB_CONCLUSIONS = {
    "failure",
    "timed_out",
    "cancelled",
    "startup_failure",
    "action_required",
}


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

    def _run(self, pr_url: str) -> str:
        self._handler._log(
            {
                "event": "tool_start",
                "tool_name": self.name,
                "input": pr_url,
            }
        )

        try:
            owner, repo, pr_number = parse_pr_url(pr_url)
            pr = self._github_client.get_pull_request(owner, repo, pr_number)
            head_sha = pr["head"]["sha"]

            runs = self._github_client.list_workflow_runs(owner, repo)
            matching_runs = [run for run in runs if run.get("head_sha") == head_sha]

            if not matching_runs:
                result = "No workflow run found for this PR head SHA."
                self._handler._log(
                    {
                        "event": "tool_end",
                        "tool_name": self.name,
                        "output": result,
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
                log_text = self._github_client.download_job_logs(owner, repo, int(job["id"]))
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

                self._handler._log(
                    {
                        "event": "tool_end",
                        "tool_name": self.name,
                        "repo": f"{owner}/{repo}",
                        "pr_number": pr_number,
                        "run_id_github": run["id"],
                        "job_id_github": job["id"],
                        "job_name": job["name"],
                        "output": f"Fetched failed log for {owner}/{repo} PR #{pr_number}",
                    }
                )
                return result

            result = "Runs found, but no failed jobs found."
            self._handler._log(
                {
                    "event": "tool_end",
                    "tool_name": self.name,
                    "output": result,
                }
            )
            return result
        except Exception as exc:
            self._handler._log(
                {
                    "event": "tool_error",
                    "tool_name": self.name,
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                }
            )
            raise
