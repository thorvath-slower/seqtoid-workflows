{{- define "seqtoid-pipeline-runner.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "seqtoid-pipeline-runner.fullname" -}}
{{- default .Chart.Name .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "seqtoid-pipeline-runner.labels" -}}
app.kubernetes.io/name: {{ include "seqtoid-pipeline-runner.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/component: pipeline-runner
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
{{- end -}}

{{- define "seqtoid-pipeline-runner.selectorLabels" -}}
app.kubernetes.io/name: {{ include "seqtoid-pipeline-runner.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "seqtoid-pipeline-runner.serviceAccountName" -}}
{{- if .Values.serviceAccount.create -}}
{{- default (include "seqtoid-pipeline-runner.fullname" .) .Values.serviceAccount.name -}}
{{- else -}}
{{- default "default" .Values.serviceAccount.name -}}
{{- end -}}
{{- end -}}
