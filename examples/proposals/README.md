# Example proposals for `aiplatform propose --from-file`

Try the guardrail pipeline without an Anthropic API key:

```
uv run --project cli aiplatform propose "Deploy document-agent with HA under $100/month" \
  --from-file examples/proposals/ha-document-agent.json --dry-run      # passes
uv run --project cli aiplatform propose "Add a NAT gateway" \
  --from-file examples/proposals/rejected-nat-gateway.json --dry-run   # rejected by OPA
```

Drop `--dry-run` to open a pull request. With `ANTHROPIC_API_KEY` set, omit
`--from-file` and the model writes the proposal.
