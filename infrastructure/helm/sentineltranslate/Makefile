.PHONY: help lint template install upgrade uninstall test dependency-update package

CHART_NAME := sentineltranslate
NAMESPACE := sentineltranslate
RELEASE_NAME := sentineltranslate

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

dependency-update: ## Update chart dependencies (Redis)
	helm repo add bitnami https://charts.bitnami.com/bitnami
	helm repo update
	helm dependency update

lint: ## Lint the Helm chart
	helm lint .

template: ## Generate Kubernetes manifests from chart
	helm template $(RELEASE_NAME) . \
		--namespace $(NAMESPACE) \
		--values values.yaml

template-dev: ## Generate manifests with dev values
	helm template $(RELEASE_NAME) . \
		--namespace $(NAMESPACE) \
		--values values-dev.yaml

template-prod: ## Generate manifests with prod values
	helm template $(RELEASE_NAME) . \
		--namespace $(NAMESPACE) \
		--values values-prod.yaml

dry-run-dev: ## Dry-run install with dev values
	helm install $(RELEASE_NAME) . \
		--namespace $(NAMESPACE) \
		--create-namespace \
		--values values-dev.yaml \
		--dry-run \
		--debug

dry-run-prod: ## Dry-run install with prod values
	helm install $(RELEASE_NAME) . \
		--namespace $(NAMESPACE) \
		--create-namespace \
		--values values-prod.yaml \
		--dry-run \
		--debug

install-dev: dependency-update ## Install chart with dev values
	helm install $(RELEASE_NAME) . \
		--namespace $(NAMESPACE) \
		--create-namespace \
		--values values-dev.yaml

install-prod: dependency-update ## Install chart with prod values
	helm install $(RELEASE_NAME) . \
		--namespace $(NAMESPACE) \
		--create-namespace \
		--values values-prod.yaml

upgrade-dev: ## Upgrade chart with dev values
	helm upgrade $(RELEASE_NAME) . \
		--namespace $(NAMESPACE) \
		--values values-dev.yaml

upgrade-prod: ## Upgrade chart with prod values
	helm upgrade $(RELEASE_NAME) . \
		--namespace $(NAMESPACE) \
		--values values-prod.yaml

uninstall: ## Uninstall the chart
	helm uninstall $(RELEASE_NAME) --namespace $(NAMESPACE)

status: ## Show release status
	helm status $(RELEASE_NAME) --namespace $(NAMESPACE)

get-pods: ## Get all pods
	kubectl get pods -n $(NAMESPACE) -l app.kubernetes.io/instance=$(RELEASE_NAME)

logs-sidecar: ## Tail sidecar logs
	kubectl logs -n $(NAMESPACE) -l app.kubernetes.io/component=sidecar --tail=100 -f

logs-api: ## Tail API logs
	kubectl logs -n $(NAMESPACE) -l app.kubernetes.io/component=api --tail=100 -f

logs-worker: ## Tail worker logs
	kubectl logs -n $(NAMESPACE) -l app.kubernetes.io/component=worker --tail=100 -f

logs-triton: ## Tail Triton logs
	kubectl logs -n $(NAMESPACE) -l app.kubernetes.io/component=triton --tail=100 -f

port-forward-sidecar: ## Port-forward sidecar API to localhost:8080
	kubectl port-forward -n $(NAMESPACE) svc/$(RELEASE_NAME)-sidecar 8080:8080

port-forward-api: ## Port-forward batch API to localhost:8090
	kubectl port-forward -n $(NAMESPACE) svc/$(RELEASE_NAME)-api 8090:8090

port-forward-triton: ## Port-forward Triton to localhost:8000
	kubectl port-forward -n $(NAMESPACE) svc/$(RELEASE_NAME)-triton 8000:8000

package: dependency-update ## Package the chart
	helm package .

test: lint template ## Run all tests (lint + template)
	@echo "Chart validation passed!"

