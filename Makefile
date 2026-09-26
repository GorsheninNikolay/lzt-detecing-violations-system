.DEFAULT_GOAL := help

COMPOSE ?= $(shell command -v docker >/dev/null 2>&1 && echo docker compose || echo podman compose)
COMPOSE_PROJECT ?= construction-evidence-local
PORT ?= 8096
export DEPLOY_PORT := 127.0.0.1:$(PORT)
export POSTGRES_PASSWORD ?= evidence-local
export MINIO_ROOT_PASSWORD ?= evidence-local-secret

compose = $(COMPOSE) -p $(COMPOSE_PROJECT) -f infra/deploy/compose.yaml

.PHONY: help up build down logs status check profile

help:
	@printf '%s\n' 'make up       Build and start the local app' 'make down     Stop containers and preserve data volumes' 'make logs     Follow service logs' 'make status   Show container status' 'make check    Check API readiness' 'make profile  Create a cloud observer profile (requires cloud credentials)' 'Override PORT=8097 or COMPOSE="podman compose" as needed.'

up: build
	$(compose) up -d
	$(MAKE) check
	@printf 'Local app: http://127.0.0.1:%s\n' '$(PORT)'

build:
	@test -n "$$(find artifacts/dataset -maxdepth 1 -name 'Свод*.xlsx' -print -quit)" || { echo 'Missing source catalog: artifacts/dataset/Свод*.xlsx' >&2; exit 1; }
	npm --prefix web ci
	npm --prefix web run build
	$(compose) build

down:
	$(compose) down

logs:
	$(compose) logs --follow --tail=100

status:
	$(compose) ps -a

check:
	curl --fail --silent --show-error --retry 30 --retry-connrefused --retry-delay 2 --max-time 5 http://127.0.0.1:$(PORT)/api/health/ready

profile:
	$(compose) run --rm backend evidence-profile
