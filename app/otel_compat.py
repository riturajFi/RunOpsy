from __future__ import annotations

try:
    from opentelemetry import metrics, trace

    OPENTELEMETRY_AVAILABLE = True
except ImportError:
    OPENTELEMETRY_AVAILABLE = False

    class _NoopSpanContext:
        is_valid = False
        trace_id = 0
        span_id = 0

    class _NoopSpan:
        def __enter__(self) -> "_NoopSpan":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def set_attribute(self, key: str, value: object) -> None:
            return None

        def get_span_context(self) -> _NoopSpanContext:
            return _NoopSpanContext()

    class _NoopTracer:
        def start_as_current_span(self, name: str) -> _NoopSpan:
            return _NoopSpan()

    class _NoopTraceModule:
        def get_tracer(self, name: str) -> _NoopTracer:
            return _NoopTracer()

        def get_current_span(self) -> _NoopSpan:
            return _NoopSpan()

        def set_tracer_provider(self, provider: object) -> None:
            return None

    class _NoopCounter:
        def add(self, amount: int | float, attributes: dict[str, object] | None = None) -> None:
            return None

    class _NoopHistogram:
        def record(self, amount: int | float, attributes: dict[str, object] | None = None) -> None:
            return None

    class _NoopMeter:
        def create_counter(self, name: str, description: str | None = None) -> _NoopCounter:
            return _NoopCounter()

        def create_histogram(
            self,
            name: str,
            unit: str | None = None,
            description: str | None = None,
        ) -> _NoopHistogram:
            return _NoopHistogram()

    class _NoopMetricsModule:
        def get_meter(self, name: str) -> _NoopMeter:
            return _NoopMeter()

        def set_meter_provider(self, provider: object) -> None:
            return None

    trace = _NoopTraceModule()
    metrics = _NoopMetricsModule()
