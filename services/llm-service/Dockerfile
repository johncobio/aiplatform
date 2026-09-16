# syntax=docker/dockerfile:1.7
# Multi-stage build: compile llama.cpp once in a fat builder, ship a slim runtime.

ARG PYTHON_VERSION=3.12

# ---------- builder ----------
FROM python:${PYTHON_VERSION}-slim-bookworm AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential cmake git ninja-build \
    && rm -rf /var/lib/apt/lists/*

# Portable CPU build (no -march=native) so the same image runs on any arm64/x86_64 host.
ENV CMAKE_ARGS="-DGGML_NATIVE=OFF" \
    CMAKE_BUILD_PARALLEL_LEVEL=4 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install dependencies first so source edits do not trigger a llama.cpp rebuild.
COPY pyproject.toml README.md ./
RUN mkdir -p src/llm_service && touch src/llm_service/__init__.py \
    && pip install ".[llamacpp]" \
    && pip uninstall -y llm-service

COPY src ./src
RUN pip install --no-deps .

# ---------- runtime ----------
FROM python:${PYTHON_VERSION}-slim-bookworm AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --system --uid 10001 --create-home app \
    && mkdir -p /models && chown app:app /models

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    LLM_BACKEND=llamacpp \
    LLM_MODEL_DIR=/models \
    PORT=8000

USER app
WORKDIR /home/app
EXPOSE 8000
VOLUME ["/models"]

HEALTHCHECK --interval=15s --timeout=3s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request,os,sys; sys.exit(0 if urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"PORT\"]}/healthz', timeout=2).status==200 else 1)"

CMD ["python", "-m", "llm_service"]
