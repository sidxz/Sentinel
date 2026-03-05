.PHONY: help setup start admin seed create-admin status clean nuke docs docs-serve pentest pentest-custom pentest-setup

help: ## Show available commands
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

setup: ## First-time setup: generates keys, installs deps, starts DB
	@mkdir -p keys
	@if [ ! -f keys/private.pem ]; then \
		openssl genrsa -out keys/private.pem 2048 2>/dev/null && \
		openssl rsa -in keys/private.pem -pubout -out keys/public.pem 2>/dev/null && \
		echo "Generated JWT keys"; \
	else \
		echo "JWT keys already exist"; \
	fi
	uv sync && cd service && uv sync
	cd admin && npm install
	docker compose up -d identity-postgres identity-redis
	@until [ "$$(docker compose ps identity-postgres --format '{{.Health}}')" = "healthy" ]; do sleep 1; done
	@echo ""
	@echo "Setup complete!"
	@echo "  make start   - start identity service (:9003)"
	@echo "  make admin   - start admin UI (:9004)"
	@echo "  make seed    - populate with test data (optional)"

start: ## Start identity service (:9003) — auto-migrates on boot
	cd service && uv run uvicorn src.main:app --port 9003 --reload

admin: ## Start admin UI dev server (:9004)
	cd admin && npm run dev

seed: ## Seed database with test data
	uv run python scripts/seed.py

create-admin: ## Create or promote a user to admin
	uv run python scripts/create_admin.py

status: ## Check what's running
	@docker compose ps 2>/dev/null || echo "No containers"
	@printf "Service: " && curl -sf http://localhost:9003/health 2>/dev/null || echo "not running"
	@curl -sf -o /dev/null http://localhost:9004 && echo "Admin:   running on :9004" || echo "Admin:   not running"

docs: ## Build documentation site
	uv run --extra docs mkdocs build

docs-serve: ## Serve documentation site with live reload
	uv run --extra docs mkdocs serve

clean: ## Stop containers and wipe database
	docker compose down -v

nuke: clean ## Full reset: wipe everything including deps and keys
	rm -rf keys/ .venv service/.venv sdk/.venv admin/node_modules
	@echo "Run 'make setup' to start fresh."

pentest-setup: ## Install pentest tools (ZAP, Nuclei, Nikto, jwt_tool)
	cd pentest && bash setup_tools.sh

pentest: ## Run full pentest suite (tools + custom scripts)
	cd pentest && python run_all.py --all

pentest-custom: ## Run custom pentest scripts only
	cd pentest && python run_all.py --custom
