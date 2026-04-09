# Runopsy

Runopsy is a small FastAPI service that:

1. Accepts a GitHub pull request URL.
2. Finds the most relevant failed GitHub Actions job for that PR.
3. Sends the failure log to an OpenAI model through LangChain.
4. Emits tool, LLM, and analysis events to Parseable using the `/api/v1/ingest` path.

## Endpoints

- `GET /health` returns deployment and env readiness.
- `POST /api/v1/analyze` analyzes a failed GitHub Actions PR check.

Example request:

```bash
curl -X POST http://localhost:8000/api/v1/analyze \
  -H "Content-Type: application/json" \
  -d '{"pr_url":"https://github.com/octocat/Hello-World/pull/1"}'
```

## Required environment variables

- `OPENAI_API_KEY`
- `PARSEABLE_URL`
- `PARSEABLE_USERNAME`
- `PARSEABLE_PASSWORD`

## Optional environment variables

- `PARSEABLE_DATASET` defaults to `agent-traces`
- `GITHUB_TOKEN` improves GitHub API rate limits
- `OPENAI_MODEL` defaults to `gpt-4.1-mini`
- `OPENAI_TEMPERATURE` defaults to `0`
- `REQUEST_TIMEOUT_SECONDS` defaults to `15`
- `LOG_TAIL_CHARS` defaults to `25000`

Copy `.env.example` into `.env` for local development.

## Local run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Railway deployment

This repo includes both a `Procfile` and a `Dockerfile`. Railway can deploy it directly from the repository root.

Set these environment variables in Railway:

- `OPENAI_API_KEY`
- `PARSEABLE_URL`
- `PARSEABLE_USERNAME`
- `PARSEABLE_PASSWORD`
- `PARSEABLE_DATASET`
- `GITHUB_TOKEN` if you want higher GitHub API limits

After deploy, use `/health` to verify configuration before sending analysis requests.
