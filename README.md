# Runopsy

Runopsy is a small FastAPI service that:

1. Accepts a GitHub pull request URL.
2. Finds the most relevant failed GitHub Actions job for that PR.
3. Sends the failure log to an OpenAI model through LangChain.
4. Emits tool, LLM, and analysis events to Parseable using the `/api/v1/ingest` path.
5. Emits normal backend logs to an OpenTelemetry Collector when OTEL is enabled.

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

- `PARSEABLE_DATASET` defaults to `runopsy-agent-events`
- `GITHUB_TOKEN` improves GitHub API rate limits
- `OPENAI_MODEL` defaults to `gpt-4.1-mini`
- `OPENAI_TEMPERATURE` defaults to `0`
- `LOG_LEVEL` defaults to `INFO`
- `REQUEST_TIMEOUT_SECONDS` defaults to `15`
- `LOG_TAIL_CHARS` defaults to `25000`
- `OTEL_ENABLED` enables OpenTelemetry export when set to `true`
- `OTEL_SERVICE_NAME` defaults to `runopsy`
- `OTEL_EXPORTER_OTLP_ENDPOINT` can be used as the shared OTLP HTTP base endpoint
- `OTEL_EXPORTER_OTLP_LOGS_ENDPOINT` overrides the logs endpoint
- `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` overrides the traces endpoint
- `OTEL_EXPORTER_OTLP_METRICS_ENDPOINT` overrides the metrics endpoint

## Observability flow

- Agent events flow directly: `RunOpsy -> Parseable /api/v1/ingest`
- Normal backend logs flow through OTEL: `RunOpsy -> OTel Collector -> Parseable /v1/logs`
- Metrics and traces also use OTEL when configured

The `/api/v1/analyze` response now returns a `request_id`. That same `request_id` is included in:

- structured application logs
- Parseable agent events
- GitHub fetch / analysis step events
- span attributes when tracing is enabled

One Parseable search by `request_id` should show the full request story across both pipelines.

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
- `OTEL_ENABLED=true`
- `OTEL_EXPORTER_OTLP_ENDPOINT` or the per-signal OTLP endpoints if you want collector export

Example collector configuration:

```bash
OTEL_ENABLED=true
OTEL_SERVICE_NAME=runopsy
OTEL_EXPORTER_OTLP_ENDPOINT=https://your-collector.example.com
```

## Parseable search idea

After one analyze request, copy the returned `request_id` and search for it in:

- `runopsy-agent-events` to see LangChain/tool/analysis events
- `runopsy-logs` to see normal app logs coming from the collector
- `runopsy-traces` if traces are enabled
- `runopsy-metrics` if your collector is exporting metrics to Parseable

After deploy, use `/health` to verify configuration before sending analysis requests.
