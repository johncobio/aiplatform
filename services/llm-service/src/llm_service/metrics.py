"""Prometheus metrics for inference workloads.

Names follow Prometheus conventions (`_total` for counters, base units in
seconds). These are the signals dashboards and autoscaling use later.
"""

from prometheus_client import Counter, Gauge, Histogram, Info

REQUESTS = Counter(
    "llm_requests_total", "Chat completion requests", ["status"]
)  # status: ok | error | rejected
REQUEST_DURATION = Histogram(
    "llm_request_duration_seconds",
    "End-to-end request latency including queue wait",
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 20, 40, 60),
)
QUEUE_WAIT = Histogram(
    "llm_queue_wait_seconds",
    "Time spent waiting for a generation slot",
    buckets=(0.001, 0.01, 0.05, 0.1, 0.5, 1, 2, 5, 10, 30),
)
PROMPT_TOKENS = Counter("llm_prompt_tokens_total", "Prompt tokens processed")
COMPLETION_TOKENS = Counter("llm_completion_tokens_total", "Completion tokens generated")
TOKENS_PER_SECOND = Histogram(
    "llm_generation_tokens_per_second",
    "Completion tokens per second of generation time, per request",
    buckets=(1, 2, 5, 10, 20, 40, 80, 160, 320),
)
INFLIGHT = Gauge("llm_inflight_requests", "Requests currently generating")
QUEUE_DEPTH = Gauge("llm_queue_depth", "Requests waiting for a generation slot")
MODEL_LOAD_SECONDS = Gauge("llm_model_load_seconds", "Time taken to load the model")
MODEL_READY = Gauge("llm_model_ready", "1 when the model is loaded and serving")
MODEL_INFO = Info("llm_model", "Model and backend in use")
