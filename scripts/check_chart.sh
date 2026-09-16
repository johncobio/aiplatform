#!/usr/bin/env bash
# Render the llm-workload chart for every engine and assert the engine-specific
# parts are present. Runs in `make helm-lint` and CI; no cluster needed.
set -euo pipefail
C=deploy/helm/llm-workload
fail() { echo "FAIL: $1" >&2; exit 1; }
assert() { grep -qE -- "$2" <<<"$3" || fail "$1"; }

out=$(helm template t "$C" --set image.tag=t --set ingress.host=x -f deploy/environments/dev/values.yaml)
assert "builtin image"           'image: "aiplatform/llm-service:t"' "$out"
assert "builtin readiness"       'path: /readyz' "$out"
assert "servicemonitor engine"   'replacement: "builtin"' "$out"

out=$(helm template t "$C" --set engine.type=llamacpp-server --set ingress.host=x --set model.url=https://h/f/m.gguf --set model.name=m)
assert "llamacpp image"          'ghcr.io/ggml-org/llama.cpp:server-' "$out"
assert "llamacpp init container" 'name: fetch-model' "$out"
assert "llamacpp model arg"      '"/models/m.gguf"' "$out"
assert "llamacpp metrics flag"   '"--metrics"' "$out"
assert "llamacpp health probe"   'path: /health' "$out"
! grep -q 'aiplatform/llm-service' <<<"$out" || fail "llamacpp must not use the builtin image"

out=$(helm template t "$C" --set engine.type=vllm --set ingress.host=x --set model.hfRepo=org/model --set model.name=m --set engine.vllm.hfTokenSecret=hf)
assert "vllm image"              'vllm/vllm-openai:v' "$out"
assert "vllm gpu limit"          'nvidia.com/gpu: 1' "$out"
assert "vllm model arg"          '"org/model"' "$out"
assert "vllm hf token"           'name: HF_TOKEN' "$out"

! helm template t "$C" --set engine.type=vllm --set ingress.host=x >/dev/null 2>&1 || fail "vllm without hfRepo must fail"
! helm template t "$C" --set engine.type=llamacpp-server --set ingress.host=x >/dev/null 2>&1 || fail "llamacpp-server without model.url must fail"
echo "chart engine checks passed"
