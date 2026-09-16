# qwen-server

A workload with **no code**: `aiplatform.yaml` asks the platform to serve
`qwen2.5-0.5b-instruct` with the upstream llama.cpp server
(`engine: llamacpp-server`). Compare with `../llm-service`, which serves the
same model from this repo's own FastAPI + llama-cpp-python image.

```
uv run --project ../../cli aiplatform deploy --target kind      # dev, direct Helm
curl -s http://qwen-server.dev.127.0.0.1.nip.io/v1/models
```
