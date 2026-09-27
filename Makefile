# Makefile
.PHONY: install run test test-integration lint format type-check up down logs clean

COMPOSE_BASE := docker compose -f docker-compose.yml
COMPOSE_DEV := $(COMPOSE_BASE) -f docker-compose.dev.yml

BACKEND_DIR := backend

install:
	cd $(BACKEND_DIR) && pip install -e ".[dev]"

run:
	cd $(BACKEND_DIR) && uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload

test:
	cd $(BACKEND_DIR) && pytest tests/unit -v

test-integration:
	cd $(BACKEND_DIR) && pytest tests/integration -v -m integration

lint:
	cd $(BACKEND_DIR) && ruff check src tests

format:
	cd $(BACKEND_DIR) && ruff format src tests

type-check:
	cd $(BACKEND_DIR) && mypy src/domain src/application

up:
	mkdir -p storage
	$(COMPOSE_DEV) up -d --build

down:
	$(COMPOSE_DEV) down

logs:
	$(COMPOSE_DEV) logs -f

clean:
	find $(BACKEND_DIR) -type d -name "__pycache__" -exec rm -rf {} +
	find $(BACKEND_DIR) -type d -name "*.egg-info" -exec rm -rf {} +
	find $(BACKEND_DIR) -type d -name ".pytest_cache" -exec rm -rf {} +
	find $(BACKEND_DIR) -type d -name ".mypy_cache" -exec rm -rf {} +
	find $(BACKEND_DIR) -type d -name ".ruff_cache" -exec rm -rf {} +
	rm -rf $(BACKEND_DIR)/htmlcov
	rm -rf .pytest_cache
