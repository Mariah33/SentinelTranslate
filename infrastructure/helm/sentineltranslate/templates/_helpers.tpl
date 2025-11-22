{{/*
Expand the name of the chart.
*/}}
{{- define "sentineltranslate.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "sentineltranslate.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "sentineltranslate.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "sentineltranslate.labels" -}}
helm.sh/chart: {{ include "sentineltranslate.chart" . }}
{{ include "sentineltranslate.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "sentineltranslate.selectorLabels" -}}
app.kubernetes.io/name: {{ include "sentineltranslate.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Component-specific labels
*/}}
{{- define "sentineltranslate.componentLabels" -}}
{{ include "sentineltranslate.labels" . }}
app.kubernetes.io/component: {{ .component }}
{{- end }}

{{/*
Component-specific selector labels
*/}}
{{- define "sentineltranslate.componentSelectorLabels" -}}
{{ include "sentineltranslate.selectorLabels" . }}
app.kubernetes.io/component: {{ .component }}
{{- end }}

{{/*
Triton fullname
*/}}
{{- define "sentineltranslate.triton.fullname" -}}
{{- printf "%s-%s" (include "sentineltranslate.fullname" .) "triton" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Sidecar fullname
*/}}
{{- define "sentineltranslate.sidecar.fullname" -}}
{{- printf "%s-%s" (include "sentineltranslate.fullname" .) "sidecar" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
API fullname
*/}}
{{- define "sentineltranslate.api.fullname" -}}
{{- printf "%s-%s" (include "sentineltranslate.fullname" .) "api" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Worker fullname
*/}}
{{- define "sentineltranslate.worker.fullname" -}}
{{- printf "%s-%s" (include "sentineltranslate.fullname" .) "worker" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Triton service account name
*/}}
{{- define "sentineltranslate.triton.serviceAccountName" -}}
{{- printf "%s-%s" (include "sentineltranslate.fullname" .) "triton" }}
{{- end }}

{{/*
Sidecar service account name
*/}}
{{- define "sentineltranslate.sidecar.serviceAccountName" -}}
{{- printf "%s-%s" (include "sentineltranslate.fullname" .) "sidecar" }}
{{- end }}

{{/*
API service account name
*/}}
{{- define "sentineltranslate.api.serviceAccountName" -}}
{{- if .Values.api.serviceAccount.create }}
{{- default (printf "%s-%s" (include "sentineltranslate.fullname" .) "api") .Values.api.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.api.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Worker service account name
*/}}
{{- define "sentineltranslate.worker.serviceAccountName" -}}
{{- if .Values.worker.serviceAccount.create }}
{{- default (printf "%s-%s" (include "sentineltranslate.fullname" .) "worker") .Values.worker.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.worker.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Redis host
*/}}
{{- define "sentineltranslate.redis.host" -}}
{{- if .Values.redis.enabled }}
{{- printf "%s-redis-master" .Release.Name }}
{{- else }}
{{- required "Redis host is required when redis.enabled is false" .Values.redis.externalHost }}
{{- end }}
{{- end }}

{{/*
Redis port
*/}}
{{- define "sentineltranslate.redis.port" -}}
{{- if .Values.redis.enabled }}
{{- .Values.redis.master.service.port | default 6379 }}
{{- else }}
{{- .Values.redis.externalPort | default 6379 }}
{{- end }}
{{- end }}

{{/*
Image pull secrets
*/}}
{{- define "sentineltranslate.imagePullSecrets" -}}
{{- if .Values.global.imagePullSecrets }}
imagePullSecrets:
{{- range .Values.global.imagePullSecrets }}
  - name: {{ . }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Return the appropriate apiVersion for HPA
*/}}
{{- define "sentineltranslate.hpa.apiVersion" -}}
{{- if semverCompare ">=1.23-0" .Capabilities.KubeVersion.GitVersion -}}
autoscaling/v2
{{- else -}}
autoscaling/v2beta2
{{- end -}}
{{- end -}}

{{/*
Return the appropriate apiVersion for PodDisruptionBudget
*/}}
{{- define "sentineltranslate.pdb.apiVersion" -}}
{{- if semverCompare ">=1.21-0" .Capabilities.KubeVersion.GitVersion -}}
policy/v1
{{- else -}}
policy/v1beta1
{{- end -}}
{{- end -}}
