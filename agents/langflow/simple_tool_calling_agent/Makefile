SHELL          := bash
AGENT_NAME     := $(shell python3 -c "import re; print(re.search(r'^name:\s*(.+)', open('agent.yaml').read(), re.M).group(1).strip())")
COMPOSE_FILE   := local/podman-compose.yml
ENV_FILE       := local/.env

.PHONY: init run stop clean status logs help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-12s %s\n", $$1, $$2}'

init: ## Create local/.env from .env.example and generate secrets
	@if [ ! -f $(ENV_FILE) ]; then \
	  cp .env.example $(ENV_FILE) && echo "Created local/.env from .env.example"; \
	else \
	  echo "local/.env already exists — skipping"; \
	fi
	@if ! grep -q '^LANGFUSE_ADMIN_PASSWORD=.\+' $(ENV_FILE) 2>/dev/null; then \
	  GENERATED_PWD=$$(openssl rand -base64 12) && \
	  sed -i.bak "s/^LANGFUSE_ADMIN_PASSWORD=.*/LANGFUSE_ADMIN_PASSWORD=$$GENERATED_PWD/" $(ENV_FILE) && \
	  rm -f $(ENV_FILE).bak && \
	  echo "Generated Langfuse admin password."; \
	fi
	@if ! grep -q '^LANGFUSE_ENCRYPTION_KEY=.\+' $(ENV_FILE) 2>/dev/null; then \
	  GENERATED_KEY=$$(openssl rand -hex 32) && \
	  sed -i.bak "s/^LANGFUSE_ENCRYPTION_KEY=.*/LANGFUSE_ENCRYPTION_KEY=$$GENERATED_KEY/" $(ENV_FILE) && \
	  rm -f $(ENV_FILE).bak && \
	  echo "Generated Langfuse encryption key."; \
	fi

run: init ## Start the local Langflow stack (Langflow + PostgreSQL + Langfuse + Ollama)
	@./deploy-local.sh

stop: ## Stop services (data preserved)
	@./cleanup-local.sh

clean: ## Stop services and remove all data
	@./cleanup-local.sh --force

status: ## Show status of running services
	@cd local && podman-compose ps

logs: ## Tail logs from all services
	@cd local && podman-compose logs -f
