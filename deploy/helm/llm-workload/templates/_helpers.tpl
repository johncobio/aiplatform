{{- define "llm-workload.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/* Release name is the workload name; keep resources named after it. */}}
{{- define "llm-workload.fullname" -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "llm-workload.labels" -}}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
app.kubernetes.io/name: {{ include "llm-workload.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Values.image.tag | default .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: aiplatform
aiplatform.io/environment: {{ .Values.environment }}
aiplatform.io/model: {{ .Values.model.name | default "none" | quote }}
aiplatform.io/engine: {{ .Values.engine.type }}
{{- end -}}

{{- define "llm-workload.selectorLabels" -}}
app.kubernetes.io/name: {{ include "llm-workload.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "llm-workload.serviceAccountName" -}}
{{- if .Values.serviceAccount.create -}}
{{ include "llm-workload.fullname" . }}
{{- else -}}
default
{{- end -}}
{{- end -}}