clean: ## Clean generated files
	rm -rf charts/*.tgz
	rm -f *.tgz

# Monitoring targets
monitoring-install-dev: dependency-update ## Install with development monitoring
	helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
	helm repo update
	helm dependency update
	helm install $(RELEASE_NAME) . \
		--namespace $(NAMESPACE) \
		--create-namespace \
		--values values.yaml \
		--values values-monitoring-dev.yaml

monitoring-install-prod: dependency-update ## Install with production monitoring
	helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
	helm repo update
	helm dependency update
	helm install $(RELEASE_NAME) . \
		--namespace $(NAMESPACE) \
		--create-namespace \
		--values values.yaml \
		--values values-monitoring.yaml \
		--set kube-prometheus-stack.grafana.adminPassword='$(GRAFANA_PASSWORD)'

monitoring-upgrade-dev: ## Upgrade with development monitoring
	helm upgrade $(RELEASE_NAME) . \
		--namespace $(NAMESPACE) \
		--values values.yaml \
		--values values-monitoring-dev.yaml

monitoring-upgrade-prod: ## Upgrade with production monitoring
	helm upgrade $(RELEASE_NAME) . \
		--namespace $(NAMESPACE) \
		--values values.yaml \
		--values values-monitoring.yaml

grafana-password: ## Get Grafana admin password
	@kubectl get secret -n $(NAMESPACE) \
		$(RELEASE_NAME)-kube-prometheus-stack-grafana \
		-o jsonpath="{.data.admin-password}" | base64 --decode ; echo

port-forward-grafana: ## Port-forward Grafana to localhost:3000
	@echo "Grafana will be available at http://localhost:3000"
	@echo "Username: admin"
	@echo "Password: run 'make grafana-password' to get password"
	kubectl port-forward -n $(NAMESPACE) \
		svc/$(RELEASE_NAME)-kube-prometheus-stack-grafana 3000:80

port-forward-prometheus: ## Port-forward Prometheus to localhost:9090
	@echo "Prometheus will be available at http://localhost:9090"
	kubectl port-forward -n $(NAMESPACE) \
		svc/$(RELEASE_NAME)-kube-prometheus-stack-prometheus 9090:9090

port-forward-alertmanager: ## Port-forward Alertmanager to localhost:9093
	@echo "Alertmanager will be available at http://localhost:9093"
	kubectl port-forward -n $(NAMESPACE) \
		svc/$(RELEASE_NAME)-kube-prometheus-stack-alertmanager 9093:9093

monitoring-status: ## Check monitoring stack status
	@echo "=== Prometheus ==="
	@kubectl get pods -n $(NAMESPACE) -l app.kubernetes.io/name=prometheus
	@echo ""
	@echo "=== Grafana ==="
	@kubectl get pods -n $(NAMESPACE) -l app.kubernetes.io/name=grafana
	@echo ""
	@echo "=== Alertmanager ==="
	@kubectl get pods -n $(NAMESPACE) -l app.kubernetes.io/name=alertmanager
	@echo ""
	@echo "=== ServiceMonitors ==="
	@kubectl get servicemonitors -n $(NAMESPACE)
	@echo ""
	@echo "=== PrometheusRules ==="
	@kubectl get prometheusrules -n $(NAMESPACE)

monitoring-dashboards: ## List Grafana dashboards
	@echo "Dashboard ConfigMaps:"
	@kubectl get configmaps -n $(NAMESPACE) -l grafana_dashboard=1

check-metrics: ## Check if metrics endpoints are accessible
	@echo "Checking Triton metrics..."
	@kubectl run -n $(NAMESPACE) --rm -i --tty metrics-test --image=curlimages/curl --restart=Never -- \
		curl -s http://$(RELEASE_NAME)-triton:8002/metrics | head -n 5 || true
	@echo ""
	@echo "Checking Sidecar metrics..."
	@kubectl run -n $(NAMESPACE) --rm -i --tty metrics-test --image=curlimages/curl --restart=Never -- \
		curl -s http://$(RELEASE_NAME)-sidecar:8080/metrics | head -n 5 || true
	@echo ""
	@echo "Checking Redis metrics..."
	@kubectl run -n $(NAMESPACE) --rm -i --tty metrics-test --image=curlimages/curl --restart=Never -- \
		curl -s http://$(RELEASE_NAME)-redis-metrics:9121/metrics | head -n 5 || true

prometheus-targets: ## Show Prometheus scrape targets
	@echo "Port-forwarding Prometheus to check targets..."
	@echo "Visit: http://localhost:9090/targets"
	@kubectl port-forward -n $(NAMESPACE) \
		svc/$(RELEASE_NAME)-kube-prometheus-stack-prometheus 9090:9090

alerts-firing: ## Show currently firing alerts
	@kubectl port-forward -n $(NAMESPACE) \
		svc/$(RELEASE_NAME)-kube-prometheus-stack-prometheus 9090:9090 &
	@sleep 2
	@curl -s http://localhost:9090/api/v1/alerts | jq '.data.alerts[] | select(.state=="firing") | {alertname: .labels.alertname, severity: .labels.severity, summary: .annotations.summary}'
	@pkill -f "port-forward.*9090" || true
