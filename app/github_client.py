from __future__ import annotations

import re
from typing import Any

import requests


PR_URL_RE = re.compile(
    r"^https?://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+)/pull/(?P<number>\d+)(?:[/?#].*)?$"
)


class GitHubAPIError(RuntimeError):
    pass


def parse_pr_url(pr_url: str) -> tuple[str, str, int]:
    match = PR_URL_RE.match(pr_url.strip())
    if not match:
        raise ValueError("Invalid GitHub PR URL. Expected https://github.com/<owner>/<repo>/pull/<number>.")
    return (
        match.group("owner"),
        match.group("repo"),
        int(match.group("number")),
    )


class GitHubClient:
    def __init__(self, api_url: str, timeout: float, token: str | None = None) -> None:
        self.api_url = api_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if token:
            self.headers["Authorization"] = f"Bearer {token}"

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> requests.Response:
        url = path if path.startswith("http") else f"{self.api_url}/{path.lstrip('/')}"
        response = self.session.request(
            method=method,
            url=url,
            params=params,
            headers=self.headers,
            timeout=self.timeout,
            allow_redirects=True,
        )
        if response.ok:
            return response

        try:
            payload = response.json()
        except ValueError:
            payload = {"message": response.text.strip() or "Unknown error"}

        message = payload.get("message", "Unknown error")
        raise GitHubAPIError(f"GitHub API request failed ({response.status_code}): {message}")

    def get_json(self, path: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._request("GET", path, params=params).json()

    def get_text(self, path: str, *, params: dict[str, Any] | None = None) -> str:
        return self._request("GET", path, params=params).text

    def get_pull_request(self, owner: str, repo: str, pr_number: int) -> dict[str, Any]:
        return self.get_json(f"/repos/{owner}/{repo}/pulls/{pr_number}")

    def list_workflow_runs(
        self,
        owner: str,
        repo: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        query_params = {"per_page": 100}
        if params:
            query_params.update(params)
        payload = self.get_json(f"/repos/{owner}/{repo}/actions/runs", params=query_params)
        return payload.get("workflow_runs", [])

    def list_run_jobs(self, owner: str, repo: str, run_id: int) -> list[dict[str, Any]]:
        payload = self.get_json(
            f"/repos/{owner}/{repo}/actions/runs/{run_id}/jobs",
            params={"per_page": 100},
        )
        return payload.get("jobs", [])

    def download_job_logs(self, owner: str, repo: str, job_id: int) -> str:
        return self.get_text(f"/repos/{owner}/{repo}/actions/jobs/{job_id}/logs")
