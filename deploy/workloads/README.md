# Desired state (GitOps)

One values file per deployed workload: `deploy/workloads/<env>/<name>.values.yaml`.
Argo CD's ApplicationSet (`deploy/argocd/applicationset.yaml`) turns every file
here into an Application rendering `deploy/helm/llm-workload` with
`deploy/environments/<env>/values.yaml` plus this file.

`aiplatform deploy --target gitops` writes the file, commits and pushes it,
then waits for Argo CD to sync. Deleting the file (`aiplatform destroy
--target gitops`) removes the workload. Hand edits are fine too: that is the
point of GitOps.
