#!/bin/bash
# Public inputs only. No AWS API calls, credentials, instance role, or SSH.
set -euo pipefail
exec > >(tee -a /var/log/aiplatform-user-data.log /dev/console) 2>&1
trap 'echo "BOOTSTRAP FAILED at line $LINENO"; docker logs --tail 30 aiplatform-service || true' ERR

# Independent safety net: terminate this demo host after two hours, including
# when a download fails. Terraform destroy removes the remaining security group.
shutdown -h +120
dnf install -y docker
systemctl enable --now docker

install -d -o 10001 -g 10001 /var/lib/aiplatform/models
model=/var/lib/aiplatform/models/qwen2.5-0.5b-instruct-q4_k_m.gguf
curl --fail --location --retry 5 --retry-delay 3 --max-time 900 \
  'https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/9217f5db79a29953eb74d5343926648285ec7e67/qwen2.5-0.5b-instruct-q4_k_m.gguf' \
  --output "$model"
echo "74a4da8c9fdbcd15bd1f6d01d621410d31c6fc00986f5eb687824e7b93d7a9db  $model" | sha256sum --check
chmod 0444 "$model"

# amd64 manifest of the already-published sha-bfc96a4 service image.
image=ghcr.io/johncobio/aiplatform/llm-service@sha256:9e5bdbec2579142d75d3d317a9ca8088a1198e8cab2a3026b9e08b62f50b9828
docker pull "$image"
docker run --detach --name aiplatform-service --restart unless-stopped \
  --user 10001:10001 --cap-drop ALL --security-opt no-new-privileges \
  --read-only --tmpfs /tmp:rw,noexec,nosuid,size=64m \
  --cpus 2 --memory 1g --memory-swap 1g --pids-limit 256 \
  --log-opt max-size=5m --log-opt max-file=2 \
  -p 8000:8000 -v /var/lib/aiplatform/models:/models:ro \
  -e LLM_BACKEND=llamacpp -e LLM_MODEL_NAME=qwen2.5-0.5b-instruct \
  -e LLM_MODEL_PATH=/models/qwen2.5-0.5b-instruct-q4_k_m.gguf \
  -e LLM_CONTEXT_LENGTH=4096 -e LLM_THREADS=2 -e LLM_MAX_TOKENS_LIMIT=128 \
  "$image"

for _attempt in $(seq 1 90); do
  if curl --fail --silent --max-time 3 http://127.0.0.1:8000/readyz; then
    echo "MODEL READY: $(date -u +%FT%TZ)"
    exit 0
  fi
  sleep 5
done
docker logs --tail 50 aiplatform-service
echo "Model readiness timeout" >&2
exit 1
