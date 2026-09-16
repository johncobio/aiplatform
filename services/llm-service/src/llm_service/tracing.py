"""OpenTelemetry tracing. Enabled only when OTEL_EXPORTER_OTLP_ENDPOINT is set.

Spans follow the GenAI semantic conventions (`gen_ai.*`) where they apply so
the traces are comparable with other inference servers (vLLM, TGI).
"""

import logging
import os

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor, SpanExporter

from llm_service import __version__

log = logging.getLogger(__name__)

EXCLUDED_URLS = "healthz,readyz,metrics"


def configure_tracing(
    exporter: SpanExporter | None = None, service_name: str | None = None
) -> bool:
    """Install a tracer provider. Returns True when tracing is active.

    With no explicit exporter, an OTLP/HTTP exporter is created from the
    standard OTEL_* environment variables; if OTEL_EXPORTER_OTLP_ENDPOINT is
    unset, tracing stays a no-op (zero overhead, no network).
    """
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "")
    if exporter is None:
        if not endpoint:
            log.info("tracing disabled (OTEL_EXPORTER_OTLP_ENDPOINT not set)")
            return False
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        exporter = OTLPSpanExporter()  # reads OTEL_EXPORTER_OTLP_ENDPOINT and appends /v1/traces
        processor = BatchSpanProcessor(exporter)
    else:
        processor = SimpleSpanProcessor(exporter)  # tests: synchronous export

    resource = Resource.create(
        {
            "service.name": service_name or os.environ.get("OTEL_SERVICE_NAME", "llm-service"),
            "service.version": __version__,
        }
    )
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)
    log.info("tracing enabled endpoint=%s", endpoint or "in-memory")
    return True


def instrument_app(app) -> None:
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    FastAPIInstrumentor.instrument_app(app, excluded_urls=EXCLUDED_URLS)


def current_trace_id() -> str:
    ctx = trace.get_current_span().get_span_context()
    return format(ctx.trace_id, "032x") if ctx.is_valid else ""


tracer = trace.get_tracer("llm_service")
