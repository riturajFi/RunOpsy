from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any

from app.config import Settings
from app.otel_compat import OPENTELEMETRY_AVAILABLE, trace
from app.request_context import get_request_id


_INITIALIZED = False
_STANDARD_LOG_RECORD_FIELDS = {
    "args",
    "asctime",
    "created",
    "exc_info",
    "exc_text",
    "filename",
    "funcName",
    "levelname",
    "levelno",
    "lineno",
    "module",
    "msecs",
    "message",
    "msg",
    "name",
    "pathname",
    "process",
    "processName",
    "relativeCreated",
    "stack_info",
    "thread",
    "threadName",
    "taskName",
}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        request_id = get_request_id()
        if request_id:
            payload["request_id"] = request_id

        span = trace.get_current_span()
        span_context = span.get_span_context()
        if span_context.is_valid:
            payload["trace_id"] = f"{span_context.trace_id:032x}"
            payload["span_id"] = f"{span_context.span_id:016x}"

        for key, value in record.__dict__.items():
            if key in _STANDARD_LOG_RECORD_FIELDS or key.startswith("_"):
                continue
            payload[key] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str)


def log_event(logger: logging.Logger, level: int, message: str, **fields: Any) -> None:
    if "request_id" not in fields and get_request_id():
        fields["request_id"] = get_request_id()
    logger.log(level, message, extra=fields)


def record_analyze_metrics(*, status_code: int, duration_ms: float) -> None:
    _ = status_code, duration_ms


def configure_observability(settings: Settings) -> None:
    global _INITIALIZED

    if _INITIALIZED:
        return

    root_logger = logging.getLogger()
    root_logger.setLevel(settings.log_level)

    if not any(getattr(handler, "_runopsy_console_handler", False) for handler in root_logger.handlers):
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(JsonFormatter())
        console_handler._runopsy_console_handler = True
        root_logger.addHandler(console_handler)

    if not settings.otel_enabled:
        _INITIALIZED = True
        return

    if not OPENTELEMETRY_AVAILABLE:
        logging.getLogger(__name__).warning(
            "OpenTelemetry packages are not installed; continuing without OTEL export.",
            extra={"step": "otel_setup", "otel_enabled": False},
        )
        _INITIALIZED = True
        return

    try:
        from opentelemetry._logs import set_logger_provider
        from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
        from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        logging.getLogger(__name__).warning(
            "OpenTelemetry dependencies are unavailable; continuing without OTEL export.",
            extra={"step": "otel_setup", "otel_enabled": False},
        )
        _INITIALIZED = True
        return

    resource = Resource.create(
        {
            "service.name": settings.otel_service_name,
            "deployment.environment": settings.environment,
        }
    )

    logs_endpoint = _resolve_signal_endpoint(
        settings.otel_exporter_otlp_logs_endpoint,
        settings.otel_exporter_otlp_endpoint,
        "v1/logs",
    )
    if logs_endpoint:
        logger_provider = LoggerProvider(resource=resource)
        logger_provider.add_log_record_processor(
            BatchLogRecordProcessor(OTLPLogExporter(endpoint=logs_endpoint))
        )
        set_logger_provider(logger_provider)

        if not any(getattr(handler, "_runopsy_otel_handler", False) for handler in root_logger.handlers):
            otel_handler = LoggingHandler(level=logging.NOTSET, logger_provider=logger_provider)
            otel_handler._runopsy_otel_handler = True
            root_logger.addHandler(otel_handler)

    traces_endpoint = _resolve_signal_endpoint(
        settings.otel_exporter_otlp_traces_endpoint,
        settings.otel_exporter_otlp_endpoint,
        "v1/traces",
    )
    if traces_endpoint:
        tracer_provider = TracerProvider(resource=resource)
        tracer_provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=traces_endpoint))
        )
        trace.set_tracer_provider(tracer_provider)

    _INITIALIZED = True


def _resolve_signal_endpoint(
    explicit_endpoint: str | None,
    shared_endpoint: str | None,
    suffix: str,
) -> str | None:
    endpoint = explicit_endpoint or shared_endpoint
    if not endpoint:
        return None

    endpoint = endpoint.rstrip("/")
    if endpoint.endswith(suffix):
        return endpoint
    return f"{endpoint}/{suffix}"
